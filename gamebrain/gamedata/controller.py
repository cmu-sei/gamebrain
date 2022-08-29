from typing import Literal

from fastapi import APIRouter, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import constr

from ..auth import check_jwt
from ..config import get_settings
from .model import GameDataTeamSpecific, GenericResponse, LocationUnlockResponse, ScanResponse

Coordinates = constr(to_lower=True, regex=r"[0-9A-Za-z]{6}")

router = APIRouter()


@router.get("/GameData")
def get_gamedata(auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))) -> GameDataTeamSpecific:
    payload = check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)


@router.get("/GameData/LocationUnlock/{coordinates}")
def get_locationunlock(coordinates: Coordinates,
                       auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))) -> LocationUnlockResponse:
    payload = check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)


@router.get("/GameData/Jump/{location}")
def get_jump(location: str,
             auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))) -> GenericResponse:
    payload = check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)


@router.get("/GameData/Initialize/{location}")
def get_init(location: str,
             auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))):
    payload = check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)


@router.get("/GameData/ExtendAntenna")
def get_extendantenna(auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))) -> GenericResponse:
    payload = check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)


@router.get("/GameData/RetractAntenna")
def get_retractantenna(auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))) -> GenericResponse:
    payload = check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)


@router.get("/GameData/ScanLocation")
def get_scanlocation(auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))) -> ScanResponse:
    payload = check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)


@router.get("/GameData/PowerMode/{status}")
def get_powermode(status: Literal["launchMode", "explorationMode", "standby"],
                  auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))) -> GenericResponse:
    payload = check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)


@router.get("/GameData/CommEventCompleted")
def get_commeventcompleted(auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))) -> GenericResponse:
    payload = check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)


@router.get("/GameData/InjectCommEvent/{commID}")
def get_injectcommevent(commID: str,
                        auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))) -> GenericResponse:
    payload = check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)


@router.get("/GameData/CodexStationPowerOn")
def get_codexstationpoweron(auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))) -> GenericResponse:
    payload = check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)


@router.get("/GameData/CodexStationPowerOff")
def get_codexstationpoweroff(auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))) -> GenericResponse:
    payload = check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)
