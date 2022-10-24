import enum
from typing import Literal

from pydantic import BaseModel, AnyUrl


TaskCompletionType = Literal[
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
    locationID: LocationID


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
