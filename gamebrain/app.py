from typing import Dict, List, Optional

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


def check_jwt(token: str, audience: Optional[str] = None, require_sub: bool = False):
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
    payload = check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamebrain_api_unpriv, True)
    user_id = payload["sub"]

    player = gameboard.get_player_by_user_id(user_id, game_id)

    team_id = player["teamId"]
    team_data = db.get_team(team_id)

    # Originally it just checked if not team_data, but because headless clients are going to be manually added ahead
    # of the start of the round, team_data will be partially populated.
    if not team_data.get("gamespace_id"):
        team = gameboard.get_team(team_id)

        specs = gameboard.get_game_specs(game_id).pop()
        external_id = specs["externalId"]

        gamespace = topomojo.register_gamespace(external_id, team["members"])

        gs_id = gamespace["id"]
        # Oddly, the team approved name is counterintuitively stored with each player as "approvedName".
        team_name = player.get("approvedName", None)

        visible_vms = [{"id": vm["id"], "name": vm["name"]} for vm in gamespace["vms"] if vm["isVisible"]]
        console_urls = {vm["id"]: f"{get_settings().topomojo.base_url}/mks/?f=1&s={gs_id}&v={vm['id']}"
                        for vm in visible_vms}

        headless_ip = team_data.get("headless_ip")

        db.store_team(team_id, gamespace_id=gs_id, team_name=team_name)
        db.store_event(team_id, f"Launched gamespace {gs_id}")
        db.store_virtual_machines(team_id, console_urls)
    else:
        gs_id = team_data["gamespace_id"]
        console_urls = {vm["id"]: vm["url"] for vm in team_data["vm_data"]}
        headless_ip = team_data["headless_ip"]

    return {"gamespaceId": gs_id, "headless_ip": headless_ip, "vms": console_urls}


@APP.put("/gamebrain/privileged/changenet/{vm_id}")
async def change_vm_net(vm_id: str, new_net: str, auth: HTTPAuthorizationCredentials = Security(HTTPBearer())):
    check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamebrain_api_priv)

    possible_networks = topomojo.get_vm_nets(vm_id).get("net")
    if possible_networks is None:
        raise HTTPException(status_code=400, detail="Specified VM cannot be found.")

    for net in possible_networks:
        if net.startswith(new_net):
            topomojo.change_vm_net(vm_id, new_net)
            break
    else:
        raise HTTPException(status_code=400, detail="Specified VM cannot be changed to the specified network.")


@APP.put("/gamebrain/admin/headlessip/{team_id}")
async def set_headless_ip(team_id: str, headless_ip: str, auth: HTTPAuthorizationCredentials = Security(HTTPBearer())):
    check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamebrain_api_admin)

    db.store_team(team_id, headless_ip=headless_ip)


@APP.post("/gamebrain/admin/secrets/{team_id}")
async def create_challenge_secrets(team_id: str,
                                   secrets: List[str],
                                   auth: HTTPAuthorizationCredentials = Security(HTTPBearer())):
    check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamebrain_api_admin)

    db.store_challenge_secrets(team_id, secrets)


@APP.post("/gamebrain/admin/media")
async def add_media_urls(media_map: Dict[str, str],
                         auth: HTTPAuthorizationCredentials = Security(HTTPBearer())):
    check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamebrain_api_admin)

    db.store_media_assets(media_map)


@APP.get("/gamestate/team_data")
async def get_team_data(auth: HTTPAuthorizationCredentials = Security(HTTPBearer())):
    check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)

    teams = db.get_teams()
    return [{"teamId": team["id"],
             "teamName": team["team_name"],
             "shipHp": team["ship_hp"],
             "shipFuel": team["ship_fuel"]} for team in teams]
