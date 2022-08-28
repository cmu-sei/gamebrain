import asyncio

from gamebrain.gamedata import view
from gamebrain.db import store_game_data


def construct_data():
    mission1_tasks = [
        view.TaskData(**{
            "TaskID": "task1",
            "MissionID": "mission1",
            "DescriptionText": "mission1 task1 description text",
            "Visible": True,
            "Complete": True,
            "InfoPresent": True,
            "InfoText": "mission1 task1 info text",
            "VideoPresent": True,
            "VideoURL": "http://example.com/mission1/task1",
            "CommID": "comm1",
        }),
    ]
    mission2_tasks = [
        view.TaskData(**{
            "TaskID": "task1",
            "MissionID": "mission2",
            "DescriptionText": "mission2 task1 description text",
            "Visible": True,
            "Complete": False,
            "InfoPresent": True,
            "InfoText": "mission2 task1 info text",
            "VideoPresent": True,
            "VideoURL": "http://example.com/mission2/task1",
            "CommID": "comm2",
        }),
        view.TaskData(**{
            "TaskID": "task2",
            "MissionID": "mission1",
            "DescriptionText": "mission1 task2 description text",
            "Visible": False,
            "Complete": False,
            "InfoPresent": True,
            "InfoText": "mission1 task2 info text",
            "VideoPresent": True,
            "VideoURL": "http://example.com/mission1/task2",
            "CommID": "comm3",
        }),
    ]
    missions = [
        view.MissionData(**{
            "MissionID": "mission1",
            "Unlocked": True,
            "Visible": True,
            "Complete": True,
            "Title": "Mission 1 Title",
            "SummaryShort": "Mission 1 Short Summary",
            "SummaryLong": "Mission 1 Long Summary",
            "MissionIcon": "http://example.com/mission1/icon",
            "IsSpecial": False,
            "RuleList": ["Mission 1 Rule 1", "Mission 1 Rule 2"],
            "TaskList": mission1_tasks,
        }),
        view.MissionData(**{
            "MissionID": "mission2",
            "Unlocked": True,
            "Visible": True,
            "Complete": True,
            "Title": "Mission 2 Title",
            "SummaryShort": "Mission 2 Short Summary",
            "SummaryLong": "Mission 2 Long Summary",
            "MissionIcon": "http://example.com/mission1/icon",
            "IsSpecial": False,
            "RuleList": ["Mission 2 Rule 1", "Mission 2 Rule 2"],
            "TaskList": mission2_tasks,
        }),
    ]

    locations = [
        view.LocationData(**{
            "LocationID": "loc1",
            "Name": "Location 1",
            "ImageID": "loc1_image",
            "BackdropID": "loc1_backdrop",
            "Unlocked": True,
            "Visited": True,
            "Scanned": True,
            "Surroundings": "Location 1 surroundings",
            "UnlockCode": "loc1unlock",
            "NetworkEstablished": True,
            "NetworkName": "loc1net",
            "FirstContactEvent": "loc1contact",
            "TrajectoryLaunch": 1,
            "TrajectoryCorrection": 1,
            "TrajectoryCube": 1,
        }),
        view.LocationData(**{
            "LocationID": "loc2",
            "Name": "Location 2",
            "ImageID": "loc2_image",
            "BackdropID": "loc2_backdrop",
            "Unlocked": False,
            "Visited": False,
            "Scanned": False,
            "Surroundings": "Location 2 surroundings",
            "UnlockCode": "loc2unlock",
            "NetworkEstablished": False,
            "NetworkName": "loc2net",
            "FirstContactEvent": "loc2contact",
            "TrajectoryLaunch": 2,
            "TrajectoryCorrection": 2,
            "TrajectoryCube": 2,
        }),
    ]

    ship_data = view.ShipData(**{
        "CodexURL": "http://example.com/ship1/codex",
        "Workstation1URL": "http://example.com/ship1/ws1",
        "Workstation2URL": "http://example.com/ship2/ws2",
        "Workstation3URL": "http://example.com/ship3/ws3",
        "Workstation4URL": "http://example.com/ship4/ws4",
        "Workstation5URL": "http://example.com/ship5/ws5",
    })

    session_data = view.SessionData(**{
        "TeamInfoName": "Team 1",
        "TeamCodexCount": 1,
        "JumpCutsceneURL": "http://example.com/cutscene/jump",
    })

    inc_transmission = view.CommEventData(**{
        "CommID": "comm1",
        "VideoURL": "http://example.com/cutscene/video1",
        "CommTemplate": "comm1template",
        "TranslationMessage": "comm1 translation",
        "ScanInfoMessage": "comm1 scaninfo",
        "FirstContact": True,
        "LocationID": "loc1",
    })

    current_status = view.CurrentLocationGameplayData(**{
        "currentLocation": locations[0].LocationID,
        "currentLocationScanned": locations[0].Scanned,
        "currentLocationSurroundings": locations[0].Surroundings,
        "antennaExtended": True,
        "networkConnected": True,
        "networkName": locations[0].NetworkName,
        "firstContactComplete": True,
        "powerStatus": "on",
        "incomingTransmission": True,
        "incomingTransmissionObject": inc_transmission
    })

    game_data = view.GameData(**{
        "currentStatus": current_status,
        "session": session_data,
        "ship": ship_data,
        "locations": locations,
        "missions": missions,
    })
    return game_data


def test_game_data_save():
    game_data = construct_data()

    asyncio.run(store_game_data("1" * 32, game_data))
