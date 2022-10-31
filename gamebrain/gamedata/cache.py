import asyncio
from collections import defaultdict
import json
import logging
from typing import Literal

from pydantic import BaseModel

from ..db import get_team
from .model import (
    GameDataTeamSpecific,
    GameDataResponse,
    InternalCommEvent,
    InternalGlobalTaskData,
    InternalTeamTaskData,
    InternalGlobalLocationData,
    InternalTeamLocationData,
    InternalGlobalMissionData,
    InternalTeamMissionData,
    InternalTeamGameData,
    LocationData,
    LocationDataFull,
    MissionData,
    MissionDataFull,
    TaskCompletionType,
    TaskCompletion,
    TaskData,
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

    def to_internal(
        self, comm_to_task_mapping: dict[CommID, TaskID]
    ) -> "InternalCommMap":
        return InternalCommMap(
            __root__={
                comm_id: InternalCommEvent(
                    **comm_event.dict()
                    | {"associated_task": comm_to_task_mapping.get(comm_id, "")}
                )
                for comm_id, comm_event in self.__root__.items()
            }
        )


class InternalCommMap(BaseModel):
    __root__: dict[CommID, InternalCommEvent]

    def to_snapshot(self) -> CommMap:
        return CommMap(
            __root__={
                comm_id: CommEventData(**comm_event.dict())
                for comm_id, comm_event in self.__root__.items()
            }
        )


class LocationMap(BaseModel):
    __root__: dict[LocationID, LocationData]

    def to_internal(self) -> "InternalLocationMap":
        return InternalLocationMap(
            __root__={
                location_id: InternalGlobalLocationData(**location.dict())
                for location_id, location in self.__root__.items()
            }
        )


class InternalLocationMap(BaseModel):
    __root__: dict[LocationID, InternalGlobalLocationData]

    def to_snapshot(self) -> LocationMap:
        return LocationMap(
            __root__={
                location_id: LocationData(**location.dict())
                for location_id, location in self.__root__.items()
            }
        )


class MissionMap(BaseModel):
    __root__: dict[MissionID, MissionData]

    def to_internal(self) -> "InternalMissionMap":
        translation_map = {}
        for mission_id, mission in self.__root__.items():
            try:
                first_task = next(iter(mission.taskList)).taskID
                last_task = next(iter(mission.taskList[::-1])).taskID
            except StopIteration:
                raise ValueError(f"Mission {mission_id} is missing tasks.")

            translation_map[mission_id] = InternalGlobalMissionData(
                **mission.dict() | {"first_task": first_task, "last_task": last_task}
            )

        return InternalMissionMap(__root__=translation_map)


class InternalMissionMap(BaseModel):
    __root__: dict[MissionID, InternalGlobalMissionData]

    def to_snapshot(self) -> MissionMap:
        return MissionMap(
            __root__={
                mission_id: MissionData(**mission.dict())
                for mission_id, mission in self.__root__.items()
            }
        )


class TaskMap(BaseModel):
    __root__: dict[TaskID, TaskData]

    def to_internal(
        self,
    ) -> "InternalTaskMap":
        return InternalTaskMap(
            __root__={
                task_id: InternalGlobalTaskData(**task.dict())
                for task_id, task in self.__root__.items()
            }
        )


class InternalTaskMap(BaseModel):
    __root__: dict[TaskID, InternalGlobalTaskData]

    def to_snapshot(self) -> TaskMap:
        return TaskMap(
            __root__={
                task_id: TaskData(**task.dict())
                for task_id, task in self.__root__.items()
            }
        )


class TeamMap(BaseModel):
    __root__: dict[TeamID, GameDataTeamSpecific]

    def to_internal(self) -> "InternalTeamMap":
        internal_map = {}
        for team_id, team_data in self.__root__.items():
            internal_map[team_id] = team_data.to_internal()
        return InternalTeamMap(__root__=internal_map)


class InternalTeamMap(BaseModel):
    __root__: dict[TeamID, InternalTeamGameData]

    def to_snapshot(self) -> TeamMap:
        internal_map = {}
        for team_id, team_data in self.__root__.items():
            internal_map[team_id] = team_data.to_snapshot()

        return TeamMap(__root__=internal_map)


class GlobalData(BaseModel):
    comm_map: CommMap
    location_map: LocationMap
    mission_map: MissionMap
    task_map: TaskMap


class GameDataCacheSnapshot(GlobalData):
    team_map: TeamMap
    team_initial_state: GameDataTeamSpecific

    def to_internal(self) -> "InternalCache":
        comm_to_task_mapping = {}
        for task in self.task_map.__root__.values():
            if task.commID:
                comm_to_task_mapping[task.commID] = task.taskID

        return InternalCache(
            comm_map=self.comm_map.to_internal(comm_to_task_mapping),
            location_map=self.location_map.to_internal(),
            mission_map=self.mission_map.to_internal(),
            task_map=self.task_map.to_internal(),
            team_map=self.team_map.to_internal(),
            team_initial_state=self.team_initial_state.to_internal(),
        )


class InternalCache(BaseModel):
    comm_map: InternalCommMap
    location_map: InternalLocationMap
    mission_map: InternalMissionMap
    task_map: InternalTaskMap
    team_map: InternalTeamMap
    team_initial_state: InternalTeamGameData

    def to_snapshot(self) -> GameDataCacheSnapshot:
        return GameDataCacheSnapshot(
            comm_map=self.comm_map.to_snapshot(),
            location_map=self.location_map.to_snapshot(),
            mission_map=self.mission_map.to_snapshot(),
            task_map=self.task_map.to_snapshot(),
            team_map=self.team_map.to_snapshot(),
            team_initial_state=self.team_initial_state.to_snapshot(),
        )


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
    _cache: InternalCache

    _settings: "SettingsModel"

    @staticmethod
    def _log_completion(
        task_id: TaskID,
        team_id: TeamID,
        task_type: TaskCompletionType,
        completion_criteria: TaskCompletion | None,
    ):
        missing_criteria = (
            ", despite the task not having a markCompleteWhen specified"
            if not completion_criteria
            else ""
        )
        message = f"Marking task {task_id} complete for team {team_id}{missing_criteria}. (looking for: {task_type})"
        if completion_criteria:
            logging.info(message)
        else:
            logging.warning(message)

    @staticmethod
    async def _get_vm_id_from_name(team_id: TeamID, vm_name: str) -> GenericResponse:
        team_db_data = await get_team(team_id)
        gamespace_id = team_db_data.get("gamespace_id")

        if not gamespace_id:
            message = f"No Gamespace for Team {team_id}"
            logging.error(message)
            return GenericResponse(success=False, message=message)

        vms = await topomojo.get_vms_by_gamespace_id(gamespace_id)
        if not vms:
            message = f"No VMs registered for Gamespace {gamespace_id}"
            logging.error(message)
            return GenericResponse(
                success=False,
                message=message,
            )

        for vm in vms:
            try:
                name, *gs_id = vm["name"].split("#")
            except Exception as e:
                logging.info(f"{vms}")
                logging.exception(
                    f"Exception when attempting to split a VM named {vm} in extend_antenna: {e}"
                )
                continue
            if name == vm_name:
                vm_id = vm["id"]
                return GenericResponse(success=True, message=vm_id)
        else:
            message = f"Antenna VM not found in Gamespace {gamespace_id}"
            logging.error(message)
            return GenericResponse(
                success=False,
                message=message,
            )

    @classmethod
    def _set_task_comm_event_active(
        cls, team_id: TeamID, team_data: InternalTeamGameData, task_id: TaskID
    ):
        """
        cache lock is assumed to be held
        """
        global_task = cls._cache.task_map.__root__.get(task_id)
        if not global_task:
            logging.error(
                f"Team {team_id} had a task in its team-specific data that "
                f"was not in the global data: {task_id}"
            )
            return
        comm_event = cls._cache.comm_map.__root__.get(global_task.commID)
        if global_task.commID != "" and not comm_event:
            logging.error(
                f"Team {team_id} had a comm event in its team-specific data that "
                f"was not in the global data: {global_task.commID}"
            )
            return
        team_data.currentStatus.incomingTransmission = bool(comm_event)
        team_data.currentStatus.incomingTransmissionObject = (
            {} if not comm_event else comm_event.to_snapshot()
        )

    @classmethod
    def _unlock_tasks_until_completion_criteria(
        cls,
        team_id: TeamID,
        team_data: InternalTeamGameData,
        global_task: InternalGlobalTaskData,
    ):
        if not team_data.tasks.get(global_task.taskID):
            # If the new task was already unlocked, don't reset its status.
            team_data.tasks[global_task.taskID] = InternalTeamTaskData(
                taskID=global_task.taskID, visible=True, complete=False
            )
            team_data.missions[global_task.missionID].tasks.append(global_task.taskID)
            logging.info(f"Team {team_id} unlocked task {global_task.taskID}.")
            if not team_data.currentStatus.incomingTransmission:
                cls._set_task_comm_event_active(team_id, team_data, global_task.taskID)
        if global_task.markCompleteWhen:
            # Keep unlocking tasks if the one we just unlocked doesn't have specified criteria.
            # Otherwise, we're done.
            return
        next_global_task = cls._cache.task_map.__root__.get(global_task.next)
        if not next_global_task:
            logging.error(
                f"Task {global_task.taskID} indicated its next task was {global_task.next}, but that task "
                "doesn't exist in the global data."
            )
            return
        cls._unlock_tasks_until_completion_criteria(
            team_id, team_data, next_global_task
        )

    @classmethod
    def _complete_task_and_unlock_next(
        cls,
        team_id: TeamID,
        team_data: InternalTeamGameData,
        global_task: InternalGlobalTaskData,
    ) -> bool:
        """
        Returns True if a task was completed.
        """
        team_task = team_data.tasks.get(global_task.taskID)
        if not team_task:
            logging.info(
                f"Team {team_id} tried to complete task {global_task.taskID}, but the team has not "
                "unlocked it yet."
            )
            return False

        completion_criteria = global_task.markCompleteWhen

        if (
            completion_criteria.locationID
            and completion_criteria.locationID
            != team_data.currentStatus.currentLocation
            and completion_criteria.type not in ("codex", "challenge")
        ):
            return False

        team_task.complete = True
        if completion_criteria.alsoComplete:
            for also_complete_task_id in global_task.markCompleteWhen.alsoComplete:
                also_complete_task = team_data.tasks.get(also_complete_task_id)
                if not also_complete_task:
                    logging.warning(
                        f"Task {global_task.taskID} had dependent task {also_complete_task_id} specified, "
                        "but it was not unlocked."
                    )
                also_complete_task.complete = True
        if global_task.next:
            next_global_task = cls._cache.task_map.__root__.get(global_task.next)
            if not next_global_task:
                logging.error(
                    f"Task {global_task.taskID} indicated its next task was {global_task.next}, but that task "
                    "doesn't exist in the global data."
                )
                return True
            cls._unlock_tasks_until_completion_criteria(
                team_id, team_data, next_global_task
            )
        else:
            mission = team_data.missions.get(global_task.missionID)
            if not mission:
                logging.error(
                    f"Team {team_id} completed task {global_task.taskID} which specified mission ID "
                    f"{global_task.missionID}, which they have not unlocked."
                )
                return True
            mission.complete = True
            logging.info(
                f"Marked mission {mission.missionID} complete for team {team_id}."
            )
        return True

    @classmethod
    def _mark_task_complete_if_unlocked(
        cls,
        team_id: TeamID,
        team_data: InternalTeamGameData,
        task_type: TaskCompletionType,
        location: LocationID = None,
    ):
        """
        cache lock is assumed to be held
        """
        active_comm_event = team_data.currentStatus.incomingTransmissionObject

        for mission in team_data.missions.values():
            global_mission = cls._cache.mission_map.__root__.get(mission.missionID)
            if not global_mission:
                logging.error(
                    f"Team {team_id} had mission {mission.missionID} unlocked "
                    "but it was not in the global data."
                )
            for task_id in map(lambda t: t.taskID, global_mission.taskList):
                team_task = team_data.tasks.get(task_id)
                if not team_task:
                    continue
                global_task = cls._cache.task_map.__root__.get(task_id)
                if not global_task:
                    logging.error(
                        f"Mission {mission.missionID} had a task in its "
                        "task list that was not in the global task map: {task}."
                    )
                    continue
                # if active_comm_event and active_comm_event.commID == global_task.commID:
                #     logging.info(
                #         f"Attempted to mark task {global_task.taskID} complete for team {team_id}, "
                #         f"but they must complete comm event {active_comm_event.commID} first."
                #     )
                #     continue
                completion_criteria = global_task.markCompleteWhen
                if not completion_criteria:
                    continue
                if location and completion_criteria.locationID != location:
                    # The specified location was for a different task - primarily for codex use.
                    continue
                if task_type != completion_criteria.type:
                    continue
                if (
                    completion_criteria.locationID
                    != team_data.currentStatus.currentLocation
                ):
                    continue

                if cls._complete_task_and_unlock_next(team_id, team_data, global_task):
                    return

    @classmethod
    def _basic_validation(cls, initial_state: GameDataCacheSnapshot):
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
            return cls._cache.to_snapshot().json()

    @classmethod
    async def init(
        cls, initial_state: GameDataCacheSnapshot, settings: "SettingsModel"
    ):
        async with cls._lock:
            cls._basic_validation(initial_state)
            cls._cache = initial_state.to_internal()
            cls._settings = settings

    @classmethod
    async def new_team(cls, team_id: TeamID):
        async with cls._lock:
            new_team_state = InternalTeamGameData(
                **cls._cache.team_initial_state.dict()
            )
            new_team_state.session.teamInfoName = team_id
            cls._cache.team_map.__root__[team_id] = new_team_state

    @classmethod
    async def check_team_exists(cls, team_id: TeamID) -> bool:
        async with cls._lock:
            return team_id in cls._cache.team_map.__root__

    @classmethod
    async def get_team_codex_status(cls, team_id: TeamID) -> dict[MissionID, bool]:
        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            mission_status = {}
            for global_mission in cls._cache.mission_map.__root__.values():
                team_mission = team_data.missions.get(global_mission.missionID)
                if not team_mission:
                    mission_status[global_mission.missionID] = False
                    continue
                mission_status[global_mission.missionID] = team_mission.complete

            return mission_status

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
            for location_id, location in team_data.locations.items():
                loc_global = cls._cache.location_map.__root__[location_id]
                loc_full = LocationDataFull(**loc_global.dict() | location.dict())
                full_loc_data.append(loc_full)

            full_mission_data = []
            for mission in team_data.missions.values():
                mission_global = cls._cache.mission_map.__root__[mission.missionID]
                task_list = []
                for task_id in mission.tasks:
                    team_task = team_data.tasks.get(task_id)
                    if not team_task:
                        logging.error(
                            f"Team {team_id} had a mission identify a task {task_id}, but the task was not "
                            "in the team's task map."
                        )
                        continue
                    global_task = cls._cache.task_map.__root__.get(task_id)
                    if not global_task:
                        logging.error(
                            f"Team {team_id} had a mission identify a task {task_id}, but the task was not "
                            "in the global task map."
                        )
                        continue
                    task_list.append(
                        TaskDataFull(**global_task.dict() | team_task.dict())
                    )
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
    async def dispatch_challenge_task_complete(cls, team_id: TeamID, task_id: str):
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
                    f"Dispatch task reported task {task_id} complete for team {team_id}, but no such task exists."
                )
                return

            if not (
                global_task_data.markCompleteWhen
                and global_task_data.markCompleteWhen.locationID
            ):
                logging.error(
                    f"Task {task_id} either doesn't have a markCompleteWhen block or "
                    "is missing a locationID in the markCompleteWhen block."
                )
                return

            cls._complete_task_and_unlock_next(team_id, team_data, global_task_data)

    @classmethod
    async def dispatch_grading_task_update(
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
            task_mapping = {
                "exoarch9": gamespace_state_output.exoArch,
                "redradr10": gamespace_state_output.redRaider,
                "antruins7": gamespace_state_output.ancientRuins,
                "cllctn11": gamespace_state_output.museum,
                "fllwrs12": gamespace_state_output.xenoCult,
            }

            for task_id, status in task_mapping.items():
                if status == "success":
                    logging.info(
                        f"Grading dispatch for team {team_id} "
                        f"indicates codex completion for task {task_id}"
                    )
                    global_task_data = cls._cache.task_map.__root__.get(task_id)
                    if not global_task_data:
                        logging.error(
                            f"Dispatch for team {team_id} indicated completion for {task_id}, "
                            "but the task doesn't exist."
                        )
                        continue
                    cls._complete_task_and_unlock_next(
                        team_id, team_data, global_task_data
                    )

            transform_map = {"up": PowerStatus.on, "down": PowerStatus.off}

            team_data.ship.commPower = transform_map.get(
                gamespace_state_output.comms, PowerStatus.off
            )
            team_data.ship.flightPower = transform_map.get(
                gamespace_state_output.flight, PowerStatus.off
            )
            team_data.ship.navPower = transform_map.get(
                gamespace_state_output.nav, PowerStatus.off
            )
            team_data.ship.pilotPower = transform_map.get(
                gamespace_state_output.pilot, PowerStatus.off
            )

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

            vm_id_response = await cls._get_vm_id_from_name(
                team_id, cls._settings.game.antenna_vm_name
            )
            if not vm_id_response.success:
                return vm_id_response
            vm_id = vm_id_response.message

            location_data = cls._cache.location_map.__root__[
                team_data.currentStatus.currentLocation
            ]
            new_net = location_data.networkName

            await topomojo.change_vm_net(vm_id, new_net)

            team_data.currentStatus.antennaExtended = True
            team_data.currentStatus.networkConnected = True
            team_data.currentStatus.networkName = new_net

            cls._mark_task_complete_if_unlocked(team_id, team_data, "antennaExtended")

            return GenericResponse(
                success=True, message=f"Team {team_id} extended their antenna."
            )

    @classmethod
    async def retract_antenna(cls, team_id: TeamID) -> GenericResponse:
        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            vm_id_response = await cls._get_vm_id_from_name(
                team_id, cls._settings.game.antenna_vm_name
            )
            if not vm_id_response.success:
                return vm_id_response
            vm_id = vm_id_response.message

            await topomojo.change_vm_net(
                vm_id, cls._settings.game.antenna_retracted_network
            )

            team_data.currentStatus.antennaExtended = False
            team_data.currentStatus.networkConnected = False
            team_data.currentStatus.networkName = (
                cls._settings.game.antenna_retracted_network
            )

            cls._mark_task_complete_if_unlocked(team_id, team_data, "antennaRetracted")

            return GenericResponse(
                success=True, message=f"Team {team_id} retracted their antenna."
            )

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

            code_match = list(
                filter(
                    lambda loc: loc.unlockCode == unlock_code,
                    cls._cache.location_map.__root__.values(),
                )
            )
            if not code_match:
                return response("invalid")

            if len(code_match) > 1:
                logging.warning(
                    f"Team {team_id} used unlock code {unlock_code}, "
                    f"which matched multiple locations: {json.dumps(code_match, indent=2)}"
                )

            location = code_match.pop()
            location_id = location.locationID
            if location_id in team_data.locations:
                return response("alreadyunlocked")

            team_data.locations[location_id] = InternalTeamLocationData(
                locationID=location_id
            )

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

            # Construct all the team task data objects first...
            mission_tasks = defaultdict(list)
            for task_id in unlocked_task_ids:
                global_task_data = cls._cache.task_map.__root__.get(task_id)
                if not global_task_data:
                    logging.error(
                        f"Team {team_id} somehow unlocked task {task_id}, which was not in the global data."
                    )
                    continue
                mission_tasks[global_task_data.missionID].append(
                    InternalTeamTaskData(taskID=task_id)
                )

            # Then use the task data objects to construct the team mission objects
            team_specific_missions = [
                InternalTeamMissionData(
                    missionID=mission_id,
                    taskList=mission_tasks[mission_id],
                    tasks=list(map(lambda t: t.taskID, mission_tasks[mission_id])),
                )
                for mission_id in unlocked_mission_ids
            ]

            for mission in team_specific_missions:
                mission_id = mission.missionID
                if mission_id in team_data.missions:
                    logging.warning(
                        f"Attempted to unlock mission {mission_id} for team {team_id}, "
                        "but it was already unlocked."
                    )
                    continue
                team_data.missions[mission_id] = mission

            return response("success", location_id)

    @classmethod
    async def jump(cls, team_id: TeamID, location_id: LocationID) -> GenericResponse:
        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            if team_data.currentStatus.currentLocation == location_id:
                logging.info(
                    f"Team {team_id} tried to jump to {location_id}, but they were already at the location."
                )
                return GenericResponse(
                    success=False, message=f"Already at {location_id}."
                )

            global_location = cls._cache.location_map.__root__.get(location_id)
            if not global_location:
                logging.error(
                    f"Team {team_id} tried to jump to {location_id}, it was not a known location ID."
                )
                return GenericResponse(
                    success=False,
                    message=f"Unable to find {location_id} in global cache.",
                )

            team_location = team_data.locations.get(location_id)
            if not team_location:
                logging.info(
                    f"Team {team_id} tried to jump to {location_id}, but it was not unlocked."
                )
                return GenericResponse(
                    success=False,
                    message=f"Location {location_id} is not yet unlocked.",
                )

            if location_id == cls._settings.game.final_destination_name:
                if team_data.session.teamCodexCount < 3:
                    logging.info(
                        f"Team {team_id} tried to unlock the final destination, "
                        "but they do not have enough codices unlocked."
                    )
                    return GenericResponse(
                        success=False, message="Not enough codices unlocked."
                    )
                else:
                    team_db_data = await get_team(team_id)
                    gamespace_id = team_db_data.get("gamespace_id")

                    if not gamespace_id:
                        logging.error(
                            f"Team {team_id} tried to unlock the final destination, "
                            "but they do not appear to have a gamespace."
                        )
                        return GenericResponse(
                            success=False, message=f"No Gamespace for Team {team_id}"
                        )

                    await topomojo.create_dispatch(
                        gamespace_id,
                        cls._settings.game.grading_vm_name,
                        f"touch {cls._settings.game.final_destination_file_path}",
                    )
                    logging.info(
                        f"Created final destination dispatch for team {team_id}."
                    )

            new_status = CurrentLocationGameplayDataTeamSpecific(
                currentLocation=location_id,
                currentLocationScanned=team_location.scanned,
                currentLocationSurroundings=global_location.surroundings,
                networkName=global_location.networkName,
                firstContactComplete=team_location.visited,
                powerStatus=team_data.currentStatus.powerStatus,
            )
            team_data.currentStatus = new_status

            cls._mark_task_complete_if_unlocked(team_id, team_data, "jump")

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

            team_location_data = team_data.locations.get(location_data.locationID)
            if not team_location_data:
                logging.error(
                    f"Team had current location {team_data.currentStatus.currentLocation}, "
                    "but the location was not unlocked."
                )
                return ScanResponse(
                    success=False,
                    message=location_data.locationID,
                    eventWaiting=False,
                    incomingTransmission={},
                )

            first_contact_event = cls._cache.comm_map.__root__.get(
                location_data.firstContactEvent
            )
            if first_contact_event and not team_location_data.visited:
                team_data.currentStatus.incomingTransmission = True
                team_data.currentStatus.incomingTransmissionObject = (
                    first_contact_event.to_snapshot()
                )
                team_data.currentStatus.currentLocationScanned = True
            else:
                first_contact_event = {}

            cls._mark_task_complete_if_unlocked(team_id, team_data, "scan")

            return ScanResponse(
                success=True,
                message=location_data.locationID,
                eventWaiting=team_data.currentStatus.incomingTransmission,
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

            cls._mark_task_complete_if_unlocked(team_id, team_data, new_mode)

            return GenericResponse(success=True, message=new_mode)

    @classmethod
    async def complete_comm_event(cls, team_id: TeamID) -> GenericResponse:
        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            current_comm_event = team_data.currentStatus.incomingTransmissionObject
            if not current_comm_event:
                logging.warning(
                    f"Team {team_id} tried to complete a comm event, "
                    "but they do not currently have a comm event."
                )
                return GenericResponse(
                    success=False,
                    message="No incoming comm event.",
                )

            internal_comm_event = cls._cache.comm_map.__root__[
                current_comm_event.commID
            ]
            global_task = cls._cache.task_map.__root__.get(
                internal_comm_event.associated_task
            )
            if not global_task:
                logging.error(
                    f"Team {team_id} tried to complete comm event {internal_comm_event.commID}, "
                    "but there was no associated task."
                )
                return GenericResponse(
                    success=False,
                    message="Could not find associated task.",
                )

            team_task = team_data.tasks.get(global_task.taskID)
            if not team_task:
                logging.error(
                    f"Team {team_id} tried to complete comm event {internal_comm_event.commID}, "
                    "but the associated task was not unlocked."
                )
                return GenericResponse(
                    success=False,
                    message="Associated task not unlocked.",
                )

            if current_comm_event.firstContact:
                current_location_id = team_data.currentStatus.currentLocation
                team_comm_location_id = current_comm_event.locationID
                if current_location_id != team_comm_location_id:
                    logging.error(
                        f"Team {team_id} tried to complete comm event {internal_comm_event.commID}, "
                        "but they were not at the right location."
                    )
                    return GenericResponse(
                        success=False,
                        message="Wrong location.",
                    )

                team_comm_location = team_data.locations.get(team_comm_location_id)
                if not team_comm_location:
                    logging.error(
                        f"Team {team_id} tried to complete comm event {internal_comm_event.commID}, "
                        "but they have not unlocked the location yet."
                    )
                    return GenericResponse(
                        success=False,
                        message="Location not unlocked.",
                    )

                team_data.currentStatus.firstContactComplete = True
                team_comm_location.visited = True

            team_data.currentStatus.incomingTransmissionObject = {}
            team_data.currentStatus.incomingTransmission = False

            cls._mark_task_complete_if_unlocked(team_id, team_data, "comm")

            logging.info(
                f"Team {team_id} completed comm event {current_comm_event.commID}."
            )
            return GenericResponse(
                success=True, message="Incoming comm event completed."
            )

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
