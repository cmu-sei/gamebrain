import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Security, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth import check_jwt
from .gamedata.cache import GameStateManager
import gamebrain.db as db
from .clients import gameboard, topomojo
from .config import Settings, get_settings, Global
from .gamedata.controller import router as gd_router


Settings.init_settings(Global.settings_path)
APP = FastAPI(docs_url="/api", root_path=get_settings().app_root_prefix)
APP.include_router(gd_router)


def format_message(event_message, event_time: Optional[datetime] = None):
    if not event_time:
        event_time = datetime.now(timezone.utc)
    return f"{event_time}: {event_message}"


async def publish_event(team_id: str, event_message: str):
    event_time = await db.store_event(team_id, event_message)
    await Global.redis.publish(
        get_settings().redis.channel_name, format_message(event_message, event_time)
    )


@APP.on_event("startup")
async def startup():
    await Global.init()


@APP.get("/live", include_in_schema=False)
async def liveness_check():
    return


@APP.get("/unprivileged/headless_client/{game_id}")
async def get_headless_ip(
    game_id: str, auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))
):
    payload = check_jwt(
        auth.credentials,
        get_settings().identity.jwt_audiences.gamebrain_api_unpriv,
        True,
    )
    user_id = payload["sub"]

    player = await gameboard.get_player_by_user_id(user_id, game_id)

    team_id = player["teamId"]
    team_data = await db.get_team(team_id)
    return team_data.get("headless_ip")


@APP.get("/privileged/deploy/{game_id}/{team_id}")
async def deploy(
    game_id: str,
    team_id: str,
    auth: HTTPAuthorizationCredentials = Security(HTTPBearer()),
):
    check_jwt(
        auth.credentials, get_settings().identity.jwt_audiences.gamebrain_api_priv
    )

    team_data = await db.get_team(team_id)

    if expiration := team_data.get("gamespace_expiration"):
        if datetime.now(timezone.utc) > expiration:
            del team_data["gamespace_expiration"]
            del team_data["gamespace_id"]
            await db.expire_team_gamespace(team_id)

    # Originally it just checked if not team_data, but because headless clients are going to be manually added ahead
    # of the start of the round, team_data will be partially populated.
    if not team_data.get("gamespace_id"):
        if not GameStateManager.check_team_exists(team_id):
            await GameStateManager.new_team(team_id)
        team = await gameboard.get_team(team_id)

        specs = (await gameboard.get_game_specs(game_id)).pop()
        external_id = specs["externalId"]

        gamespace = await topomojo.register_gamespace(external_id, team["members"])

        gs_id = gamespace["id"]

        # Oddly, the single-team data structure doesn't contain the name.
        teams_list = await gameboard.get_teams(game_id)
        for team_meta in teams_list:
            if team_meta["id"] == team_id:
                team_name = team_meta["name"]
                break
        else:
            team_name = None

        visible_vms = [
            {"id": vm["id"], "name": vm["name"]}
            for vm in gamespace["vms"]
            if vm["isVisible"]
        ]
        console_urls = [
            {
                "Id": vm["id"],
                "Url": f"{get_settings().topomojo.base_url}/mks/?f=1&s={gs_id}&v={vm['name']}",
                "Name": vm["name"],
            }
            for vm in visible_vms
        ]

        headless_ip = team_data.get("headless_ip")

        gamespace_expiration = gamespace["expirationTime"]
        event_message = f"Launched gamespace {gs_id}"
        await db.store_team(
            team_id,
            gamespace_id=gs_id,
            gamespace_expiration=gamespace_expiration,
            team_name=team_name,
        )
        await db.store_virtual_machines(team_id, console_urls)

        await publish_event(team_id, event_message)
    else:
        gs_id = team_data["gamespace_id"]
        console_urls = [
            {
                "Id": vm["id"],
                "Url": f"{get_settings().topomojo.base_url}/mks/?f=1&s={gs_id}&v={vm['name']}",
                "Name": vm["name"],
            }
            for vm in team_data["vm_data"]
        ]
        headless_ip = team_data["headless_ip"]

    return {"gamespaceId": gs_id, "headless_ip": headless_ip, "vms": console_urls}


@APP.post("/privileged/event/{team_id}")
async def push_event(
    team_id: str,
    event_message: str,
    auth: HTTPAuthorizationCredentials = Security(HTTPBearer()),
):
    check_jwt(
        auth.credentials, get_settings().identity.jwt_audiences.gamebrain_api_priv
    )

    team = await db.get_team(team_id)
    if not team:
        return HTTPException(status_code=400, detail="Unknown Team ID")

    for event_action in get_settings().game.event_actions:
        if event_action.event_message_partial not in event_message:
            continue
        if event_action.action.action_type == "change-net":
            gs_id = team.get("gamespace_id")
            if gs_id is None:
                return HTTPException(
                    status_code=400,
                    detail="Unable to retrieve team's ship gamespace ID.",
                )
            gs_info = await topomojo.get_gamespace(gs_id)
            for vm in gs_info["vms"]:
                if vm["name"].startswith(event_action.action.vm_name):
                    vm_id = vm["id"]
                    break
            else:
                return HTTPException(
                    status_code=400,
                    detail=f"Unable to find a VM with the name "
                    f"{event_action.action.vm_name}",
                )
            await _change_vm_net(vm_id, event_action.action.new_net)
        elif event_action.action.action_type == "dispatch":
            gs_id = team.get("gamespace_id")
            if gs_id is None:
                return HTTPException(
                    status_code=400,
                    detail="Unable to retrieve team's ship gamespace ID.",
                )

            dispatch = await topomojo.create_dispatch(
                gs_id, event_action.action.vm_name, event_action.action.command
            )
            print(dispatch)

    await publish_event(team_id, event_message)


@APP.put("/privileged/changenet/{vm_id}")
async def change_vm_net(
    vm_id: str,
    new_net: str,
    auth: HTTPAuthorizationCredentials = Security(HTTPBearer()),
):
    check_jwt(
        auth.credentials, get_settings().identity.jwt_audiences.gamebrain_api_priv
    )

    await _change_vm_net(vm_id, new_net)


async def _change_vm_net(vm_id: str, new_net: str):
    vm = await db.get_vm(vm_id)
    if not vm:
        raise HTTPException(status_code=400, detail="Specified VM cannot be found.")
    team_id = vm["team_id"]

    possible_networks = (await topomojo.get_vm_nets(vm_id)).get("net")
    if possible_networks is None:
        raise HTTPException(status_code=400, detail="Specified VM cannot be found.")

    for net in possible_networks:
        if net.startswith(new_net):
            await topomojo.change_vm_net(vm_id, new_net)
            break
    else:
        raise HTTPException(
            status_code=400,
            detail="Specified VM cannot be changed to the specified network.",
        )

    event_message = f"Changed VM {vm_id} network to {new_net} for team {team_id}"
    await publish_event(team_id, event_message)


@APP.put("/admin/headlessip/{team_id}")
async def set_headless_ip(
    team_id: str,
    headless_ip: str,
    auth: HTTPAuthorizationCredentials = Security(HTTPBearer()),
):
    check_jwt(
        auth.credentials, get_settings().identity.jwt_audiences.gamebrain_api_admin
    )

    await db.store_team(team_id, headless_ip=headless_ip)


@APP.post("/admin/secrets/{team_id}")
async def create_challenge_secrets(
    team_id: str,
    secrets: List[str],
    auth: HTTPAuthorizationCredentials = Security(HTTPBearer()),
):
    check_jwt(
        auth.credentials, get_settings().identity.jwt_audiences.gamebrain_api_admin
    )

    await db.store_team(team_id)
    await db.store_challenge_secrets(team_id, secrets)


@APP.post("/admin/media")
async def add_media_urls(
    media_map: Dict[str, str],
    auth: HTTPAuthorizationCredentials = Security(HTTPBearer()),
):
    check_jwt(
        auth.credentials, get_settings().identity.jwt_audiences.gamebrain_api_admin
    )

    await db.store_media_assets(media_map)


@APP.get("/gamestate/team_data")
async def get_team_data(auth: HTTPAuthorizationCredentials = Security(HTTPBearer())):
    check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)

    teams = await db.get_teams()
    return [
        {
            "teamId": team["id"],
            "teamName": team["team_name"],
            "shipHp": team["ship_hp"],
            "shipFuel": team["ship_fuel"],
        }
        for team in teams
    ]


@APP.websocket("/gamestate/websocket/events")
async def subscribe_events(ws: WebSocket):
    settings = get_settings()

    try:
        await ws.accept()
        try:
            # Make sure an unauthorized client can't just hold a connection open.
            token = await asyncio.wait_for(ws.receive_text(), timeout=10.0)
        except asyncio.TimeoutError:
            return

        try:
            check_jwt(token, get_settings().identity.jwt_audiences.gamestate_api)
        except HTTPException:
            await ws.send_text(format_message("Websocket Unauthorized"))
            return

        timestamp_message = format_message("Current server time")
        await ws.send_text(timestamp_message)

        events = await db.get_events()
        for event in events:
            message = event["message"]
            received_time = event["received_time"]
            await ws.send_text(format_message(message, received_time))
    except WebSocketDisconnect:
        return

    pubsub = Global.redis.pubsub(ignore_subscribe_messages=True)
    await pubsub.subscribe(settings.redis.channel_name)
    while True:
        message = await pubsub.get_message(timeout=10.0)
        try:
            if not message:
                # Check if the handled websocket is still connected.
                try:
                    await asyncio.wait_for(ws.receive_text(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
            else:
                await ws.send_text(message["data"].decode())
        except WebSocketDisconnect:
            break
    await pubsub.unsubscribe(settings.redis.channel_name)
