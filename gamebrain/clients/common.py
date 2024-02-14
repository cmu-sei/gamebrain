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

from enum import Enum
from logging import error
from typing import Any

from httpx import AsyncClient, Response


class HttpMethod(Enum):
    GET = "GET"
    PUT = "PUT"
    POST = "POST"


class RequestFailure(Exception):
    def __init__(self, message, status_code, *args, **kwargs):
        super().__init__(message, *args, **kwargs)
        self.status_code = status_code


async def _service_request_and_log(
    client: AsyncClient, method: HttpMethod, endpoint: str, data: dict[Any] = None
) -> Response:
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
        api_key = request.headers.get('x-api-key')
        if api_key:
            request.headers['x-api-key'] = '<secret>'
        message = (
            f"HTTP Request to {response.url} returned {response.status_code}\n"
            f"HTTP Method was: {request.method}\n"
            f"Headers were: {request.headers}\n"
            f"Request Body was: {request.content}\n"
            f"Response content was: {response.content}\n"
        )
        error(message)
        raise RequestFailure(message, response.status_code)

    return response
