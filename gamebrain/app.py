# Cyber Defenders Video Game

# Copyright 2023 Carnegie Mellon University.

# NO WARRANTY. THIS CARNEGIE MELLON UNIVERSITY AND SOFTWARE ENGINEERING
# INSTITUTE MATERIAL IS FURNISHED ON AN "AS-IS" BASIS. CARNEGIE MELLON
# UNIVERSITY MAKES NO WARRANTIES OF ANY KIND, EITHER EXPRESSED OR IMPLIED, AS
# TO ANY MATTER INCLUDING, BUT NOT LIMITED TO, WARRANTY OF FITNESS FOR PURPOSE
# OR MERCHANTABILITY, EXCLUSIVITY, OR RESULTS OBTAINED FROM USE OF THE
# MATERIAL. CARNEGIE MELLON UNIVERSITY DOES NOT MAKE ANY WARRANTY OF ANY KIND
# WITH RESPECT TO FREEDOM FROM PATENT, TRADEMARK, OR COPYRIGHT INFRINGEMENT.

# Released under a MIT (SEI)-style license, please see license.txt or contact
# permission@sei.cmu.edu for full terms.

# [DISTRIBUTION STATEMENT A] This material has been approved for public
# release and unlimited distribution.  Please see Copyright notice for
# non-US Government use and distribution.

# This Software includes and/or makes use of Third-Party Software each subject
# to its own license.

# DM23-0100

import asyncio
from datetime import datetime, timezone
import logging
import sys
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
from gamebrain.gamedata.model import GenericResponse
from .clients import gameboard, topomojo
from .config import Settings, get_settings, Global
from .gamedata.controller import gamestate_router as gd_router
from .pubsub import PubSub, Subscriber
from .test_endpoints import test_router
from .util import url_path_join

Settings.init_settings(Global.settings_path)

LOGLEVEL = get_settings().log_level
print(f"Got log level: {LOGLEVEL}")
logging.basicConfig(
    level=LOGLEVEL,
    format=(
        "Severity: %(levelname)s | "
        "Time: %(asctime)s | "
        "File: %(pathname)s | "
        "Function: %(funcName)s | "
        "Line: %(lineno)d | "
        "Message: %(message)s"
    )
)
uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.setLevel(LOGLEVEL)

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


def get_sanitized_headers(request: Request) -> dict:
    # Starlette's Request Headers property is immutable,
    # but I want to remove the API key from logs.
    headers = dict(request.headers)
    sanitize_keys = ['x-api-key', 'authorization']
    for key in sanitize_keys:
        if key in headers:
            headers[key] = '<secret>'
    return headers


@APP.exception_handler(HTTPException)
async def debug_exception_handler(
    request: Request,
    exc: HTTPException
):
    headers = get_sanitized_headers(request)
    logging.error(headers)
    return await http_exception_handler(request, exc)


@APP.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
):
    headers = get_sanitized_headers(request)
    body = await request.json()
    logging.error(
        f"Got invalid request headers: {headers} and body {body}")
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
    logging.info(f"Python version: {sys.version}")
    try:
        with open("/build-date.txt") as f:
            logging.info(
                f"Build time: {f.read().strip()}"
            )
    except FileNotFoundError:
        logging.warning(
            "Build time file not found."
        )
    await Global.init()


@APP.get("/live", include_in_schema=False)
async def liveness_check():
    return


class GetTeamPostData(BaseModel):
    user_token: str
    server_container_hostname: str


@priv_router.post("/get_team")
async def get_team_from_user(
    post_data: GetTeamPostData,
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
):
    def _find_user_session_and_team(sessions, user_id):
        for session in sessions:
            for team in session["teams"]:
                for player in team["players"]:
                    if player["user_id"] == user_id:
                        return (session, team)
        logging.error(
            f"User {user_id} tried to start a game, but could not find"
            f" a session with that user ID. Active sessions: {sessions}"
        )
        return (None, None)

    check_jwt(
        auth.credentials,
        get_settings().identity.jwt_audiences.gamestate_api
    )

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

    sessions = await db.get_active_game_sessions()
    user_session, team_data = _find_user_session_and_team(sessions, user_id)
    if not (user_session and team_data):
        raise HTTPException(
            status_code=400,
            detail="Failed to find a valid game session."
        )

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

    return {"teamID": team_data["id"]}


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
        raise HTTPException(
            status_code=400, detail="Specified VM cannot be found.")
    team_id = vm["team_id"]

    possible_networks = (await topomojo.get_vm_nets(vm_id)).get("net")
    if possible_networks is None:
        raise HTTPException(
            status_code=400, detail="Specified VM cannot be found.")

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


@admin_router.get("/team_active/{team_id}")
async def admin_get_is_team_active(
    team_id: str
) -> GenericResponse:
    return await get_is_team_active(team_id)


@gamestate_router.get("/team_active/{team_id}")
async def gamestate_get_is_team_active(
    team_id: str, auth: HTTPAuthorizationCredentials = Security(HTTPBearer())
) -> GenericResponse:
    check_jwt(auth.credentials, get_settings(
    ).identity.jwt_audiences.gamestate_api)

    return await get_is_team_active(team_id)


async def get_is_team_active(
    team_id: str
) -> GenericResponse:
    from util import enable_sql_logger, disable_sql_logger

    logging.info("Enabling SQL logging")
    enable_sql_logger()
    active_teams = {
        team["id"]
        for team in await db.get_active_teams()
    }
    disable_sql_logger()
    logging.info("Disabled SQL logging")
    response = GenericResponse(
        success=(team_id in active_teams),
        message=team_id
    )
    return response


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
