from ..config import get_settings
from ..util import url_path_join
from .common import get_oauth2_session


async def get_player_by_user_id(user_id: str, game_id: str):
    settings = get_settings()
    session = await get_oauth2_session()

    # This endpoint claims that it can accept query params, but "uid" appears not to work.
    players = (await session.get(
        url_path_join(settings.gameboard.base_api_url, "players")
    )).json()
    for player in players:
        if player["userId"] == user_id and player["gameId"] == game_id:
            return player
    return None


async def get_game_specs(game_id: str):
    settings = get_settings()
    session = await get_oauth2_session()

    return (await session.get(
        url_path_join(settings.gameboard.base_api_url, f"game/{game_id}/specs")
    )).json()


async def get_team(team_id: str):
    settings = get_settings()
    session = await get_oauth2_session()

    return (await session.get(
        url_path_join(settings.gameboard.base_api_url, f"team/{team_id}")
    )).json()


async def get_teams(game_id: str):
    settings = get_settings()
    session = await get_oauth2_session()

    return (await session.get(
        url_path_join(settings.gameboard.base_api_url, f"teams/{game_id}")
    )).json()
