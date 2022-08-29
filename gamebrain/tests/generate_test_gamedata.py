from pydantic import BaseModel

from gamebrain.gamedata import model, cache


class GenerationParameters(BaseModel):
    location_count: int = 2
    comm_event_count: int = 2
    mission_count: int = 2
    team_count: int = 2


def construct_global_locations(
    params: GenerationParameters,
) -> cache.LocationMap:
    locations = {}

    for i in range(params.location_count):
        location_id = f"location{i+1}"
        name = f"Location {i+1}"

        location_data = model.LocationData(
            **{
                "LocationID": location_id,
                "Name": name,
                "ImageID": f"{location_id}_image",
                "BackdropID": f"{location_id}_backdrop",
                "Surroundings": f"{name} surroundings",
                "UnlockCode": "000000",
                "TrajectoryLaunch": i,
                "TrajectoryCorrection": i,
                "TrajectoryCube": i,
                "FirstContactEvent": f"{location_id}commfc",
                "NetworkName": f"{location_id}net",
            }
        )

        locations[location_id] = location_data

    return cache.LocationMap(__root__=locations)


def construct_global_comm_events(
    location: cache.LocationID,
    params: GenerationParameters,
) -> cache.CommMap:
    comm_events = {}

    for i in range(params.comm_event_count):
        comm_id = f"{location}comm{i}"
        if i == 0:
            comm_id = f"{location}commfc"

        comm_event = model.CommEventData(
            **{
                "CommID": comm_id,
                "VideoURL": f"https://example.com/comms/{comm_id}",
                "CommTemplate": "badTranslation",
                "TranslationMessage": f"{comm_id} translation message",
                "ScanInfoMessage": f"{comm_id} scan info message",
                "FirstContact": i == 0,
                "LocationID": location,
            }
        )

        comm_events[comm_id] = comm_event

    return cache.CommMap(__root__=comm_events)


def construct_global_tasks(
    mission_id: cache.MissionID, comm_events: list[model.CommEventData]
) -> cache.TaskMap:
    tasks = {}

    for i, event in enumerate(comm_events):
        task_id = f"{mission_id}task{i+1}"
        comm_id = event.CommID

        task_data = model.TaskData(
            **{
                "TaskID": task_id,
                "MissionID": mission_id,
                "DescriptionText": f"{mission_id} {task_id} description text",
                "InfoPresent": True,
                "InfoText": f"{mission_id} {task_id} info text",
                "VideoPresent": True,
                "VideoURL": f"https://example.com/{mission_id}/{task_id}",
                "CommID": comm_id,
            }
        )

        tasks[task_id] = task_data

    return cache.TaskMap(__root__=tasks)


def construct_global_missions_comm_events_and_tasks(
    location: cache.LocationID,
    params: GenerationParameters,
) -> (cache.CommMap, cache.MissionMap, cache.TaskMap,):
    comm_events = {}
    missions = {}
    tasks = {}

    for i in range(params.mission_count):
        mission_id = f"mission{i+1}"
        title = f"Mission {i+1}"

        location_comm_events = construct_global_comm_events(location, params)
        mission_tasks = construct_global_tasks(
            mission_id, list(location_comm_events.__root__.values())
        )

        comm_events.update(location_comm_events.__root__)

        mission_data = model.MissionData(
            **{
                "MissionID": mission_id,
                "Title": f"{title} Title",
                "SummaryShort": f"{title} Short Summary",
                "SummaryLong": f"{title} Long Summary",
                "MissionIcon": f"https://example.com/{mission_id}/icon",
                "IsSpecial": False,
                "RuleList": [f"{title} Rule {j+1}" for j in range(3)],
                "TaskList": list(mission_tasks.__root__.values()),
            }
        )

        missions[mission_id] = mission_data
        tasks.update(mission_tasks.__root__)

    return (
        cache.CommMap(__root__=comm_events),
        cache.MissionMap(__root__=missions),
        cache.TaskMap(__root__=tasks),
    )


def construct_global_data(
    params: GenerationParameters,
) -> cache.GlobalData:
    missions = {}
    comm_events = {}
    tasks = {}

    locations = construct_global_locations(params)
    for location in locations.__root__:
        (
            local_comm_events,
            local_missions,
            local_tasks,
        ) = construct_global_missions_comm_events_and_tasks(location, params)

        comm_events.update(local_comm_events.__root__)
        missions.update(local_missions.__root__)
        tasks.update(local_tasks.__root__)

    return cache.GlobalData(
        comm_map=cache.CommMap(__root__=comm_events),
        location_map=locations,
        mission_map=cache.MissionMap(__root__=missions),
        task_map=cache.TaskMap(__root__=tasks),
    )


def construct_team_ship_data(
    team_id: cache.TeamID,
) -> model.ShipDataTeamSpecific:
    return model.ShipDataTeamSpecific(
        **{
            f"Workstation{i+1}URL": f"https://example.com/{team_id}_ship/ws{i + 1}"
            for i in range(5)
        }
        | {
            "CodexURL": f"https://example.com/{team_id}_ship/codex",
        }
    )


def construct_team_session_data(
    team_name: str,
) -> model.SessionDataTeamSpecific:
    return model.SessionDataTeamSpecific(
        **{
            "TeamInfoName": team_name,
            "TeamCodexCount": 0,
            "JumpCutsceneURL": f"https://example.com/jump",
        }
    )


def construct_team_current_location(
    current_location: model.LocationData,
) -> model.CurrentLocationGameplayDataTeamSpecific:
    return model.CurrentLocationGameplayDataTeamSpecific(
        **{
            "currentLocation": current_location.LocationID,
            "currentLocationScanned": False,
            "currentLocationSurroundings": current_location.Surroundings,
            "antennaExtended": False,
            "networkConnected": False,
            "networkName": f"{current_location.NetworkName}",
            "firstContactComplete": False,
            "powerStatus": "on",
            "incomingTransmission": False,
            "incomingTransmissionObject": None,
        }
    )


def construct_team_specific_data(
    team_id: cache.TeamID,
    first_location: cache.LocationID,
    first_mission: cache.MissionID,
    locations: cache.LocationMap,
    missions: cache.MissionMap,
) -> model.GameDataTeamSpecific:
    team_name = f"Team {team_id[-1]}"

    ship_data = construct_team_ship_data(team_id)
    session_data = construct_team_session_data(team_name)
    current_status = construct_team_current_location(locations.__root__[first_location])

    unlocked_locations = [
        model.LocationDataTeamSpecific(
            **{
                "LocationID": locations.__root__[first_location].LocationID,
                "Unlocked": True,
                "Visited": False,
                "Scanned": False,
                "NetworkEstablished": False,
            }
        )
    ]
    unlocked_missions = [
        model.MissionDataTeamSpecific(
            **{
                "MissionID": missions.__root__[first_mission].MissionID,
                "Unlocked": True,
                "Visible": False,
                "Complete": False,
            }
        )
    ]

    game_data = model.GameDataTeamSpecific(
        **{
            "currentStatus": current_status,
            "session": session_data,
            "ship": ship_data,
            "locations": unlocked_locations,
            "missions": unlocked_missions,
        }
    )

    return game_data


def construct_teams(
    first_location: cache.LocationID,
    first_mission: cache.MissionID,
    locations: cache.LocationMap,
    missions: cache.MissionMap,
    params: GenerationParameters,
) -> cache.TeamMap:
    team_data = {}

    for i in range(params.team_count):
        team_id = f"team{i+1}"

        game_data = construct_team_specific_data(
            team_id, first_location, first_mission, locations, missions
        )

        team_data[team_id] = game_data

    return cache.TeamMap(__root__=team_data)


def construct_data(params: GenerationParameters = None) -> cache.GameDataCache:
    if params is None:
        params = GenerationParameters()

    global_data = construct_global_data(params)
    team_data = construct_teams(
        "location1",
        "mission1",
        global_data.location_map,
        global_data.mission_map,
        params,
    )

    return cache.GameDataCache(**global_data.dict(), team_map=team_data)
