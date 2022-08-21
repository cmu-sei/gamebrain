from typing import Literal

from fastapi import APIRouter, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import constr

from .view import GameData, GenericResponse, LocationUnlockResponse, ScanResponse

Coordinates = constr(to_lower=True, regex=r"[0-9A-Za-z]{6}")

router = APIRouter()


@router.get("/GameData")
def get_gamedata(auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))) -> GameData:
    ...


@router.get("/GameData/LocationUnlock/{coordinates}")
def get_locationunlock(coordinates: Coordinates,
                       auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))) -> LocationUnlockResponse:
    ...


@router.get("/GameData/Jump/{location}")
def get_jump(location: str,
             auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))) -> GenericResponse:
    ...


@router.get("/GameData/Initialize/{location}")
def get_init(location: str,
             auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))):
    ...


@router.get("/GameData/ExtendAntenna")
def get_extendantenna(auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))) -> GenericResponse:
    ...


@router.get("/GameData/RetractAntenna")
def get_retractantenna(auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))) -> GenericResponse:
    ...


@router.get("/GameData/ScanLocation")
def get_scanlocation(auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))) -> ScanResponse:
    ...


@router.get("/GameData/PowerMode/{status}")
def get_powermode(status: Literal["launchMode", "explorationMode", "standby"],
                  auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))) -> GenericResponse:
    ...


@router.get("/GameData/CommEventCompleted")
def get_commeventcompleted(auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))) -> GenericResponse:
    ...


@router.get("/GameData/InjectCommEvent/{commID}")
def get_injectcommevent(commID: str,
                        auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))) -> GenericResponse:
    ...


@router.get("/GameData/CodexStationPowerOn")
def get_codexstationpoweron(auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))) -> GenericResponse:
    ...


@router.get("/GameData/CodexStationPowerOff")
def get_codexstationpoweroff(auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))) -> GenericResponse:
    ...
