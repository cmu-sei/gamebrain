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


class TaskCompletion(BaseModel):
    type: TaskCompletionType
    locationID: str


class TaskData(BaseModel):
    taskID: str
    missionID: str
    descriptionText: str
    infoPresent: bool = True
    infoText: str
    videoPresent: bool = True
    videoURL: str
    commID: str
    markCompleteWhen: TaskCompletion = None


class TaskDataTeamSpecific(BaseModel):
    taskID: str
    visible: bool = True
    complete: bool = False


class TaskDataFull(TaskData, TaskDataTeamSpecific):
    ...


class MissionData(BaseModel):
    missionID: str
    title: str
    summaryShort: str
    summaryLong: str
    missionIcon: str
    isSpecial: bool = False
    roleList: list[str]
    taskList: list[TaskData]


class MissionDataTeamSpecific(BaseModel):
    missionID: str
    unlocked: bool = True
    visible: bool = False
    complete: bool = False
    taskList: list[TaskDataTeamSpecific]


class MissionDataFull(MissionData, MissionDataTeamSpecific):
    taskList: list[TaskDataFull]


class LocationData(BaseModel):
    locationID: str
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
    locationID: str
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
    commID: str
    videoURL: str
    commTemplate: Literal["incoming", "probe", "badTranslation"]
    translationMessage: str
    scanInfoMessage: str
    firstContact: bool
    locationID: str


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
    locationID: str
    enteredCoordinates: str


class ScanResponse(GenericResponse):
    eventWaiting: bool
    incomingTransmission: CommEventData | None
