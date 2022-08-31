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
    PowerMode,
)

Coordinates = constr(to_lower=True, regex=r"[0-9A-Za-z]{6}")

router = APIRouter()


@router.get("/GameData/{team_id}")
async def get_gamedata(
    team_id: TeamID,
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
) -> GameDataResponse:
    check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)
    try:
        return await GameStateManager.get_team_data(team_id)
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


@router.get("/GameData/LocationUnlock/{coordinates}/{team_id}")
async def get_locationunlock(
    coordinates: Coordinates,
    team_id: TeamID,
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
) -> LocationUnlockResponse:
    check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)
    try:
        return await GameStateManager.unlock_location(team_id, coordinates)
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


@router.get("/GameData/Jump/{location_id}/{team_id}")
async def get_jump(
    location_id: LocationID,
    team_id: TeamID,
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
) -> GenericResponse:
    check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)
    try:
        return await GameStateManager.jump(team_id, location_id)
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


@router.get("/GameData/Initialize/{location}")
async def get_init(
    location: str, auth: HTTPAuthorizationCredentials = Security((HTTPBearer()))
):
    payload = check_jwt(
        auth.credentials, get_settings().identity.jwt_audiences.gamestate_api
    )


@router.get("/GameData/ExtendAntenna/{team_id}")
async def get_extendantenna(
    team_id: TeamID,
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
) -> GenericResponse:
    check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)


@router.get("/GameData/RetractAntenna/{team_id}")
async def get_retractantenna(
    team_id: TeamID,
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
) -> GenericResponse:
    check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)


@router.get("/GameData/ScanLocation/{team_id}")
async def get_scanlocation(
    team_id: TeamID,
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
) -> ScanResponse:
    check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)
    try:
        return await GameStateManager.scan(team_id)
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


@router.get("/GameData/PowerMode/{status}/{team_id}")
async def get_powermode(
    status: PowerMode,
    team_id: TeamID,
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
) -> GenericResponse:
    check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)
    try:
        return await GameStateManager.set_power_mode(team_id, status)
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


@router.get("/GameData/CommEventCompleted/{team_id}")
async def get_commeventcompleted(
    team_id: TeamID,
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
) -> GenericResponse:
    check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)
    try:
        return await GameStateManager.complete_comm_event(team_id)
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


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
