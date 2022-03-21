from typing import Optional
from urllib.parse import urljoin

from fastapi import FastAPI, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
import requests
from requests_oauthlib import OAuth2Session
import yaml

from .config import load_settings
from .util import url_path_join


SETTINGS = load_settings("./settings.yaml")
JWKS = requests.get(url_path_join(SETTINGS.identity.base_url, SETTINGS.identity.jwks_endpoint), verify=SETTINGS.ca_cert_path).json()

app = FastAPI()
security = HTTPBearer()


def check_jwt(token: str):
    print(token)
    payload = jwt.decode(token, JWKS, audience=SETTINGS.identity.jwt_audience, issuer=SETTINGS.identity.jwt_issuer)
    return payload

@app.get("/authtest")
async def header_test(auth: HTTPAuthorizationCredentials = Security(security)):
    try:
        payload = check_jwt(auth.credentials)
    except Exception as e:
        print(e)
    else:
        print(payload)
    return ""


if __name__ == "__main__":
    main()
