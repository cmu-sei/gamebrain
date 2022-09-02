import asyncio

from pydantic import BaseModel

from ..clients.topomojo import change_vm_power, get_vm_desc
from .model import (
    GameDataTeamSpecific,
    GameDataResponse,
    LocationData,
    LocationDataTeamSpecific,
    LocationDataFull,
    MissionData,
    MissionDataTeamSpecific,
    MissionDataFull,
    TaskData,
    TaskDataTeamSpecific,
    TaskDataFull,
    CommEventData,
    PowerMode,
    CodexPowerStatus,
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

                    # Each Comm Event has a LocationID, so gather the ones associated with the new location.
                    unlocked_comm_event_ids = set(
                        map(
                            lambda c: c.CommID,
                            (
                                filter(
                                    lambda c: c.LocationID == location_id,
                                    cls._cache.comm_map.__root__.values(),
                                )
                            ),
                        )
                    )
                    # Next gather the tasks that are associated with a Comm Event in the previous set.
                    unlocked_task_ids = set(
                        map(
                            lambda t: t.TaskID,
                            filter(
                                lambda t: t.CommID in unlocked_comm_event_ids,
                                cls._cache.task_map.__root__.values(),
                            ),
                        )
                    )
                    # Finally gather the missions associated with the previous set of tasks.
                    unlocked_mission_ids = set(
                        map(
                            lambda m: m.MissionID,
                            filter(
                                lambda m: set(map(lambda t: t.TaskID, m.TaskList))
                                & unlocked_task_ids,
                                cls._cache.mission_map.__root__.values(),
                            ),
                        )
                    )

                    # Now use the gathered sets to actually update the cache.
                    team_specific_missions = [
                        MissionDataTeamSpecific(
                            MissionID=mission_id,
                            TaskList=[
                                TaskDataTeamSpecific(
                                    TaskID=task_id,
                                )
                                for task_id in unlocked_task_ids
                                if mission_id
                                == cls._cache.task_map.__root__[task_id].MissionID
                            ],
                        )
                        for mission_id in unlocked_mission_ids
                    ]

                    team_data.missions.extend(team_specific_missions)

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
                powerStatus=team_data.currentStatus.powerStatus,
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

    @classmethod
    async def set_power_mode(
        cls, team_id: TeamID, new_mode: PowerMode
    ) -> GenericResponse:
        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            team_data.currentStatus.powerStatus = new_mode

            return GenericResponse(success=True, message=new_mode)

    @classmethod
    async def complete_comm_event(cls, team_id: TeamID) -> GenericResponse:
        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            current_comm_event = team_data.currentStatus.incomingTransmissionObject
            if not current_comm_event:
                return GenericResponse(
                    success=False,
                    message="noIncomingComm",
                )
            associated_global_task = next(
                filter(
                    lambda t: t.CommID == current_comm_event.CommID,
                    cls._cache.task_map.__root__.values(),
                )
            )

            team_specific_task = None
            for mission in team_data.missions:
                for task in mission.TaskList:
                    if task.TaskID == associated_global_task.TaskID:
                        team_specific_task = task
                        break
                if team_specific_task:
                    break
            else:
                return GenericResponse(success=False, message="noTaskFound")

            if current_comm_event.FirstContact:
                team_data.currentStatus.firstContactComplete = True
                for location in team_data.locations:
                    if current_comm_event.LocationID == location.LocationID:
                        location.Visited = True
                        break
                else:
                    return GenericResponse(
                        success=False,
                        message="locationNotUnlocked",
                    )

            team_specific_task.Complete = True
            team_data.currentStatus.incomingTransmissionObject = None
            team_data.currentStatus.incomingTransmission = False

            return GenericResponse(success=True, message="incomingCommComplete")

    @staticmethod
    async def check_vm_power_status(vm_id: str) -> CodexPowerStatus | None:
        desc = await get_vm_desc(vm_id)
        if not desc or "state" not in desc:
            return

        return CodexPowerStatus(desc["state"])

    @staticmethod
    async def change_vm_power_status(vm_id: str, new_setting: CodexPowerStatus):
        # str to shut up linter
        await change_vm_power(vm_id, str(new_setting.value))

    @classmethod
    async def codex_power(
        cls, team_id: TeamID, new_setting: CodexPowerStatus
    ) -> GenericResponse:
        async with cls._lock:
            team_data = cls._cache.team_map.__root__.get(team_id)
            if not team_data:
                raise NonExistentTeam()

            vm_id = ""
            current_power = await cls.check_vm_power_status(vm_id)
            if current_power == new_setting:
                return GenericResponse(
                    success=False,
                    message=f"codexAlready{new_setting.value.capitalize()}",
                )
            elif current_power is None:
                return GenericResponse(
                    success=False,
                    message=f"TopoMojoAPIFailure",
                )

            await cls.change_vm_power_status(vm_id, new_setting)
            return GenericResponse(success=True, message=f"{vm_id}_{new_setting}")
