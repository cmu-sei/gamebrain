from typing import Optional

from fastapi import FastAPI, Header, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from oauthlib.oauth2 import BackendApplicationClient
from pydantic import BaseModel
import requests
from requests_oauthlib import OAuth2Session
import yaml

from .config import load_settings


SETTINGS = load_settings("./settings.yaml")
IDENTITY = SETTINGS.identity
JWKS = requests.get(f"{IDENTITY.base_url}.well-known/openid-configuration/jwks", verify=SETTINGS.ca_cert_path).json()

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
