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

from ..commonmodels import ConsoleUrl
from datetime import datetime
import enum
from typing import Literal

from pydantic import BaseModel, root_validator


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
DispatchID = str
Regex = str


# This model corresponds to data in a Workspace's document.
class Dispatch(BaseModel):
    id: DispatchID
    vm_name: str
    # command will sometimes need weird workarounds such as the following:
    # bash -c "cat /home/user/audit && rm /home/user/audit"
    command: str
    # Minimum time in seconds before this dispatch is created.
    trigger_delay: int
    # Patterns to search in the command output for success/fail.
    success_text: Regex = ""
    # List of dispatches to trigger on success/fail/every completion.
    if_success: list[DispatchID] = []
    fail_text: Regex = ""
    if_fail: list[DispatchID] = []
    always_run: list[DispatchID] = []


class GamespaceData(BaseModel):
    # A workspace without a task ID denotes a ship gamespace.
    # Mutually exclusive with gatewayVmName and gatewayNic.
    taskID: TaskID | None
    # A location ID is used to determine which gamespace ID
    # to use when extending the ship antenna.
    locationID: str | None
    # If location ID is defined in a challenge workspace,
    # the following two will also need to be defined OR
    # set noGateway: true in the workspace document.
    gatewayVmName: str | None
    gatewayNic: int | None
    noGateway: bool = False
    # Whether the VM consoles listed in this workspace will be
    # pushed to players.
    visible: bool = True
    # Next two are currently unused.
    dispatches: list[Dispatch] = []
    initial_dispatches: list[DispatchID] = []
    # Filled in by Gamebrain, not Topomojo.
    gamespaceID: GamespaceID
    consoleURLs: list[ConsoleUrl]
    # Only the ship workspace should have the following values.
    useGalaxyDisplayMap: bool = True
    useCodices: bool = False
    timerTitle: str = ""
    gatewayWanNetworkName: str | None
    isPC4Workspace: bool = False
    # The next four may be specified in the workspace document
    # OR the game data JSON. Values specified in the workspace
    # document will take priority.
    galaxyMapXPos: float = 0.0
    galaxyMapYPos: float = 0.0
    galaxyMapTargetXPos: float = 0.0
    galaxyMapTargetYPos: float = 0.0

    @root_validator
    def validate_taskID_gatewayVmName_and_gatewayNic(cls, values):
        def raise_and_error(specified, unspecified):
            raise ValueError(
                f"If {specified} is specified, {unspecified} "
                "must also be specified."
            )

        # Specifically check if these were unspecified or null.
        (locationID,
         noGateway,
         gatewayVmName,
         gatewayNic) = (values.get("locationID") is not None,
                        values.get("noGateway") is not None,
                        values.get("gatewayVmName") is not None,
                        values.get("gatewayNic") is not None)
        if locationID and not noGateway:
            if not gatewayVmName and not gatewayNic:
                raise_and_error("locationID", "gatewayVmName and gatewayNic")
            elif not gatewayVmName:
                raise_and_error("locationID", "gatewayVmName")
            elif not gatewayNic:
                raise_and_error("locationID", "gatewayNic")

        return values


class TeamGamespaceInfo(BaseModel):
    ship_gamespace_id: GamespaceID
    ship_gamespace_data: GamespaceData
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
    # Pretend the task is incomplete when the ship is away from its
    # completion location, the current status is incorrect (a markCompleteWhen
    # which requires exploration mode when the ship is in launch mode, for
    # example) AND the associated mission is not complete. Only applied when
    # markCompleteWhen is specified with a location.
    # Purely for appearance - internal state is not changed, only what is
    # sent to the game server. Primarily meant for "explorationMode",
    # or "antennaExtended" at the moment.
    showIncompleteWhenAwayOrStatusIncorrect: bool = False


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

    # Mostly for testing purposes. Enables adding coordinates through
    # the game data document without creating a workspace.
    galaxyMapXPos: float = 0.0
    galaxyMapYPos: float = 0.0
    galaxyMapTargetXPos: float = 0.0
    galaxyMapTargetYPos: float = 0.0


class MissionDataTeamSpecific(BaseModel):
    missionID: MissionID
    unlocked: bool = True
    visible: bool = True
    complete: bool = False
    taskList: list[TaskDataTeamSpecific]
    gamespaceID: str = None


class MissionScoreData(BaseModel):
    current_score: int
    possible_max_score: int
    base_solve_value: int
    bonus_remaining: int


class AssociatedChallengeData(BaseModel):
    missionID: MissionID
    unlockCode: str


class MissionDataFull(MissionData, MissionDataTeamSpecific):
    taskList: list[TaskDataFull]

    associatedChallenges: list[AssociatedChallengeData] = []

    # The next four come from the workspace document.
    galaxyMapXPos: float = 0.0
    galaxyMapYPos: float = 0.0
    galaxyMapTargetXPos: float = 0.0
    galaxyMapTargetYPos: float = 0.0

    # Comes from a call to gameboard's team-score.
    currentScore: int = 0
    possibleMaximumScore: int = 0
    baseSolveValue: int = 0
    bonusRemaining: int = 0

    # Total teams in game overall.
    totalTeams: int = 0
    # Teams who have completed the challenge.
    solveTeams: int = 0


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


class VmURL(BaseModel):
    vmName: str
    vmURL: str


class ChallengeURLs(BaseModel):
    missionID: MissionID
    missionIcon: str
    missionName: str
    vmURLs: list[VmURL]


class ShipDataTeamSpecific(BaseModel):
    class Config:
        use_enum_values = True

    codexURL: str = ""
    workstation1URL: str = ""
    workstation2URL: str = ""
    workstation3URL: str = ""
    workstation4URL: str = ""
    workstation5URL: str = ""
    challengeURLs: list[ChallengeURLs] = None
    commPower: PowerStatus = PowerStatus.off
    flightPower: PowerStatus = PowerStatus.off
    navPower: PowerStatus = PowerStatus.off
    pilotPower: PowerStatus = PowerStatus.off
    nextJumpTime: str = ""
    gamespaceData: GamespaceData = None


class SessionDataTeamSpecific(BaseModel):
    teamInfoName: str = None
    teamCodexCount: int = 0
    jumpCutsceneURL: str
    useGalaxyDisplayMap: bool = True
    useCodices: bool = False
    displayIncompleteMissionPogs: bool = False
    timerTitle: str = ""
    gameStartTime: datetime = datetime.fromordinal(1)
    gameEndTime: datetime = datetime.fromordinal(36000)
    gameCurrentTime: datetime = datetime.fromordinal(1)


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

    pc4_handling_cllctn6: datetime = datetime.now()

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

    # This is special handling for PC4 games.
    pc4_handling_cllctn6: datetime = datetime.now()

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
