from typing import Optional
from urllib.parse import urljoin

from fastapi import FastAPI, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from oauthlib.oauth2 import LegacyApplicationClient
import requests
from requests_oauthlib import OAuth2Session
import yaml

from .config import load_settings
from .util import url_path_join


SETTINGS = load_settings("./settings.yaml")

JWKS = requests.get(
    url_path_join(SETTINGS.identity.base_url, SETTINGS.identity.jwks_endpoint),
    verify=SETTINGS.ca_cert_path
).json()

OAUTH2_SESSION = OAuth2Session(client=LegacyApplicationClient(client_id=SETTINGS.identity.client_id))

OAUTH2_SESSION.fetch_token(
    token_url=url_path_join(SETTINGS.identity.base_url, SETTINGS.identity.token_endpoint),
    username="administrator@foundry.local",
    password="foundry",
    client_id=SETTINGS.identity.client_id,
    client_secret=SETTINGS.identity.client_secret,
    verify=SETTINGS.ca_cert_path
)

APP = FastAPI()


def check_jwt(token: str):
    try:
        return jwt.decode(token, JWKS, audience=SETTINGS.identity.jwt_audience, issuer=SETTINGS.identity.jwt_issuer)
    except (JWTError, JWTClaimsError, ExpiredSignatureError) as e:
        raise HTTPException(status_code=401, detail="JWT Error")

@APP.get("/authtest")
async def auth_test(auth: HTTPAuthorizationCredentials = Security(HTTPBearer())):
    payload = check_jwt(auth.credentials)
    user_id = payload["sub"]

    params = {"uid": user_id, "Filter": "collapse"}
    players = OAUTH2_SESSION.get(
        url_path_join(SETTINGS.gameboard.base_gb_url, SETTINGS.gameboard.players_endpoint),
        verify=SETTINGS.ca_cert_path,
        params=params
    ).json()
    player = {}
    for item in players:
        if item["userId"] == user_id:
            player = item
    if not player:
        raise Exception("NYI")

    game_id = player["gameId"]
    endpoint = SETTINGS.gameboard.specs_endpoint.format(game_id)
    specs = OAUTH2_SESSION.get(
        url_path_join(SETTINGS.gameboard.base_gb_url, endpoint),
        verify=SETTINGS.ca_cert_path
    ).json()[0]

    external_id = specs["externalId"]
    endpoint = SETTINGS.topomojo.workspace_endpoint.format(external_id)
    workspace = OAUTH2_SESSION.get(
        url_path_join(SETTINGS.topomojo.base_api_url, endpoint),
        verify=SETTINGS.ca_cert_path
    ).json()

    print(workspace)

    return ""
