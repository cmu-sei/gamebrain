import logging

from fastapi import APIRouter, Depends, HTTPException

from .auth import admin_api_key_dependency
from .gamedata.cache import GameStateManager, GamespaceStateOutput, GameDataResponse
from .clients import topomojo


test_router = APIRouter(
    prefix="/test", dependencies=(Depends(admin_api_key_dependency),)
)


@test_router.get("/net_change/{gamespace_id}/{vm_name}/{network}")
async def test_net_change(gamespace_id: str, vm_name: str, network: str):
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

    await topomojo.change_vm_net(vm_id, network)


@test_router.get("/mark_challenge_task_complete/{team_id}/{task_id}")
async def test_mark_challenge_task_complete(
    team_id: str, task_id: str
) -> GameDataResponse:
    await GameStateManager.dispatch_challenge_task_complete(team_id, task_id)
    return await GameStateManager.get_team_data(team_id)


@test_router.get("/mark_codexes_complete/{team_id}")
async def test_mark_codexes_complete(team_id: str) -> GameDataResponse:
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
