from typing import Literal

from pydantic import BaseModel, AnyUrl


class TaskData(BaseModel):
    TaskID: str
    MissionID: str
    DescriptionText: str
    InfoPresent: bool
    InfoText: str
    VideoPresent: bool
    VideoURL: str
    CommID: str


class TaskDataTeamSpecific(BaseModel):
    TaskID: str
    Visible: bool = True
    Complete: bool = False


class TaskDataFull(TaskData, TaskDataTeamSpecific):
    ...


class MissionData(BaseModel):
    MissionID: str
    Title: str
    SummaryShort: str
    SummaryLong: str
    MissionIcon: str
    IsSpecial: bool
    RuleList: list[str]
    TaskList: list[TaskData]


class MissionDataTeamSpecific(BaseModel):
    MissionID: str
    Unlocked: bool
    Visible: bool
    Complete: bool
    TaskList: list[TaskDataTeamSpecific]


class MissionDataFull(MissionData, MissionDataTeamSpecific):
    TaskList: list[TaskDataFull]


class LocationData(BaseModel):
    LocationID: str
    Name: str
    ImageID: str
    BackdropID: str
    Surroundings: str
    UnlockCode: str
    TrajectoryLaunch: int
    TrajectoryCorrection: int
    TrajectoryCube: int
    FirstContactEvent: str
    NetworkName: str


class LocationDataTeamSpecific(BaseModel):
    LocationID: str
    Unlocked: bool = True
    Visited: bool = False
    Scanned: bool = False
    NetworkEstablished: bool = False


class LocationDataFull(LocationData, LocationDataTeamSpecific):
    ...


class ShipDataTeamSpecific(BaseModel):
    CodexURL: AnyUrl
    Workstation1URL: AnyUrl
    Workstation2URL: AnyUrl
    Workstation3URL: AnyUrl
    Workstation4URL: AnyUrl
    Workstation5URL: AnyUrl


class SessionDataTeamSpecific(BaseModel):
    TeamInfoName: str
    TeamCodexCount: int
    JumpCutsceneURL: AnyUrl


class CommEventData(BaseModel):
    CommID: str
    VideoURL: str
    CommTemplate: Literal["incoming", "probe", "badTranslation"]
    TranslationMessage: str
    ScanInfoMessage: str
    FirstContact: bool
    LocationID: str


class CurrentLocationGameplayDataTeamSpecific(BaseModel):
    currentLocation: str
    currentLocationScanned: bool = False
    currentLocationSurroundings: str
    antennaExtended: bool = False
    networkConnected: bool = False
    networkName: str
    firstContactComplete: bool = False
    powerStatus: str
    incomingTransmission: bool = False
    incomingTransmissionObject: CommEventData | None = None


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
    ResponseStatus: Literal["success", "invalid", "alreadyunlocked"]
    LocationID: str
    EnteredCoordinates: str


class ScanResponse(GenericResponse):
    EventWaiting: bool
    CommID: CommEventData | None
