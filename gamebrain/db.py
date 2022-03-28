from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, insert, select
from sqlalchemy.orm import declarative_base, relationship, Session


class DBManager:
    orm_base = declarative_base()
    engine = None

    class ChallengeSecret(orm_base):
        __tablename__ = "challenge_secret"

        id = Column(Integer, primary_key=True)
        secret = Column(String(40))

    class TeamData(orm_base):
        __tablename__ = "team_data"

        id = Column(String(36), primary_key=True)
        headless_ip = Column(Integer)
        console_urls = relationship("ConsoleUrl")

    class ConsoleUrl(orm_base):
        __tablename__ = "console_url"

        id = Column(Integer, primary_key=True)
        team_id = Column(String(36), ForeignKey("team_data.id"), nullable=False)
        url = Column(String, nullable=False)

    @classmethod
    def _init_db(cls):
        cls.engine = create_engine("sqlite+pysqlite:///:memory:", echo=True, future=True)
        cls.orm_base.metadata.create_all(cls.engine)

    @classmethod
    def test_db(cls):
        cls._init_db()

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

            team = session.scalars(
                select(cls.TeamData)
            ).first()

            print(team.console_urls)
