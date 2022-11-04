import asyncio
import json as jsonlib
import time
import ssl
from typing import Any, Optional

from authlib.integrations.httpx_client.oauth2_client import AsyncOAuth2Client
from httpx import AsyncClient

from .common import _service_request_and_log, HttpMethod
from ..util import url_path_join


GameID = str


class ModuleSettings:
    settings = None


def get_settings():
    if ModuleSettings.settings is None:
        raise AttributeError("Gameboard settings are not initialized.")
    return ModuleSettings.settings


class AuthTokenCache:
    """
    It's stupid, but the authlib httpx integration doesn't seem to insert the authorization header when using
    client.send, so I just construct an OAuth2AsyncClient to fetch a token, and then hand it off to an AsyncClient.
    """

    token = None
    token_lock = asyncio.Lock()

    @classmethod
    def _get_token_client(cls):
        settings = get_settings()
        ssl_context = ssl.create_default_context()
        if settings.ca_cert_path:
            ssl_context.load_verify_locations(cafile=settings.ca_cert_path)

        return AsyncOAuth2Client(
            settings.identity.client_id,
            settings.identity.client_secret,
            verify=ssl_context,
        )

    @classmethod
    async def get_access_token(cls, settings: "SettingsModel") -> str:
        async with cls.token_lock:
            if not cls.token or ((cls.token["expires_at"] - time.time()) < 30.0):
                client = cls._get_token_client()
                await client.fetch_token(
                    url_path_join(
                        settings.identity.base_url, settings.identity.token_endpoint
                    ),
                    username=settings.identity.token_user,
                    password=settings.identity.token_password,
                )
                cls.token = client.token
            return cls.token["access_token"]


def _get_gameboard_client(access_token: str) -> AsyncClient:
    settings = get_settings()
    ssl_context = ssl.create_default_context()
    if settings.ca_cert_path:
        ssl_context.load_verify_locations(cafile=settings.ca_cert_path)

    return AsyncClient(
        base_url=settings.gameboard.base_api_url,
        verify=ssl_context,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=60.0,
    )


async def _gameboard_request(
    method: HttpMethod, endpoint: str, data: Optional[Any]
) -> Optional[Any] | None:
    settings = get_settings()
    access_token = await AuthTokenCache.get_access_token(settings)
    response = await _service_request_and_log(
        _get_gameboard_client(access_token), method, endpoint, data
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
        f"unity/challenges",
        {
            "gameId": game_id,
            "teamId": team_id,
            "points": get_settings().game.total_points,
        },
    )


async def mission_update(
    team_id: str, mission_id: str, mission_name: str, points_scored: int
):
    return await _gameboard_post(
        "unity/mission-update",
        {
            "teamId": team_id,
            "missionId": mission_id,
            "missionName": mission_name,
            "pointsScored": points_scored,
        },
    )
