# Gamebrain

## Overview

This application controls the game logic for the Cubespace game. It interacts with both Gameboard and Topomojo in its operation - Gameboard to know when to deploy a game and post scores, and Topomojo to check the state of the team's workspace.

## Configuration

The `settings.yaml` file holds all of the environment settings, as well as a few game settings. There is an example `settings.yaml` in this directory.

`initial_state.json` contains the 2022 game missions, tasks, and locations.

> ### ca_cert_path: str

(Optional) This is a path to a CA certificate file used to authenticate Gameboard and Topomojo. Default is ...

TODO: Check what happens when no path is provided.

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

## Setup

After setting up your environment and settings, you need to install dependencies. If you are using Docker, you can just run `docker build . -t gamebrain:latest` to build and tag an image that can be used with any Docker environment. Otherwise you will need to create a Python 3.10+ [virtual environment](https://docs.python.org/3/tutorial/venv.html) and then run `pip install -r requirements.txt` in this directory to install all of the project dependencies.

[Uvicorn](https://www.uvicorn.org/#usage) is installed as a dependency, and it is recommended. `uvicorn gamebrain.app:APP` should start the server.
