import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import admin_api_key_dependency
from ..clients import gameboard, topomojo
from ..clients.gameboard import GameID
from ..clients.topomojo import GamespaceID, GamespaceExpiration
from ..config import get_settings
from ..db import (
    expire_team_gamespace,
    get_team,
    get_teams,
    store_virtual_machines,
    store_team,
    get_assigned_headless_urls,
)
from ..gamedata.cache import GameStateManager, TeamID
from ..util import url_path_join, TeamLocks


HeadlessUrl = str


admin_router = APIRouter(
    prefix="/admin", dependencies=(Depends(admin_api_key_dependency),)
)


def construct_vm_url(gamespace_id: str, vm_name: str):
    gameboard_base_url = get_settings().gameboard.base_url
    return url_path_join(gameboard_base_url, f"/mks/?f=1&s={gamespace_id}&v={vm_name}")


class HeadlessManager:
    _lock = asyncio.Lock()

    @classmethod
    async def assign_headless(cls, team_id: TeamID):
        async with cls._lock:
            assigned_headless_urls = await get_assigned_headless_urls()

            if url := assigned_headless_urls.get(team_id):
                return str(url)

            all_headless_urls = set(get_settings().game.headless_client_urls.values())

            available_headless_urls = all_headless_urls - set(
                assigned_headless_urls.values()
            )
            try:
                headless_url = available_headless_urls.pop()
            except KeyError:
                logging.warning(
                    f"Team {team_id} tried to request a headless client assignment, but the pool is expended.\n"
                    f"The current assignments are: {json.dumps(assigned_headless_urls, indent=2)}"
                )
                return None

            logging.info(f"Assigning headless server {headless_url} to team {team_id}.")
            await store_team(team_id, headless_url=str(headless_url))
            return str(headless_url)


class ConsoleUrl(BaseModel):
    Id: str
    Url: str
    Name: str


class DeployResponse(BaseModel):
    headlessUrl: HeadlessUrl | None
    gamespaceId: GamespaceID | None
    vms: list[ConsoleUrl]


async def get_team_from_db(team_id: TeamID) -> dict:
    team_data = await get_team(team_id)

    if expiration := team_data.get("gamespace_expiration"):
        if datetime.now(timezone.utc) > expiration:
            logging.info(f"Team {team_id} had an expired gamespace {team_data['gamespace_id']}. "
                         f"Expiration time was {expiration}. "
                         "Dropping internal tracking.")
            del team_data["gamespace_expiration"]
            del team_data["gamespace_id"]
            del team_data["vm_data"]
            del team_data["headless_url"]
            await expire_team_gamespace(team_id)

    return team_data


async def register_gamespace_and_get_vms(
    game_id: GameID, team_id: TeamID
) -> (GamespaceID, GamespaceExpiration, list[ConsoleUrl]):
    gameboard_team = await gameboard.get_team(team_id)
    if not gameboard_team:
        logging.error(
            f"Unable to retrieve team data from Gameboard for team {team_id}."
        )
        raise HTTPException(status_code=500, detail="Internal Server Error")

    game_specs = await gameboard.get_game_specs(game_id)
    if not game_specs:
        logging.error(
            f"Unable to retrieve game specs from Gameboard for game {game_id}."
        )
        raise HTTPException(status_code=500, detail="Internal Server Error")
    try:
        game_specs = game_specs.pop()
    except IndexError:
        logging.error(f"Game {game_id} does not have any specs defined in Gameboard.")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    external_id = game_specs["externalId"]
    gamespace = await topomojo.register_gamespace(
        external_id, gameboard_team["sessionEnd"], gameboard_team["members"]
    )
    if not gamespace:
        logging.error(
            f"Unable to register a gamespace for team {team_id} from workspace {external_id}."
        )
        raise HTTPException(status_code=500, detail="Internal Server Error")

    console_urls = [
        ConsoleUrl(
            **{
                "Id": vm["id"],
                "Url": construct_vm_url(gamespace["id"], vm["name"]),
                "Name": vm["name"],
            }
        )
        for vm in gamespace["vms"]
        if vm["isVisible"]
    ]

    return gamespace["id"], gamespace["expirationTime"], console_urls


async def get_team_name(game_id: GameID, team_id: TeamID) -> str:
    teams_list = await gameboard.get_teams(game_id)
    if not teams_list:
        logging.error(f"Unable to get teams list from Gameboard for game {game_id}.")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    for team_meta in teams_list:
        if team_meta["id"] == team_id:
            return team_meta["name"]
    return f"Unknown Name for Team {team_id}"


@admin_router.get("/deploy/{game_id}/{team_id}")
async def get_deployment(game_id: GameID, team_id: TeamID) -> DeployResponse:
    return await deploy(game_id, team_id, False)


@admin_router.post("/deploy/{game_id}/{team_id}")
async def create_deployment(game_id: GameID, team_id: TeamID) -> DeployResponse:
    return await deploy(game_id, team_id, True)


async def deploy(
    game_id: GameID,
    team_id: TeamID,
    create_gamespace_if_none: bool,
) -> DeployResponse:
    async with TeamLocks(team_id):
        team_data = await get_team_from_db(team_id)

        gamespace_id = team_data.get("gamespace_id")
        headless_url = team_data.get("headless_url")
        vm_data = team_data.get("vm_data", [])
        console_urls = [
            ConsoleUrl(
                **{
                    "Id": vm["id"],
                    "Url": construct_vm_url(gamespace_id, vm["name"]),
                    "Name": vm["name"],
                }
            )
            for vm in vm_data
        ]

        if create_gamespace_if_none and (not gamespace_id or not headless_url):
            # If a team has no gamespace, they should be reset to the beginning of the game.
            await GameStateManager.new_team(team_id)

            headless_url = await HeadlessManager.assign_headless(team_id)
            if not headless_url:
                return DeployResponse(gamespaceId=None, headlessUrl=None, vms=[])

            try:
                (
                    gamespace_id,
                    gamespace_expiration,
                    console_urls,
                ) = await register_gamespace_and_get_vms(game_id, team_id)
                team_name = await get_team_name(game_id, team_id)
            except Exception as e:
                # If anything goes wrong with gamespace deployment,
                # we should free whatever headless URL was assigned before leaving.
                await expire_team_gamespace(team_id)
                raise e
            await store_team(
                team_id,
                gamespace_id=gamespace_id,
                gamespace_expiration=gamespace_expiration,
                team_name=team_name,
            )
            await store_virtual_machines(
                team_id, [console_url.dict() for console_url in console_urls]
            )
            await GameStateManager.update_team_urls(
                team_id, {vm.Name: vm.Url for vm in console_urls}
            )
            logging.info(f"Registered gamespace {gamespace_id} for team {team_id}, "
                         f"assigned to headless server {headless_url}. "
                         f"VM Console URLs: {json.dumps([url.dict() for url in console_urls], indent=2)}")

        return DeployResponse(
            gamespaceId=gamespace_id, headlessUrl=headless_url, vms=console_urls
        )


@admin_router.get("/undeploy/{team_id}")
async def undeploy(
    team_id: TeamID,
):
    team_data = await get_team(team_id)
    if not team_data:
        raise HTTPException(status_code=404, detail="Team not found.")

    if gamespace_id := team_data.get("gamespace_id"):
        await topomojo.complete_gamespace(gamespace_id)
        await expire_team_gamespace(team_id)


class ActiveTeamsResponse(BaseModel):
    __root__: dict[TeamID, bool]


@admin_router.get("/teams_active")
async def get_teams_active() -> ActiveTeamsResponse:
    teams = await get_teams()
    active_teams = {team.get("id"): bool(team.get("gamespace_id")) for team in teams}

    logging.info(f"Active teams: {json.dumps(active_teams, indent=2)}")
    return ActiveTeamsResponse(__root__=active_teams)
