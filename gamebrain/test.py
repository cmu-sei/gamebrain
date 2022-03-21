from typing import Optional

from fastapi import FastAPI, Header, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from oauthlib.oauth2 import BackendApplicationClient
from pydantic import BaseModel
import requests
from requests_oauthlib import OAuth2Session
import yaml

from .gbsettings import load_settings


SETTINGS = load_settings("./settings.yaml")
IDENTITY = SETTINGS.identity
JWKS = requests.get(f"{IDENTITY.base_url}.well-known/openid-configuration/jwks", verify=SETTINGS.ca_cert_path).json()

class User(BaseModel):
    user_id: str


def main():
    identity = SETTINGS.identity
    token_url = f'{identity.base_url}{identity.token_endpoint}'

    global JWKS
    JWKS = requests.get(f"{identity.base_url}.well-known/openid-configuration/jwks", verify=SETTINGS.ca_cert_path).json()

    # client = BackendApplicationClient(client_id=identity.client_id)
    # session = OAuth2Session(client=client)
    # token = session.fetch_token(token_url=token_url, client_id=identity.client_id, client_secret=identity.client_secret, verify=SETTINGS.ca_cert_path)

    # print(token)

    # r = session.get("https://foundry.local/topomojo/api/gamespaces")
    # print(r.status_code)

def check_jwt(token: str):
    print(token)
    payload = jwt.decode(token, JWKS, audience=SETTINGS.identity.jwt_audience, issuer=SETTINGS.identity.jwt_issuer)
    return payload

app = FastAPI()
security = HTTPBearer()

@app.get("/authtest")
async def header_test(auth: HTTPAuthorizationCredentials = Security(security)):
    print(JWKS)
    try:
        payload = check_jwt(auth.credentials)
    except Exception as e:
        print(e)
    else:
        print(payload)
    return ""


if __name__ == "__main__":
    main()
