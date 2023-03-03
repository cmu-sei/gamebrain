
from enum import Enum
from logging import error
from typing import Any

from httpx import AsyncClient, Response


class HttpMethod(Enum):
    GET = "GET"
    PUT = "PUT"
    POST = "POST"


async def _service_request_and_log(
    client: AsyncClient, method: HttpMethod, endpoint: str, data: dict[Any] = None
) -> Response:
    async with client:
        args = {
            "method": method.value,
            "url": endpoint,
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
                f"Response content was: {response.content}\n"
            )

        return response
