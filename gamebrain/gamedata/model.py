import enum
from typing import Literal

from pydantic import BaseModel, AnyUrl


TaskCompletionType = Literal[
    "comm",
    "jump",
    "explorationMode",
    "launchMode",
    "standby",
    "scan",
    "antennaExtended",
    "antennaRetracted",
    "challenge",
    "codex",
]


CommID = str
MissionID = str
LocationID = str
TaskID = str


class TaskCompletion(BaseModel):
    type: TaskCompletionType
    locationID: LocationID = None


class TaskData(BaseModel):
    taskID: TaskID
    missionID: MissionID
    descriptionText: str
    infoPresent: bool = True
    infoText: str
    videoPresent: bool = True
    videoURL: str
    commID: CommID
    markCompleteWhen: TaskCompletion = None


class TaskDataTeamSpecific(BaseModel):
    taskID: TaskID
    visible: bool = True
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


class MissionDataTeamSpecific(BaseModel):
    missionID: MissionID
    unlocked: bool = True
    visible: bool = False
    complete: bool = False
    taskList: list[TaskDataTeamSpecific]


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

    codexURL: AnyUrl
    workstation1URL: AnyUrl
    workstation2URL: AnyUrl
    workstation3URL: AnyUrl
    workstation4URL: AnyUrl
    workstation5URL: AnyUrl
    commPower: PowerStatus = PowerStatus.off
    flightPower: PowerStatus = PowerStatus.off
    navPower: PowerStatus = PowerStatus.off
    pilotPower: PowerStatus = PowerStatus.off


class SessionDataTeamSpecific(BaseModel):
    teamInfoName: str = None
    teamCodexCount: int = 0
    jumpCutsceneURL: AnyUrl


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
                    filter(lambda t: t.complete is False, mission_data.taskList)
                ).taskID
            except StopIteration:
                current_task = None
            missions[mission_data.missionID] = mission_data.dict() | {
                "current_task": current_task
            }

            for task_data in mission_data.taskList:
                tasks[task_data.taskID] = task_data.dict()

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
    incomingTransmission: CommEventData | None


class InternalCommEvent(CommEventData):
    associated_task: TaskID

    def to_snapshot(self) -> CommEventData:
        return CommEventData(**self.dict())


class InternalGlobalLocationData(LocationData):
    ...


class InternalTeamLocationData(LocationDataTeamSpecific):
    ...


class InternalGlobalTaskData(TaskData):
    next: TaskID | None
    prev: TaskID | None


class InternalTeamTaskData(TaskDataTeamSpecific):
    ...


class InternalGlobalMissionData(MissionData):
    first_task: TaskID


class InternalTeamMissionData(MissionDataTeamSpecific):
    current_task: TaskID | None


class InternalTeamGameData(BaseModel):
    currentStatus: CurrentLocationGameplayDataTeamSpecific
    session: SessionDataTeamSpecific
    ship: ShipDataTeamSpecific
    locations: dict[LocationID, InternalTeamLocationData]
    missions: dict[MissionID, InternalTeamMissionData]
    tasks: dict[TaskID, InternalTeamTaskData]

    def to_snapshot(self) -> GameDataTeamSpecific:
        locations = [location.dict() for location in self.locations.values()]
        missions = [mission.dict() for mission in self.missions.values()]

        return GameDataTeamSpecific(
            currentStatus=self.currentStatus,
            session=self.session,
            ship=self.ship,
            locations=locations,
            missions=missions,
        )
