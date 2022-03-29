from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, insert, select
from sqlalchemy.orm import declarative_base, relationship, Session


class DBManager:
    orm_base = declarative_base()
    engine = None

    class ChallengeSecret(orm_base):
        __tablename__ = "challenge_secret"

        id = Column(Integer, primary_key=True)
        secret = Column(String(40))

        def __repr__(self):
            return f"ChallengeSecret(id={self.id!r}, secret={self.secret!r})"

    class TeamData(orm_base):
        __tablename__ = "team_data"

        id = Column(String(36), primary_key=True)
        headless_ip = Column(Integer)
        console_urls = relationship("ConsoleUrl")

        def __repr__(self):
            return f"TeamData(id={self.id!r}, headless_ip={self.headless_ip!r}, console_urls={[console_url for console_url in self.console_urls]!r}"

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
        event = Column(String, nullable=False)

    @classmethod
    def _init_db(cls, connection_string: str):
        cls.engine = create_engine(connection_string, echo=True, future=True)
        cls.orm_base.metadata.create_all(cls.engine)

    @classmethod
    def test_db(cls):
        cls._init_db("sqlite+pysqlite:///:memory:")

        from ipaddress import IPv4Address
        addr = IPv4Address("192.168.1.91")
        team_id = "4af9eada-c6e2-4dab-951b-d5ff711a43e5"

        with Session(cls.engine) as session:
            session.execute(
                insert(cls.TeamData),
                {"id": team_id, "headless_ip": int(addr)}
            )
            session.execute(
                insert(cls.ConsoleUrl),
                {"team_id": team_id, "url": "https://foundry.local/console"}
            )
            session.commit()

        with Session(cls.engine) as session:
            team = session.scalars(
                select(cls.TeamData)
            ).first()

            print(team)
