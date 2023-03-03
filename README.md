# Gamebrain

## Overview

This application controls the game logic for the Cubespace game. It interacts with both Gameboard and Topomojo in its operation - Gameboard to know when to deploy a game and post scores, and Topomojo to check the state of the team's workspace.

## settings.yaml

The `settings.yaml` file holds all of the environment settings, as well as a few game settings. There is an example `settings.yaml` in this directory with each field commented.

## initial_state.json

`initial_state.json` contains the 2022 game missions, tasks, and locations.

> ### comm_map

A JSON object containing objects with the following fields:

```
  commID: CommID - A unique identifier for this comm event.
  videoURL: str - Which video should play when this comm event is viewed.
  commTemplate: Literal["incoming", "probe", "badTranslation"] - "incoming" denotes a message coming from an alien, "probe" represents the result of a scan, and "badTranslation" denotes that a challenge must be completed. These are primarily flavor options.
  translationMessage: str - Message shown before initiating the scan.
  scanInfoMessage: str - Message shown after scanning.
  firstContact: bool - Whether this event is considered to be the first contact event for some location.
  locationID: LocationID - The identifier of the location at which this event will play.
```

> ### location_map

A JSON object containing objects with the following fields:

```
  locationID: LocationID - a unique identifier for this location.
  name: str - The name shown in the navigation console for this location.
  imageID: str - The image shown in the navigation console for this location. Part of the game client assets.
  backdropID: str - The image shown when at this location. Part of the game client assets.
  surroundings: str - Text shown when at the location.
  unlockCode: str - Code that players can input at the navigation console to unlock this location. Only relevant if not unlocked initially.
  trajectoryLaunch: int - Top dial value at the piloting console.
  trajectoryCorrection: int - Middle dial value at the piloting console.
  trajectoryCube: int - Bottom dial value at the piloting console.
  firstContactEvent: str - The identifier of this location's first contact event, if there is one.
  networkName: str - The name of the network to switch to when the antenna is extended at this location on the Antenna VM specified in settings.yaml. To switch any network interface aside from the first, TopoMojo requires a suffix of ":0", ":1", ":2", etc. The suffix is not required for changing the first network interface.
```

> ### mission_map

A JSON object containing objects with the following fields:

```
  missionID: MissionID - A unique identifier for this mission.
  title: str - The title shown in the mission log of the mission.
  summaryShort: str - The summary shown in the list of missions in-game. Supports HTML formatting.
  summaryLong: str - The summary shown on the right pane when the mission is selected. Supports HTML formatting.
  missionIcon: str - Icon shown in the mission log. Part of the game client assets.
  isSpecial: bool = False - Highlight the mission in the log to make it look special. Effect is visual only.
  roleList: list[str] - The list of work roles associated with this mission.
  taskList: list[TaskDataIdentifierStub] - A list of objects whose only key is "taskID", with a value equalling one of the task identifiers in the task map.
  points: int - The number of points awarded for this mission's completion.
```

> ### task_map

A JSON object containing objects with the following fields:

```
  taskID: TaskID - A unique identifier for this task.
  missionID: MissionID - The identifier of the mission this task is associated with.
  descriptionText: str - A summary of the task shown in the list of tasks for a mission in the mission log when a mission is selected.
  infoPresent: bool - Whether the task has more detailed information.
  infoText: str - More detailed information about the requirements for completing this task, shown when a task is selected from the mission log. Supports HTML formatting.
  videoPresent: bool - Indicates whether the task has a video associated with it after it completes. Generally used for tasks triggering comm events.
  videoURL: str - The URL of the video if there is one.
  commID: CommID - The identifier of an associated comm event, if there is one.
  next: TaskID - The identifier of the next task to show when this one is completed.
  completesMission: bool - Mark the associated mission complete when this task is completed.
  markCompleteWhen: TaskBranch - Criteria for marking this task complete. See below for TaskBranch structure.
  failWhen: TaskBranch - Criteria for a "fail" path for this task. The task itself does not actually fail, but can be used to show a remediation task in the task log, for example to tell the players that they will need to try again.
  cancelWhen: TaskBranch - Criteria to clear this task from the task log. Can be used to clear a remediation task once it's done.
```

> #### TaskBranch

```
  type: Literal[
    "comm", - Watch a comm event.
    "jump", - Jump to a location.
    "explorationMode", - Change the ship's power mode to exploration mode.
    "launchMode", - Change the ship's power mode to launch mode.
    "standby", - Change the ship's power mode to standby mode.
    "scan", - Initiate a scan at a location.
    "antennaExtended", - Extend the antenna.
    "antennaRetracted", - Retract the antenna.
    "challenge", - A challenge is completed. See settings.yaml's game.challenge_tasks setting to set up the task dispatches.
    "challengeFail", - A challenge is failed. See settings.yaml's game.challenge_tasks setting to set up the task dispatches.
    "codex", - A codex has been decoded. Codex tasks are not currently configurable.
    "indirect", - Indicate that this branch is triggered by another task's alsoComplete. Only valid if this task branch is a completion branch.
]
  locationID: LocationID - (Optional) The location at which this branch is triggered.
  alsoComplete: list[TaskID] - (Optional) A list of task identifiers to also mark complete. The target tasks must be "indirect" type.
  unlocks: TaskID - (Optional) A task to unlock on this branch. Primarily used with failure branches to unlock a remediation task.
  unlockLocation: LocationID - (Optional) A location identifier to unlock when this task branch is triggered.
  indirectPrerequisiteTasks: list[TaskID] - A list of tasks that are required before this task is marked complete. Only valid for "indirect" completion branches.
```

> ### team_map

Internal use only. It is not recommended to use this field.

> ### team_initial_state

This section controls the starting conditions for a team that has just started a run of the game. Its top-level structure is a JSON object with the following structure, and note the last two fields are both lists:

```
  currentStatus: CurrentLocationGameplayDataTeamSpecific
  session: SessionDataTeamSpecific
  ship: ShipDataTeamSpecific
  locations: list[LocationDataTeamSpecific]
  missions: list[MissionDataTeamSpecific]
```

> #### CurrentLocationGameplayDataTeamSpecific

```
  currentLocation: str - Starting location.
  currentLocationScanned: bool - In the game client, switches the screen used and activates the scan screen based on whether the current location has been scanned and its surroundings.
  currentLocationSurroundings: str - The "surroundings" text which shows at the current location in the game client.
  antennaExtended: bool - Used for the antenna lever's position.
  networkConnected: bool - Whether a network shows as connected in the game client.
  networkName: str - The name of the connected network if the above is true.
  firstContactComplete: bool - Setting to true blocks extending the antenna until the first contact event is completed.
  powerStatus: Literal["launchMode", "explorationMode", "standby"] - The current power mode. Does not affect individual console power settings, only the overall power setting.
  incomingTransmission: bool - Whether a comm event is available. Generally best to leave this set to false for the initial state and use tasks to make a comm event available.
  incomingTransmissionObject: CommEventData | null - The full comm event data of an active comm event. See the comm_map section for details.
```

> #### SessionDataTeamSpecific

```
  teamInfoName: str - The display name of the team. This value gets updated with the team's Gameboard team ID.
  teamCodexCount: int - The number of codexes the team currently has. Usually should be set to 0 for the initial state.
  jumpCutsceneURL: str - The cutscene video to be displayed when jumping to a new location.
```

> #### ShipDataTeamSpecific

The fields for this structure are all required, but the URLs can be set to empty strings ("") or any default URL. They are updated via endpoint called from Gameboard after deployment. The power settings can be set to "off" or "on" but they are not currently in use.

```
  codexURL: str
  workstation1URL: str
  workstation2URL: str
  workstation3URL: str
  workstation4URL: str
  workstation5URL: str
  commPower: Literal["off", "on"] - Communication console power. Currently unused.
  flightPower: Literal["off", "on"] - Flight console power. Currently unused.
  navPower: Literal["off", "on"] - Navigation console power. Currently unused.
  pilotPower: Literal["off", "on"] - Pilot console power. Currently unused.
```

> #### LocationDataTeamSpecific

```
  locationID: LocationID - The identifier for this location.
  unlocked: bool - Whether the location shows in the list of travel destinations.
  visited: bool - Whether the first contact comm event has been completed at this location.
  scanned: bool - Whether or not the location has been marked as scanned.
  networkEstablished: bool - Unused.
```

> #### MissionDataTeamSpecific

```
  missionID: MissionID - The identifier for this mission.
  unlocked: bool - Whether the mission is considered unlocked internally.
  visible: bool - Whether the mission shows up in the mission log.
  complete: bool - Whether this mission is complete. Most of the time this should be false.
  taskList: list[TaskDataTeamSpecific] - See below for TaskDataTeamSpecific structure.
```

> ##### TaskDataTeamSpecific

```
  taskID: TaskID - The identifier for this task.
  visible: bool - Whether this task is displayed in the mission log task list.
  complete: bool - Whether this task is complete.
```


## Setup

After setting up your environment and settings, you need to install dependencies. If you are using Docker, you can just run `docker build . -t gamebrain:latest` to build and tag an image that can be used with any Docker environment. Otherwise you will need to create a Python 3.10+ [virtual environment](https://docs.python.org/3/tutorial/venv.html) and then run `pip install -r requirements.txt` in this directory to install all of the project dependencies.

[Uvicorn](https://www.uvicorn.org/#usage) is installed as a dependency, and it is recommended. `uvicorn gamebrain.app:APP` should start the server.
