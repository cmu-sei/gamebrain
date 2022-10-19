import asyncio
import json
import logging
from typing import Literal

from pydantic import BaseModel

from ..db import get_team
from .model import (
    GameDataTeamSpecific,
    GameDataResponse,
    LocationData,
    LocationDataTeamSpecific,
    LocationDataFull,
    MissionData,
    MissionDataTeamSpecific,
    MissionDataFull,
    TaskCompletionType,
    TaskData,
    TaskDataTeamSpecific,
    TaskDataFull,
    CommEventData,
    PowerMode,
    PowerStatus,
    CurrentLocationGameplayDataTeamSpecific,
    LocationUnlockResponse,
    GenericResponse,
    ScanResponse,
)
from ..clients import topomojo

CommID = str
LocationID = str
MissionID = str
TaskID = str
TeamID = str

JsonStr = str

VmName = str
VmURL = str


class NonExistentTeam(Exception):
    ...


class CommMap(BaseModel):
    __root__: dict[CommID, CommEventData]


class LocationMap(BaseModel):
    __root__: dict[LocationID, LocationData]


class MissionMap(BaseModel):
    __root__: dict[MissionID, MissionData]


class TaskMap(BaseModel):
    __root__: dict[TaskID, TaskData]


class TeamMap(BaseModel):
    __root__: dict[TeamID, GameDataTeamSpecific]


class GlobalData(BaseModel):
    comm_map: CommMap
    location_map: LocationMap
    mission_map: MissionMap
    task_map: TaskMap


class GameDataCache(GlobalData):
    team_map: TeamMap
    team_initial_state: GameDataTeamSpecific


# I wasn't sure if the output models should really be here, but there wasn't really any other obvious place to put them.
SuccessOrFail = Literal["success", "fail"]
UpOrDown = Literal["up", "down"]


class GamespaceStateOutput(BaseModel):
    exoArch: SuccessOrFail = "fail"
    redRaider: SuccessOrFail = "fail"
    ancientRuins: SuccessOrFail = "fail"
    xenoCult: SuccessOrFail = "fail"
    museum: SuccessOrFail = "fail"
    finalGoal: SuccessOrFail = "fail"
    comms: UpOrDown = "down"
    flight: UpOrDown = "down"
    nav: UpOrDown = "down"
    pilot: UpOrDown = "down"


class GameStateManager:
    _lock = asyncio.Lock()
    _cache: GameDataCache

    _settings: "SettingsModel"

    @classmethod
    def _mark_task_complete_if_current(
        cls,
        team_id: TeamID,
        team_data: GameDataTeamSpecific,
        task_type: TaskCompletionType,
    ):
        """
        cache lock is assumed to be held
        """
        current_loc = team_data.currentStatus.currentLocation

        tasks_at_location = {
            task.taskID
            for task in cls._cache.task_map.__root__.values()
            if task.markCompleteWhen and task.markCompleteWhen.locationID == current_loc
        }

        task_completed = False
        for mission in team_data.missions:
            for task in mission.taskList:
                if task.taskID not in tasks_at_location:
                    break
                if task.complete:
                    continue
                if task_completed:
                    global_task = cls._cache.task_map.__root__.get(task.taskID)
                    if not global_task:
                        logging.error(f"Team {team_id} had a task in its team-specific data that "
                                      f"was not in the global data: {task.taskID}")
                    comm_event = cls._cache.comm_map.__root__.get(global_task.commID)
                    if global_task.commID != "" and not comm_event:
                        logging.error(f"Team {team_id} had a comm event in its team-specific data that "
                                      f"was not in the global data: {global_task.commID}")
                    team_data.currentStatus.incomingTransmission = bool(comm_event)
                    team_data.currentStatus.incomingTransmissionObject = comm_event or {}
                    return
                completion_criteria = cls._cache.task_map.__root__[
                    task.taskID
                ].markCompleteWhen
                if completion_criteria is None:
                    logging.warning(
                        f"Marking task {task.taskID} complete for team {team_id}, "
                        f"despite the task not having a markCompleteWhen specified. (looking for: {task_type})"
                    )
                    task.complete = True
                    task_completed = True
                    continue
                if completion_criteria.type == task_type:
                    logging.info(
                        f"Marking task {task.taskID} complete for team {team_id}. (looking for: {task_type})"
                    )
                    task.complete = True
                    task_completed = True
                    continue
                logging.debug(
                    f"Did not mark any specified tasks complete, but did complete a check for team {team_id}. "
                    f"(looking for: {task_type})"
                )
                return
            if task_completed:
                mission.complete = True
                return

    @classmethod
    def _basic_validation(cls, initial_state: GameDataCache):
        for task_id, task in initial_state.task_map.__root__.items():
            if task.markCompleteWhen is None:
                logging.warning(
                    f"Task {task_id} does not have a markCompleteWhen field specified."
                )
                continue
            if (
                bad_loc := task.markCompleteWhen.locationID
                not in initial_state.location_map.__root__
            ):
                logging.warning(
                    f"Task {task_id}'s markCompleteWhen field specifies location {bad_loc} "
                    "which is not in the location map."
                )

    @classmethod
    async def snapshot_data(cls) -> JsonStr:
        async with cls._lock:
            return cls._cache.json()

    @classmethod
    async def init(cls, initial_state: GameDataCache, settings: "SettingsModel"):
        async with cls._lock:
            cls._basic_validation(initial_state)
            cls._cache = initial_state
            cls._settings = settings

    @classmethod
    async def new_team(cls, team_id: TeamID):
        async with cls._lock:
            new_team_state = GameDataTeamSpecific(
                **cls._cache.team_initial_state.dict()
            )
            new_team_state.session.teamInfoName = team_id
            cls._cache.team_map.__root__[team_id] = new_team_state

    @classmethod
    async def check_team_exists(cls, team_id: TeamID) -> bool:
        async with cls._lock:
            return team_id in cls._cache.team_map.__root__

    @classmethod
    async def get_team_data(cls, team_id: TeamID | None) -> GameDataResponse | None:
        async with cls._lock:
            if team_id is None:
                team_data = cls._cache.team_initial_state
            else:
                team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            full_loc_data = []
            for location in team_data.locations:
                loc_global = cls._cache.location_map.__root__[location.locationID]
                loc_full = LocationDataFull(**loc_global.dict() | location.dict())
                full_loc_data.append(loc_full)

            full_mission_data = []
            for mission in team_data.missions:
                mission_global = cls._cache.mission_map.__root__[mission.missionID]
                task_list = [
                    TaskDataFull(
                        **cls._cache.task_map.__root__[task.taskID].dict() | task.dict()
                    )
                    for task in mission.taskList
                ]
                mission_full = MissionDataFull(
                    **mission_global.dict() | mission.dict() | {"taskList": task_list}
                )
                full_mission_data.append(mission_full)

            full_team_data = GameDataResponse(
                currentStatus=team_data.currentStatus,
                session=team_data.session,
                ship=team_data.ship,
                locations=full_loc_data,
                missions=full_mission_data,
            )

            logging.info(
                f"Ship Data response: {json.dumps(team_data.ship.dict(), indent=2)}"
            )

            return full_team_data

    @classmethod
    async def challenge_task_complete(cls, team_id: TeamID, task_id: str):
        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                logging.error(
                    f"Dispatch task reported team {team_id} completed a task, but that team does not exist."
                )
                return

            global_task_data = cls._cache.task_map.__root__.get(task_id)
            if not global_task_data:
                logging.error(
                    f"Dispatch task reported task {task_id} complete, but no such task exists."
                )
                return

            # Some challenge tasks have an immediate follow-up that we can't directly detect, so just mark it complete.
            cls._mark_task_complete_if_current(team_id, team_data, "challenge")
            cls._mark_task_complete_if_current(team_id, team_data, "challenge")

    @classmethod
    async def team_state_from_gamespace(
        cls, team_id: TeamID, gamespace_state_output: GamespaceStateOutput
    ):
        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            team_data.session.teamCodexCount = sum(
                1
                for _ in filter(
                    lambda v: v == "success", gamespace_state_output.dict().values()
                )
            )

            # TODO: Generalize this.
            location_mapping = {
                "aursys": gamespace_state_output.exoArch,
                "j900": gamespace_state_output.redRaider,
                "vitlra": gamespace_state_output.ancientRuins,
                "aurmusm": gamespace_state_output.museum,
                "astfld_correct": gamespace_state_output.xenoCult,
                "lgpt22": gamespace_state_output.finalGoal,
            }
            current_loc = location_mapping.get(team_data.currentStatus.currentLocation)
            if current_loc and "success" in current_loc.lower():
                # Some codex tasks have an immediate follow-up that we can't directly detect, so just mark it complete.
                cls._mark_task_complete_if_current(team_id, team_data, "codex")
                cls._mark_task_complete_if_current(team_id, team_data, "codex")

            transform_map = {"up": PowerStatus.on, "down": PowerStatus.off}

            team_data.ship.commPower = transform_map.get(gamespace_state_output.comms, PowerStatus.off)
            team_data.ship.flightPower = transform_map.get(gamespace_state_output.flight, PowerStatus.off)
            team_data.ship.navPower = transform_map.get(gamespace_state_output.nav, PowerStatus.off)
            team_data.ship.pilotPower = transform_map.get(gamespace_state_output.pilot, PowerStatus.off)

    @classmethod
    async def update_team_urls(cls, team_id: TeamID, vm_urls: dict[VmName, VmURL]):
        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            team_data.ship.workstation1URL = vm_urls.get("operator-terminal-1")
            team_data.ship.workstation2URL = vm_urls.get("operator-terminal-2")
            team_data.ship.workstation3URL = vm_urls.get("operator-terminal-3")
            team_data.ship.workstation4URL = vm_urls.get("operator-terminal-4")
            team_data.ship.workstation5URL = vm_urls.get("operator-terminal-5")
            team_data.ship.codexURL = vm_urls.get("codex-decoder")

            logging.info(
                f"Team Data for team {team_id} updated: {json.dumps(team_data.ship.dict(), indent=2)}"
            )

    @classmethod
    async def extend_antenna(cls, team_id: TeamID) -> GenericResponse:
        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            if not team_data.currentStatus.firstContactComplete:
                return GenericResponse(
                    success=False, message="First Contact Event Incomplete"
                )

            team_db_data = await get_team(team_id)
            gamespace_id = team_db_data.get("gamespace_id")

            if not gamespace_id:
                return GenericResponse(
                    success=False, message=f"No Gamespace for Team {team_id}"
                )

            vms = await topomojo.get_vms_by_gamespace_id(gamespace_id)
            if not vms:
                return GenericResponse(
                    success=False,
                    message=f"No VMs registered for Gamespace {gamespace_id}",
                )

            for vm in vms:
                try:
                    name, *gs_id = vm["name"].split("#")
                except Exception as e:
                    logging.info(f"{vms}")
                    logging.exception(f"Exception when attempting to split a VM named {vm} in extend_antenna: {e}")
                    continue
                if name == cls._settings.game.antenna_vm_name:
                    vm_id = vm["id"]
                    break
            else:
                return GenericResponse(
                    success=False,
                    message=f"Antenna VM not found in Gamespace {gamespace_id}",
                )

            location_data = cls._cache.location_map.__root__[
                team_data.currentStatus.currentLocation
            ]
            new_net = location_data.networkName

            await topomojo.change_vm_net(vm_id, new_net)

            team_data.currentStatus.antennaExtended = True
            team_data.currentStatus.networkConnected = True
            team_data.currentStatus.networkName = new_net

            cls._mark_task_complete_if_current(team_id, team_data, "antennaExtended")

            return GenericResponse(
                success=True, message=f"Team {team_id} extended their antenna."
            )

    @classmethod
    async def retract_antenna(cls, team_id: TeamID) -> GenericResponse:
        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            team_data.currentStatus.antennaExtended = False
            team_data.currentStatus.networkConnected = False
            team_data.currentStatus.networkName = ""

            cls._mark_task_complete_if_current(team_id, team_data, "antennaRetracted")

            return GenericResponse(success=True, message="antennaRetracted")

    @classmethod
    async def unlock_location(
        cls, team_id: TeamID, unlock_code: str
    ) -> LocationUnlockResponse:
        def response(status, location=""):
            return LocationUnlockResponse(
                responseStatus=status,
                locationID=location,
                enteredCoordinates=unlock_code,
            )

        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            team_unlocked_locations = set(
                map(
                    lambda loc: loc.locationID,
                    filter(lambda loc: loc.unlocked, team_data.locations),
                )
            )
            for location_id, location_data in cls._cache.location_map.__root__.items():
                if location_data.unlockCode != unlock_code:
                    continue
                if location_id in team_unlocked_locations:
                    return response("alreadyunlocked")
                else:
                    newly_unlocked = LocationDataTeamSpecific(
                        locationID=location_id,
                    )
                    team_data.locations.append(newly_unlocked)

                    # Each Comm Event has a LocationID, so gather the ones associated with the new location.
                    unlocked_comm_event_ids = set(
                        map(
                            lambda c: c.commID,
                            (
                                filter(
                                    lambda c: c.locationID == location_id,
                                    cls._cache.comm_map.__root__.values(),
                                )
                            ),
                        )
                    )
                    # Next gather the tasks that are associated with a Comm Event in the previous set.
                    unlocked_task_ids = set(
                        map(
                            lambda t: t.taskID,
                            filter(
                                lambda t: t.commID in unlocked_comm_event_ids,
                                cls._cache.task_map.__root__.values(),
                            ),
                        )
                    )
                    # Finally gather the missions associated with the previous set of tasks.
                    unlocked_mission_ids = set(
                        map(
                            lambda m: m.missionID,
                            filter(
                                lambda m: set(map(lambda t: t.taskID, m.taskList))
                                & unlocked_task_ids,
                                cls._cache.mission_map.__root__.values(),
                            ),
                        )
                    )

                    # Now use the gathered sets to actually update the cache.
                    team_specific_missions = [
                        MissionDataTeamSpecific(
                            missionID=mission_id,
                            taskList=[
                                TaskDataTeamSpecific(
                                    taskID=task_id,
                                )
                                for task_id in unlocked_task_ids
                                if mission_id
                                == cls._cache.task_map.__root__[task_id].missionID
                            ],
                        )
                        for mission_id in unlocked_mission_ids
                    ]

                    team_data.missions.extend(team_specific_missions)

                    return response("success", location_id)

            return response("invalid")

    @classmethod
    async def jump(cls, team_id: TeamID, location_id: LocationID) -> GenericResponse:
        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            if team_data.currentStatus.currentLocation == location_id:
                return GenericResponse(
                    success=False, message=f"Already at {location_id}."
                )

            location_data = cls._cache.location_map.__root__.get(location_id)
            if not location_data:
                return GenericResponse(
                    success=False,
                    message=f"Unable to find {location_id} in global cache.",
                )

            destination = [
                loc for loc in team_data.locations if loc.locationID == location_id
            ]
            if not destination:
                return GenericResponse(
                    success=False,
                    message=f"Location {location_id} is not yet unlocked.",
                )

            location_team_specific = destination.pop()

            if (
                location_team_specific.locationID
                == cls._settings.game.final_destination_name
            ):
                if team_data.session.teamCodexCount < 3:
                    return GenericResponse(
                        success=False, message="Not enough codices unlocked."
                    )
                else:
                    team_db_data = await get_team(team_id)
                    gamespace_id = team_db_data.get("gamespace_id")

                    if not gamespace_id:
                        return GenericResponse(
                            success=False, message=f"No Gamespace for Team {team_id}"
                        )

                    await topomojo.create_dispatch(
                        gamespace_id,
                        cls._settings.game.grading_vm_name,
                        f"touch {cls._settings.game.final_destination_file_path}",
                    )

            new_status = CurrentLocationGameplayDataTeamSpecific(
                currentLocation=location_id,
                currentLocationScanned=location_team_specific.scanned,
                currentLocationSurroundings=location_data.surroundings,
                networkName=location_data.networkName,
                firstContactComplete=location_team_specific.visited,
                powerStatus=team_data.currentStatus.powerStatus,
            )
            team_data.currentStatus = new_status

            cls._mark_task_complete_if_current(team_id, team_data, "jump")

            return GenericResponse(success=True, message=location_id)

    @classmethod
    async def scan(cls, team_id: TeamID) -> ScanResponse:
        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            location_data = cls._cache.location_map.__root__[
                team_data.currentStatus.currentLocation
            ]
            first_contact_event = cls._cache.comm_map.__root__[
                location_data.firstContactEvent
            ]

            cls._mark_task_complete_if_current(team_id, team_data, "scan")

            team_data.currentStatus.incomingTransmission = True
            team_data.currentStatus.incomingTransmissionObject = first_contact_event
            team_data.currentStatus.currentLocationScanned = True

            return ScanResponse(
                success=True,
                message=location_data.locationID,
                eventWaiting=True,
                incomingTransmission=first_contact_event,
            )

    @classmethod
    async def set_power_mode(
        cls, team_id: TeamID, new_mode: PowerMode
    ) -> GenericResponse:
        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            team_data.currentStatus.powerStatus = new_mode

            cls._mark_task_complete_if_current(team_id, team_data, new_mode)

            return GenericResponse(success=True, message=new_mode)

    @classmethod
    async def complete_comm_event(cls, team_id: TeamID) -> GenericResponse:
        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            current_comm_event = team_data.currentStatus.incomingTransmissionObject
            if not current_comm_event:
                return GenericResponse(
                    success=False,
                    message="noIncomingComm",
                )
            associated_global_task = next(
                filter(
                    lambda t: t.commID == current_comm_event.commID,
                    cls._cache.task_map.__root__.values(),
                )
            )

            team_specific_task = None
            for mission in team_data.missions:
                for task in mission.taskList:
                    if task.taskID == associated_global_task.taskID:
                        team_specific_task = task
                        break
                if team_specific_task:
                    break
            else:
                return GenericResponse(success=False, message="noTaskFound")

            if current_comm_event.firstContact:
                team_data.currentStatus.firstContactComplete = True
                for location in team_data.locations:
                    if current_comm_event.locationID == location.locationID:
                        location.visited = True
                        break
                else:
                    return GenericResponse(
                        success=False,
                        message="locationNotUnlocked",
                    )

            team_specific_task.complete = True
            team_data.currentStatus.incomingTransmissionObject = {}
            team_data.currentStatus.incomingTransmission = False

            return GenericResponse(success=True, message="incomingCommComplete")

    @classmethod
    async def check_vm_power_status(cls, vm_id: str) -> PowerStatus | None:
        desc = await topomojo.get_vm_desc(vm_id)
        if not desc or "state" not in desc:
            return

        return PowerStatus(desc["state"])

    @classmethod
    async def change_vm_power_status(cls, vm_id: str, new_setting: PowerStatus):
        # str to shut up linter
        await topomojo.change_vm_power(vm_id, str(new_setting.value))

    @classmethod
    async def codex_power(
        cls, team_id: TeamID, new_setting: PowerStatus
    ) -> GenericResponse:
        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            vm_id = ""
            current_power = await cls.check_vm_power_status(vm_id)
            if current_power == new_setting:
                return GenericResponse(
                    success=False,
                    message=f"codexAlready{new_setting.value.capitalize()}",
                )
            elif current_power is None:
                return GenericResponse(
                    success=False,
                    message=f"TopoMojoAPIFailure",
                )

            await cls.change_vm_power_status(vm_id, new_setting)
            return GenericResponse(success=True, message=f"{vm_id}_{new_setting}")
