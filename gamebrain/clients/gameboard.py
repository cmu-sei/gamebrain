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

import json as jsonlib
from logging import error, warning
import ssl
from typing import Any, Optional

from httpx import AsyncClient
from pydantic import ValidationError

from .common import _service_request_and_log, HttpMethod
from .gameboardmodels import GameEngineGameState, TeamGameScoreSummary


GameID = str


class ModuleSettings:
    settings = None


def get_settings():
    if ModuleSettings.settings is None:
        raise AttributeError("Gameboard settings are not initialized.")
    return ModuleSettings.settings


def _get_gameboard_client() -> AsyncClient:
    settings = get_settings()
    ssl_context = ssl.create_default_context()
    if settings.ca_cert_path:
        ssl_context.load_verify_locations(cafile=settings.ca_cert_path)
    api_key = settings.gameboard.x_api_key
    api_client = settings.gameboard.x_api_client

    return AsyncClient(
        base_url=settings.gameboard.base_api_url,
        verify=ssl_context,
        headers={"x-api-key": api_key, "x-api-client": api_client},
        timeout=60.0,
    )


async def _gameboard_request(
    method: HttpMethod, endpoint: str, data: Optional[Any]
) -> Optional[Any] | None:
    response = await _service_request_and_log(
        _get_gameboard_client(), method, endpoint, data
    )
    try:
        return response.json()
    except jsonlib.JSONDecodeError:
        return None


async def _gameboard_get(
    endpoint: str, query_params: Optional[dict] = None
) -> Optional[Any] | None:
    return await _gameboard_request(HttpMethod.GET, endpoint, query_params)


async def _gameboard_post(
    endpoint: str, json_data: Optional[Any]
) -> Optional[Any] | None:
    return await _gameboard_request(HttpMethod.POST, endpoint, json_data)


async def _gameboard_put(
    endpoint: str, json_data: Optional[Any]
) -> Optional[Any] | None:
    return await _gameboard_request(HttpMethod.PUT, endpoint, json_data)


async def get_player_by_user_id(user_id: str, game_id: str) -> Optional[Any]:
    players = await _gameboard_get("players")
    if players:
        # This endpoint claims that it can accept query params, but "uid" appears not to work.
        for player in players:
            if player["userId"] == user_id and player["gameId"] == game_id:
                return player
    return None


async def get_game_specs(game_id: str):
    return await _gameboard_get(f"game/{game_id}/specs")


async def get_team(team_id: str):
    return await _gameboard_get(f"team/{team_id}")


async def get_teams(game_id: str):
    return await _gameboard_get(f"teams/{game_id}")


async def create_challenge(game_id: str, team_id: str):
    return await _gameboard_post(
        "unity/challenges",
        {
            "gameId": game_id,
            "teamId": team_id,
            "points": get_settings().game.total_points,
        },
    )


async def mission_update(team_id: str) -> list[GameEngineGameState] | None:
    result = await _gameboard_get("gameEngine/state", {"teamId": team_id})
    if result is None:
        return None

    challenge_states = []
    for challenge_status in result:
        try:
            game_state = GameEngineGameState(**challenge_status)
        except ValidationError:
            warning(
                "Gameboard gameEngine/state returned an item that could not "
                f"be validated as a GameEngineGameState: {challenge_status}. "
                "This is expected for the team's ship workspace."
            )
        else:
            challenge_states.append(game_state)

    return challenge_states


async def team_score(team_id: str) -> TeamGameScoreSummary:
    result = await _gameboard_get(f"team/{team_id}/score")
    if result is None:
        return None

    try:
        return TeamGameScoreSummary(**result)
    except ValidationError:
        error(
            f"Gameboard team/{team_id}/score returned JSON that could "
            "not be validated as a TeamGameScoreSummary."
        )
