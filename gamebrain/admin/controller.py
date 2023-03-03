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
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import admin_api_key_dependency
from ..clients import gameboard, topomojo
from ..clients.gameboard import GameID
from ..clients.topomojo import GamespaceID
from ..config import get_settings
from ..db import (
    expire_team_gamespace,
    get_team,
    get_teams,
    store_virtual_machines,
    store_team,
    get_assigned_headless_urls,
)
from ..gamedata.cache import (
    GameStateManager,
    TeamID,
    MissionID,
    NonExistentTeam,
    TaskID,
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


class ConsoleUrl(BaseModel):
    id: str
    url: str
    name: str


def construct_vm_url(gamespace_id: str, vm_name: str):
    gameboard_base_url = get_settings().gameboard.base_url
    return url_path_join(gameboard_base_url, f"/mks/?f=1&s={gamespace_id}&v={vm_name}")


def console_urls_from_vm_data(
    gamespace_id: GamespaceID, vm_data: dict | None
) -> list[ConsoleUrl]:
    console_urls = []
    if not all((gamespace_id, vm_data)):
        return console_urls

    for vm in vm_data:
        visible = vm.get("isVisible")
        # Mock hypervisor doesn't include this key for some reason.
        if visible or visible is None:
            console_urls.append(
                ConsoleUrl(
                    **{
                        "id": vm["id"],
                        "url": construct_vm_url(gamespace_id, vm["name"]),
                        "name": vm["name"],
                    }
                )
            )
    return console_urls


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


class TeamGamespaceInfo:
    ship_gamespace: GamespaceID
    uncontested_gamespaces: dict[TaskID, GamespaceID]


class ShipGamespaceNotFound(Exception):
    ...


def retrieve_gamespace_info(
    uncontested_gamespaces: list[GamespaceID],
) -> TeamGamespaceInfo:
    team_gamespace_info = TeamGamespaceInfo()

    # TODO: Do a real implementation that actually pulls info from TopoMojo.
    try:
        ship_gamespace = uncontested_gamespaces.pop()
    except IndexError:
        raise ShipGamespaceNotFound

    team_gamespace_info.ship_gamespace = ship_gamespace
    team_gamespace_info.uncontested_gamespaces = {
        str(i): g for i, g in enumerate(uncontested_gamespaces)
    }

    return team_gamespace_info


class TeamDeploymentData(BaseModel):
    team_name: str
    uncontested_gamespaces: list[GamespaceID]


class DeploymentData(BaseModel):
    game_id: GameID
    teams: dict[TeamID, TeamDeploymentData]
    contested_gamespaces: list[GamespaceID]


class DeploymentResponse(BaseModel):
    __root__: dict[TeamID, HeadlessUrl]


@admin_router.post("/deploy")
async def deploy(deployment_data: DeploymentData) -> DeploymentResponse:
    assignments = await HeadlessManager.assign_headless(
        [team_id for team_id in deployment_data.teams]
    )

    for team_id, team_data in deployment_data.teams.items():
        team_gamespace_info = retrieve_gamespace_info(
            team_data.uncontested_gamespaces)

        await GameStateManager.new_team(team_id)

        await store_team(
            team_id,
            ship_gamespace_id=team_gamespace_info.ship_gamespace,
            team_name=team_data.team_name,
        )

    return DeploymentResponse(__root__=assignments)


@admin_router.post("/undeploy")
async def undeploy():
    active_teams = await get_teams_active()

    for team_id in active_teams:
        async with TeamLocks(team_id):
            team_data = await get_team(team_id)
            if not team_data:
                logging.error(
                    f"get_teams_active() call returned team {team_id}, "
                    "but no such team appears to exist."
                )
                continue

            await expire_team_gamespace(team_id)


class ActiveTeamsResponse(BaseModel):
    __root__: dict[TeamID, HeadlessUrl]


@admin_router.get("/teams_active")
async def get_teams_active() -> ActiveTeamsResponse:
    teams = await get_teams()
    active_teams = {}
    for team in teams:
        ship_gamespace_id = team.get("ship_gamespace_id")
        headless_url = team.get("headless_url")
        vm_data = team.get("vm_data")
        if not (ship_gamespace_id and headless_url and vm_data):
            # Team is inactive.
            continue
        active_teams[team.get("id")] = headless_url

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


@admin_router.post("/update_console_urls/{team_id}")
async def update_console_urls(team_id: TeamID, post_data: UpdateConsoleUrlsPostData):
    async with TeamLocks(team_id):
        team_data = await get_team(team_id)
        if not team_data:
            logging.error(
                f"update_console_urls Team {team_id} does not exist.")
            raise HTTPException(status_code=400, detail="Team does not exist.")

        console_urls = post_data.__root__
        logging.info(
            f"Got a console URL update for team {team_id}: {console_urls}")

        await store_virtual_machines(
            team_id, [console_url.dict() for console_url in console_urls]
        )
        await GameStateManager.update_team_urls(
            team_id, {vm.name: vm.url for vm in console_urls}
        )
