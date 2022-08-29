from datetime import datetime, timezone
from functools import partial
from ipaddress import IPv4Address, AddressValueError
from typing import Dict, List, Optional

from dateutil.parser import isoparse
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, ForeignKey, TIMESTAMP, inspect, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from .gamedata import model


NonNullStrCol = partial(Column, String, nullable=False)
NonNullBoolCol = partial(Column, Boolean, nullable=False)
NonNullIntCol = partial(Column, Integer, nullable=False)


class DBManager:
    orm_base = declarative_base()
    engine = None
    session_factory = None

    class ChallengeSecret(orm_base):
        __tablename__ = "challenge_secret"

        id = Column(String(40), primary_key=True)
        team_id = Column(String(36), ForeignKey("team_data.id"), nullable=False)

    class TeamData(orm_base):
        __tablename__ = "team_data"

        id = Column(String(36), primary_key=True)
        gamespace_id = Column(String(36))
        gamespace_expiration = Column(TIMESTAMP(timezone.utc))
        headless_ip = Column(BigInteger)
        team_name = Column(String)

        # lazy="joined" to prevent session errors.
        vm_data = relationship("VirtualMachine", lazy="joined")
        event_log = relationship("Event", lazy="joined")
        secrets = relationship("ChallengeSecret", lazy="joined")
        # ship_data = relationship("GameData", backref="game_data", uselist=False, lazy="joined")

    class VirtualMachine(orm_base):
        __tablename__ = "console_url"

        id = Column(String(36), primary_key=True)
        team_id = Column(String(36), ForeignKey("team_data.id"), nullable=False)
        url = Column(String, nullable=False)
        name = Column(String, nullable=False)

    class Event(orm_base):
        __tablename__ = "event"

        id = Column(Integer, primary_key=True)
        team_id = Column(String(36), ForeignKey("team_data.id"), nullable=False)
        message = Column(String, nullable=False)
        received_time = Column(TIMESTAMP(timezone.utc), nullable=False)

    class MediaAsset(orm_base):
        __tablename__ = "media_assets"

        id = Column(String, primary_key=True)
        url = Column(String, nullable=False)

    # class TaskData(orm_base):
    #     __tablename__ = "task_data"

    #     task_id = Column(String, primary_key=True)
    #     mission_id = Column(String, primary_key=True)
    #     description = NonNullStrCol()
    #     visible = NonNullBoolCol()
    #     complete = NonNullBoolCol()
    #     info_present = NonNullBoolCol()
    #     info_text = NonNullStrCol()
    #     video_present = NonNullBoolCol()
    #     video_text = NonNullStrCol()
    #     comm_id = NonNullStrCol()

    # class MissionRules(orm_base):
    #     __tablename__ = "mission_rules"

    #     id = Column(String, primary_key=True)

    # class MissionData(orm_base):
    #     __tablename__ = "mission_data"

    #     id = Column(String, primary_key=True)
    #     mission_id = NonNullStrCol()
    #     unlocked = NonNullBoolCol()
    #     visible = NonNullBoolCol()
    #     complete = NonNullBoolCol()
    #     title = NonNullStrCol()
    #     summary_short = NonNullStrCol()
    #     summary_long = NonNullStrCol()
    #     mission_icon = NonNullStrCol()
    #     is_special = NonNullBoolCol()

    #     rule_list = relationship("MissionRules", lazy="joined")
    #     task_list = relationship("TaskData", lazy="joined")

    # class LocationData(orm_base):
    #     __tablename__ = "location_data"

    #     id = Column(String, primary_key=True)
    #     location_id = NonNullStrCol()
    #     name = NonNullStrCol()
    #     image_id = NonNullStrCol()
    #     backdrop_id = NonNullStrCol()
    #     unlocked = NonNullBoolCol()
    #     visited = NonNullBoolCol()
    #     scanned = NonNullBoolCol()
    #     surroundings = NonNullStrCol()
    #     unlock_code = NonNullStrCol()
    #     network_established = NonNullBoolCol()
    #     network_name = NonNullStrCol()
    #     first_contact_event = NonNullStrCol()
    #     trajectory_launch = NonNullIntCol()
    #     trajectory_correction = NonNullIntCol()
    #     trajectory_cube = NonNullIntCol()

    # class ShipData(orm_base):
    #     __tablename__ = "ship_data"

    #     id = Column(String, ForeignKey("team_data.id"), primary_key=True)
    #     codex_url = NonNullStrCol()
    #     workstation_1_url = NonNullStrCol()
    #     workstation_2_url = NonNullStrCol()
    #     workstation_3_url = NonNullStrCol()
    #     workstation_4_url = NonNullStrCol()
    #     workstation_5_url = NonNullStrCol()

    # class SessionData(orm_base):
    #     __tablename__ = "session_data"

    #     id = Column(String, ForeignKey("team_data.id"), primary_key=True)
    #     team_info_name = NonNullStrCol()
    #     team_codex_count = NonNullIntCol()
    #     jump_cutscene_url = NonNullStrCol()

    # class CommEventData(orm_base):
    #     __tablename__ = "comm_event_data"

    #     id = Column(String, primary_key=True)
    #     video_url = NonNullStrCol()
    #     comm_template = NonNullStrCol()
    #     translation_message = NonNullStrCol()
    #     scan_info_message = NonNullStrCol()
    #     first_contact = NonNullBoolCol()
    #     location_id = NonNullStrCol()

    # class CurrentLocationGameplayData(orm_base):
    #     __tablename__ = "current_location_gameplay_data"

    #     id = Column(String, ForeignKey("team_data.id"), primary_key=True)
    #     current_location = NonNullStrCol()
    #     current_location_scanned = NonNullBoolCol()
    #     current_location_surroundings = NonNullStrCol()
    #     antenna_extended = NonNullBoolCol()
    #     network_connected = NonNullBoolCol()
    #     network_name = NonNullStrCol()
    #     first_contact_complete = NonNullBoolCol()
    #     power_status = NonNullBoolCol()

    #     incoming_transmission = relationship("CommEventData", lazy="joined", uselist=False)

    # class GameData(orm_base):
    #     __tablename__ = "game_data"

    #     team_id = Column(String(36), ForeignKey("team_data.id"), primary_key=True, nullable=False)

    #     current_status = relationship("CurrentLocationGameplayData", lazy="joined", uselist=False)
    #     session = relationship("SessionData", lazy="joined", uselist=False)
    #     ship = relationship("ShipData", lazy="joined", uselist=False)
    #     locations = relationship("LocationData", lazy="joined")
    #     missions = relationship("MissionData", lazy="joined")

    @classmethod
    def _orm_obj_to_dict(cls, obj: orm_base) -> Dict:
        result = {}
        for column in inspect(obj).mapper.column_attrs.keys():
            result[column] = getattr(obj, column)
        for relation in inspect(obj).mapper.relationships.keys():
            result[relation] = [cls._orm_obj_to_dict(item) for item in getattr(obj, relation)]
        return result

    @classmethod
    async def init_db(cls, connection_string: str = "", drop_first=False, echo=False):
        if cls.engine and not drop_first:
            return
        cls.engine = create_async_engine(connection_string, echo=echo, future=True)
        # I don't know if expire_on_commit is necessary here, but the SQLAlchemy docs used it.
        cls.session_factory = sessionmaker(cls.engine, expire_on_commit=False, class_=AsyncSession)
        async with cls.engine.begin() as connection:
            if drop_first:
                await connection.run_sync(cls.orm_base.metadata.drop_all)
            await connection.run_sync(cls.orm_base.metadata.create_all)

    @classmethod
    async def get_rows(cls, orm_class: orm_base, *args) -> List[Dict]:
        async with cls.session_factory() as session:
            query = select(orm_class).where(*args)
            result = (await session.execute(query)).unique().scalars().all()
            return [cls._orm_obj_to_dict(item) for item in result]

    @classmethod
    async def merge_rows(cls, items: List):
        async with cls.session_factory() as session:
            for item in items:
                await session.merge(item)
            await session.commit()


async def store_event(team_id: str, message: str):
    received_time = datetime.now(timezone.utc)
    event = [DBManager.Event(team_id=team_id, message=message, received_time=received_time)]
    await DBManager.merge_rows(event)
    return received_time


async def get_events(team_id: Optional[str] = None):
    args = []
    if team_id:
        args.append(DBManager.Event.team_id == team_id)
    return await DBManager.get_rows(DBManager.Event, *args)


async def store_virtual_machines(team_id: str, vms: List[Dict]):
    """
    vms: List of {"Id": str, "Url": str, "Name": str} dicts
    """
    vm_data = [DBManager.VirtualMachine(id=vm["Id"], team_id=team_id, url=vm["Url"], name=vm["Name"]) for vm in vms]
    await DBManager.merge_rows(vm_data)


async def store_team(team_id: str,
                     gamespace_id: Optional[str] = None,
                     gamespace_expiration: Optional[str] = None,
                     headless_ip: Optional[str] = None,
                     team_name: Optional[str] = None):
    """
    gamespace_id: Maximum 36 character string.
    gamespace_expiration: https://dateutil.readthedocs.io/en/stable/parser.html#dateutil.parser.isoparse
    """
    try:
        address = int(IPv4Address(headless_ip))
    except AddressValueError:
        address = None
    # Avoid clobbering existing values
    kwargs = {}
    if gamespace_id:
        kwargs["gamespace_id"] = gamespace_id
    if gamespace_expiration:
        kwargs["gamespace_expiration"] = isoparse(gamespace_expiration)
    if address:
        kwargs["headless_ip"] = address
    if team_name:
        kwargs["team_name"] = team_name
    team_data = DBManager.TeamData(id=team_id,
                                   **kwargs)
    await DBManager.merge_rows([team_data])


async def expire_team_gamespace(team_id: str):
    team_data = DBManager.TeamData(id=team_id, gamespace_id=None, gamespace_expiration=None)
    await DBManager.merge_rows([team_data])


async def get_team(team_id: str) -> Dict:
    try:
        return (await DBManager.get_rows(DBManager.TeamData, DBManager.TeamData.id == team_id)).pop()
    except IndexError:
        return {}


async def get_teams() -> List[Dict]:
    return await DBManager.get_rows(DBManager.TeamData)


async def get_vm(vm_id: str) -> Dict:
    try:
        return (await DBManager.get_rows(DBManager.VirtualMachine, DBManager.VirtualMachine.id == vm_id)).pop()
    except IndexError:
        return {}


async def store_challenge_secrets(team_id: str, secrets: List[str]):
    objects = [DBManager.ChallengeSecret(id=secret, team_id=team_id) for secret in secrets]
    await DBManager.merge_rows(objects)


async def store_media_assets(asset_map: Dict):
    """
    asset_map: shortname: url key-value pairs
    """
    objects = [DBManager.MediaAsset(id=short_name, url=url) for short_name, url in asset_map.items()]
    await DBManager.merge_rows(objects)


async def store_game_data(team_id: str, game_data: model.GameDataTeamSpecific):
    comm_event_data = None
    if game_data.currentStatus.incomingTransmissionObject:
        obj = game_data.currentStatus.incomingTransmissionObject
        comm_event_data = DBManager.CommEventData(**{
            "id": obj.CommID,
            "video_url": obj.VideoURL,
            "comm_template": obj.CommTemplate,
            "translation_message": obj.TranslationMessage,
            "scan_info_message": obj.ScanInfoMessage,
            "first_contact": obj.FirstContact,
            "location_id": obj.LocationID,
        })

    current_loc_data = DBManager.CurrentLocationGameplayData(**{
        "current_location": game_data.currentStatus.currentLocation,
        "current_location_scanned": game_data.currentStatus.currentLocationScanned,
        "current_location_surroundings": game_data.currentStatus.currentLocationSurroundings,
        "antenna_extended": game_data.currentStatus.antennaExtended,
        "network_connected": game_data.currentStatus.networkConnected,
        "network_name": game_data.currentStatus.networkName,
        "first_contact_complete": game_data.currentStatus.firstContactComplete,
        "power_status": game_data.currentStatus.powerStatus,
        "incoming_transmission": game_data.currentStatus.incomingTransmission,
        "incoming_transmission_object": comm_event_data,
    })

    session_data = DBManager.SessionData(**{
        "team_info_name": game_data.session.TeamInfoName,
        "team_codex_count": game_data.session.TeamCodexCount,
        "jump_cutscene_url": game_data.session.JumpCutsceneURL,
    })

    ship_data = DBManager.ShipData(**{
        "codex_url": game_data.ship.CodexURL,
        "workstation_1_url": game_data.ship.Workstation1URL,
        "workstation_2_url": game_data.ship.Workstation2URL,
        "workstation_3_url": game_data.ship.Workstation3URL,
        "workstation_4_url": game_data.ship.Workstation4URL,
        "workstation_5_url": game_data.ship.Workstation5URL,
    })

    location_data_list = [DBManager.LocationData(**{
        "id": location.LocationID,
        "name": location.Name,
        "image_id": location.ImageID,
        "backdrop_id": location.BackdropID,
        "unlocked": location.Unlocked,
        "visited": location.Visited,
        "scanned": location.Scanned,
        "surroundings": location.Surroundings,
        "unlock_code": location.UnlockCode,
        "network_established": location.NetworkEstablished,
        "network_name": location.NetworkName,
        "first_contact_event": location.FirstContactEvent,
        "trajectory_launch": location.TrajectoryLaunch,
        "trajectory_correction": location.TrajectoryCorrection,
        "trajectory_cube": location.TrajectoryCube,
    }) for location in game_data.locations]

    mission_data_list = [DBManager.MissionData(**{
        "id": mission.MissionID,
        "unlocked": mission.Unlocked,
        "visible": mission.Visible,
        "complete": mission.Complete,
        "title": mission.Title,
        "summary_short": mission.SummaryShort,
        "summary_long": mission.SummaryLong,
        "mission_icon": mission.MissionIcon,
        "is_special": mission.IsSpecial,
        "rule_list": [DBManager.MissionRules(id=rule) for rule in mission.RuleList],
        "task_list": [DBManager.TaskData(**{
            "task_id": task.TaskID,
            "mission_id": task.MissionID,
            "description_text": task.DescriptionText,
            "visible": task.Visible,
            "complete": task.Complete,
            "info_present": task.InfoPresent,
            "info_text": task.InfoText,
            "video_present": task.VideoPresent,
            "video_url": task.VideoURL,
            "comm_id": task.CommID,
        }) for task in mission.TaskList],
    }) for mission in game_data.missions]

    game_data = DBManager.GameData(
        team_id=team_id,
        current_status=current_loc_data,
        session=session_data,
        ship=ship_data,
        locations=location_data_list,
        missions=mission_data_list,
    )

    await DBManager.merge_rows(game_data)
