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

import enum
from typing import Literal

from pydantic import BaseModel


TaskBranchType = Literal[
    "comm",
    "jump",
    "explorationMode",
    "launchMode",
    "standby",
    "scan",
    "antennaExtended",
    "antennaRetracted",
    "challenge",
    "challengeFail",
    "codex",
    "indirect",
]


CommID = str
MissionID = str
LocationID = str
TaskID = str
NPCShipID = str
GamespaceID = str


class GamespaceData(BaseModel):
    # A workspace without a task ID denotes a ship gamespace.
    taskID: TaskID | None
    gatewayVmName: str
    gatewayNic: int
    # Filled in by Gamebrain, not Topomojo.
    gamespaceID: GamespaceID


class TeamGamespaceInfo(BaseModel):
    ship_gamespace: GamespaceID
    gamespaces: dict[TaskID, GamespaceData]


class NPCShipData(BaseModel):
    shipID: NPCShipID
    route: list[LocationID]
    currentLocation: LocationID


class TaskBranch(BaseModel):
    type: TaskBranchType
    locationID: LocationID = None
    alsoComplete: list[TaskID] = None
    unlocks: TaskID = None
    unlockLocation: LocationID = None
    indirectPrerequisiteTasks: list[TaskID] = []


class TaskData(BaseModel):
    taskID: TaskID
    missionID: MissionID
    descriptionText: str
    infoPresent: bool = True
    infoText: str
    videoPresent: bool = True
    videoURL: str
    commID: CommID
    next: TaskID = None
    completesMission: bool = False
    markCompleteWhen: TaskBranch = None
    failWhen: TaskBranch = None
    cancelWhen: TaskBranch = None


class TaskDataTeamSpecific(BaseModel):
    taskID: TaskID
    visible: bool = False
    complete: bool = False


class TaskDataFull(TaskData, TaskDataTeamSpecific):
    ...


class TaskDataIdentifierStub(BaseModel):
    taskID: TaskID


class MissionData(BaseModel):
    missionID: MissionID
    title: str
    summaryShort: str
    summaryLong: str
    missionIcon: str
    isSpecial: bool = False
    roleList: list[str]
    taskList: list[TaskDataIdentifierStub]
    points: int = 0
    npcShip: str = ""
    # The unlocks after completing a mission, in the order of which team
    # completes the mission first. The last list of mission IDs will be used
    # for all subsequent completions.
    firstNthCompletionUnlocks: list[list[MissionID]] = []


class MissionDataTeamSpecific(BaseModel):
    missionID: MissionID
    unlocked: bool = True
    visible: bool = False
    complete: bool = False
    taskList: list[TaskDataTeamSpecific]
    gamespaceID: str = None


class MissionDataFull(MissionData, MissionDataTeamSpecific):
    taskList: list[TaskDataFull]


class LocationData(BaseModel):
    locationID: LocationID
    name: str
    imageID: str
    backdropID: str
    surroundings: str
    unlockCode: str
    trajectoryLaunch: int
    trajectoryCorrection: int
    trajectoryCube: int
    firstContactEvent: str
    networkName: str


class LocationDataTeamSpecific(BaseModel):
    locationID: LocationID
    unlocked: bool = True
    visited: bool = False
    scanned: bool = False
    networkEstablished: bool = False


class LocationDataFull(LocationData, LocationDataTeamSpecific):
    ...


class PowerStatus(enum.Enum):
    on = "on"
    off = "off"


class ShipDataTeamSpecific(BaseModel):
    class Config:
        use_enum_values = True

    codexURL: str
    workstation1URL: str
    workstation2URL: str
    workstation3URL: str
    workstation4URL: str
    workstation5URL: str
    commPower: PowerStatus = PowerStatus.off
    flightPower: PowerStatus = PowerStatus.off
    navPower: PowerStatus = PowerStatus.off
    pilotPower: PowerStatus = PowerStatus.off
    nextJumpTime: str = ""
    # NICs are zero-indexed.
    antennaNic: int


class SessionDataTeamSpecific(BaseModel):
    teamInfoName: str = None
    teamCodexCount: int = 0
    jumpCutsceneURL: str


class CommEventData(BaseModel):
    commID: CommID
    videoURL: str
    commTemplate: Literal["incoming", "probe", "badTranslation"]
    translationMessage: str
    scanInfoMessage: str
    firstContact: bool
    locationID: LocationID


PowerMode = Literal["launchMode", "explorationMode", "standby"]


class CurrentLocationGameplayDataTeamSpecific(BaseModel):
    currentLocation: str
    currentLocationScanned: bool = False
    currentLocationSurroundings: str
    antennaExtended: bool = False
    networkConnected: bool = False
    networkName: str = ""
    firstContactComplete: bool = False
    powerStatus: PowerMode = "launchMode"
    incomingTransmission: bool = False
    incomingTransmissionObject: CommEventData | None | dict = {}


class GameDataTeamSpecific(BaseModel):
    currentStatus: CurrentLocationGameplayDataTeamSpecific
    session: SessionDataTeamSpecific
    ship: ShipDataTeamSpecific
    locations: list[LocationDataTeamSpecific]
    missions: list[MissionDataTeamSpecific]

    def to_internal(self) -> "InternalTeamGameData":
        locations = {
            location.locationID: location.dict() for location in self.locations
        }
        missions = {}
        tasks = {}
        for mission_data in self.missions:
            try:
                # Get the first task that is not marked complete for this mission.
                current_task = next(
                    filter(lambda t: t.complete is False,
                           mission_data.taskList)
                ).taskID
            except StopIteration:
                current_task = None
            missions[mission_data.missionID] = mission_data.dict() | {
                "current_task": current_task,
                "tasks": [],
            }

            for task_data in mission_data.taskList:
                task_model = InternalTeamTaskData(**task_data.dict())
                tasks[task_data.taskID] = task_model
                missions[mission_data.missionID]["tasks"].append(
                    task_data.taskID)

        return InternalTeamGameData(
            currentStatus=self.currentStatus,
            session=self.session,
            ship=self.ship,
            locations=locations,
            missions=missions,
            tasks=tasks,
        )


class GameDataResponse(GameDataTeamSpecific):
    locations: list[LocationDataFull]
    missions: list[MissionDataFull]


class GenericResponse(BaseModel):
    success: bool
    message: str


class LocationUnlockResponse(BaseModel):
    responseStatus: Literal["success", "invalid", "alreadyunlocked"]
    locationID: LocationID
    enteredCoordinates: str


class ScanResponse(GenericResponse):
    eventWaiting: bool
    incomingTransmission: CommEventData | dict


class InternalCommEvent(CommEventData):
    associated_task: TaskID

    def to_snapshot(self) -> CommEventData:
        return CommEventData(**self.dict())


class InternalGlobalLocationData(LocationData):
    ...


class InternalTeamLocationData(LocationDataTeamSpecific):
    ...


class InternalGlobalTaskData(TaskData):
    ...


class InternalTeamTaskData(TaskDataTeamSpecific):
    ...


class InternalGlobalMissionData(MissionData):
    first_task: TaskID
    last_task: TaskID


class InternalTeamMissionData(MissionDataTeamSpecific):
    tasks: list[TaskID]


class InternalTeamGameData(BaseModel):
    currentStatus: CurrentLocationGameplayDataTeamSpecific
    session: SessionDataTeamSpecific
    ship: ShipDataTeamSpecific
    locations: dict[LocationID, InternalTeamLocationData]
    missions: dict[MissionID, InternalTeamMissionData]
    tasks: dict[TaskID, InternalTeamTaskData]

    def to_snapshot(self) -> GameDataTeamSpecific:
        locations = [location.dict() for location in self.locations.values()]
        missions = []
        for mission in self.missions.values():
            task_list = []
            for task in mission.tasks:
                task_data = self.tasks[task]
                task_list.append(TaskDataTeamSpecific(**task_data.dict()))
            mission_data = mission.dict() | {"taskList": task_list}
            missions.append(mission_data)

        return GameDataTeamSpecific(
            currentStatus=self.currentStatus,
            session=self.session,
            ship=self.ship,
            locations=locations,
            missions=missions,
        )
