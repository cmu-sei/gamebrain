import datetime
from typing import Dict, List

from ..config import get_settings
from ..util import url_path_join
from .common import get_oauth2_session


async def get_workspace(workspace_id: str):
    settings = get_settings()
    session = await get_oauth2_session()

    return (await session.get(
        url_path_join(settings.base_api_url, f"workspace/{workspace_id}")
    )).json()


async def register_gamespace(workspace_id: str, team_members: List[Dict]):
    """
    team_members: Each dict contains 'id' and 'approvedName' keys.
    """
    settings = get_settings()
    session = await get_oauth2_session()

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
    return (await session.post(
        url_path_join(settings.topomojo.base_api_url, endpoint),
        json=post_data,
        # This call can take a while.
        timeout=60.0
    )).json()


async def get_vm_nets(vm_id: str):
    settings = get_settings()
    session = await get_oauth2_session()

    endpoint = f"vm/{vm_id}/nets"
    return (await session.get(
        url_path_join(settings.topomojo.base_api_url, endpoint)
    )).json()


async def change_vm_net(vm_id: str, new_net: str):
    settings = get_settings()
    session = await get_oauth2_session()

    endpoint = f"vm/{vm_id}/change"
    params = {"key": "net", "value": new_net}
    return (await session.put(
        url_path_join(settings.topomojo.base_api_url, endpoint),
        json=params,
        timeout=60.0
    )).json()
