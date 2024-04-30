# Cyber Defenders Video Game

# Copyright 2023 Carnegie Mellon University.

# NO WARRANTY. THIS CARNEGIE MELLON UNIVERSITY AND SOFTWARE ENGINEERING
# INSTITUTE MATERIAL IS FURNISHED ON AN "AS-IS" BASIS. CARNEGIE MELLON
# UNIVERSITY MAKES NO WARRANTIES OF ANY KIND, EITHER EXPRESSED OR IMPLIED, AS
# TO ANY MATTER INCLUDING, BUT NOT LIMITED TO, WARRANTY OF FITNESS FOR PURPOSE
# OR MERCHANTABILITY, EXCLUSIVITY, OR RESULTS OBTAINED FROM USE OF THE
# MATERIAL. CARNEGIE MELLON UNIVERSITY DOES NOT MAKE ANY WARRANTY OF ANY KIND
# WITH RESPECT TO FREEDOM FROM PATENT, TRADEMARK, OR COPYRIGHT INFRINGEMENT.

# Released under a MIT (SEI)-style license, please see license.txt or contact
# permission@sei.cmu.edu for full terms.

# [DISTRIBUTION STATEMENT A] This material has been approved for public
# release and unlimited distribution.  Please see Copyright notice for
# non-US Government use and distribution.

# This Software includes and/or makes use of Third-Party Software each subject
# to its own license.

# DM23-0100

import json
import logging

from fastapi import APIRouter, Security, HTTPException
from pydantic import constr

from ..auth import gamestate_jwt_dependency
from .cache import GameStateManager, NonExistentTeam, TeamID, LocationID
from .model import (
    GameDataResponse,
    GenericResponse,
    LocationUnlockResponse,
    ScanResponse,
    PowerMode,
)

Coordinates = constr(to_lower=True, regex=r"[0-9A-Za-z]{6}")

gamestate_router = APIRouter(
    prefix="/GameData",
    dependencies=(Security(gamestate_jwt_dependency),),
)


@gamestate_router.get("/")
@gamestate_router.get("/{team_id}")
async def get_gamedata(
    team_id: TeamID | None = None,
) -> GameDataResponse:
    try:
        game_data = await GameStateManager.get_team_data(team_id)
        logging.debug(
            f"Team {team_id} GameData: \n{json.dumps(game_data.dict(), indent=2, default=str)}"
        )
        return game_data
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


@gamestate_router.get("/LocationUnlock/{coordinates}/{team_id}")
async def get_locationunlock(
    coordinates: Coordinates,
    team_id: TeamID,
) -> LocationUnlockResponse:
    try:
        return await GameStateManager.unlock_location(team_id, coordinates)
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


@gamestate_router.get("/Jump/{location_id}/{team_id}")
async def get_jump(
    location_id: LocationID,
    team_id: TeamID,
) -> GenericResponse:
    try:
        return await GameStateManager.jump(team_id, location_id)
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


@gamestate_router.get("/ExtendAntenna/{team_id}")
async def get_extendantenna(
    team_id: TeamID,
) -> GenericResponse:
    try:
        result = await GameStateManager.extend_antenna(team_id)
        logging.info(f"{result.json(indent=2)}")
        return result
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


@gamestate_router.get("/RetractAntenna/{team_id}")
async def get_retractantenna(
    team_id: TeamID,
) -> GenericResponse:
    try:
        result = await GameStateManager.retract_antenna(team_id)
        logging.info(f"{result.json(indent=2)}")
        return result
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


@gamestate_router.get("/ScanLocation/{team_id}")
async def get_scanlocation(
    team_id: TeamID,
) -> ScanResponse:
    try:
        return await GameStateManager.scan(team_id)
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


@gamestate_router.get("/PowerMode/{status}/{team_id}")
async def get_powermode(
    status: PowerMode,
    team_id: TeamID,
) -> GenericResponse:
    try:
        return await GameStateManager.set_power_mode(team_id, status)
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


@gamestate_router.get("/CommEventCompleted/{team_id}")
async def get_commeventcompleted(
    team_id: TeamID,
) -> GenericResponse:
    try:
        result = await GameStateManager.complete_comm_event(team_id)
        logging.info(f"{result}")
        return result
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")
