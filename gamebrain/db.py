from ipaddress import IPv4Address, AddressValueError
from typing import Dict, List, Optional

from sqlalchemy import create_engine, Column, Integer, BigInteger, String, ForeignKey, select, inspect
from sqlalchemy.orm import declarative_base, relationship, Session

from .config import get_settings


class DBManager:
    orm_base = declarative_base()
    engine = None

    class ChallengeSecret(orm_base):
        __tablename__ = "challenge_secret"

        id = Column(String(40), primary_key=True)

        def __repr__(self):
            return f"ChallengeSecret(id={self.id!r}, secret={self.secret!r})"

    class TeamData(orm_base):
        __tablename__ = "team_data"

        id = Column(String(36), primary_key=True)
        gamespace_id = Column(String(36))
        headless_ip = Column(BigInteger)
        ship_hp = Column(Integer, default=100, nullable=False)
        ship_fuel = Column(Integer, default=100, nullable=False)
        team_name = Column(String)

        console_urls = relationship("ConsoleUrl", lazy="joined")

        def __repr__(self):
            return f"TeamData(id={self.id!r}, " \
                   f"headless_ip={self.headless_ip!r}, " \
                   f"console_urls={[console_url for console_url in self.console_urls]!r}"

    class ConsoleUrl(orm_base):
        __tablename__ = "console_url"

        id = Column(Integer, primary_key=True)
        team_id = Column(String(36), ForeignKey("team_data.id"), nullable=False)
        url = Column(String, nullable=False)

        def __repr__(self):
            return f"ConsoleUrl(id={self.id!r}, team_id={self.team_id!r}, url={self.url!r}"

    class Event(orm_base):
        __tablename__ = "event"

        id = Column(Integer, primary_key=True)
        message = Column(String, nullable=False)

    class MediaAsset(orm_base):
        __tablename__ = "media_assets"

        id = Column(Integer, primary_key=True)
        short_name = Column(String, nullable=False)
        url = Column(String, nullable=False)

        def __repr__(self):
            return f"MediaAsset(id={self.id!r}, short_name={self.short_name!r}, url={self.url!r}"

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
    def test_db(cls):
        from ipaddress import IPv4Address
        addr = IPv4Address("192.168.1.91")
        team_id = "4af9eada-c6e2-4dab-951b-d5ff711a43e5"

        team = cls.TeamData(id=team_id, headless_ip=int(addr))
        console_url = cls.ConsoleUrl(team_id=team.id, url="https://foundry.local/console")

        cls._merge_rows([console_url, team], "sqlite+pysqlite:///:memory:")

        with Session(cls.engine) as session:
            team = session.scalars(
                select(cls.TeamData)
            ).first()

            print(team)

    @classmethod
    def merge_rows(cls, items: List):
        settings = get_settings()
        cls._merge_rows(items, settings.db.connection_string)


def store_events(messages: List[str]):
    events = [DBManager.Event(message=message) for message in messages]
    DBManager.merge_rows(events)


def store_console_urls(team_id: str, urls: List[str]):
    console_urls = [DBManager.ConsoleUrl(team_id=team_id, url=url) for url in urls]
    DBManager.merge_rows(console_urls)


def store_team(team_id: str,
               gamespace_id: Optional[str] = None,
               headless_ip: Optional[str] = None,
               team_name: Optional[str] = None):
    try:
        address = int(IPv4Address(headless_ip))
    except AddressValueError:
        address = None
    team_data = DBManager.TeamData(id=team_id,
                                   gamespace_id=gamespace_id,
                                   headless_ip=address,
                                   team_name=team_name)
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
