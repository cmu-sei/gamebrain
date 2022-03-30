from fastapi import FastAPI, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JWTError, JWTClaimsError, ExpiredSignatureError
import requests

from gamebrain.clients import gameboard, topomojo
import gamebrain.db as db
from .config import Settings, get_settings
from .util import url_path_join


class Global:
    settings_path = "settings.yaml"
    jwks = None

    @classmethod
    def init(cls):
        Settings.init_settings(cls.settings_path)
        settings = get_settings()
        db.DBManager.init_db(settings.db.connection_string, settings.db.drop_app_tables)
        cls._init_jwks()

    @classmethod
    def _init_jwks(cls):
        settings = get_settings()
        cls.jwks = requests.get(
            url_path_join(settings.identity.base_url, settings.identity.jwks_endpoint),
            verify=settings.ca_cert_path
        ).json()

    @classmethod
    def get_jwks(cls):
        return cls.jwks


Global.init()
APP = FastAPI()


def check_jwt(token: str):
    settings = get_settings()
    try:
        return jwt.decode(token, Global.get_jwks(), audience=settings.identity.jwt_audience,
                          issuer=settings.identity.jwt_issuer)
    except (JWTError, JWTClaimsError, ExpiredSignatureError) as e:
        raise HTTPException(status_code=401, detail="JWT Error")


@APP.get("/deploy")
async def deploy(auth: HTTPAuthorizationCredentials = Security(HTTPBearer())):
    payload = check_jwt(auth.credentials)
    user_id = payload["sub"]

    player = gameboard.get_player_by_user_id(user_id)

    game_id = player["gameId"]
    # This needs to be corrected. Will need to get game ID elsewhere.
    specs = gameboard.get_game_specs(game_id).pop()

    team_id = player["teamId"]
    team = gameboard.get_team(team_id)

    external_id = specs["externalId"]

    gamespace = topomojo.register_gamespace(external_id, team["members"])

    gs_id = gamespace["id"]
    visible_vms = [{"id": vm["id"], "name": vm["name"]} for vm in gamespace["vms"] if vm["isVisible"]]

    console_urls = [f"https://topomojo.cyberforce.site/mks/?f=1&s={gs_id}&v={vm['id']}" for vm in visible_vms]
    # TODO: Fix IP address.
    db.store_team(team_id, "192.168.1.1")
    db.store_console_urls(team_id, console_urls)

    return {"gamespaceId": gs_id, "vms": visible_vms}
