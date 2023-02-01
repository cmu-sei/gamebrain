# Copyright 2023 Carnegie Mellon University. All Rights Reserved.
# Released under a MIT (SEI)-style license. See LICENSE.md in the project root for license information.

###
# Imports raw game data into live_initial_state.json (overwrite initial_state.json at runtime).
###

from collections import defaultdict
import json
from os.path import isfile, join

from gamebrain.gamedata.cache import (
    CommMap,
    TaskMap,
    MissionMap,
    LocationMap,
    GameDataCacheSnapshot,
)
from gamebrain.gamedata.model import (
    SessionDataTeamSpecific,
    ShipDataTeamSpecific,
    GameDataTeamSpecific,
    CurrentLocationGameplayDataTeamSpecific,
)

TEST_MODE = True

FILE_PREFIX = "test" if TEST_MODE else "live"

INITIAL_LOCATION = "dunesea" if TEST_MODE else "plto"
INITIAL_UNLOCKED_LOCS = (
    ("dunesea", "cantina", "rebel")
    if TEST_MODE
    else ("aurmusm", "vitlra", "j900", "aursys", "astfld_correct")
)

RAW_FILES_DIR = "raw_gamedata"
COMMS_PATH = join(RAW_FILES_DIR, f"{FILE_PREFIX}CommStore.json")
TASKS_PATH = join(RAW_FILES_DIR, f"{FILE_PREFIX}TaskTemplate.json")
MISSIONS_PATH = join(RAW_FILES_DIR, f"{FILE_PREFIX}MissionTemplate.json")
LOCS_PATH = join(RAW_FILES_DIR, f"{FILE_PREFIX}Locations.json")
SESSION_PATH = join(RAW_FILES_DIR, f"{FILE_PREFIX}SessionTemplate.json")
SHIP_PATH = join(RAW_FILES_DIR, f"{FILE_PREFIX}ShipTemplate1.json")

JsonStr = str


def get_comm_map(comm_file_content: JsonStr) -> CommMap:
    data = json.loads(comm_file_content)
    return CommMap(__root__=data)


def get_task_map(task_file_content: JsonStr) -> TaskMap:
    data = json.loads(task_file_content)
    return TaskMap(__root__=data)


def get_mission_map(task_data: TaskMap, mission_file_content: JsonStr) -> MissionMap:
    data = json.loads(mission_file_content)
    mission_tasks = defaultdict(list)
    for task in task_data.__root__.values():
        mission_tasks[task.missionID].append(task)
    for mission_data in data.values():
        mission_data["taskList"] = mission_tasks[mission_data["missionID"]]
    return MissionMap(__root__=data)


def get_location_map(location_file_content: JsonStr) -> LocationMap:
    data = json.loads(location_file_content)
    return LocationMap(__root__=data)


def main():
    missing_raw_files = []
    for variable, value in globals().items():
        if variable.endswith("_PATH"):
            if not isfile(value):
                missing_raw_files.append(value)

    if missing_raw_files:
        raise FileNotFoundError("\n".join(missing_raw_files))

    with open(COMMS_PATH) as f:
        comm_map = get_comm_map(f.read())

    with open(TASKS_PATH) as f:
        task_map = get_task_map(f.read())

    with open(MISSIONS_PATH) as f:
        mission_map = get_mission_map(task_map, f.read())

    with open(LOCS_PATH) as f:
        location_map = get_location_map(f.read())

    with open(SESSION_PATH) as f:
        initial_session = SessionDataTeamSpecific(**json.loads(f.read()))

    with open(SHIP_PATH) as f:
        initial_ship = ShipDataTeamSpecific(**json.loads(f.read()))

    current_status = CurrentLocationGameplayDataTeamSpecific(
        currentLocation=INITIAL_LOCATION,
        currentLocationSurroundings=location_map.__root__[
            INITIAL_LOCATION
        ].surroundings,
    )

    unlocked_locations = [
        location_map.__root__[location_id] for location_id in INITIAL_UNLOCKED_LOCS
    ]

    unlocked_mission_ids = tuple(mission_map.__root__.keys())
    unlocked_missions = [
        mission_map.__root__[mission_id] for mission_id in unlocked_mission_ids
    ]

    team_initial_state = GameDataTeamSpecific(
        currentStatus=current_status,
        session=initial_session,
        ship=initial_ship,
        locations=unlocked_locations,
        missions=unlocked_missions,
    )

    initial_cache = GameDataCacheSnapshot(
        comm_map=comm_map,
        task_map=task_map,
        mission_map=mission_map,
        location_map=location_map,
        team_map={},
        team_initial_state=team_initial_state,
    )

    # Basic validation.

    for task_id, task in task_map.__root__.items():
        assert (
            task.missionID in mission_map.__root__
        ), f"Task {task_id} has mission {task.missionID}."

    for mission_id, mission in mission_map.__root__.items():
        for task in mission.taskList:
            assert (
                task.taskID in task_map.__root__
            ), f"Mission {mission_id} has task {task.taskID}."

    for comm_id, comm in comm_map.__root__.items():
        assert (
            comm.locationID in location_map.__root__
        ), f"Comm event {comm_id} has location {comm.locationID}."

    for location_id, location in location_map.__root__.items():
        assert (
            location.firstContactEvent in comm_map.__root__
        ), f"Location {location_id} has first contact event {location.firstContactEvent}."

    with open(f"{FILE_PREFIX}_initial_state.json", "w") as f:
        json.dump(initial_cache.dict(), f, indent=2)


if __name__ == "__main__":
    main()
