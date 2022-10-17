from logging import error
from enum import Enum
import json as jsonlib
import ssl
from typing import Any, Dict, List, Optional

from httpx import AsyncClient


class ModuleSettings:
    settings = None


def get_settings():
    if ModuleSettings.settings is None:
        raise AttributeError("TopoMojo settings are not initialized.")
    return ModuleSettings.settings


class HttpMethod(Enum):
    GET = "GET"
    PUT = "PUT"
    POST = "POST"


def _get_topomojo_client() -> AsyncClient:
    settings = get_settings()
    ssl_context = ssl.create_default_context()
    if settings.ca_cert_path:
        ssl_context.load_verify_locations(cafile=settings.ca_cert_path)
    api_key = settings.topomojo.x_api_key
    api_client = settings.topomojo.x_api_client

    return AsyncClient(
        base_url=settings.topomojo.base_api_url,
        verify=ssl_context,
        headers={"x-api-key": api_key, "x-api-client": api_client},
    )


async def _topomojo_request(
    method: HttpMethod, endpoint: str, data: Optional[Any]
) -> Optional[Any] | None:
    async with _get_topomojo_client() as client:
        args = {
            "method": method.value,
            "url": endpoint,
            "timeout": 300.0,
        }
        if method in (HttpMethod.PUT, HttpMethod.POST):
            args["json"] = data
        elif method in (HttpMethod.GET,):
            args["params"] = data
        else:
            raise ValueError("Unsupported HTTP method.")

        request = client.build_request(**args)

        response = await client.send(request)
        if not response.is_success:
            error(
                f"HTTP Request to {response.url} returned {response.status_code}\n"
                f"HTTP Method was: {request.method}\n"
                f"Headers were: {request.headers}\n"
                f"Request Body was: {request.content}\n"
            )

    try:
        return response.json()
    except jsonlib.JSONDecodeError:
        return None


async def _topomojo_get(
    endpoint: str, query_params: Optional[Dict] = None
) -> Optional[Any] | None:
    return await _topomojo_request(HttpMethod.GET, endpoint, query_params)


async def _topomojo_post(
    endpoint: str, json_data: Optional[Any]
) -> Optional[Any] | None:
    return await _topomojo_request(HttpMethod.POST, endpoint, json_data)


async def _topomojo_put(
    endpoint: str, json_data: Optional[Any]
) -> Optional[Any] | None:
    return await _topomojo_request(HttpMethod.PUT, endpoint, json_data)


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


async def register_gamespace(
    workspace_id: str, expiration_time: str, team_members: List[Dict]
):
    """
    team_members: Each dict contains 'id' and 'approvedName' keys.
    """
    settings = get_settings()

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
        "expirationTime": expiration_time,
        "players": [
            {"subjectId": player["id"], "subjectName": player["approvedName"]}
            for player in team_members
        ],
    }
    endpoint = "gamespace"
    return await _topomojo_post(endpoint, post_data)


async def stop_gamespace(gamespace_id: str):
    endpoint = f"gamespace/{gamespace_id}/stop"
    return await _topomojo_post(endpoint, {})


async def complete_gamespace(gamespace_id: str):
    endpoint = f"gamespace/{gamespace_id}/complete"
    return await _topomojo_post(endpoint, {})


async def change_vm_params(vm_id: str, params: dict):
    endpoint = f"vm/{vm_id}/change"
    return await _topomojo_put(endpoint, params)


async def change_vm_net(vm_id: str, new_net: str):
    params = {"key": "net", "value": new_net}
    return await change_vm_params(vm_id, params)


async def change_vm_power(vm_id: str, new_state: str):
    params = {"key": "state", "value": new_state}
    return await change_vm_params(vm_id, params)


async def create_dispatch(gamespace_id: str, vm_name: str, command: str):
    endpoint = "dispatch"
    params = {
        "referenceId": "gamebrain",
        "trigger": command,
        "targetGroup": gamespace_id,
        "targetName": vm_name,
    }
    return await _topomojo_post(endpoint, params)
