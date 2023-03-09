# Gamebrain

## Overview

This application controls the game logic for the Cubespace game. It interacts with both Gameboard and Topomojo in its operation - Gameboard to know when to deploy a game and post scores, and Topomojo to check the state of the team's workspace.

## settings.yaml

The `settings.yaml` file holds all of the environment settings, as well as a few game settings. There is an example `settings.yaml` in this directory.

> ### ca_cert_path: str

(Optional) This is a path to a CA certificate file used to authenticate Gameboard and Topomojo. Default is null, which makes the application trust the system's default CA certificates instead.

> ### app_root_prefix: str

(Optional) A URL path prefix for all endpoints. Default is "/gamebrain".

> ### identity: dict

This is a section that has various subkeys related to interactions with Identity server.

>> #### base_url: str

Used to communicate with Identity.

>> #### token_endpoint: str

Used as a suffix to the base URL when retrieving a token.
    
>> #### jwks_endpoint: str

Used to validate received tokens.

>> #### client_id: str

A client should be made in Identity specifically for Gamebrain. Its ID should be provided here. Currently this client must be a Resource Owner.

>> #### client_secret: str

Generate a secret for the Gamebrain client and supply it here.

>> #### jwt_issuer: str

Usually will be the same as base_url, but not necessarily. Check other tokens from Identity to verify the issuer.

>> #### token_user: str

A real user account needs to be created for Gameboard interactions.

>> #### token_password: str

The password for the above account.
    
>> #### jwt_audiences: dict

Configuration section for JWT **scopes** for API endpoints. The name is a holdover from early development.

>>> ##### gamebrain_api_unpriv: str

This scope is required for an individual player's identity token.

>>> ##### gamebrain_api_priv: str

(Optional) This scope is deprecated, but currently required to be specified. An empty string is fine.

>>> ##### gamestate_api: str

This scope is required for any interactions with the game logic API. This should be included in the Cubespace server's authentication token.

> ### topomojo: dict

This is a section with keys related to interactions with Topomojo.

>> #### base_api_url: str

This will usually be a URL to Topomojo ending in `/api` or `/api/`.

>> #### x_api_client: str

Gamebrain will need a configured bot account in Topomojo with Observer permission enabled in order to do its work. The name of that bot account should be inserted here.

>> #### x_api_key: str

Generate a secret for the created bot account and insert it here.

> ### gameboard: dict

This is a section with keys related to interactions with Gameboard.

>> #### base_url: str

Gameboard's base URL.

>> #### base_api_url: str

Gameboard's API URL. This will usually, but not necessarily, start with `base_url` and then end with `/api` or `/api/`.

> ### db: dict

>> #### connection_string: str

This option is directly passed to [create_async_engine](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#sqlalchemy.ext.asyncio.create_async_engine). By default, `requirements.txt` only includes the `asyncpg` package, and that is the only one that has been tested. It should be possible to swap the async engine to use another database by installing another async package, but it has never been tested.

>> #### drop_app_tables: bool

(Optional) Mostly used for testing. This will drop all tables associated with Gamebrain on startup. Defaults to false.

>> #### echo_sql: bool

(Optional) Mostly used for testing. Print out all SQL commands executed. Defaults to false.

> ### game: dict

These settings set certain game parameters that are not set within the game initial state file.

>> #### event_actions: list[dict]

Deprecated.

>> #### gamespace_duration_minutes: int

(Optional) Maximum time a gamespace can exist (subject to Topomojo settings). Why is this here instead of Topomojo settings? I have no idea.

>> #### ship_network_vm_name: str

Deprecated.

>> #### antenna_vm_name: str 

This is the name of the VM used as a gateway to challenges within the game's Topomojo workspace. It will have its network changed at each location when the in-game antenna is extended or retracted based on data in the game state.

>> #### antenna_retracted_network: str

When the antenna is retracted, the VM named above will be set on this network. At the time of writing, It should have a `:1` or `:2` suffix to denote which network interface should be switched (`:1` denotes the first interface).

>> #### grading_vm_name: str

This is the main grading VM. This VM will have some scripting that allows it to report completed codexes.

>> #### grading_vm_dispatch_command: str

This is the command that will periodically run on the above grading VM. The command should print the following keys in JSON format (values can be "success" or "fail" for the first six listed keys, "up" or "down" for the remainder):

```
{
  exoArch: fail,
  redRaider: success,
  ancientRuins: fail,
  xenoCult: fail,
  museum: fail,
  finalGoal: fail,
  comms: up,
  flight: up,
  nav: down,
  pilot: up
}
```

>> #### final_destination_name: str

The location ID of the "win" location, as it is specified within the game initial state JSON.

>> #### final_destination_file_path: str

The name of a file to create on the **grading VM** to make it aware that the final goal is complete within the game.

>> #### challenge_tasks: list[dict]

A list of dictionaries with the following keys:

>>> ##### task_id: str

Task ID that corresponds to a task in the JSON game data which needs to be completed within the team's gamespace.

>>> ##### vm_name: str
A VM to run a command on. This VM should not be accessible to players.

>>> ##### dispatch_command: str

A command to execute on the target VM. The result of the command should include the string "success" or "fail".

>> #### gamestate_test_mode: bool

Deprecated.

>> #### game_id: str

The Gameboard Game ID which launches teams into the Cubespace game.

>> #### headless_client_urls: dict[str, str]

`key: value` pairs addressing each cubespace headless server. The key is the `hostname` the server program can see within its environment. The value is a public URL to the server.

> ### profiling: bool

(Optional) Whether to turn performance profiling on or not. Mostly used for development purposes. Default is false.

> ### gamebrain_admin_api_key: str

This is a key that will be shared with Gameboard API so that it can deploy and undeploy Cubespace games. Also used to call test endpoints.

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
