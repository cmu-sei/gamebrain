import datetime
import json as jsonlib
from typing import Any, Dict, List, Optional

from .common import get_oauth2_session, _service_get
from ..config import get_settings
from ..util import url_path_join


async def _topomojo_get(endpoint: str, query_params: Optional[Dict] = None) -> Optional[Any]:
    resp = await _service_get(get_settings().topomojo.base_api_url, endpoint, query_params)
    try:
        return resp.json()
    except jsonlib.JSONDecodeError:
        return None


async def get_workspace(workspace_id: str) -> Optional[Any]:
    return await _topomojo_get(f"workspace/{workspace_id}")


async def get_gamespace(gamespace_id: str) -> Optional[Any]:
    return await _topomojo_get(f"gamespace/{gamespace_id}")


async def get_vm_nets(vm_id: str) -> Optional[Any]:
    return await _topomojo_get(f"vm/{vm_id}/nets")


async def get_vm_desc(vm_id: str) -> Optional[Any]:
    return await _topomojo_get(f"vm/{vm_id}")


async def poll_dispatch(dispatch_id: str) -> Optional[Any]:
    return await _topomojo_get(f"dispatch/{dispatch_id}")


async def register_gamespace(workspace_id: str, team_members: List[Dict]):
    """
    team_members: Each dict contains 'id' and 'approvedName' keys.
    """
    settings = get_settings()
    session = await get_oauth2_session()

    expiration_time = datetime.datetime.now(datetime.timezone.utc) + \
                      datetime.timedelta(minutes=settings.game.gamespace_duration_minutes)
    post_data = {
        "resourceId": workspace_id,
        "graderKey": "",
        "graderUrl": "",
        "variant": 0,
        "playerCount": len(team_members),
        "maxAttempts": 3,
        "maxMinutes": settings.game.gamespace_duration_minutes,
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


async def change_vm_params(vm_id: str, params: dict):
    settings = get_settings()
    session = await get_oauth2_session()

    endpoint = f"vm/{vm_id}/change"
    return (await session.put(
        url_path_join(settings.topomojo.base_api_url, endpoint),
        json=params,
        timeout=60.0
    )).json()


async def change_vm_net(vm_id: str, new_net: str):
    params = {"key": "net", "value": new_net}
    return await change_vm_params(vm_id, params)


async def change_vm_power(vm_id: str, new_state: str):
    params = {"key": "state", "value": new_state}
    return await change_vm_params(vm_id, params)


async def create_dispatch(gamespace_id: str, vm_name: str, command: str):
    settings = get_settings()
    session = await get_oauth2_session()

    endpoint = "dispatch"
    params = {"referenceId": "gamebrain",
              "trigger": command,
              "targetGroup": gamespace_id,
              "targetName": vm_name}
    return (await session.post(
        url_path_join(settings.topomojo.base_api_url, endpoint),
        json=params,
        timeout=60.0
    )).json()
