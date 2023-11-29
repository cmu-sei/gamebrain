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

import asyncio
from enum import Enum
from collections import defaultdict
from dataclasses import dataclass
import datetime
from datetime import timezone
import json
import logging
from typing import Literal

from httpx import AsyncClient
from pydantic import BaseModel

from ..admin.controllermodels import DeploymentSession
from ..db import get_team, get_active_teams, get_team_game_session
from ..clients.gameboardmodels import (
    GameEngineQuestionView,
    TeamGameScoreQueryResponse,
    GameEngineGameState
)
from .model import (
    AssociatedChallengeData,
    ChallengeURLs,
    DispatchID,
    Dispatch,
    NPCShipData,
    GameDataTeamSpecific,
    GameDataResponse,
    GamespaceData,
    TeamGamespaceInfo,
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
    MissionScoreData,
    TaskBranchType,
    TaskBranch,
    TaskData,
    TaskDataFull,
    CommEventData,
    PowerMode,
    PowerStatus,
    CurrentLocationGameplayDataTeamSpecific,
    LocationUnlockResponse,
    GenericResponse,
    ScanResponse,
    VmURL,
)
from ..clients import gameboard, topomojo

CommID = str
LocationID = str
MissionID = str
TaskID = str
TeamID = str
NPCShipID = str
GamespaceID = str

JsonStr = str

VmName = str
VmUrlStr = str

NPCShipMap = dict[NPCShipID, NPCShipData]
ChallengeMap = dict[MissionID, GamespaceData]

JUMP_TIME_DELTA = datetime.timedelta(minutes=10)
SPAM_REDUCTION_FACTOR = 20
EXPECTED_TEAM_COUNT = 5


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
    npc_ships: NPCShipMap = {}
    challenges: dict[TeamID, ChallengeMap] = {}
    gamespace_to_mission: dict[GamespaceID, MissionID] = {}


class GameDataCacheSnapshot(GlobalData):
    team_map: TeamMap
    team_initial_state: GameDataTeamSpecific
    jump_cycle_number: int = 0

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
            npc_ships=self.npc_ships,
            jump_cycle_number=self.jump_cycle_number,
            challenges=self.challenges,
            gamespace_to_mission=self.gamespace_to_mission,
        )


class InternalCache(BaseModel):
    comm_map: InternalCommMap
    location_map: InternalLocationMap
    mission_map: InternalMissionMap
    task_map: InternalTaskMap
    team_map: InternalTeamMap
    team_initial_state: InternalTeamGameData
    npc_ships: NPCShipMap
    jump_cycle_number: int = 0
    challenges: dict[TeamID, ChallengeMap] = {}
    gamespace_to_mission: dict[GamespaceID, MissionID] = {}

    def to_snapshot(self) -> GameDataCacheSnapshot:
        return GameDataCacheSnapshot(
            comm_map=self.comm_map.to_snapshot(),
            location_map=self.location_map.to_snapshot(),
            mission_map=self.mission_map.to_snapshot(),
            task_map=self.task_map.to_snapshot(),
            team_map=self.team_map.to_snapshot(),
            team_initial_state=self.team_initial_state.to_snapshot(),
            npc_ships=self.npc_ships,
            jump_cycle_number=self.jump_cycle_number,
            challenges=self.challenges,
            gamespace_to_mission=self.gamespace_to_mission,
        )


# I wasn't sure if the output models should really be here,
# but there wasn't really any other obvious place to put them.
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
    _active_game_timer_task: asyncio.Task = None
    _active_dispatch_timer_task: asyncio.Task = None
    _active_mission_timer_task: asyncio.Task = None

    _next_npc_ship_jump: datetime.datetime = None
    _next_video_refresh: datetime.datetime = None

    _spam_reduction_tracker: int = 0

    @staticmethod
    def _log_completion(
        task_id: TaskID,
        team_id: TeamID,
        task_type: TaskBranchType,
        completion_criteria: TaskBranch | None,
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
    async def _get_vm_id_from_name_for_gamespace(
        gamespace_id: GamespaceID, vm_name: str
    ) -> GenericResponse:
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
                    "_get_vm_id_from_name_for_gamespace: "
                    f"Exception when attempting to split a VM named {vm}: {e}"
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

    @staticmethod
    async def _get_vm_id_from_name_for_team(
        team_id: TeamID, team_data: InternalTeamGameData, vm_name: str
    ) -> GenericResponse:
        gamespace_id = team_data.ship.gamespaceData.gamespaceID

        if not gamespace_id:
            message = f"No Ship Gamespace for Team {team_id}"
            logging.error(message)
            return GenericResponse(success=False, message=message)

        return await GameStateManager._get_vm_id_from_name_for_gamespace(
            gamespace_id, vm_name
        )

    @classmethod
    async def video_freshness_task(cls):
        video_urls = []
        async with cls._lock:
            for comm_event in cls._cache.comm_map.__root__.values():
                video_urls.append(comm_event.videoURL)

            next_refresh = cls._next_video_refresh

        now = datetime.datetime.now(timezone.utc)
        if next_refresh <= now:
            logging.info("Starting Video URL refresh...")

            async with cls._lock:
                cls._next_video_refresh = now + datetime.timedelta(days=7)
                logging.info(f"Next refresh set to {cls._next_video_refresh}")

            async with AsyncClient() as client:
                # Technically should be a task group or something, but
                # it's not important.
                for url in video_urls:
                    async with client.stream("GET", url) as response:
                        async for chunk in response.aiter_raw():
                            # I don't care what is actually being sent,
                            # just as long as the video downloads.
                            ...
                        if response.is_success:
                            logging.info(f"Refreshed URL {url} successfully.")
                        else:
                            logging.error(
                                f"HTTP Request to {response.url} returned {response.status_code}\n")
        else:
            logging.info("Skipping Video URL refresh...")

    @classmethod
    def _set_task_comm_event_active(
        cls,
        team_id: TeamID,
        team_data: InternalTeamGameData,
        global_task: InternalGlobalTaskData,
    ):
        """
        cache lock is assumed to be held
        """
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
        if team_data.currentStatus.incomingTransmission:
            logging.info(
                f"Set comm event {global_task.commID} for team {team_id}.")
        else:
            logging.info(f"Did not set comm event for team {team_id}.")

    @classmethod
    def _unlock_specific_task(
        cls,
        team_id: TeamID,
        team_data: InternalTeamGameData,
        global_task: InternalGlobalTaskData,
    ):
        team_task = team_data.tasks.get(global_task.taskID)
        if not team_task:
            # If the new task was already unlocked, don't reset its status.
            team_task = InternalTeamTaskData(
                taskID=global_task.taskID, visible=True, complete=False
            )
            team_data.tasks[global_task.taskID] = team_task
            team_data.missions[global_task.missionID].tasks.append(
                global_task.taskID)
            logging.info(f"Team {team_id} unlocked task {global_task.taskID}.")
            cls._find_comm_event_to_activate(team_id, team_data)
        else:
            team_task.visible = True

    @classmethod
    def _unlock_tasks_until_completion_criteria(
        cls,
        team_id: TeamID,
        team_data: InternalTeamGameData,
        global_task: InternalGlobalTaskData,
    ):
        cls._unlock_specific_task(team_id, team_data, global_task)
        if (
            global_task.markCompleteWhen
            and global_task.markCompleteWhen.type != "indirect"
        ):
            # Keep unlocking tasks if the one we just unlocked doesn't have specified criteria.
            # Otherwise, we're done.
            return
        next_global_task = cls._cache.task_map.__root__.get(global_task.next)
        if not next_global_task:
            logging.warning(
                f"Task {global_task.taskID} indicated its next task was "
                f"{global_task.next}, but that task "
                "doesn't exist in the global data. This is no problem "
                "if this task is intended to be the last task in a chain."
            )
            return
        cls._unlock_tasks_until_completion_criteria(
            team_id, team_data, next_global_task
        )

    @classmethod
    def _complete_indirect_task(
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

        if (
            global_task.markCompleteWhen
            and global_task.markCompleteWhen.type == "indirect"
        ):
            for task_id in global_task.markCompleteWhen.indirectPrerequisiteTasks:
                prereq_team_task = team_data.tasks.get(task_id)
                not_unlocked = False
                not_completed = False
                if not prereq_team_task:
                    not_unlocked = True
                if prereq_team_task and not prereq_team_task.complete:
                    not_completed = True
                if not_unlocked or not_completed:
                    reason = "unlocked" if not_unlocked else "completed"
                    logging.info(
                        f"Team {team_id} tried to complete task {global_task.taskID}, but the team has not "
                        f"{reason} its prerequisite task {task_id} yet."
                    )
                    return False

        team_task.complete = True
        return True

    @classmethod
    def _handle_mission_unlock(
        cls,
        team_id: TeamID,
        team_data: InternalTeamGameData,
        global_mission: InternalGlobalMissionData,
    ):
        first_task = cls._cache.task_map.__root__.get(
            global_mission.first_task)

        if not first_task:
            logging.error(
                f"Mission {global_mission.missionID} "
                f"indicated its first task is {global_mission.first_task} "
                "which does not exist in the game data."
            )
            return

        cls._unlock_tasks_until_completion_criteria(
            team_id, team_data, first_task)

        mission_task_ids = list(
            map(
                lambda t: t.taskID,
                filter(
                    lambda t: t.missionID == global_mission.missionID,
                    cls._cache.task_map.__root__.values(),
                ),
            )
        )
        task_list = [
            InternalTeamTaskData(taskID=task_id)
            for task_id in mission_task_ids
        ]

        if team_mission := team_data.missions.get(global_mission.missionID):
            logging.info(
                f"Team mission data found for team {team_id}. "
                f"Marking mission {global_mission.missionID} unlocked."
            )
            team_mission.unlocked = True
            if len(team_mission.taskList) < len(task_list):
                # If the team mission data came from team_initial_state, it
                # may not have all the task it should have. Otherwise leave
                # it alone.
                team_mission.taskList = task_list
        else:
            logging.info(
                f"Team mission data not found for team {team_id}. "
                "Constructing internal data and then "
                f"marking mission {global_mission.missionID} unlocked."
            )
            unlocked_mission = InternalTeamMissionData(
                missionID=global_mission.missionID,
                taskList=task_list,
                tasks=mission_task_ids,
            )
            team_data.missions[global_mission.missionID] = unlocked_mission

    @classmethod
    def _get_mission_completion_in_team_session(
        cls,
        team_id: TeamID,
        global_mission: InternalGlobalMissionData,
    ) -> int:
        session = await get_team_game_session(team_id)
        if not session:
            logging.error(
                "_get_mission_completion_in_team_session: "
                f"Team {team_id} is not associated with any session."
            )
        session_teams = [team["id"] for team in session["teams"]]
        total_completions = 0

        for team_id in session_teams:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                logging.error(
                    "_get_mission_completion_in_team_session: "
                    f"Session {session['id']} had a team {team_id} that is "
                    "not being tracked in GameStateManager."
                )
                continue

            team_mission = team_data.missions.get(global_mission.missionID)
            if not team_mission:
                # This team has not even unlocked the mission, so move on.
                continue
            total_completions += int(team_mission.complete)

        return total_completions

    @classmethod
    def _complete_mission_and_unlock_next(
        cls,
        team_id: TeamID,
        team_data: InternalTeamGameData,
        team_mission: InternalTeamMissionData,
        global_mission: InternalGlobalMissionData,
    ):
        logging.info(
            f"Marking mission {team_mission.missionID} complete for team {team_id}."
        )
        team_mission.complete = True
        team_data.session.teamCodexCount = sum((
            1 if team_mission.complete and not global_mission.isSpecial else 0
            for team_mission in team_data.missions.values()
        ))

        if not global_mission.firstNthCompletionUnlocks:
            logging.warning(
                f"Mission {team_mission.missionID} does not unlock any "
                "additional missions. No problem if this is intentional."
            )
            return

        times_completed = cls._get_mission_completion_in_team_session(
            team_id, global_mission
        )

        idx = (
            times_completed
            if (times_completed < len(global_mission.firstNthCompletionUnlocks))
            else -1
        )
        new_missions = global_mission.firstNthCompletionUnlocks[idx]

        for mission_id in new_missions:
            unlocked_global_mission = cls._cache.mission_map.__root__.get(
                mission_id)
            if not unlocked_global_mission:
                logging.error(
                    f"Mission {global_mission.missionID} indicates "
                    f"mission {mission_id} should be unlocked, but "
                    "there is no such mission."
                )
                continue

            cls._handle_mission_unlock(
                team_id, team_data, unlocked_global_mission)

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

        team_task.complete = True
        if completion_criteria:
            if completion_criteria.alsoComplete:
                for also_complete_task_id in global_task.markCompleteWhen.alsoComplete:
                    also_complete_global_task = cls._cache.task_map.__root__.get(
                        also_complete_task_id
                    )
                    if not also_complete_global_task:
                        logging.error(
                            f"Task {global_task.taskID} had dependent task {also_complete_task_id} specified, "
                            "but it was not in the global task map."
                        )
                        continue
                    cls._complete_indirect_task(
                        team_id, team_data, also_complete_global_task
                    )
            if completion_criteria.unlockLocation:
                cls._unlock_location_for_team(
                    team_id, team_data, completion_criteria.unlockLocation
                )
        if global_task.next:
            next_global_task = cls._cache.task_map.__root__.get(
                global_task.next)
            if not next_global_task:
                logging.error(
                    f"Task {global_task.taskID} indicated its next task was {global_task.next}, but that task "
                    "doesn't exist in the global data."
                )
                return True
            cls._unlock_tasks_until_completion_criteria(
                team_id, team_data, next_global_task
            )
        if not global_task.next or global_task.completesMission:
            mission = team_data.missions.get(global_task.missionID)
            if not mission:
                logging.error(
                    f"Team {team_id} completed task {global_task.taskID} which specified mission ID "
                    f"{global_task.missionID}, which they have not unlocked."
                )
                return True
            global_mission = cls._cache.mission_map.__root__.get(
                mission.missionID)
            if not global_mission:
                logging.error(
                    f"Team {team_id} had unlocked a mission with ID {mission.missionID}, but it does not "
                    "exist in the global data."
                )
            else:
                cls._complete_mission_and_unlock_next(
                    team_id, team_data, mission, global_mission)

            logging.info(
                f"Marked mission {mission.missionID} complete for team {team_id}."
            )
        return True

    @classmethod
    def _mark_task_complete_if_unlocked(
        cls,
        team_id: TeamID,
        team_data: InternalTeamGameData,
        task_type: TaskBranchType,
    ):
        """
        cache lock is assumed to be held
        """
        # Make a separate list so I can modify the team task map (for unlocking).
        for task in list(team_data.tasks.values()):
            if task.complete:
                continue
            global_task = cls._cache.task_map.__root__.get(task.taskID)
            if not global_task:
                logging.error(
                    f"Team {team_id} had a task in its "
                    "task list that was not in the global task map: {task}."
                )
                continue

            # TODO: Eventually this should have a big refactor, but for now it just needs to work.
            current_location = team_data.currentStatus.currentLocation
            if (
                global_task.markCompleteWhen
                and global_task.markCompleteWhen.locationID == current_location
                and global_task.markCompleteWhen.type == task_type
            ):
                if not (
                    global_task.markCompleteWhen.type != "comm"
                    or (
                        global_task.markCompleteWhen.type == "comm"
                        and global_task.commID
                        == team_data.currentStatus.incomingTransmissionObject.commID
                    )
                ):
                    continue
                cls._complete_task_and_unlock_next(
                    team_id, team_data, global_task)
            elif (
                global_task.cancelWhen
                and global_task.cancelWhen.locationID == current_location
                and global_task.cancelWhen.type == task_type
            ):
                if not (
                    global_task.cancelWhen.type != "comm"
                    or (
                        global_task.cancelWhen.type == "comm"
                        and global_task.commID
                        == team_data.currentStatus.incomingTransmissionObject.commID
                    )
                ):
                    continue
                team_mission = team_data.missions.get(global_task.missionID)
                if not team_mission:
                    logging.error(
                        f"Team had task {task.taskID} unlocked but not its associated mission."
                    )
                try:
                    team_mission.tasks.remove(task.taskID)
                except ValueError:
                    logging.error(
                        f"Tried to remove {task.taskID} from mission {team_mission.missionID} for team "
                        f"{team_id}, but failed."
                    )
                else:
                    team_data.tasks.pop(task.taskID)
            elif (
                global_task.failWhen
                and global_task.failWhen.locationID == current_location
                and global_task.failWhen.type == task_type
            ):
                next_global_task = cls._cache.task_map.__root__.get(
                    global_task.failWhen.unlocks
                )
                if not next_global_task:
                    logging.error(
                        f"Task {task.taskID} referenced task {global_task.failWhen.unlocks} in its failWhen block, "
                        "but that task does not exist."
                    )
                    continue
                cls._unlock_specific_task(team_id, team_data, next_global_task)

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

    # @classmethod
    # async def _npc_jump_net_change(cls, ship_id: NPCShipID, destination: LocationID):
    #     challenge_data_teams = cls._cache.challenges.get(ship_id)
    #     if not challenge_data_teams:
    #         logging.error(
    #             "Uncontested NPC ship jump attempted with invalid ship ID "
    #             f"{ship_id}."
    #         )
    #         return
    #
    #     for team_id, challenge_data in challenge_data_teams.items():
    #         response = await cls._get_vm_id_from_name_for_gamespace(
    #             challenge_data.gamespaceID, challenge_data.gatewayVmName
    #         )
    #
    #         if response.success is False:
    #             logging.error(
    #                 f"Uncontested NPC jump for ship {ship_id} failed "
    #                 f"with reason {response.message}."
    #             )
    #             continue
    #         location_data = cls._cache.location_map.__root__[destination]
    #         location_net = location_data.networkName
    #         new_net = f"{location_net}:{challenge_data.gatewayNic}"
    #
    #         vm_id = response.message
    #
    #         await topomojo.change_vm_net(vm_id, new_net)

    # @classmethod
    # async def _npc_jump(cls, ship_id: NPCShipID, destination: LocationID):
    #     challenge_list = list(
    #         map(
    #             lambda t: ship_id in cls._cache.challenges[t],
    #             cls._cache.challenges.keys(),
    #         )
    #     )
    #     if all(challenge_list):
    #         await cls._npc_jump_net_change(ship_id, destination)
    #     elif any(challenge_list):
    #         logging.error(
    #             f"NPC Ship {ship_id} attempted to jump, but at least one team "
    #             "does not have this ship in its list of challenges."
    #         )
    #     else:
    #         logging.error(
    #             f"NPC Ship {ship_id} attempted to jump, but it was "
    #             "not associated with any challenges."
    #         )

    @classmethod
    async def _game_timer_task(cls):
        cls._next_npc_ship_jump = datetime.datetime.now()

        while True:
            # Sleep before the operation so the task will sleep after continue.
            await asyncio.sleep(2)

            async with cls._lock:
                if datetime.datetime.now() < cls._next_npc_ship_jump:
                    continue

                for ship, route in cls._cache.npc_ships.items():
                    destination = route[cls._cache.jump_cycle_number % len(
                        route)]
                    await cls._npc_jump(ship, destination)

                cls._next_npc_ship_jump += JUMP_TIME_DELTA
                cls._cache.jump_cycle_number += 1

    @classmethod
    async def _dispatch_timer_task(cls):
        # TODO: Store this data in the cache to be able
        # to restore the state after restart.
        @dataclass
        class DispatchStatus:
            dispatch_data: Dispatch
            remaining_time: datetime.timedelta | None = None

        DispatchStatusMap = dict[DispatchID, DispatchStatus]
        dispatches: dict[GamespaceID, DispatchStatusMap] = {}

        async with cls._lock:
            for _, challenge_map in cls._cache.challenges.items():
                for _, gamespace_data in challenge_map.items():
                    gs_id = gamespace_data.gamespaceID

                    dispatch_status_map: DispatchStatusMap = {}

                    for dispatch in gamespace_data.dispatches:
                        dispatch_status_map[dispatch.id] = DispatchStatus(
                            dispatch)
                    for disp_id in gamespace_data.initial_dispatches:
                        disp_status = dispatch_status_map.get(disp_id)
                        if not disp_status:
                            logging.error(
                                f"Gamespace {gs_id} lists {disp_id} as an initial "
                                "dispatch, but it was not in the gamespace data."
                            )
                            continue
                        remaining_time = datetime.timedelta(
                            seconds=disp_status.dispatch_data.trigger_delay
                        )
                        disp_status.remaining_time = remaining_time

                    dispatches[gs_id] = dispatch_status_map

        while True:
            # Sleep before the operation so the task will sleep after continue.
            await asyncio.sleep(2)
            # TODO: Do dispatcher things here.

    @classmethod
    async def _handle_first_year_tasks(
        cls,
        team_id: TeamID,
        team_data: InternalTeamGameData,
        challenge_questions: [GameEngineQuestionView],
    ) -> bool:
        """
        Special handling for game tasks from PC4. Returns True if the given
        task is named the same as one of the special tasks from PC4, False
        otherwise.
        """
        question_summary = [
            (question.text, question.isCorrect)
            for question in challenge_questions
        ]
        logging.info(
            "Question summary: "
            f"{json.dumps(question_summary)}"
        )

        cllctn6_completions = {
            "cllctn6_term1": False,
            "cllctn6_term2": False,
            "cllctn6_term3": False,
            "cllctn6_term4": False,
            "cllctn6_term5": False,
            "cllctn6_critical": False,
            "cllctn6_firewall": False,
        }
        send_cllctn6_failure = False

        pc4_game = False
        for question in challenge_questions:
            task_id = question.text.lower().strip()
            if task_id not in (
                "antruins8",
                "cllctn11",
                "exoarch6",
                "exoarch9",
                "fllwrs12",
                "redradr6",
                "redradr10",
            ) and task_id not in cllctn6_completions:
                continue

            logging.info(
                "Doing special handling "
                f"for team {team_id} and task {task_id}"
            )

            pc4_game = True

            if not question.isCorrect:
                # For this task, failure triggers a new task with a failure video.
                if task_id in cllctn6_completions:
                    try:
                        last_failed_audit = datetime.datetime.fromisoformat(
                            question.answer
                        )
                    except TypeError:
                        logging.error(
                            "Question "
                            f"{task_id} in PC4 game had a null answer."
                        )
                    except ValueError:
                        # This means the answer was a non-ISO-format string.
                        # It's no problem if the question is marked correct.
                        logging.error(
                            "Question "
                            f"{task_id} in PC4 game had an answer "
                            "not in ISO format."
                        )
                    else:
                        if team_data.pc4_handling_cllctn6 < last_failed_audit:
                            send_cllctn6_failure = True
                        team_data.pc4_handling_cllctn6 = datetime.datetime.now()
                continue
            elif task_id in cllctn6_completions:
                cllctn6_completions[task_id] = True
                # We're not marking cllctn6 done yet - we need all
                # of the terminals to pass the audit.
                continue

            global_task = cls._cache.task_map.__root__.get(task_id)
            if not global_task:
                logging.error(
                    "Gamespace had task ID "
                    f"{task_id}, but it does not exist in the game data."
                )
                continue
            cls._complete_task_and_unlock_next(team_id, team_data, global_task)

        if send_cllctn6_failure:
            await cls._dispatch_challenge_task_failed(team_id, "cllctn6")
        elif all(cllctn6_completions.values()):
            global_task = cls._cache.task_map.__root__.get("cllctn6")
            if global_task:
                cls._complete_task_and_unlock_next(team_id, team_data, global_task)
            else:
                logging.error(
                    "Could not find "
                    "'cllctn6' in the global task cache."
                )

        return pc4_game

    @classmethod
    async def _mission_timer_challenge_handling(
        cls,
        team_id: TeamID,
        team_data: InternalTeamGameData,
        challenge: GameEngineGameState,
    ):
        if await cls._handle_first_year_tasks(
            team_id,
            team_data,
            challenge.challenge.questions,
        ):
            return

        if challenge.isActive or not challenge.endTime:
            # The condition is for completed challenges.
            return

        gamespace_id = challenge.id
        mission_id = cls._cache.gamespace_to_mission.get(gamespace_id)
        if not mission_id:
            logging.error(
                f"Got a challenge for team {team_id} "
                f"indicating a gamespace ID {gamespace_id}, "
                "but that gamespace was not mapped to a mission."
            )
            return

        team_challenge_data = cls._cache.challenges.get(team_id)
        if not team_challenge_data:
            logging.error(
                f"Got an uninitialized team ID: {team_id}"
            )
            return

        gs_data = team_challenge_data.get(mission_id)
        if not gs_data:
            logging.error(
                f"Had a challenge with ID {gamespace_id} for team "
                f"{team_id} that mapped to a mission {mission_id}, "
                "but no gamespace data was saved during challenge init."
            )
            return

        global_task = cls._cache.task_map.__root__.get(gs_data.taskID)
        if global_task is None:
            logging.error(
                f"Team challenge {gamespace_id} listed task "
                f"{gs_data.taskID} but it does not exist."
            )
            return

        cls._complete_task_and_unlock_next(
            team_id,
            team_data,
            global_task
        )

    @classmethod
    async def _mission_timer_body(cls):
        for team_id, _ in cls._cache.challenges.items():
            team_data = cls._cache.team_map.__root__.get(team_id)
            if team_data is None:
                logging.error(
                    f"Team {team_id} is in the challenge map, "
                    "but not the team map."
                )
                continue

            try:
                team_challenges = await gameboard.mission_update(team_id)
            except TypeError:
                logging.error(
                    "Attempted to get a mission update for team "
                    f"{team_id}, but Gameboard could not find that team."
                )
                continue
            else:
                logging.info(
                    "Got mission update for team "
                    f"{team_id}."
                )

            if not team_challenges:
                # It's already being logged.
                continue

            for challenge in team_challenges:
                await cls._mission_timer_challenge_handling(
                    team_id,
                    team_data,
                    challenge
                )

    @classmethod
    async def _mission_timer_task(cls):
        while True:
            # Sleep before the operation so the task will sleep after continue.
            await asyncio.sleep(2)

            try:
                async with cls._lock:
                    await cls._mission_timer_body()
            except Exception as e:
                logging.error(f"Mission timer task exception: {e}")

    @staticmethod
    def _handle_task_result(task: asyncio.Task) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            logging.info("Task %r cancelled.", task)
        except Exception:  # pylint: disable=broad-except
            logging.exception("Exception raised by task = %r", task)

    @classmethod
    async def start_game_timers(cls):
        async with cls._lock:
            # cls._active_game_timer_task = asyncio.create_task(
            #     cls._game_timer_task())
            # cls._active_game_timer_task.add_done_callback(
            #     cls._handle_task_result)
            #
            # cls._active_dispatch_timer_task = asyncio.create_task(
            #     cls._dispatch_timer_task()
            # )
            # cls._active_dispatch_timer_task.add_done_callback(
            #     cls._handle_task_result)

            cls._active_mission_timer_task = asyncio.create_task(
                cls._mission_timer_task()
            )
            cls._active_mission_timer_task.add_done_callback(
                cls._handle_task_result)

    # @classmethod
    # async def stop_game_timers(cls):
    #     async with cls._lock:
    #         if cls._active_game_timer_task is None:
    #             logging.warning(
    #                 "stop_game_timers called without timers being started.")
    #             return
    #
    #         cls._active_game_timer_task.cancel()
    #         cls._active_game_timer_task = None
    #
    #         cls._active_dispatch_timer_task.cancel()
    #         cls._active_dispatch_timer_task = None
    #
    #         cls._active_mission_timer_task.cancel()
    #         cls._active_mission_timer_task = None

    @classmethod
    async def get_total_points(cls) -> int:
        async with cls._lock:
            return sum(
                map(lambda m: m.points, cls._cache.mission_map.__root__.values())
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
            cls._next_video_refresh = datetime.datetime.now(timezone.utc)

    class VmIdResponseFailure(Exception):
        ...

    @classmethod
    async def _change_gamespace_gateway_network(
        cls,
        current_location: LocationID,
        target_network: str,
        gamespace_data: GamespaceData,
        force_target_network: bool = False,
        target_gamespace_id: GamespaceID = None,
    ):

        gamespace_id = gamespace_data.gamespaceID
        gateway_vm_name = gamespace_data.gatewayVmName
        gateway_nic = gamespace_data.gatewayNic
        location_id = gamespace_data.locationID

        if gamespace_data.noGateway:
            logging.info(
                f"Gamespace {gamespace_data} has noGateway "
                "set to True. Will not attempt to change a network for it."
            )
            return

        if not location_id and not force_target_network:
            logging.warning(
                f"Gamespace {gamespace_id} does not have "
                "a location ID referenced. This is fine if the ship does not "
                "need to connect to the gamespace's network."
            )

        if location_id == current_location or force_target_network:
            if target_gamespace_id:
                net_name, *_ = target_network.split("#")
                target_network = f"{net_name}#{target_gamespace_id}"
            new_net = f"{target_network}:{gateway_nic}"
        else:
            new_net = (
                f"{cls._settings.game.antenna_retracted_network}#"
                f"{gamespace_id}:"
                f"{gateway_nic}"
            )

        vm_id_response = await cls._get_vm_id_from_name_for_gamespace(
            gamespace_id,
            gateway_vm_name
        )
        if not vm_id_response.success:
            logging.error(
                "Could not get a VM ID for a VM named "
                f"{gateway_vm_name} in "
                f"Gamespace {gamespace_id}"
                f"VM ID response: {vm_id_response.message}"
            )
            raise cls.VmIdResponseFailure

        await topomojo.change_vm_net(vm_id_response.message, new_net)

    @classmethod
    def _prioritize_gamespace_document_data(
            cls,
            mission_id: MissionID,
            gamespace_data: GamespaceData,
    ):
        try:
            global_mission = cls._cache.mission_map.__root__[mission_id]
        except KeyError:
            logging.error(
                f"Could not find mission {mission_id}."
            )
            return

        # The values may be specified in the initial game data, but the
        # workspace values should be prioritized.

        if not gamespace_data.galaxyMapXPos:
            gamespace_data.galaxyMapXPos = global_mission.galaxyMapXPos
        if not gamespace_data.galaxyMapYPos:
            gamespace_data.galaxyMapYPos = global_mission.galaxyMapYPos
        if not gamespace_data.galaxyMapTargetXPos:
            gamespace_data.galaxyMapTargetXPos = global_mission.galaxyMapTargetXPos
        if not gamespace_data.galaxyMapTargetYPos:
            gamespace_data.galaxyMapTargetYPos = global_mission.galaxyMapTargetYPos

    @classmethod
    async def init_challenges(
        cls,
        team_gamespaces: dict[TeamID, TeamGamespaceInfo],
    ):
        # def get_npc_ship_id(task_id):
        #     global_task_data = cls._cache.task_map.__root__.get(task_id)
        #     if not global_task_data:
        #         logging.error(
        #             f"Gamespace {gamespace_data.gamespaceID} had an "
        #             f"invalid task ID {task_id}."
        #         )
        #         return
        #
        #     mission_id = global_task_data.missionID
        #     global_mission_data = cls._cache.mission_map.__root__[mission_id]
        #
        #     return global_mission_data.npcShip

        def get_mission_id(task_id):
            global_task_data = cls._cache.task_map.__root__.get(task_id)
            if not global_task_data:
                logging.error(
                    f"Gamespace {gamespace_data.gamespaceID} had an "
                    f"invalid task ID {task_id}."
                )
                return

            return global_task_data.missionID

        async with cls._lock:
            for team_id, gamespace_info in team_gamespaces.items():
                team_data = await get_team(team_id)
                if not team_data:
                    logging.error(
                        f"Tried to look up team {team_id} "
                        "but it was not found in the database!"
                    )
                    continue

                cls._cache.challenges[team_id] = {}

                for (
                    task_id,
                    gamespace_data,
                ) in gamespace_info.gamespaces.items():
                    # npc_ship_id = get_npc_ship_id(task_id)
                    # if not npc_ship_id:
                    #     continue
                    mission_id = get_mission_id(task_id)
                    if not mission_id:
                        logging.warning(
                            f"Team {team_id} gamespace "
                            f"{gamespace_data.gamespaceID} "
                            f"has a task ID {task_id} without a corresponding "
                            "mission. Unable to associate a mission to this "
                            "gamespace."
                        )
                        continue

                    cls._prioritize_gamespace_document_data(
                        mission_id,
                        gamespace_data
                    )

                    cls._cache.challenges[team_id][mission_id] = gamespace_data
                    gamespace_id = gamespace_data.gamespaceID
                    cls._cache.gamespace_to_mission[gamespace_id] = mission_id

                    logging.info(
                        f"Team {team_id} had mission {mission_id} "
                        f"assigned to gamespace {gamespace_id}."
                    )

    @classmethod
    async def _uninit_body(cls, team_id: TeamID):
        try:
            del cls._cache.challenges[team_id]
        except KeyError:
            logging.warning(
                f"Tried to uninit team {team_id} but it "
                "was not being tracked in the challenge map."
            )

    @classmethod
    async def uninit_challenges(cls, teams: list[str] = None):
        async with cls._lock:
            if teams is None:
                # Don't delete from an iterating dict.
                teams = list(cls._cache.challenges.keys())
            for team_id in teams:
                await cls._uninit_body(team_id)

    @classmethod
    async def uninit_team(cls, team_id: TeamID):
        async with cls._lock:
            await cls._uninit_body(team_id)

    @classmethod
    async def new_team(
        cls,
        team_id: TeamID,
        deployment_session: DeploymentSession,
        ship_gamespace_info: GamespaceData,
    ):
        async with cls._lock:
            new_team_state = InternalTeamGameData(
                **cls._cache.team_initial_state.dict()
            )
            new_team_state.session.teamInfoName = team_id
            new_team_state.session.gameStartTime = deployment_session.sessionBegin
            new_team_state.session.gameEndTime = deployment_session.sessionEnd
            new_team_state.session.gameCurrentTime = deployment_session.now
            new_team_state.session.useGalaxyDisplayMap = (
                ship_gamespace_info.useGalaxyDisplayMap
            )
            new_team_state.session.useCodices = ship_gamespace_info.useCodices
            new_team_state.session.timerTitle = ship_gamespace_info.timerTitle

            new_team_state.ship.gamespaceData = ship_gamespace_info

            cls._cache.team_map.__root__[team_id] = new_team_state

            logging.info(
                f"Team {team_id} created with missions {new_team_state.missions} "
                f"and session {json.dumps(new_team_state.session, indent=2, default=str)}"
            )

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
    def _map_team_score_data(
        cls, team_score_data: TeamGameScoreQueryResponse
    ) -> {MissionID, MissionScoreData}:
        """
        Assumes that the class lock is held.
        """
        if not team_score_data:
            return {}

        spec_map = {
            spec.id: spec
            for spec in team_score_data.gameInfo.specs
        }

        mission_map = {}
        for team_challenge_score in team_score_data.score.challenges:
            gamespace_id = team_challenge_score.id
            mission_id = cls._cache.gamespace_to_mission.get(gamespace_id)
            challenge_spec = spec_map[team_challenge_score.specId]
            if not mission_id:
                logging.info(
                    f"Tried to look up gamespace {gamespace_id} to get "
                    "a mission ID, but it was not there. This is normal "
                    "if the gamespace is from a ship workspace."
                )
                continue

            mission_score_data = {
                "current_score": team_challenge_score.score.totalScore,
                "possible_max_score": challenge_spec.maxPossibleScore,
                "base_solve_value": challenge_spec.completionScore,
                "bonus_remaining": max(
                    map(
                        lambda b: b.pointValue,
                        team_challenge_score.unclaimedBonuses,
                    ),
                    default=0,
                ),
            }
            mission_map[mission_id] = MissionScoreData(**mission_score_data)

        return mission_map

    @classmethod
    def _get_team_unlocked_locations(
        cls, team_data: InternalTeamGameData
    ) -> list[LocationDataFull]:
        full_loc_data = []

        for location_id, location in team_data.locations.items():
            loc_global = cls._cache.location_map.__root__[location_id]
            loc_full = LocationDataFull(
                **loc_global.dict() | location.dict())
            full_loc_data.append(loc_full)

        return full_loc_data

    @classmethod
    def _get_team_mission_unlocked_tasks(
        cls,
        team_id: str,
        team_data: InternalTeamGameData,
        mission: InternalTeamMissionData,
    ) -> list[TaskDataFull]:
        mission_task_data = []

        for task_id in mission.tasks:
            team_task = team_data.tasks.get(task_id)
            if not team_task:
                logging.error(
                    f"Team {team_id} had a mission identify a task {task_id}"
                    ", but the task was not in the team's task map."
                )
                continue
            global_task = cls._cache.task_map.__root__.get(task_id)
            if not global_task:
                logging.error(
                    f"Team {team_id} had a mission identify a task {task_id}"
                    ", but the task was not in the global task map."
                )
                continue
            if not team_task.visible:
                continue

            mission_task_data.append(
                TaskDataFull(**global_task.dict() | team_task.dict())
            )

        return mission_task_data

    @classmethod
    async def _get_team_unlocked_missions(
        cls,
        team_id: str,
        team_data: InternalTeamGameData,
        mission_map: dict[MissionID, MissionScoreData]
    ) -> list[MissionDataFull]:
        full_mission_data = []
        associated_challenges = {}
        mission_unlock_codes = {}

        total_teams = await get_active_teams()

        for mission in team_data.missions.values():
            if not mission.unlocked:
                continue

            mission_global = cls._cache.mission_map.__root__[
                mission.missionID]

            mission_task_data = cls._get_team_mission_unlocked_tasks(
                team_id,
                team_data,
                mission
            )

            try:
                gamespace_data = cls._cache.challenges[team_id].get(mission.missionID)
            except KeyError:
                gamespace_data = None
            position_data = {}
            if team_id and not gamespace_data:
                logging.error(
                    f"Team {team_id}'s mission {mission.missionID} has "
                    "not been populated with gamespace data."
                )
            elif team_id is None:
                # This is fine, but don't try to access gamespace_data.
                pass
            else:
                position_data["galaxyMapXPos"] = gamespace_data.galaxyMapXPos
                position_data["galaxyMapYPos"] = gamespace_data.galaxyMapYPos
                position_data["galaxyMapTargetXPos"] = gamespace_data.galaxyMapTargetXPos
                position_data["galaxyMapTargetYPos"] = gamespace_data.galaxyMapTargetYPos

                associated_mission_ids = {
                    mission_id
                    for completion_order in mission_global.firstNthCompletionUnlocks
                    for mission_id in completion_order
                }

                associated_challenges[mission.missionID] = sorted(
                    list(
                        associated_mission_ids
                    )
                )
                location = cls._cache.location_map.__root__.get(gamespace_data.locationID)
                if location:
                    mission_unlock_codes[mission.missionID] = location.unlockCode
                else:
                    mission_unlock_codes[mission.missionID] = ""
                    logging.warning(
                        f"Gamespace {gamespace_data.gamespaceID} had location "
                        f"{gamespace_data.locationID} in its workspace "
                        "document, but that location does not exist!"
                    )

            score_data = {}
            mission_score_data = mission_map.get(mission_global.missionID)
            if mission_score_data:
                score_data["currentScore"] = mission_score_data.current_score
                score_data["possibleMaximumScore"] = mission_score_data.possible_max_score
                score_data["baseSolveValue"] = mission_score_data.base_solve_value
                score_data["bonusRemaining"] = mission_score_data.bonus_remaining
            elif team_id:
                logging.warning(
                    f"Team {team_id} had no score data for "
                    f"mission {mission.missionID}"
                )

            teams_solved = cls._get_mission_completion_for_teams(mission_global)
            completion_data = {
                "solveTeams": teams_solved,
                "totalTeams": len(total_teams),
            }

            mission_full = MissionDataFull(
                **mission_global.dict()
                | mission.dict()
                | {"taskList": mission_task_data}
                | position_data
                | score_data
                | completion_data
            )
            full_mission_data.append(mission_full)

        for mission_data in full_mission_data:
            if mission_data.missionID not in associated_challenges:
                # Likely means there is no associated gamespace,
                # which was logged earlier.
                continue
            for associated_mission_id in associated_challenges[mission_data.missionID]:
                # Only put unlock codes in the output if the associated
                # mission is actually unlocked. The mission ID will only
                # be in associated_challenges and mission_unlock_codes
                # if it's unlocked.
                unlock_code = ""
                if associated_mission_id in mission_unlock_codes:
                    unlock_code = mission_unlock_codes[associated_mission_id]
                associated_data = AssociatedChallengeData(
                    missionID=associated_mission_id,
                    unlockCode=unlock_code,
                )
                mission_data.associatedChallenges.append(associated_data)

        return full_mission_data

    @classmethod
    async def get_team_data(cls, team_id: TeamID | None) -> GameDataResponse | None:
        async with cls._lock:
            mission_map = {}

            if team_id is None:
                team_data = cls._cache.team_initial_state
            else:
                team_data = cls._cache.team_map.__root__.get(team_id)

                gamebrain_time = datetime.datetime.now(timezone.utc)
                team_data.session.gameCurrentTime = gamebrain_time

                team_score_data = await gameboard.team_score(team_id)
                mission_map = cls._map_team_score_data(team_score_data)
                if cls._spam_reduction_tracker >= 20:
                    logging.info(
                        f"Got score data for team {team_id}: "
                        f"{json.dumps(mission_map, indent=2, default=str)}"
                    )
                    cls._spam_reduction_tracker = 0
                else:
                    cls._spam_reduction_tracker += 1

            if not team_data:
                raise NonExistentTeam()

            # Implemented for cancelled feature - leaving for possible future use.
            if cls._next_npc_ship_jump:
                team_data.ship.nextJumpTime = cls._next_npc_ship_jump.isoformat()
            else:
                team_data.ship.nextJumpTime = datetime.datetime.max.isoformat()

            if team_data.currentStatus.antennaExtended:
                antenna_state = cls.ExtendOrRetract.extend
            else:
                antenna_state = cls.ExtendOrRetract.retract

            await cls._update_team_urls_body(team_id, antenna_state)

            full_loc_data = cls._get_team_unlocked_locations(team_data)

            full_mission_data = await cls._get_team_unlocked_missions(
                team_id,
                team_data,
                mission_map
            )

            full_team_data = GameDataResponse(
                currentStatus=team_data.currentStatus,
                session=team_data.session,
                ship=team_data.ship,
                locations=full_loc_data,
                missions=full_mission_data,
            )

            if cls._spam_reduction_tracker >= 20:
                logging.info(
                    "Full team data response:"
                    f"{json.dumps(full_team_data.dict(), default=str)}"
                )
                cls._spam_reduction_tracker = 0
            else:
                cls._spam_reduction_tracker += 1

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

            cls._complete_task_and_unlock_next(
                team_id, team_data, global_task_data)

    @classmethod
    async def dispatch_challenge_task_failed(cls, team_id: TeamID, task_id: str):
        async with cls._lock:
            await cls._dispatch_challenge_task_failed(team_id, task_id)

    @classmethod
    async def _dispatch_challenge_task_failed(cls, team_id: TeamID, task_id: str):
        """
        Lock is assumed to be held.
        """
        team_data = cls._cache.team_map.__root__.get(team_id)
        if not team_data:
            logging.error(
                f"Dispatch task reported team {team_id} failed a task, but that team does not exist."
            )
            return

        if task_id not in team_data.tasks:
            # Team has not yet unlocked the relevant task, so just don't do anything.
            return

        global_task_data = cls._cache.task_map.__root__.get(task_id)
        if not global_task_data:
            logging.error(
                f"Dispatch task reported task {task_id} failed for team {team_id}, but no such task exists."
            )
            return

        if not (
            global_task_data.failWhen
            and global_task_data.failWhen.type == "challengeFail"
            and global_task_data.failWhen.unlocks
        ):
            return

        next_task = global_task_data.failWhen.unlocks
        if not next_task:
            return

        next_task_data = cls._cache.task_map.__root__.get(next_task)
        if not next_task_data:
            logging.error(
                f"Task {global_task_data.taskID} has a failWhen block that specifies task "
                f"{next_task} to unlock, but the task does not exist in the global data."
            )
            return

        cls._unlock_specific_task(team_id, team_data, next_task_data)

    @classmethod
    async def dispatch_grading_task_update(
        cls, team_id: TeamID, gamespace_state_output: GamespaceStateOutput
    ):
        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            # TODO: Generalize this.
            task_mapping = {
                "exoarch9": gamespace_state_output.exoArch,
                "redradr10": gamespace_state_output.redRaider,
                "antruins8": gamespace_state_output.ancientRuins,
                "cllctn11": gamespace_state_output.museum,
                "fllwrs12": gamespace_state_output.xenoCult,
            }

            for task_id, status in task_mapping.items():
                if status == "success":
                    logging.info(
                        f"Grading dispatch for team {team_id} "
                        f"indicates codex completion for task {task_id}"
                    )
                    global_task_data = cls._cache.task_map.__root__.get(
                        task_id)
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
    async def pc4_update_team_urls(
        cls,
        team_id: TeamID,
        pc4_urls: dict[VmName, VmUrlStr],
    ):
        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            team_data.ship.workstation1URL = pc4_urls.get(
                "operator-terminal-1", "")
            team_data.ship.workstation2URL = pc4_urls.get(
                "operator-terminal-2", "")
            team_data.ship.workstation3URL = pc4_urls.get(
                "operator-terminal-3", "")
            team_data.ship.workstation4URL = pc4_urls.get(
                "operator-terminal-4", "")
            team_data.ship.workstation5URL = pc4_urls.get(
                "operator-terminal-5", "")
            team_data.ship.codexURL = pc4_urls.get("codex-decoder", "")

            logging.info(
                f"Team Data for team {team_id} updated: "
                "{team_data.ship.dict()}"
            )

    class ExtendOrRetract(Enum):
        extend = 0
        retract = 1

    @classmethod
    async def _update_team_urls_body(
        cls,
        team_id: TeamID,
        extend_or_retract: ExtendOrRetract = ExtendOrRetract.retract,
    ):
        team_data = cls._cache.team_map.__root__[team_id]
        if team_data.ship.gamespaceData.isPC4Workspace:
            # This method is only used in newer game types.
            team_data.ship.challengeURLs = None
            return

        team_challenge_map = cls._cache.challenges[team_id]

        ship_gamespace_vm_urls = [
            VmURL(
                vmName=console_url.name,
                vmURL=console_url.url,
            ) for console_url in team_data.ship.gamespaceData.consoleURLs]

        ship_challenge_urls = [
            ChallengeURLs(
                missionID="ship",
                missionName="Ship Consoles",
                missionIcon="",
                vmURLs=ship_gamespace_vm_urls,
            )
        ] if ship_gamespace_vm_urls else []

        if extend_or_retract == cls.ExtendOrRetract.retract:
            team_data.ship.challengeURLs = ship_challenge_urls
            return

        team_challenge_urls = []

        for mission_id, gamespace_data in team_challenge_map.items():
            if team_data.currentStatus.currentLocation != gamespace_data.locationID:
                continue
            if team_data.missions[mission_id].complete:
                continue
            if not gamespace_data.consoleURLs:
                continue
            global_mission_data = cls._cache.mission_map.__root__.get(mission_id)
            if not global_mission_data:
                logging.error(
                    f"Team {team_id} had a gamespace for mission "
                    f"{mission_id}, but no such mission exists. "
                    "Unable to extract VM Consoles."
                )
                continue
            mission_name = global_mission_data.title

            gamespace_vm_urls = [
                VmURL(
                    vmName=console_url.name,
                    vmURL=console_url.url,
                ) for console_url in gamespace_data.consoleURLs]

            challenge_urls = ChallengeURLs(
                missionID=mission_id,
                missionName=mission_name,
                missionIcon=global_mission_data.missionIcon,
                vmURLs=gamespace_vm_urls,
            )
            team_challenge_urls.append(challenge_urls)

        team_challenge_urls.sort(key=lambda el: el.missionName)
        team_data.ship.challengeURLs = ship_challenge_urls + team_challenge_urls

    @classmethod
    async def update_team_urls(
        cls,
        team_id: TeamID,
        extend_or_retract: ExtendOrRetract = ExtendOrRetract.retract,
    ):
        async with cls._lock:
            await cls._update_team_urls_body(team_id, extend_or_retract)

    @classmethod
    async def update_all_active_team_urls(
        cls,
        extend_or_retract: ExtendOrRetract = ExtendOrRetract.retract,
    ):
        async with cls._lock:
            active_teams = await get_active_teams()
            for team in active_teams:
                team_id = team["id"]
                await cls._update_team_urls_body(team_id, extend_or_retract)

    @classmethod
    async def _pc4_network_change_team_gamespace(
        cls,
        team_data: InternalTeamGameData,
        extend_or_retract: ExtendOrRetract,
    ) -> str:
        if extend_or_retract == cls.ExtendOrRetract.extend:
            location_id = team_data.currentStatus.currentLocation
            location_data = cls._cache.location_map.__root__[location_id]
            network_name = location_data.networkName
        else:
            network_name = cls._settings.game.antenna_retracted_network

        await cls._change_gamespace_gateway_network(
            location_id,
            network_name,
            team_data.ship.gamespaceData,
            force_target_network=True,
            target_gamespace_id=team_data.ship.gamespaceData.gamespaceID,
        )

        return network_name

    @classmethod
    async def _bulk_network_change_team_gamespaces(
        cls,
        team_id: TeamID,
        team_data: InternalTeamGameData,
        target_network_name: str,
        extend_or_retract: ExtendOrRetract,
        target_gamespace_id: GamespaceID = None,
    ):
        if extend_or_retract == cls.ExtendOrRetract.extend:
            location = team_data.currentStatus.currentLocation
            network = target_network_name
        else:
            location = ""
            network = ""

        # Make sure the ship gateway is on the right VLAN.
        tasks = [
            cls._change_gamespace_gateway_network(
                team_data.currentStatus.currentLocation,
                target_network_name,
                team_data.ship.gamespaceData,
                force_target_network=True,
                target_gamespace_id=target_gamespace_id,
            )
        ]
        # Then make sure all the challenges are either on the same VLAN,
        # or set to their own "deepspace" network, unreachable from
        # the ship.
        for _, gamespace_data in cls._cache.challenges[team_id].items():
            tasks.append(cls._change_gamespace_gateway_network(
                location,
                network,
                gamespace_data,
                target_gamespace_id=target_gamespace_id,
            ))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, cls.VmIdResponseFailure):
                logging.error(
                    f"Team {team_id} got a VM ID Response failure."
                )

        await cls._update_team_urls_body(team_id, extend_or_retract)

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

            if team_data.ship.gamespaceData.isPC4Workspace:
                network_name = await cls._pc4_network_change_team_gamespace(
                    team_data,
                    cls.ExtendOrRetract.extend,
                )
            else:
                network_name = team_data.ship.gamespaceData.gatewayWanNetworkName
                ship_gamespace_id = team_data.ship.gamespaceData.gamespaceID
                if not network_name:
                    logging.warning(
                        f"Gamespace {ship_gamespace_id} does not have "
                        "'gatewayWanNetworkName' specified. Defaulting to 'ship'"
                    )
                    network_name = "ship"

                await cls._bulk_network_change_team_gamespaces(
                        team_id,
                        team_data,
                        network_name,
                        cls.ExtendOrRetract.extend,
                        target_gamespace_id=ship_gamespace_id
                )

            team_data.currentStatus.antennaExtended = True
            team_data.currentStatus.networkConnected = True
            team_data.currentStatus.networkName = network_name

            cls._mark_task_complete_if_unlocked(
                team_id,
                team_data,
                "antennaExtended"
            )

            return GenericResponse(
                success=True, message=f"Team {team_id} extended their antenna."
            )

    @classmethod
    async def _retract_antenna_body(cls, team_id: TeamID) -> GenericResponse:
        team_data = cls._cache.team_map.__root__.get(team_id)
        if not team_data:
            raise NonExistentTeam()

        if team_data.ship.gamespaceData.isPC4Workspace:
            await cls._pc4_network_change_team_gamespace(
                team_data,
                cls.ExtendOrRetract.retract,
            )
        else:
            network_name = team_data.ship.gamespaceData.gatewayWanNetworkName
            ship_gamespace_id = team_data.ship.gamespaceData.gamespaceID
            if not network_name:
                logging.warning(
                    f"Gamespace {ship_gamespace_id} does not have "
                    "'gatewayWanNetworkName' specified. Defaulting to 'ship'"
                )
                network_name = "ship"

            await cls._bulk_network_change_team_gamespaces(
                    team_id,
                    team_data,
                    network_name,
                    cls.ExtendOrRetract.retract,
                    target_gamespace_id=ship_gamespace_id,
            )

        team_data.currentStatus.antennaExtended = False
        team_data.currentStatus.networkConnected = False
        team_data.currentStatus.networkName = (
            cls._settings.game.antenna_retracted_network
        )

        cls._mark_task_complete_if_unlocked(
            team_id,
            team_data,
            "antennaRetracted"
        )

        return GenericResponse(
            success=True,
            message=f"Team {team_id} retracted their antenna."
        )

    @classmethod
    async def retract_antenna(cls, team_id: TeamID) -> GenericResponse:
        async with cls._lock:
            return await cls._retract_antenna_body(team_id)

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
                    lambda loc: loc.unlockCode.lower() == unlock_code.lower(),
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

            cls._unlock_location_for_team(team_id, team_data, location_id)

            return response("success", location_id)

    @classmethod
    def _unlock_location_for_team(
        cls, team_id: TeamID, team_data: InternalTeamGameData, location_id: LocationID
    ):
        global_location = cls._cache.location_map.__root__.get(location_id)
        if not global_location:
            logging.error(
                f"Team {team_id} tried to unlock location {location_id} but it doesn't exist."
            )
            return
        # "visited" is used to signify that the first contact has been completed for a location
        # In the case where a location has no associated comm event, it should automatically be considered visited.
        # Scanned is used only by the game, but the above should apply to it as well
        scanned_and_visited = not bool(global_location.firstContactEvent)
        team_data.locations[location_id] = InternalTeamLocationData(
            locationID=location_id,
            visited=scanned_and_visited,
            scanned=scanned_and_visited,
        )

        # Each Comm Event has a LocationID, so gather the ones associated with the new location.
        unlocked_comm_event_ids = set(
            map(
                lambda c: c.commID,
                filter(
                    lambda c: c.locationID == location_id,
                    cls._cache.comm_map.__root__.values(),
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
            await cls._retract_antenna_body(team_id)

            cls._mark_task_complete_if_unlocked(team_id, team_data, "jump")

            if team_location.visited:
                cls._find_comm_event_to_activate(team_id, team_data)

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

            team_location_data = team_data.locations.get(
                location_data.locationID)
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
    def _find_comm_event_to_activate(
        cls, team_id: TeamID, team_data: InternalTeamGameData
    ):
        def is_relevant_task(global_task: InternalGlobalTaskData) -> bool:
            team_task = team_data.tasks.get(global_task.taskID)
            if not (team_task and team_task.visible):
                return False
            if team_task.complete:
                return False
            completion_criteria = global_task.markCompleteWhen
            if not completion_criteria:
                return False
            if completion_criteria.type != "comm":
                return False
            if (
                completion_criteria.locationID
                != team_data.currentStatus.currentLocation
            ):
                return False
            return True

        relevant_tasks = list(
            filter(is_relevant_task, cls._cache.task_map.__root__.values())
        )
        try:
            task = relevant_tasks.pop()
        except IndexError:
            team_data.currentStatus.incomingTransmissionObject = {}
            team_data.currentStatus.incomingTransmission = False
        else:
            cls._set_task_comm_event_active(team_id, team_data, task)

    @classmethod
    async def complete_comm_event(cls, team_id: TeamID) -> GenericResponse:
        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            current_comm_event = team_data.currentStatus.incomingTransmissionObject
            if not current_comm_event:
                logging.info(
                    f"Team {team_id} tried to complete a comm event, "
                    "but they do not currently have a comm event."
                )
                return GenericResponse(
                    success=False,
                    message=f"Team {team_id} did not have "
                    "an active comm event to complete.",
                )

            if current_comm_event and current_comm_event.firstContact:
                current_location_id = team_data.currentStatus.currentLocation
                team_comm_location_id = current_comm_event.locationID
                if current_location_id == team_comm_location_id:
                    team_comm_location = team_data.locations.get(
                        team_comm_location_id)
                    if not team_comm_location:
                        logging.error(
                            f"Team {team_id} tried to complete comm event {current_comm_event.commID}, "
                            "but they have not unlocked the location yet."
                        )
                        return GenericResponse(
                            success=False,
                            message="Location not unlocked.",
                        )

                    team_data.currentStatus.firstContactComplete = True
                    team_comm_location.visited = True

            cls._mark_task_complete_if_unlocked(team_id, team_data, "comm")

            cls._find_comm_event_to_activate(team_id, team_data)

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
                    message="TopoMojoAPIFailure",
                )

            await cls.change_vm_power_status(vm_id, new_setting)
            return GenericResponse(success=True, message=f"{vm_id}_{new_setting}")
