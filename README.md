# Gamebrain

## Overview

This application controls the game logic for the Cubespace game. It interacts with both Gameboard and Topomojo in its operation - Gameboard to know when to deploy a game and post scores, and Topomojo to check the state of the team's workspace.

## Configuration

### settings.yaml

The `settings.yaml` file holds all of the environment settings, as well as a few game settings. There is an example `settings.yaml` in this directory with each field commented.

### initial_state.json

`initial_state.json` is an example flle containing the 2022 game missions, tasks, and locations. It is provided as an example of the structure, but the contents should be changed to reflect your intended use case. 

#### `comm_map`

The communications mapping is a JSON object which provides information needed by the communications system. This system is responsible for managing when video based content is provided to end users within the shipboard interface. These messages can appear for a variety of reasons - in response to being "hailed" by another ship, in response to "scanning" an area, or other events related to the narrative. 

The object supports the following fields:

| Field name | type | Description |
| --- | --- | --- |
| commID | string | An identifier for a comm event. Must be unique. |
| videoURL | string | Which video should play when this comm event is viewed. |
| commTemplate | Literal | Valid values are: "incoming", "probe", "badTranslation". <br/>"incoming" denotes a message coming from an alien.<br/>"probe" represents the result of a scan.<br/>"badTranslation" denotes that a challenge must be completed before content is available. |
| translationMessage | string | This text will be displayed to a player as placeholder text if no scan has been is initiated. This is most often used as a call to action such as - "No scan data available, intitiate scan to access." |
| scanInfoMessage | string | This text will be shown after scanning. |
| firstContact | bool | This determines if this event is considered to be the first contact event for some location. First contact events unlock follow-on activities at that location (such as allowing access to challenge content). This is intended to prevent participants from accessing material without having viewed the relevant lead-in content). |
| locationID | string | The identifier of the location at which this event will play. This string must match a valid location name. |


#### `location_map`

The location mapping is a JSON object which provides information about the various locations which participants can travel to during the course of a game. 

The object supports the following fields: 

| Field name | type | Description |
| --- | --- | --- |
| locationID | string | An identifier for a location. Must be unique. | 
| name | string | The name shown in the Cubespace navigation console for this location. |
| imageID | string | The image shown in the Cubespace navigation console for this location. Must match the Cubespace client asset name. |
| backdropID | string | The image shown in the background by Cubespace when at this location. Must match the Cubespace client asset name. |
| surroundings | string | Text shown when at the location. |
| unlockCode | string | Code that players can input at the navigation console to unlock this location. Only relevant if not unlocked initially. |
| trajectoryLaunch | int | Top dial value at the piloting console. |
| trajectoryCorrection | int | Middle dial value at the piloting console. |
| trajectoryCube | int | Bottom dial value at the piloting console. |
| firstContactEvent | string | The identifier of this location's first contact event, if there is one. |
| networkName | string | The name of the network to switch to when the antenna is extended at this location on the Antenna VM specified in settings.yaml. To switch any network interface aside from the first, TopoMojo requires a suffix of ":0", ":1", ":2", etc. The suffix is not required for changing the first network interface. |


#### `mission_map`

The mission mapping is a JSON object which provides information about the different missions participants can undertake during the course of a game to earn points. These missions hold lists of tasks within them which guide players through mission completion.

The object supports the following fields:

| Field name | type | Description |
| --- | --- | --- |
| missionID | string | An identifier for a mission. Must be unique. |
| title | string | The title shown in the mission log of the mission. |
| summaryShort | string | The summary shown in the list of missions in-game. Supports HTML formatting. |
| summaryLong | string | The summary shown on the right pane when the mission is selected. Supports HTML formatting. |
| missionIcon | string | The icon shown in the mission log. Must match the Cubespace client asset name. |
| isSpecial | bool | This determines whether to highlight the mission in the log to make it look special. This effect is visual only. Defaults to `False`. |
| roleList | list[string] | The list of NICE work roles associated with this mission. |
| taskList | list[TaskDataIdentifierStub] | A list of objects whose only key is "taskID", with a value equal to one of the task identifiers in the task map. |
| points | int | The number of points awarded for this mission's completion. |


#### `task_map`

The task mapping is a JSON object which provides information about the different tasks each mission can hold. Each task list acts as a set of instructions for players as they move through a mission.

The object supports the following fields:

| Field name | type | Description |
| --- | --- | --- |
| taskID | string | An identifier for a mission. Must be unique. |
| missionID | string | The identifier of the mission this task is associated with. This does not have to be unique, as multiple tasks should be assigned to the same mission. |
| descriptionText | string | A short summary, shown for this task in the task list of a mission when a player selects that mission in the mission log. |
| infoPresent | bool | Whether the task has more detailed information. |
| infoText | string | More detailed information about the requirements for completing this task, shown when a task is selected from the mission log. Supports HTML formatting. |
| videoPresent | bool | Indicates whether the task has a video associated with it after it completes. Generally used for tasks triggering comm events. |
| videoURL | string | The URL of the video to show with this task, if there is one. |
| commID | string | The identifier of an associated comm event, if there is one. |
| next | string | The identifier of the next task to show when this one is completed. |
| completesMission | bool | This determines if the associated mission should be marked as complete when this task is completed. |
| markCompleteWhen | TaskBranch | Criteria for marking this task complete. See below for TaskBranch structure. |
| failWhen | TaskBranch | Criteria for a "fail" path for this task. The task itself does not actually fail, but this can be used to show a remediation task in the task log, for example to tell the players that they will need to try again. |
| cancelWhen | TaskBranch | Criteria to clear this task from the task log. Can be used to clear a remediation task once it's done. |


##### `TaskBranch`

The task branch is a JSON object which advances a task when it meets the specified criteria.

The object supports the following fields:

| Field name | type | Description |
| --- | --- | --- |
| type | Literal | The type of event that should advance the task. Valid values are: "comm", "jump", "explorationMode", "launchMode", "standby", "scan", "antennaExtended", "antennaRetracted", "challenge", "challengeFail", "codex", "indirect".<br/>"comm" advances when a players initiate a comm event.<br/>"jump" advances when the ship jumps to a specified location.<br/>"explorationMode" advances when the ship's power mode is set to exploration mode.<br/>"launchMode" advances when the ship's power mode is set to launch mode.<br/>"standby" advances when the ship's power mode is set to standby mode.<br/>"scan" advances when players initiate a scan at the specified location.<br/>"antennaExtended" advances when players extend the antenna.<br/>"antennaRetracted" advances when players retract the antenna.<br/>"challenge" advances when a challenge is completed. See settings.yaml's game.challenge_tasks setting to set up the task dispatches.<br/>"challengeFail" advances when a challenge is failed. See settings.yaml's game.challenge_tasks setting to set up the task dispatches.<br/>"codex" advances when a codex has been decoded. Codex tasks are not currently configurable.<br/>"indirect" indicates that this branch is triggered by another task's alsoComplete. This is only valid if this task branch is a completion branch. |
| locationID | string | (Optional) The location at which this branch is triggered. |
| alsoComplete | list[string] | (Optional) A list of task identifiers to also mark complete. The target tasks must be of type "indirect", and must all correspond with existing taskIDs. |
| unlocks | string | (Optional) A task to unlock on this branch. Primarily used with failure branches to unlock a remediation task. This must correspond with an existing taskID. |
| unlockLocation | string | (Optional) A location identifier to unlock when this task branch is triggered. This must correspond with an existing locationID. |
| indirectPrerequisiteTasks | list[string] | A list of tasks that are required before this task is marked complete. Only valid for "indirect" completion branches. These must all correspond with existing taskIDs. |


#### `team_map`

The team mapping is for Gamebrain internal use only when a team is first created. This is a deprecated value and should be provided in the initial JSON as an empty dictionary. This will be removed in a future version.


#### `team_initial_state`

The team initial state is a JSON object which controls the starting conditions for a team that has just started a run in Cubespace.

This object supports the following fields:

| Field name | type | Description |
| --- | --- | --- |
| currentStatus | CurrentLocationGameplayDataTeamSpecific | A JSON object representing the current status of each team, as detailed in the CurrentLocationGameplayDataTeamSpecific section. |
| session | SessionDataTeamSpecific | A JSON object describing the team's default information, as detailed in the SessionDataTeamSpecific section. |
| ship | ShipDataTeamSpecific | A JSON object describing the team's workstation information, as detailed in the ShipDataTeamSpecific section. |
| locations | list[LocationDataTeamSpecific] | A JSON object describing the possible locations a team can visit (as locationIDs), as well as additional information as detailed in the LocationDataTeamSpecific section. |
| missions | list[MissionDataTeamSpecific] | A JSON object representing the initial missions available to the team, as detailed in the MissionDataTeamSpecific section. |


##### `CurrentLocationGameplayDataTeamSpecific`

The current location gameplay data team specific structure describes the attributes of the team's current location and all associated data. Note that changes to these values will immediately change the status of the ship in Cubespace.

This object supports the following fields:

| Field name | type | Description |
| --- | --- | --- |
| currentLocation | string | The locationID of the team's current location. |
| currentLocationScanned | bool | Identifies whether a scan has already been performed at this location. This may affect what options the players have to interact with this location. |
| currentLocationSurroundings | string | The "surroundings" text which shows at the current location in the Cubespace client. |
| antennaExtended | bool | Identifies whether the antenna lever is in the extended position. |
| networkConnected | bool | Identifies whether a network shows as connected in the Cubespace client. |
| networkName | string | The name of the connected network if the above is true. |
| firstContactComplete | bool | Identifies whether the first contact event for this location has been completed. Setting this to true will allow participants to extend the antenna. |
| powerStatus | Literal | Valid values are "launchMode", "explorationMode", "standby". The current overall power mode. |
| incomingTransmission | bool | Identifies whether a comm event is available. |
| incomingTransmissionObject | CommEventData | The full comm event data of an active comm event. Null by default. See the comm_map section for details. |


##### `SessionDataTeamSpecific`

The session data team specific structure describes default information for a team.

This object supports the following fields:

| Field name | type | Description |
| --- | --- | --- |
| teamInfoName | string | The display name of the team. This value gets updated with the team's Gameboard team ID. |
| teamCodexCount | int | The number of codexes the team currently has. This should be set to 0 for the initial state. |
| jumpCutsceneURL | string | The cutscene video to be displayed when jumping to a new location. |


##### `ShipDataTeamSpecific`

The ship data team specific structure describes workstation information available to a team.

All fields for this structure are required, but may be set to empty strings (""). These fields are updated via endpoint called from Gameboard after deployment. Setting an initial URL here allows for providing a landing page with an error message so that if values are not updated, information can be provided to users on what is happening (such as VM deployment, status, or other relevant error information). Valid power settings are "off" or "on"; these fields are reserved for future use.

This object supports the following fields:

| Field name | type | Description |
| --- | --- | --- |
| codexURL | string | The URL used for participants to access the codex decoder virtual machine. |
| workstation1URL | string | The URL used for participants to access Cyber Operator workstation #1. |
| workstation2URL | string | The URL used for participants to access Cyber Operator workstation #2. |
| workstation3URL | string | The URL used for participants to access Cyber Operator workstation #3. |
| workstation4URL | string | The URL used for participants to access Cyber Operator workstation #4. |
| workstation5URL | string | The URL used for participants to access Cyber Operator workstation #5. |
| commPower | Literal | Communication console power. Valid values are "off" or "on". Reserved for future use. |
| flightPower | Literal | Flight console power. Valid values are "off" or "on". Reserved for future use. |
| navPower | Literal | Navigation console power. Valid values are "off" or "on". Reserved for future use. |
| pilotPower | Literal | Pilot console power. Valid values are "off" or "on". Reserved for future use. |


##### `LocationDataTeamSpecific`

The location data team specific structure describes the possible locations a team can visit (as locationIDs) and the associated team-specific status information for each location. This allows teams to leave a location and return without losing any progress.

This object supports the following fields:

| Field name | type | Description |
| --- | --- | --- |
| locationID | string | The identifier for this location. Must be unique. |
| unlocked | bool | Whether the location shows in the list of travel destinations in the Cubespace navigation workstation. |
| visited | bool | Whether the first contact comm event has been completed at this location. |
| scanned | bool | Whether or not the location has been marked as scanned. |
| networkEstablished | bool | Reserved for future use. |


##### `MissionDataTeamSpecific`

The mission data team specific structure provides all information which may be presented in the team's mission log. Note this information is used internally within Gamebrain in order to determine what subset of this information should be provided to the individual Cubespace host. This ensures that participants cannot reverse engineer their local client to gain additional information.

This object supports the following fields:

| Field name | type | Description |
| --- | --- | --- |
| missionID | string | The identifier for this mission. Must be unique. |
| unlocked | bool | Whether the mission is considered unlocked internally. |
| visible | bool | Whether the mission shows up in the mission log. |
| complete | bool | Whether this mission is complete. |
| taskList | list[TaskDataTeamSpecific] | See below for TaskDataTeamSpecific structure. |


###### `TaskDataTeamSpecific`

The task data team specific structure provides information regarding the tasks available within a mission in the team's mission log. Note this information is used internally within Gamebrain in order to determine what subset of this information should be provided to the individual Cubespace host. This ensures that participants cannot reverse engineer their local client to gain additional information.

This object supports the following fields:

| Field name | type | Description |
| --- | --- | --- |
| taskID | string | The identifier for this task. Must be unique. |
| visible | bool | Whether this task is displayed in the mission log task list. |
| complete | bool | Whether this task is complete. |


## Build and Run

After setting up your environment and settings, you need to install dependencies. If you are using Docker, you can just run `docker build . -t gamebrain:latest` to build and tag an image that can be used with any Docker environment. Otherwise you will need to create a Python 3.10+ [virtual environment](https://docs.python.org/3/tutorial/venv.html) and then run `pip install -r requirements.txt` in this directory to install all of the project dependencies.

[Uvicorn](https://www.uvicorn.org/#usage) is installed as a dependency, and it is recommended. `uvicorn gamebrain.app:APP` should start the server.
