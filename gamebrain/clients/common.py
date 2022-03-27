import time

from oauthlib.oauth2 import LegacyApplicationClient
from requests_oauthlib import OAuth2Session

from ..config import get_settings
from ..util import url_path_join


class SharedOAuth2Session:
    _session = None

    @classmethod
    def _init_session(cls):
        settings = get_settings()
        cls._session = OAuth2Session(client=LegacyApplicationClient(client_id=settings.identity.client_id))
        cls._new_token()

    @classmethod
    def _new_token(cls):
        settings = get_settings()
        cls._session.fetch_token(
            token_url=url_path_join(settings.identity.base_url, settings.identity.token_endpoint),
            username=settings.identity.token_user,
            password=settings.identity.token_password,
            client_id=settings.identity.client_id,
            client_secret=settings.identity.client_secret,
            verify=settings.ca_cert_path
        )

    @classmethod
    def get_session(cls):
        if not cls._session:
            cls._init_session()
        if cls._session.token["expires_at"] - time.time() < 30.0:
            cls._new_token()
        return cls._session

def get_oauth2_session():
    return SharedOAuth2Session.get_session()
