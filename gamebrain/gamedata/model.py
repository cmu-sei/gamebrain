import enum
from typing import Literal

from pydantic import BaseModel, AnyUrl


class TaskData(BaseModel):
    TaskID: str
    MissionID: str
    DescriptionText: str
    InfoPresent: bool = True
    InfoText: str
    VideoPresent: bool = True
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
    IsSpecial: bool = False
    RuleList: list[str]
    TaskList: list[TaskData]


class MissionDataTeamSpecific(BaseModel):
    MissionID: str
    Unlocked: bool = True
    Visible: bool = False
    Complete: bool = False
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


class PowerStatus(enum.Enum):
    On = "on"
    Off = "off"


class ShipDataTeamSpecific(BaseModel):
    CodexURL: AnyUrl
    Workstation1URL: AnyUrl
    Workstation2URL: AnyUrl
    Workstation3URL: AnyUrl
    Workstation4URL: AnyUrl
    Workstation5URL: AnyUrl
    CodexStationPower: PowerStatus = PowerStatus.Off
    CommPower: PowerStatus = PowerStatus.Off
    FlightPower: PowerStatus = PowerStatus.Off
    NavPower: PowerStatus = PowerStatus.Off
    PilotPower: PowerStatus = PowerStatus.Off


class SessionDataTeamSpecific(BaseModel):
    TeamInfoName: str = None
    TeamCodexCount: int = 0
    JumpCutsceneURL: AnyUrl


class CommEventData(BaseModel):
    CommID: str
    VideoURL: str
    CommTemplate: Literal["incoming", "probe", "badTranslation"]
    TranslationMessage: str
    ScanInfoMessage: str
    FirstContact: bool
    LocationID: str


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
