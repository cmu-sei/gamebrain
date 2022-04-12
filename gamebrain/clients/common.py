import time

from authlib.integrations.httpx_client import AsyncOAuth2Client

from ..config import get_settings
from ..util import url_path_join


class SharedOAuth2Session:
    _session = None

    @classmethod
    async def _init_session(cls):
        settings = get_settings()
        cls._session = AsyncOAuth2Client(settings.identity.client_id,
                                         settings.identity.client_secret,
                                         verify=settings.ca_cert_path)
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
    async def get_session(cls):
        if not cls._session:
            await cls._init_session()
        if cls._session.token["expires_at"] - time.time() < 30.0:
            await cls._new_token()
        return cls._session


async def get_oauth2_session():
    return await SharedOAuth2Session.get_session()
