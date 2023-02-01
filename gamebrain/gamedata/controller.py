# Copyright 2023 Carnegie Mellon University. All Rights Reserved.
# Released under a MIT (SEI)-style license. See LICENSE.md in the project root for license information.

import json
import logging

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
    PowerStatus,
)

Coordinates = constr(to_lower=True, regex=r"[0-9A-Za-z]{6}")

router = APIRouter()


@router.get("/GameData")
@router.get("/GameData/{team_id}")
async def get_gamedata(
    team_id: TeamID | None = None,
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
) -> GameDataResponse:
    check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)
    try:
        game_data = await GameStateManager.get_team_data(team_id)
        logging.debug(f"Team {team_id} GameData: \n{json.dumps(game_data.dict(), indent=2)}")
        return game_data
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


@router.get("/GameData/ExtendAntenna/{team_id}")
async def get_extendantenna(
    team_id: TeamID,
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
) -> GenericResponse:
    check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)
    try:
        result = await GameStateManager.extend_antenna(team_id)
        logging.info(f"ExtendAntenna result: \n{result.json(indent=2)}")
        return result
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


@router.get("/GameData/RetractAntenna/{team_id}")
async def get_retractantenna(
    team_id: TeamID,
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
) -> GenericResponse:
    check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)
    try:
        result = await GameStateManager.retract_antenna(team_id)
        logging.info(f"RetractAntenna result: \n{result.json(indent=2)}")
        return result
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


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
        result = await GameStateManager.complete_comm_event(team_id)
        logging.info(f"CommEventCompleted result: {result}.")
        return result
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


@router.get("/GameData/CodexStationPowerOn/{team_id}")
async def get_codexstationpoweron(
    team_id: TeamID,
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
) -> GenericResponse:
    check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)
    try:
        return await GameStateManager.codex_power(team_id, PowerStatus.on)
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


@router.get("/GameData/CodexStationPowerOff/{team_id}")
async def get_codexstationpoweroff(
    team_id: TeamID,
    auth: HTTPAuthorizationCredentials = Security((HTTPBearer())),
) -> GenericResponse:
    check_jwt(auth.credentials, get_settings().identity.jwt_audiences.gamestate_api)
    try:
        return await GameStateManager.codex_power(team_id, PowerStatus.off)
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")
