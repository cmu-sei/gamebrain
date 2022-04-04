from datetime import datetime, timezone
from ipaddress import IPv4Address, AddressValueError
from typing import Dict, List, Optional

from sqlalchemy import create_engine, Column, Integer, BigInteger, String, ForeignKey, DateTime, select, inspect
from sqlalchemy.orm import declarative_base, relationship, Session

from .config import get_settings


class DBManager:
    orm_base = declarative_base()
    engine = None

    class ChallengeSecret(orm_base):
        __tablename__ = "challenge_secret"

        id = Column(String(40), primary_key=True)

    class TeamData(orm_base):
        __tablename__ = "team_data"

        id = Column(String(36), primary_key=True)
        gamespace_id = Column(String(36))
        headless_ip = Column(BigInteger)
        ship_hp = Column(Integer, default=100, nullable=False)
        ship_fuel = Column(Integer, default=100, nullable=False)
        team_name = Column(String)

        vm_data = relationship("VirtualMachine", lazy="joined")
        event_log = relationship("Event", lazy="joined")

    class VirtualMachine(orm_base):
        __tablename__ = "console_url"

        id = Column(String(36), primary_key=True)
        team_id = Column(String(36), ForeignKey("team_data.id"), nullable=False)
        url = Column(String, nullable=False)

    class Event(orm_base):
        __tablename__ = "event"

        id = Column(Integer, primary_key=True)
        team_id = Column(String(36), ForeignKey("team_data.id"), nullable=False)
        message = Column(String, nullable=False)
        received_time = Column(DateTime, nullable=False)

    class MediaAsset(orm_base):
        __tablename__ = "media_assets"

        id = Column(Integer, primary_key=True)
        short_name = Column(String, nullable=False)
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
    def init_db(cls, connection_string: str = "", drop_first=False, echo=False):
        if cls.engine and not drop_first:
            return
        if not connection_string:
            settings = get_settings()
            connection_string = settings.db.connection_string
        cls.engine = create_engine(connection_string, echo=echo, future=True)
        if drop_first:
            cls.orm_base.metadata.drop_all(cls.engine)
        cls.orm_base.metadata.create_all(cls.engine)

    @classmethod
    def _merge_rows(cls, items: List, connection_string: str = ""):
        cls.init_db(connection_string)
        with Session(cls.engine) as session:
            for item in items:
                session.merge(item)
            session.commit()

    @classmethod
    def get_rows(cls, orm_class: orm_base, **kwargs) -> List[Dict]:
        with Session(cls.engine) as session:
            result = session.query(orm_class).filter_by(**kwargs).all()
            return [cls._orm_obj_to_dict(item) for item in result]

    @classmethod
    def merge_rows(cls, items: List):
        settings = get_settings()
        cls._merge_rows(items, settings.db.connection_string)


def store_event(team_id: str, message: str):
    received_time = datetime.now(timezone.utc)
    event = [DBManager.Event(team_id=team_id, message=message, received_time=received_time)]
    DBManager.merge_rows(event)


def store_virtual_machines(team_id: str, vms: Dict):
    """
    vms: vm_id: url pairs
    """
    vm_data = [DBManager.VirtualMachine(id=vm_id, team_id=team_id, url=url) for vm_id, url in vms.items()]
    DBManager.merge_rows(vm_data)


def store_team(team_id: str,
               gamespace_id: Optional[str] = None,
               headless_ip: Optional[str] = None,
               team_name: Optional[str] = None):
    try:
        address = int(IPv4Address(headless_ip))
    except AddressValueError:
        address = None
    # Avoid clobbering existing values
    kwargs = {}
    if gamespace_id:
        kwargs["gamespace_id"] = gamespace_id
    if address:
        kwargs["headless_ip"] = address
    if team_name:
        kwargs["team_name"] = team_name
    team_data = DBManager.TeamData(id=team_id,
                                   **kwargs)
    DBManager.merge_rows([team_data])


def get_team(team_id: str) -> Dict:
    try:
        return DBManager.get_rows(DBManager.TeamData, id=team_id).pop()
    except IndexError:
        return {}


def get_teams() -> List[Dict]:
    return DBManager.get_rows(DBManager.TeamData)


def store_challenge_secret(secret: str):
    challenge_secret = DBManager.ChallengeSecret(id=secret)
    DBManager.merge_rows([challenge_secret])
