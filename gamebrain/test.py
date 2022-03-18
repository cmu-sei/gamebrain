from typing import Optional

from fastapi import FastAPI, Header
from oauthlib.oauth2 import BackendApplicationClient
from pydantic import BaseModel
import requests
from requests_oauthlib import OAuth2Session
import yaml

from .gbsettings import load_settings


class User(BaseModel):
    user_id: str


def main():
    settings = load_settings("./settings.yaml")

    identity = settings.identity
    token_url = f'{identity.base_url}{identity.token_endpoint}'

    JWKS = requests.get(f"{identity.base_url}.well-known/openid-configuration/jwks", verify=settings.ca_cert_path)

    # client = BackendApplicationClient(client_id=identity.client_id)
    # session = OAuth2Session(client=client)
    # token = session.fetch_token(token_url=token_url, client_id=identity.client_id, client_secret=identity.client_secret, verify=settings.ca_cert_path)

    # print(token)

    # r = session.get("https://foundry.local/topomojo/api/gamespaces")
    # print(r.status_code)

settings = load_settings("./settings.yaml")
identity = settings.identity
token_url = f'{identity.base_url}{identity.token_endpoint}'
auth_url = f'{identity.base_url}authorize'

app = FastAPI()

@app.get("/authtest")
async def header_test(authorization: str = Header(None)):
    print(authorization)


if __name__ == "__main__":
    main()
