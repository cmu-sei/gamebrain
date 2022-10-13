import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
    Security,
    WebSocket,
    WebSocketDisconnect,
    Request,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
from pydantic import BaseModel
import yappi

from .auth import check_jwt
from .gamedata.cache import GameStateManager
import gamebrain.db as db
from .clients import gameboard, topomojo
from .config import Settings, get_settings, Global
from .gamedata.controller import router as gd_router
from .pubsub import PubSub, Subscriber

Settings.init_settings(Global.settings_path)

startup = []
shutdown = []

if get_settings().profiling:

    def _profiling_output():
        with open("profiling_result.prof", "w") as f:
            yappi.get_func_stats().print_all(f)

    logging.info("Profiling is ON")
    startup.append(yappi.start)
    shutdown.append(yappi.stop)
    shutdown.append(_profiling_output)
APP = FastAPI(
    docs_url="/api",
    root_path=get_settings().app_root_prefix,
    on_startup=startup,
    on_shutdown=shutdown,
)


def admin_api_key_dependency(x_api_key: str = Depends(APIKeyHeader(name="X-API-Key"))):
    expected_api_key = get_settings().gamebrain_admin_api_key
    if x_api_key != expected_api_key:
        logging.error(
            "Invalid X-API-Key header received.\n"
            f"Secret is expected to be: {expected_api_key}\n"
            f"Request included: {x_api_key}\n"
        )
        raise HTTPException(
            status_code=401,
            detail=f"Invalid X-API-Key header received. You sent: \n{x_api_key}",
        )


admin_router = APIRouter(
    prefix="/admin", dependencies=(Depends(admin_api_key_dependency),)
)
# unpriv_router = APIRouter(prefix="/unprivileged")
priv_router = APIRouter(prefix="/privileged")
gamestate_router = APIRouter(prefix="/gamestate")


def format_message(event_message, event_time: Optional[datetime] = None):
    if not event_time:
        event_time = datetime.now(timezone.utc)
    return f"{event_time}: {event_message}"


async def publish_event(team_id: str, event_message: str):
    event_time = await db.store_event(team_id, event_message)
    await PubSub.publish(format_message(event_message, event_time))


@APP.on_event("startup")
async def startup():
    await Global.init()


@APP.get("/live", include_in_schema=False)
async def liveness_check():
    return


@APP.get("/request_client")
async def request_client(request: Request):
    print(request.client)
    return request.client


@admin_router.get("/headless_client/{team_id}")
async def get_headless_url(team_id: str) -> str | None:
    assigned_headless_urls = await db.get_assigned_headless_urls()

    if url := assigned_headless_urls.get(team_id):
        return str(url)

    all_headless_urls = set(get_settings().game.headless_client_urls.values())

    available_headless_urls = all_headless_urls - set(assigned_headless_urls.values())
    try:
        headless_url = available_headless_urls.pop()
    except KeyError:
        logging.warning(
            f"Team {team_id} tried to request a headless client assignment, but the pool is expended.\n"
            f"The current assignments are: {json.dumps(assigned_headless_urls, indent=2)}"
        )
        return None

    await db.store_team(team_id, headless_url=str(headless_url))
    return str(headless_url)


@admin_router.get("/headless_client_unassign/{team_id}")
async def get_unassign_headless(team_id: str):
    await db.store_team(team_id, headless_url=None)
    return True


@admin_router.get("/headless_client_unassign")
async def get_unassign_all_headless():
    assigned_headless_urls = await db.get_assigned_headless_urls()
    for team_id in assigned_headless_urls:
        await db.store_team(team_id, headless_url=None)
    return True


class GetTeamPostData(BaseModel):
    user_token: str
    server_container_hostname: str


@priv_router.post("/get_team")
async def get_team_from_user(
    post_data: GetTeamPostData,
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
):
    try:
        payload = check_jwt(
            post_data.user_token,
            get_settings().identity.jwt_audiences.gamebrain_api_unpriv,
            True,
        )
    except HTTPException as e:
        e.detail = "User token could not be validated."
        raise e

    user_id = payload["sub"]

    check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)

    player = await gameboard.get_player_by_user_id(user_id, get_settings().game.game_id)

    team_id = player["teamId"]

    team_data = await db.get_team(team_id)

    assigned_headless_url = team_data["headless_url"]
    request_headless_url = get_settings().game.headless_client_urls.get(
        post_data.server_container_hostname
    )
    if not assigned_headless_url == request_headless_url:
        logging.warning(
            "Game client attempted to use a game server that it was not assigned to."
            f" (It was assigned to {assigned_headless_url}.)"
        )
        raise HTTPException(
            status_code=401,
            detail="Game client attempted to use a game server that it was not assigned to."
            f" (It was assigned to {assigned_headless_url}.)",
        )

    return {"teamID": team_id}


@admin_router.get("/deploy/{game_id}/{team_id}")
async def deploy(
    game_id: str,
    team_id: str,
):

    team_data = await db.get_team(team_id)

    if expiration := team_data.get("gamespace_expiration"):
        if datetime.now(timezone.utc) > expiration:
            del team_data["gamespace_expiration"]
            del team_data["gamespace_id"]
            await db.expire_team_gamespace(team_id)

    # Originally it just checked if not team_data, but because headless clients are going to be manually added ahead
    # of the start of the round, team_data will be partially populated.
    if not team_data.get("gamespace_id"):
        if not await GameStateManager.check_team_exists(team_id):
            await GameStateManager.new_team(team_id)
        team = await gameboard.get_team(team_id)

        specs = (await gameboard.get_game_specs(game_id)).pop()
        external_id = specs["externalId"]

        gamespace_expiration_time = team["sessionEnd"]
        gamespace = await topomojo.register_gamespace(
            external_id, gamespace_expiration_time, team["members"]
        )

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

        headless_url = team_data.get("headless_url")

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
        headless_url = team_data["headless_url"]

    return {"gamespaceId": gs_id, "headless_url": headless_url, "vms": console_urls}


@admin_router.get("/undeploy/{game_id}/{team_id}")
async def undeploy(
    team_id: str,
):

    team_data = await db.get_team(team_id)
    if not team_data:
        raise HTTPException(status_code=404, detail="Team not found.")

    if gamespace_id := team_data.get("gamespace_id"):
        await topomojo.stop_gamespace(gamespace_id)
        await db.expire_team_gamespace(team_id)


@priv_router.post("/event/{team_id}")
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
        raise HTTPException(status_code=400, detail="Unknown Team ID")

    for event_action in get_settings().game.event_actions:
        if event_action.event_message_partial not in event_message:
            continue
        if event_action.action.action_type == "change-net":
            gs_id = team.get("gamespace_id")
            if gs_id is None:
                raise HTTPException(
                    status_code=400,
                    detail="Unable to retrieve team's ship gamespace ID.",
                )
            gs_info = await topomojo.get_gamespace(gs_id)
            for vm in gs_info["vms"]:
                if vm["name"].startswith(event_action.action.vm_name):
                    vm_id = vm["id"]
                    break
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unable to find a VM with the name "
                    f"{event_action.action.vm_name}",
                )
            await _change_vm_net(vm_id, event_action.action.new_net)
        elif event_action.action.action_type == "dispatch":
            gs_id = team.get("gamespace_id")
            if gs_id is None:
                raise HTTPException(
                    status_code=400,
                    detail="Unable to retrieve team's ship gamespace ID.",
                )

            dispatch = await topomojo.create_dispatch(
                gs_id, event_action.action.vm_name, event_action.action.command
            )
            print(dispatch)

    await publish_event(team_id, event_message)


@priv_router.put("/changenet/{vm_id}")
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


@admin_router.post("/secrets/{team_id}")
async def create_challenge_secrets(
    team_id: str,
    secrets: List[str],
):

    await db.store_team(team_id)
    await db.store_challenge_secrets(team_id, secrets)


@admin_router.get("/admin/media")
async def add_media_urls(
    media_map: Dict[str, str],
):
    await db.store_media_assets(media_map)


@gamestate_router.get("/team_data", deprecated=True)
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


@gamestate_router.websocket("/websocket/events")
async def subscribe_events(ws: WebSocket):
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

    subscriber = Subscriber()
    await subscriber.subscribe()
    while True:
        message = await subscriber.get(10.0)
        try:
            if not message:
                # Check if the handled websocket is still connected.
                try:
                    await asyncio.wait_for(ws.receive_text(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
            else:
                await ws.send_text(message)
        except WebSocketDisconnect:
            break
    await subscriber.unsubscribe()


APP.include_router(admin_router)
APP.include_router(priv_router)
APP.include_router(gamestate_router)
APP.include_router(gd_router)
