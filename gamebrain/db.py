from datetime import datetime, timezone
from ipaddress import IPv4Address, AddressValueError
from typing import Dict, List, Optional

from dateutil.parser import isoparse
from sqlalchemy import Column, Integer, BigInteger, String, ForeignKey, TIMESTAMP, inspect, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from .config import get_settings


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
        ship_hp = Column(Integer, default=100, nullable=False)
        ship_fuel = Column(Integer, default=100, nullable=False)
        team_name = Column(String)

        # lazy="joined" to prevent session errors.
        vm_data = relationship("VirtualMachine", lazy="joined")
        event_log = relationship("Event", lazy="joined")
        secrets = relationship("ChallengeSecret", lazy="joined")

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
        if not connection_string:
            settings = get_settings()
            connection_string = settings.db.connection_string
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
