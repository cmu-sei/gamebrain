import datetime
from typing import Dict, List

from ..config import get_settings
from ..util import url_path_join
from .common import get_oauth2_session


def get_workspace(workspace_id: str):
    settings = get_settings()
    session = get_oauth2_session()

    return session.get(
        url_path_join(settings.base_api_url, f"workspace/{workspace_id}"),
        verify=settings.ca_cert_path
    )

def register_gamespace(workspace_id: str, team_members: List[Dict]):
    """
    team_members: Each dict contains 'id' and 'approvedName' keys.
    """
    settings = get_settings()
    session = get_oauth2_session()

    expiration_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    post_data = {
        "resourceId": workspace_id,
        "graderKey": "",
        "graderUrl": "",
        "variant": 0,
        "playerCount": len(team_members),
        "maxAttempts": 3,
        "maxMinutes": 60,
        "points": 100,
        "allowReset": True,
        "allowPreview": True,
        "startGamespace": True,
        "expirationTime": expiration_time.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "players": [
            {"subjectId": player["id"],
             "subjectName": player["approvedName"]} for player in team_members
        ]
    }
    endpoint = "gamespace"
    return session.post(
        url_path_join(settings.topomojo.base_api_url, endpoint),
        verify=settings.ca_cert_path,
        json=post_data
    ).json()
