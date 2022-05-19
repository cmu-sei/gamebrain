import json as jsonlib
from typing import Any, Dict, Optional

from .common import _service_get
from ..config import get_settings


async def _gameboard_get(endpoint: str, query_params: Optional[Dict] = None) -> Optional[Any]:
    resp = await _service_get(get_settings().gameboard.base_api_url, endpoint, query_params)
    try:
        return resp.json()
    except jsonlib.JSONDecodeError:
        return None


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
