import asyncio

from pydantic import BaseModel

from .model import (
    GameDataTeamSpecific,
    GameDataResponse,
    LocationData,
    LocationDataTeamSpecific,
    LocationDataFull,
    MissionData,
    MissionDataFull,
    TaskData,
    TaskDataFull,
    CommEventData,
    CurrentLocationGameplayDataTeamSpecific,
    LocationUnlockResponse,
    GenericResponse,
    ScanResponse,
)


CommID = str
LocationID = str
MissionID = str
TaskID = str
TeamID = str


class NonExistentTeam(Exception):
    ...


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

    @classmethod
    async def get_team_data(cls, team_id: TeamID) -> GameDataResponse | None:
        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            full_loc_data = []
            for location in team_data.locations:
                loc_global = cls._cache.location_map.__root__[location.LocationID]
                loc_full = LocationDataFull(**loc_global.dict() | location.dict())
                full_loc_data.append(loc_full)

            full_mission_data = []
            for mission in team_data.missions:
                mission_global = cls._cache.mission_map.__root__[mission.MissionID]
                task_list = [
                    TaskDataFull(
                        **cls._cache.task_map.__root__[task.TaskID].dict() | task.dict()
                    )
                    for task in mission.TaskList
                ]
                mission_full = MissionDataFull(
                    **mission_global.dict() | mission.dict() | {"TaskList": task_list}
                )
                full_mission_data.append(mission_full)

            full_team_data = GameDataResponse(
                currentStatus=team_data.currentStatus,
                session=team_data.session,
                ship=team_data.ship,
                locations=full_loc_data,
                missions=full_mission_data,
            )

            return full_team_data

    @classmethod
    async def unlock_location(
        cls, team_id: TeamID, unlock_code: str
    ) -> LocationUnlockResponse:
        def response(status, location=""):
            return LocationUnlockResponse(
                ResponseStatus=status,
                LocationID=location,
                EnteredCoordinates=unlock_code,
            )

        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            team_unlocked_locations = set(
                map(
                    lambda loc: loc.LocationID,
                    filter(lambda loc: loc.Unlocked, team_data.locations),
                )
            )
            for location_id, location_data in cls._cache.location_map.__root__.items():
                if location_data.UnlockCode != unlock_code:
                    continue
                if location_id in team_unlocked_locations:
                    return response("alreadyunlocked")
                else:
                    newly_unlocked = LocationDataTeamSpecific(
                        LocationID=location_id,
                    )
                    team_data.locations.append(newly_unlocked)
                    return response("success", location_id)

            return response("invalid")

    @classmethod
    async def jump(cls, team_id: TeamID, location_id: LocationID) -> GenericResponse:
        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            if team_data.currentStatus.currentLocation == location_id:
                return GenericResponse(success=False, message=location_id)

            location_data = cls._cache.location_map.__root__.get(location_id)
            if not location_data:
                return GenericResponse(success=False, message=location_id)

            destination = [
                loc for loc in team_data.locations if loc.LocationID == location_id
            ]
            if not destination:
                return GenericResponse(success=False, message=location_id)

            location_team_specific = destination.pop()

            new_status = CurrentLocationGameplayDataTeamSpecific(
                currentLocation=location_id,
                currentLocationScanned=location_team_specific.Scanned,
                currentLocationSurroundings=location_data.Surroundings,
                networkName=location_data.NetworkName,
                firstContactComplete=location_team_specific.Visited,
                powerStatus="launchMode",
            )
            team_data.currentStatus = new_status

            return GenericResponse(success=True, message=location_id)

    @classmethod
    async def scan(cls, team_id: TeamID) -> ScanResponse:
        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            location_data = cls._cache.location_map.__root__[
                team_data.currentStatus.currentLocation
            ]
            first_contact_event = cls._cache.comm_map.__root__[
                location_data.FirstContactEvent
            ]

            team_data.currentStatus.incomingTransmission = True
            team_data.currentStatus.incomingTransmissionObject = first_contact_event

            return ScanResponse(
                success=True,
                message=location_data.LocationID,
                EventWaiting=True,
                CommID=first_contact_event,
            )
