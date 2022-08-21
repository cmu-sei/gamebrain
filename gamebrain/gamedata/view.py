from typing import Literal

from pydantic import BaseModel, AnyUrl


class TaskData(BaseModel):
    TaskID: str
    MissionID: str
    DescriptionText: str
    Visible: bool
    Complete: bool
    InfoPresent: bool
    InfoText: str
    VideoPresent: bool
    VideoURL: str
    CommID: str


class MissionData(BaseModel):
    MissionID: str
    Unlocked: bool
    Visible: bool
    Complete: bool
    Title: str
    SummaryShort: str
    SummaryLong: str
    MissionIcon: str
    IsSpecial: bool
    RuleList: list[str]
    TaskList: list[TaskData] = None


class LocationData(BaseModel):
    LocationID: str
    Name: str
    ImageID: str
    BackdropID: str
    Unlocked: bool
    Visited: bool
    Scanned: bool
    Surroundings: str
    UnlockCode: str
    NetworkEstablished: bool
    NetworkName: str
    FirstContactEvent: str
    TrajectoryLaunch: int
    TrajectoryCorrection: int
    TrajectoryCube: int


class ShipData(BaseModel):
    CodexURL: AnyUrl
    Workstation1URL: AnyUrl
    Workstation2URL: AnyUrl
    Workstation3URL: AnyUrl
    Workstation4URL: AnyUrl
    Workstation5URL: AnyUrl


class SessionData(BaseModel):
    TeamInfoName: str
    TeamCodexCount: int
    JumpCutsceneURL: AnyUrl


class CommEventData(BaseModel):
    CommID: str
    VideoURL: str
    CommTemplate: str
    TranslationMessage: str
    ScanInfoMessage: str
    FirstContact: bool
    LocationID: str


class CurrentLocationGameplayData(BaseModel):
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


class GameData(BaseModel):
    currentStatus: CurrentLocationGameplayData
    session: SessionData
    ship: ShipData
    locations: list[LocationData]
    missions: list[MissionData]


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
