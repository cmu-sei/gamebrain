import asyncio
from datetime import datetime, timezone
import logging
import os
from typing import Dict, List, Optional

from fastapi import (
    APIRouter,
    FastAPI,
    HTTPException,
    Security,
    WebSocket,
    WebSocketDisconnect,
    Request,
)
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
import yappi

from .auth import check_jwt
from .admin.controller import admin_router
import gamebrain.db as db
from .clients import gameboard, topomojo
from .config import Settings, get_settings, Global
from .gamedata.controller import router as gd_router
from .pubsub import PubSub, Subscriber
from .test_endpoints import test_router
from .util import url_path_join

Settings.init_settings(Global.settings_path)

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
print(f"Got log level: {LOGLEVEL}")
logging.basicConfig(level=LOGLEVEL)

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


@APP.exception_handler(HTTPException)
async def debug_exception_handler(request: Request, exc: HTTPException):
    logging.error(request.headers)
    return await http_exception_handler(request, exc)


@APP.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logging.error(
        f"Got invalid request headers: {request.headers} and body {request.body()}"
    )
    return await request_validation_exception_handler(request, exc)


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


def construct_vm_url(gamespace_id: str, vm_name: str):
    gameboard_base_url = get_settings().gameboard.base_url
    return url_path_join(gameboard_base_url, f"/mks/?f=1&s={gamespace_id}&v={vm_name}")


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


@gamestate_router.get("/team_active/{team_id}")
async def get_is_team_active(
    team_id: str, auth: HTTPAuthorizationCredentials = Security(HTTPBearer())
) -> bool:
    check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)

    team = await db.get_team(team_id)
    return bool(team.get("gamespace_id"))


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
APP.include_router(test_router)
