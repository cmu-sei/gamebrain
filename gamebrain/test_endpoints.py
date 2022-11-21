from json import JSONDecodeError, load as json_load, loads as json_loads
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from .admin.controller import get_teams_active
from .auth import admin_api_key_dependency
from .config import get_settings, SettingsModel
from .clients import topomojo
from .gamedata.cache import (
    GameDataCacheSnapshot,
    GameStateManager,
    GamespaceStateOutput,
    GameDataResponse,
    GenericResponse,
    LocationUnlockResponse,
    ScanResponse,
    NonExistentTeam,
    TeamID,
    TaskID,
    LocationID,
    PowerMode,
)


test_router = APIRouter(
    prefix="/test", dependencies=(Depends(admin_api_key_dependency),)
)


@test_router.get("/net_change/{gamespace_id}/{vm_name}/{network}")
async def test_net_change(
    gamespace_id: topomojo.GamespaceID, vm_name: str, network: str
):
    gamespace_id = gamespace_id.strip()
    vm_name = vm_name.strip()
    network = network.strip()
    logging.info(
        "Got the following in test_net_change: "
        f"Gamespace: {gamespace_id}, VM Name: {vm_name}, Network: {network}"
    )
    vms = await topomojo.get_vms_by_gamespace_id(gamespace_id)
    if not vms:
        result = "Could not retrieve VMs by gamespace ID."
        logging.error(result)
        raise HTTPException(status_code=500, detail=result)

    for vm in vms:
        try:
            name, *gs_id = vm["name"].split("#")
        except Exception as e:
            logging.info(f"{vms}")
            result = f"Exception when attempting to split a vm named {vm} in test_net_change: {e}"
            logging.error(result)
            raise HTTPException(status_code=500, detail=result)
        if name == vm_name:
            vm_id = vm["id"]
            break
    else:
        result = (
            f"Could not find a VM by the name {vm_name} in gamespace {gamespace_id}."
        )
        logging.error(result)
        raise HTTPException(status_code=500, detail=result)

    logging.info(f"Test net change endpoint called with network: {network}")

    await topomojo.change_vm_net(vm_id, network)


@test_router.get("/gamedata/{team_id}")
async def test_get_team_data(team_id: TeamID) -> GameDataResponse:
    return await GameStateManager.get_team_data(team_id)


@test_router.get("/complete/challenge/{task_id}/{team_id}")
async def test_complete_challenge(team_id: TeamID, task_id: TaskID):
    await GameStateManager.dispatch_challenge_task_complete(team_id, task_id)


@test_router.get("/fail/challenge/{task_id}/{team_id}")
async def test_fail_challenge(team_id: TeamID, task_id: TaskID):
    await GameStateManager.dispatch_challenge_task_failed(team_id, task_id)


@test_router.get("/complete/codex/{team_id}")
async def test_complete_codex(team_id: TeamID) -> GameDataResponse:
    state_update = GamespaceStateOutput(
        exoArch="success",
        redRaider="success",
        ancientRuins="success",
        xenoCult="success",
        museum="success",
        finalGoal="success",
        comms="up",
        flight="up",
        nav="up",
        pilot="up",
    )
    await GameStateManager.dispatch_grading_task_update(team_id, state_update)
    return await GameStateManager.get_team_data(team_id)


@test_router.get("/complete/comm/{team_id}")
async def test_complete_comm(team_id: TeamID) -> GenericResponse:
    try:
        return await GameStateManager.complete_comm_event(team_id)
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


@test_router.get("/complete/jump/{location_id}/{team_id}")
async def test_complete_jump(
    location_id: LocationID, team_id: TeamID
) -> GenericResponse:
    try:
        return await GameStateManager.jump(team_id, location_id)
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


@test_router.get("/complete/extendAntenna/{team_id}")
async def test_complete_extend_antenna(team_id: TeamID) -> GenericResponse:
    try:
        return await GameStateManager.extend_antenna(team_id)
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


@test_router.get("/complete/retractAntenna/{team_id}")
async def test_complete_retract_antenna(team_id: TeamID) -> GenericResponse:
    try:
        return await GameStateManager.retract_antenna(team_id)
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


@test_router.get("/complete/scan/{team_id}")
async def test_complete_scan(team_id: TeamID) -> ScanResponse:
    try:
        return await GameStateManager.scan(team_id)
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


@test_router.get("/complete/power/{new_status}/{team_id}")
async def test_complete_power_change(
    new_status: PowerMode, team_id: TeamID
) -> GenericResponse:
    try:
        return await GameStateManager.set_power_mode(team_id, new_status)
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


@test_router.get("/complete/unlock/{coordinates}/{team_id}")
async def test_unlock_location(
    coordinates: str,
    team_id: TeamID,
) -> LocationUnlockResponse:
    try:
        return await GameStateManager.unlock_location(team_id, coordinates)
    except NonExistentTeam:
        raise HTTPException(status_code=404, detail="Team not found.")


@test_router.get("/settings")
async def test_get_settings() -> SettingsModel:
    return get_settings()


@test_router.get("/current_state")
async def test_get_current_state() -> GameDataCacheSnapshot:
    snapshot = await GameStateManager.snapshot_data()
    snapshot_data = json_loads(snapshot)
    new_state = GameDataCacheSnapshot(**snapshot_data)
    return new_state


@test_router.get("/overwrite_current_state")
async def test_overwrite_current_state():
    active_teams = await get_teams_active()
    if active_teams.__root__:
        raise HTTPException(
            status_code=400, detail="There are active teams. Will not overwrite."
        )

    with open("initial_state.json") as f:
        try:
            new_state_data = json_load(f)
        except JSONDecodeError as e:
            raise HTTPException(
                status_code=400, detail=f"JSON has invalid formatting: {e}"
            )

        try:
            new_state = GameDataCacheSnapshot(**new_state_data)
        except ValidationError as e:
            raise HTTPException(
                status_code=400, detail=f"Could not validate new cache state: {e}"
            )

    await GameStateManager.init(new_state, GameStateManager._settings)
