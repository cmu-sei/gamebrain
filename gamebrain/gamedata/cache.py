import asyncio

from pydantic import BaseModel

from .model import (
    GameDataTeamSpecific,
    LocationData,
    MissionData,
    TaskData,
    CommEventData,
)


CommID = str
LocationID = str
MissionID = str
TaskID = str
TeamID = str


class CommMap(BaseModel):
    __root__: dict[CommID, CommEventData]


class LocationMap(BaseModel):
    __root__: dict[LocationID, LocationData]


class MissionMap(BaseModel):
    __root__: dict[MissionID, MissionData]


class TaskMap(BaseModel):
    __root__: dict[TaskID, TaskData]


class TeamMap(BaseModel):
    __root__: dict[TeamID, GameDataTeamSpecific]


class GlobalData(BaseModel):
    comm_map: CommMap
    location_map: LocationMap
    mission_map: MissionMap
    task_map: TaskMap


class GameDataCache(GlobalData):
    team_map: TeamMap


class GameStateManager:
    _lock = asyncio.Lock()
    _test_mode = False

    _cache: GameDataCache

    @classmethod
    async def save_data(cls):
        if cls._test_mode:
            return

    async def extend_antenna(self, team_id: TeamID):
        ...

    @classmethod
    async def test_init(cls):
        cls._test_mode = True

        from ..tests.generate_test_gamedata import construct_data

        cls._cache = construct_data()
