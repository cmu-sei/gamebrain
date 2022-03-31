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
        db.DBManager.init_db(settings.db.connection_string, settings.db.drop_app_tables, settings.db.echo_sql)
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


def check_jwt(token: str, audience: str, require_sub: bool = False):
    settings = get_settings()
    try:
        return jwt.decode(token,
                          Global.get_jwks(),
                          audience=audience,
                          issuer=settings.identity.jwt_issuer,
                          options={"require_aud": True,
                                   "require_iss": True,
                                   "require_sub": require_sub}
                          )
    except (JWTError, JWTClaimsError, ExpiredSignatureError):
        raise HTTPException(status_code=401, detail="JWT Error")


@APP.get("/gamebrain/deploy/{game_id}")
async def deploy(game_id: str, auth: HTTPAuthorizationCredentials = Security(HTTPBearer())):
    payload = check_jwt(auth.credentials, get_settings().identity.gamebrain_jwt_audience, True)
    user_id = payload["sub"]

    player = gameboard.get_player_by_user_id(user_id, game_id)

    team_id = player["teamId"]
    team_data = db.get_team(team_id)

    if not team_data:
        team = gameboard.get_team(team_id)

        specs = gameboard.get_game_specs(game_id).pop()
        external_id = specs["externalId"]

        gamespace = topomojo.register_gamespace(external_id, team["members"])

        gs_id = gamespace["id"]
        visible_vms = [{"id": vm["id"], "name": vm["name"]} for vm in gamespace["vms"] if vm["isVisible"]]

        console_urls = [f"https://topomojo.cyberforce.site/mks/?f=1&s={gs_id}&v={vm['id']}" for vm in visible_vms]
        db.store_team(team_id, gs_id)
        db.store_console_urls(team_id, console_urls)
    else:
        gs_id = team_data["gamespace_id"]
        console_urls = [console_url["url"] for console_url in team_data["console_urls"]]

    return {"gamespaceId": gs_id, "vms": console_urls}


@APP.get("/gamestate/team_data")
async def get_team_data(auth: HTTPAuthorizationCredentials = Security(HTTPBearer())):
    check_jwt(auth.credentials, get_settings().identity.gamestate_jwt_audience)

    return db.get_teams()
