from ..config import get_settings
from ..util import url_path_join
from .common import get_oauth2_session


def get_player_by_user_id(user_id: str, game_id: str):
    settings = get_settings()
    session = get_oauth2_session()

    # This endpoint claims that it can accept query params, but "uid" appears not to work.
    players = session.get(
        url_path_join(settings.gameboard.base_api_url, "players"),
        verify=settings.ca_cert_path
    ).json()
    for player in players:
        if player["userId"] == user_id and player["gameId"] == game_id:
            return player
    return None


def get_game_specs(game_id: str):
    settings = get_settings()
    session = get_oauth2_session()

    return session.get(
        url_path_join(settings.gameboard.base_api_url, f"game/{game_id}/specs"),
        verify=settings.ca_cert_path
    ).json()


def get_team(team_id: str):
    settings = get_settings()
    session = get_oauth2_session()

    return session.get(
        url_path_join(settings.gameboard.base_api_url, f"team/{team_id}"),
        verify=settings.ca_cert_path
    ).json()
