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
import json
import logging
from urllib.parse import urlparse, parse_qs

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError
import yaml

from ..auth import admin_api_key_dependency
from .controllermodels import Deployment
from ..commonmodels import ConsoleUrl
from ..clients import gameboard, topomojo
from ..clients.gameboard import GameID
from ..clients.topomojo import GamespaceID
from ..config import get_settings
from ..db import (
    deactivate_team,
    get_team,
    store_virtual_machines,
    store_team,
    get_assigned_headless_urls,
    store_game_session,
    PlayerInfo as DBPlayerInfo
)
from ..gamedata.cache import (
    GameStateManager,
    TeamID,
    MissionID,
    NonExistentTeam,
)
from ..gamedata.model import (
    GamespaceData,
    TeamGamespaceInfo,
)
from ..util import url_path_join, TeamLocks


HeadlessUrl = str
Success = bool


admin_router = APIRouter(
    prefix="/admin", dependencies=(Depends(admin_api_key_dependency),)
)


class OutOfGameServersError(Exception):
    ...


class HeadlessManager:
    _lock = asyncio.Lock()

    @classmethod
    async def assign_headless(cls, teams: list[TeamID]) -> dict[TeamID, HeadlessUrl]:
        async with cls._lock:
            assigned_headless_urls = await get_assigned_headless_urls()

            assignments = {}

            for team_id in teams:
                if url := assigned_headless_urls.get(team_id):
                    # Somehow this team already had a headless URL.
                    logging.warning(
                        f"Team {team_id} was already assigned a headless URL. "
                        "This is fine, but atypical and may indicate other "
                        "problems."
                    )
                    assignments[team_id] = url
                    teams.remove(team_id)

            all_headless_urls = set(
                get_settings().game.headless_client_urls.values())

            available_headless_urls = all_headless_urls - set(
                assigned_headless_urls.values()
            )

            if len(available_headless_urls) < len(teams):
                logging.error(
                    "Could not assign a headless clients for all teams in "
                    "a deployment request.\n"
                    "The current assignments are:\n"
                    f"{json.dumps(assigned_headless_urls, indent=2)}"
                )
                raise OutOfGameServersError

            for team_id in teams:
                # Should be fine to pop without a try block because of the
                # previous check.
                headless_url = available_headless_urls.pop()
                assignments[team_id] = headless_url
                logging.info(
                    f"Assigning server {headless_url} to team {team_id}.")
                await store_team(team_id, headless_url=str(headless_url))

            return assignments


async def get_team_name(game_id: GameID, team_id: TeamID) -> str:
    teams_list = await gameboard.get_teams(game_id)
    if not teams_list:
        logging.error(
            f"Unable to get teams list from Gameboard for game {game_id}.")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    for team_meta in teams_list:
        if team_meta["id"] == team_id:
            return team_meta["name"]
    return f"Unknown Name for Team {team_id}"


class ShipGamespaceNotFound(Exception):
    ...


class TooManyShipGamespacesFound(Exception):
    ...


async def retrieve_gamespace_info(
    team_id: str,
    gamespace_consoles: dict[GamespaceID, list[ConsoleUrl]],
) -> TeamGamespaceInfo:
    ship_gamespace_id = None
    ship_gamespace_data = None
    gamespace_data = {}

    for gamespace_id, console_urls in gamespace_consoles.items():
        preview_data = await topomojo.get_gamespace(gamespace_id)
        markdown = preview_data.get("markdown")
        if not markdown:
            logging.error(
                f"Gamespace {gamespace_id} preview did not "
                "contain a 'markdown' field. "
                f"This is the data returned: {preview_data}"
            )
            raise KeyError()
        gs_data_yaml = yaml.safe_load(markdown)
        try:
            gs_data = GamespaceData(
                **gs_data_yaml,
                gamespaceID=gamespace_id,
                consoleURLs=console_urls
            )
        except (ValidationError, TypeError) as e:
            logging.error(
                f"Exception: {str(e)} -"
                f"Gamespace {gamespace_id} had a document that could "
                f"not be parsed as YAML. Contents: {markdown}"
            )
            continue

        if gs_data.taskID is None:
            if ship_gamespace_id:
                raise TooManyShipGamespacesFound
            ship_gamespace_id = gamespace_id
            ship_gamespace_data = gs_data
            logging.info(
                "Found ship gamespace "
                f"{ship_gamespace_id} for team "
                f"{team_id}. Gamespace data: {gs_data.dict()} "
                f"Workspace YAML: {gs_data_yaml}"
            )
        else:
            gamespace_data[gs_data.taskID] = gs_data

    if not ship_gamespace_id:
        raise ShipGamespaceNotFound

    team_gs_info = TeamGamespaceInfo(
        ship_gamespace_id=ship_gamespace_id,
        ship_gamespace_data=ship_gamespace_data,
        gamespaces=gamespace_data,
    )

    return team_gs_info


class DeploymentResponse(BaseModel):
    __root__: dict[TeamID, HeadlessUrl]


def parse_vm_urls(vm_urls: list[str]) -> list[ConsoleUrl]:
    console_urls = []

    for url in vm_urls:
        parsed_url = urlparse(url)
        parsed_qs = parse_qs(parsed_url.query)

        # Currently these keys should exist in the query string.
        # Maybe improve in the future by raising a custom exception
        # if they are not there.
        vm_id = parsed_qs['s'][0]
        vm_name = parsed_qs['v'][0]

        console_url = ConsoleUrl(id=vm_id, name=vm_name, url=url)

        console_urls.append(console_url)

    return console_urls


async def _internal_deploy(deployment_data: Deployment):
    gamespace_info = {}

    session_teams = []

    logging.info(
        f"Got start time {str(deployment_data.session.sessionBegin)}, "
        f"end time {str(deployment_data.session.sessionEnd)}, and current "
        f"time {str(deployment_data.session.now)} from Gameboard."
    )

    gamebrain_time = datetime.now(tz=timezone.utc)
    if abs(gamebrain_time - deployment_data.session.now).seconds > 2:
        logging.warning(
            f"Deployment at Gamebrain time {gamebrain_time} "
            "differs more than 2 seconds from deployer time "
            f"of {deployment_data.session.now}"
        )

    deployment_data.session.now = gamebrain_time

    for team in deployment_data.teams:
        team_gamespace_vms = {
            gs.id: parse_vm_urls(gs.vmUris)
            for gs in team.gamespaces
        }
        team_gamespace_info = await retrieve_gamespace_info(
            team.id,
            team_gamespace_vms,
        )

        gamespace_info[team.id] = team_gamespace_info
        session_teams.append(team.id)

        logging.info(
            f"Team {team} had gamespace mappings "
            f"{json.dumps(team_gamespace_info.gamespaces, indent=2, default=str)}"
        )

        await GameStateManager.new_team(
            team.id,
            deployment_data.session,
            team_gamespace_info.ship_gamespace_data
        )

        await store_team(
            team.id,
            ship_gamespace_id=team_gamespace_info.ship_gamespace_id,
            team_name=team.name,
        )

        ship_console_urls = team_gamespace_vms[
            team_gamespace_info.ship_gamespace_id
        ]

        await store_virtual_machines(
            team.id, [console_url.dict() for console_url in ship_console_urls]
        )
        await GameStateManager.pc4_update_team_urls(
            team.id,
            {
                vm.name: vm.url
                for vm in ship_console_urls
            }
        )

    players = [
        DBPlayerInfo(
            player_id=player.playerId,
            user_id=player.userId,
            team_id=team.id,
        )
        for team in deployment_data.teams
        for player in team.players
    ]
    await store_game_session(
        session_teams,
        deployment_data.session.sessionBegin,
        deployment_data.session.sessionEnd,
        deployment_data.session.now,
        deployment_data.game.id,
        players,
    )

    await GameStateManager.init_challenges(gamespace_info)
    await GameStateManager.update_all_active_team_urls()


class VideoRefreshManager:
    _task_lock = asyncio.Lock()
    _active_task: asyncio.Task = None

    @classmethod
    async def start_video_refresh_task(cls):
        async with cls._task_lock:
            if cls._active_task and not cls._active_task.done():
                return
            cls._active_task = asyncio.create_task(
                GameStateManager.video_freshness_task())


DEPLOY_LOCK = asyncio.Lock()


@admin_router.post("/deploy")
async def deploy(deployment_data: Deployment) -> DeploymentResponse:
    logging.info(
        "deployment_data contents - "
        f"{json.dumps(deployment_data.dict(), default=str, indent=2)}"
    )
    await VideoRefreshManager.start_video_refresh_task()

    assignments = await HeadlessManager.assign_headless(
        [team.id for team in deployment_data.teams]
    )

    try:
        async with DEPLOY_LOCK:
            await _internal_deploy(deployment_data)
    except Exception as e:
        for team in deployment_data.teams:
            await deactivate_team(team.id)
        raise e

    return DeploymentResponse(__root__=assignments)


class ActiveTeamsResponse(BaseModel):
    __root__: dict[TeamID, HeadlessUrl]


@admin_router.get("/teams_active")
async def get_teams_active() -> ActiveTeamsResponse:
    active_teams = await get_assigned_headless_urls()

    response = ActiveTeamsResponse(__root__=active_teams)
    logging.info(f"Active teams: {json.dumps(response.dict(), indent=2)}")
    return response


class MissionProgressResponse(BaseModel):
    __root__: dict[MissionID, bool]


@admin_router.get("/progress/{team_id}")
async def get_team_progress(team_id: TeamID) -> MissionProgressResponse:
    try:
        status = await GameStateManager.get_team_codex_status(team_id)
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")
    return MissionProgressResponse(__root__=status)


class UpdateConsoleUrlsPostData(BaseModel):
    __root__: list[ConsoleUrl]


# @admin_router.post("/update_console_urls/{team_id}")
async def update_console_urls(team_id: TeamID, post_data: UpdateConsoleUrlsPostData):
    async with TeamLocks(team_id):
        team_data = await get_team(team_id)
        if not team_data:
            logging.error(
                f"Team {team_id} does not exist.")
            raise HTTPException(status_code=400, detail="Team does not exist.")

        console_urls = post_data.__root__
        logging.info(
            f"Got a console URL update for team {team_id}: {console_urls}")

        await store_virtual_machines(
            team_id, [console_url.dict() for console_url in console_urls]
        )
        await GameStateManager.pc4_update_team_urls(
            team_id, {vm.name: vm.url for vm in console_urls}
        )
