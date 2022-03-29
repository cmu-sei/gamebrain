from ipaddress import IPv4Address
from typing import List

from sqlalchemy import create_engine, Column, Integer, BigInteger, String, ForeignKey, select
from sqlalchemy.orm import declarative_base, relationship, Session

from config import get_settings


class DBManager:
    orm_base = declarative_base()
    engine = None

    class ChallengeSecret(orm_base):
        __tablename__ = "challenge_secret"

        id = Column(Integer, primary_key=True)
        secret = Column(String(40), nullable=False)

        def __repr__(self):
            return f"ChallengeSecret(id={self.id!r}, secret={self.secret!r})"

    class TeamData(orm_base):
        __tablename__ = "team_data"

        id = Column(String(36), primary_key=True)
        headless_ip = Column(BigInteger, nullable=False)
        console_urls = relationship("ConsoleUrl")

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

    @classmethod
    def _init_db(cls, connection_string: str = "", drop_first=False):
        if cls.engine and not drop_first:
            return
        if not connection_string:
            settings = get_settings()
            connection_string = settings.db.connection_string
        cls.engine = create_engine(connection_string, echo=True, future=True)
        if drop_first:
            cls.orm_base.metadata.drop_all(cls.engine)
        cls.orm_base.metadata.create_all(cls.engine)

    @classmethod
    def _add_rows(cls, items: List, connection_string: str = ""):
        cls._init_db(connection_string)
        with Session(cls.engine) as session:
            for item in items:
                session.add(item)
            session.commit()

    @classmethod
    def test_db(cls):
        from ipaddress import IPv4Address
        addr = IPv4Address("192.168.1.91")
        team_id = "4af9eada-c6e2-4dab-951b-d5ff711a43e5"

        team = cls.TeamData(id=team_id, headless_ip=int(addr))
        console_url = cls.ConsoleUrl(team_id=team.id, url="https://foundry.local/console")

        cls._add_rows([console_url, team], "sqlite+pysqlite:///:memory:")

        with Session(cls.engine) as session:
            team = session.scalars(
                select(cls.TeamData)
            ).first()

            print(team)

    @classmethod
    def add_rows(cls, items: List):
        settings = get_settings()
        cls._add_rows(items, settings.db.connection_string)


def store_events(messages: List[str]):
    events = [DBManager.Event(message=message) for message in messages]
    DBManager.add_rows(events)


def store_console_urls(team_id: str, urls: List[str]):
    console_urls = [DBManager.ConsoleUrl(team_id=team_id, url=url) for url in urls]
    DBManager.add_rows(console_urls)


def store_team(team_id: str, headless_ip: str):
    address = IPv4Address(headless_ip)
    team_data = DBManager.TeamData(id=team_id, headless_ip=int(address))
    DBManager.add_rows([team_data])


def store_challenge_secret(secret: str):
    secret = DBManager.ChallengeSecret(secret=secret)
    DBManager.add_rows([secret])
