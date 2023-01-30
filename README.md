# Gamebrain

## Overview

This application controls the game logic for the Cubespace game. It interacts with both Gameboard and Topomojo in its operation - Gameboard to know when to deploy a game and post scores, and Topomojo to check the state of the team's workspace.

## Configuration

The `settings.yaml` file holds all of the environment settings, as well as a few game settings. There is an example `settings.yaml` in this directory.

`initial_state.json` contains the 2022 game missions, tasks, and locations.

TODO: Explain more about the configuration options.

## Setup

After setting up your environment and settings, you need to install dependencies. If you are using Docker, you can just run `docker build . -t gamebrain:latest` to build and tag an image that can be used with any Docker environment. Otherwise you will need to create a Python 3.10+ [virtual environment](https://docs.python.org/3/tutorial/venv.html) and then run `pip install -r requirements.txt` in this directory to install all of the project dependencies.

[Uvicorn](https://www.uvicorn.org/#usage) is installed as a dependency, and it is recommended. `uvicorn gamebrain.app:APP` should start the server.
