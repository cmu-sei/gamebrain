from typing import Literal

from fastapi import APIRouter, Security, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import constr

from ..auth import check_jwt
from .cache import GameStateManager, NonExistentTeam, TeamID, LocationID
from ..config import get_settings
from .model import (
    GameDataResponse,
    GenericResponse,
    LocationUnlockResponse,
    ScanResponse,
)

Coordinates = constr(to_lower=True, regex=r"[0-9A-Za-z]{6}")

router = APIRouter()


@router.get("/GameData/{team_id}")
async def get_gamedata(
    team_id: TeamID,
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
) -> GameDataResponse:
    check_jwt(
        auth.credentials, get_settings().identity.jwt_audiences.gamestate_api
    )
    try:
        return await GameStateManager.get_team_data(team_id)
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


@router.get("/GameData/LocationUnlock/{coordinates}")
async def get_locationunlock(
    coordinates: Coordinates,
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
) -> LocationUnlockResponse:
    payload = check_jwt(
        auth.credentials, get_settings().identity.jwt_audiences.gamestate_api
    )


@router.get("/GameData/Jump/{location}")
async def get_jump(
    location: str, auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))
) -> GenericResponse:
    payload = check_jwt(
        auth.credentials, get_settings().identity.jwt_audiences.gamestate_api
    )


@router.get("/GameData/Initialize/{location}")
async def get_init(
    location: str, auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))
):
    payload = check_jwt(
        auth.credentials, get_settings().identity.jwt_audiences.gamestate_api
    )


@router.get("/GameData/ExtendAntenna")
async def get_extendantenna(
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
) -> GenericResponse:
    payload = check_jwt(
        auth.credentials, get_settings().identity.jwt_audiences.gamestate_api
    )


@router.get("/GameData/RetractAntenna")
async def get_retractantenna(
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
) -> GenericResponse:
    payload = check_jwt(
        auth.credentials, get_settings().identity.jwt_audiences.gamestate_api
    )


@router.get("/GameData/ScanLocation")
async def get_scanlocation(
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
) -> ScanResponse:
    payload = check_jwt(
        auth.credentials, get_settings().identity.jwt_audiences.gamestate_api
    )


@router.get("/GameData/PowerMode/{status}")
async def get_powermode(
    status: Literal["launchMode", "explorationMode", "standby"],
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
) -> GenericResponse:
    payload = check_jwt(
        auth.credentials, get_settings().identity.jwt_audiences.gamestate_api
    )


@router.get("/GameData/CommEventCompleted")
async def get_commeventcompleted(
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
) -> GenericResponse:
    payload = check_jwt(
        auth.credentials, get_settings().identity.jwt_audiences.gamestate_api
    )


@router.get("/GameData/InjectCommEvent/{commID}")
async def get_injectcommevent(
    commID: str, auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))
) -> GenericResponse:
    payload = check_jwt(
        auth.credentials, get_settings().identity.jwt_audiences.gamestate_api
    )


@router.get("/GameData/CodexStationPowerOn")
async def get_codexstationpoweron(
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
) -> GenericResponse:
    payload = check_jwt(
        auth.credentials, get_settings().identity.jwt_audiences.gamestate_api
    )


@router.get("/GameData/CodexStationPowerOff")
async def get_codexstationpoweroff(
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
) -> GenericResponse:
    payload = check_jwt(
        auth.credentials, get_settings().identity.jwt_audiences.gamestate_api
    )
