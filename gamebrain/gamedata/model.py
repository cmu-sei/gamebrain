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
    Visible: bool
    Complete: bool


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
    TaskList: list[TaskData] = None


class MissionDataTeamSpecific(BaseModel):
    MissionID: str
    Unlocked: bool
    Visible: bool
    Complete: bool


class MissionDataFull(MissionData, MissionDataTeamSpecific):
    ...


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
    Unlocked: bool
    Visited: bool
    Scanned: bool
    NetworkEstablished: bool


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
    currentLocationScanned: bool
    currentLocationSurroundings: str
    antennaExtended: bool
    networkConnected: bool
    networkName: str
    firstContactComplete: bool
    powerStatus: str
    incomingTransmission: bool
    incomingTransmissionObject: CommEventData | None


class GameDataTeamSpecific(BaseModel):
    currentStatus: CurrentLocationGameplayDataTeamSpecific
    session: SessionDataTeamSpecific
    ship: ShipDataTeamSpecific
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