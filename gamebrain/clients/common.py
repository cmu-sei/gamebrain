import time
from logging import error
import ssl
from typing import Optional, Dict

from authlib.integrations.httpx_client import AsyncOAuth2Client
from httpx import Response

from ..config import get_settings
from ..util import url_path_join


class SharedOAuth2Session:
    _session = None

    @classmethod
    async def _init_session(cls):
        settings = get_settings()
        ssl_context = ssl.create_default_context()
        if settings.ca_cert_path:
            ssl_context.load_verify_locations(cafile=settings.ca_cert_path)
        cls._session = AsyncOAuth2Client(settings.identity.client_id,
                                         settings.identity.client_secret,
                                         verify=ssl_context)
        await cls._new_token()

    @classmethod
    async def _new_token(cls):
        settings = get_settings()
        await cls._session.fetch_token(
            url_path_join(settings.identity.base_url, settings.identity.token_endpoint),
            username=settings.identity.token_user,
            password=settings.identity.token_password
        )

    @classmethod
    async def get_session(cls) -> AsyncOAuth2Client:
        if not cls._session:
            await cls._init_session()
        if cls._session.token["expires_at"] - time.time() < 30.0:
            await cls._new_token()
        return cls._session


async def get_oauth2_session() -> AsyncOAuth2Client:
    return await SharedOAuth2Session.get_session()


async def _service_get(service_api_url: str, endpoint: str, query_params: Optional[Dict] = None) -> Response:
    if query_params is None:
        query_params = {}

    session = await get_oauth2_session()

    url = url_path_join(service_api_url, endpoint)
    resp = await session.get(url, params=query_params)
    if resp.status_code != 200:
        error(f"HTTP Request to {url} returned {resp.status_code}")
    return resp
