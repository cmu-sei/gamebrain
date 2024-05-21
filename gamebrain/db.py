# Cyber Defenders Video Game

# Copyright 2023 Carnegie Mellon University.

# NO WARRANTY. THIS CARNEGIE MELLON UNIVERSITY AND SOFTWARE ENGINEERING
# INSTITUTE MATERIAL IS FURNISHED ON AN "AS-IS" BASIS. CARNEGIE MELLON
# UNIVERSITY MAKES NO WARRANTIES OF ANY KIND, EITHER EXPRESSED OR IMPLIED, AS
# TO ANY MATTER INCLUDING, BUT NOT LIMITED TO, WARRANTY OF FITNESS FOR PURPOSE
# OR MERCHANTABILITY, EXCLUSIVITY, OR RESULTS OBTAINED FROM USE OF THE
# MATERIAL. CARNEGIE MELLON UNIVERSITY DOES NOT MAKE ANY WARRANTY OF ANY KIND
# WITH RESPECT TO FREEDOM FROM PATENT, TRADEMARK, OR COPYRIGHT INFRINGEMENT.

# Released under a MIT (SEI)-style license, please see license.txt or contact
# permission@sei.cmu.edu for full terms.

# [DISTRIBUTION STATEMENT A] This material has been approved for public
# release and unlimited distribution.  Please see Copyright notice for
# non-US Government use and distribution.

# This Software includes and/or makes use of Third-Party Software each subject
# to its own license.

# DM23-0100

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
import json
import logging
from typing import Dict, List, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Boolean,
    JSON,
    ForeignKey,
    TIMESTAMP,
    inspect,
    select,
    delete,
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, relationship, sessionmaker


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
        team_id = Column(String(36), ForeignKey(
            "team_data.id"), nullable=False)

    class GameSession(orm_base):
        __tablename__ = "game_session"

        id = Column(Integer, primary_key=True)
        session_start = Column(DateTime(timezone=True), nullable=False)
        session_end = Column(DateTime(timezone=True), nullable=False)
        deployer_initial_time = Column(DateTime(timezone=True), nullable=False)
        game_id = Column(String(36), nullable=False)
        active = Column(Boolean(), nullable=False)

        teams = relationship("TeamData", lazy="joined")

    class TeamData(orm_base):
        __tablename__ = "team_data"

        id = Column(String(36), primary_key=True)
        game_session_id = Column(Integer, ForeignKey("game_session.id"))
        ship_gamespace_id = Column(String(36))
        headless_url = Column(String)
        team_name = Column(String)
        active = Column(Boolean(), nullable=False, default=True)

        # lazy="joined" to prevent session errors.
        vm_data = relationship("VirtualMachine", lazy="joined")
        event_log = relationship("Event", lazy="joined")
        secrets = relationship("ChallengeSecret", lazy="joined")
        # ship_data = relationship("GameData", backref="game_data", uselist=False, lazy="joined")

        players = relationship("PlayerInfo", lazy="joined")

    class PlayerInfo(orm_base):
        __tablename__ = "player_info"

        id = Column(String(36), primary_key=True)
        team_id = Column(String, ForeignKey("team_data.id"))
        user_id = Column(String(36))

    class VirtualMachine(orm_base):
        __tablename__ = "console_url"

        id = Column(String(36), primary_key=True)
        team_id = Column(String(36), ForeignKey(
            "team_data.id"), nullable=False)
        url = Column(String, nullable=False)
        name = Column(String, nullable=False)

    class Event(orm_base):
        __tablename__ = "event"

        id = Column(Integer, primary_key=True)
        team_id = Column(String(36), ForeignKey(
            "team_data.id"), nullable=False)
        message = Column(String, nullable=False)
        received_time = Column(TIMESTAMP(timezone.utc), nullable=False)

    class MediaAsset(orm_base):
        __tablename__ = "media_assets"

        id = Column(String, primary_key=True)
        url = Column(String, nullable=False)

    class CacheSnapshot(orm_base):
        __tablename__ = "cache_snapshot"

        id = Column(Integer, primary_key=True)
        snapshot = Column(JSON)

    @classmethod
    def _orm_obj_to_dict(cls, obj: orm_base) -> Dict:
        result = {}
        for column in inspect(obj).mapper.column_attrs.keys():
            result[column] = getattr(obj, column)
        for relation in inspect(obj).mapper.relationships.keys():
            result[relation] = [
                cls._orm_obj_to_dict(item) for item in getattr(obj, relation)
            ]
        return result

    @classmethod
    async def init_db(
        cls,
        connection_string: str = "",
        drop_first=False,
        echo=False,
        change_echo=False,
    ):
        if cls.engine and not (drop_first or change_echo):
            return
        cls.engine = create_async_engine(
            connection_string,
            echo=echo,
            future=True,
            pool_pre_ping=True,
            pool_timeout=10,
            connect_args={
                "timeout": 10,
            },
        )
        # I don't know if expire_on_commit is necessary here, but the SQLAlchemy docs used it.
        cls.session_factory = sessionmaker(
            cls.engine, expire_on_commit=False, class_=AsyncSession
        )
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
    async def merge_rows(cls, items: list[object]) -> list[object]:
        new_items = []
        async with cls.session_factory() as session:
            for item in items:
                new_items.append(await session.merge(item))
            await session.commit()
        return new_items

    @classmethod
    async def delete_where(cls, orm_class: orm_base, *args):
        async with cls.session_factory() as session:
            query = delete(orm_class).where(*args)
            await session.execute(query)
            await session.commit()


async def store_event(team_id: str, message: str):
    received_time = datetime.now(timezone.utc)
    event = [
        DBManager.Event(team_id=team_id, message=message,
                        received_time=received_time)
    ]
    await DBManager.merge_rows(event)
    return received_time


async def get_events(team_id: Optional[str] = None):
    args = []
    if team_id:
        args.append(DBManager.Event.team_id == team_id)
    return await DBManager.get_rows(DBManager.Event, *args)


async def store_virtual_machines(team_id: str, vms: List[Dict]):
    """
    vms: List of {"id": str, "url": str, "name": str} dicts
    """
    vm_data = [
        DBManager.VirtualMachine(
            id=vm["id"], team_id=team_id, url=vm["url"], name=vm["name"]
        )
        for vm in vms
    ]
    await DBManager.merge_rows(vm_data)


@dataclass
class PlayerInfo:
    team_id: str
    player_id: str
    user_id: str


async def store_players(
    players: list[PlayerInfo]
):
    db_players = []
    for player in players:
        db_players.append(
            DBManager.PlayerInfo(
                id=player.player_id,
                team_id=player.team_id,
                user_id=player.user_id,
            )
        )

    await DBManager.merge_rows(db_players)


async def store_team(
    team_id: str,
    ship_gamespace_id: Optional[str] = None,
    headless_url: Optional[str] | None = "",
    team_name: Optional[str] = None,
    game_session_id: Optional[int] = None,
    active: Optional[bool] = None,
):
    """
    ship_gamespace_id: Maximum 36 character string.
    """
    # Avoid clobbering existing values
    kwargs = {}
    if ship_gamespace_id:
        kwargs["ship_gamespace_id"] = ship_gamespace_id
    if headless_url or headless_url is None:
        kwargs["headless_url"] = headless_url
    if team_name:
        kwargs["team_name"] = team_name
    if game_session_id:
        kwargs["game_session_id"] = game_session_id
    if active is not None:
        kwargs["active"] = active
    team_data = DBManager.TeamData(id=team_id, **kwargs)
    await DBManager.merge_rows([team_data])


async def store_game_session(
    team_ids: [str],
    session_start: datetime,
    session_end: datetime,
    deployer_initial_time: datetime,
    game_id: str,
    players: list[PlayerInfo],
):
    session_data = DBManager.GameSession(
        session_start=session_start,
        session_end=session_end,
        deployer_initial_time=deployer_initial_time,
        game_id=game_id,
        active=True,
    )
    merged_session_data = await DBManager.merge_rows([session_data])

    for team_id in team_ids:
        await store_team(
            team_id,
            game_session_id=merged_session_data[0].id,
            active=True
        )

    await store_players(players)


async def get_team_game_session(team_id: str) -> dict:
    team = await get_team(team_id)
    if not team:
        return None
    try:
        game_session = (
            await DBManager.get_rows(
                DBManager.GameSession,
                DBManager.GameSession.id == team["game_session_id"],
                DBManager.GameSession.active == True,
            )
        ).pop()
        return game_session
    except IndexError:
        return None


async def get_active_game_sessions() -> list[dict]:
    return await DBManager.get_rows(
        DBManager.GameSession,
        DBManager.GameSession.active == True,
    )


async def get_all_sessions() -> list[dict]:
    return await DBManager.get_rows(DBManager.GameSession)


async def get_active_teams() -> list[dict]:
    return await DBManager.get_rows(
        DBManager.TeamData,
        DBManager.TeamData.active == True
    )


async def deactivate_team(team_id: str):
    team = await get_team(team_id)
    if not team:
        logging.warning(
            f"Called with a nonexistent team {team_id}."
        )
        return
    team_data = DBManager.TeamData(
        id=team_id,
        active=False,
    )
    await DBManager.merge_rows([team_data])


async def deactivate_game_session(session_id: int):
    # active_game = await get_team_game_session(session_id)
    try:
        session = (await DBManager.get_rows(
            DBManager.GameSession,
            DBManager.GameSession.id == session_id,
        )
        ).pop()
    except IndexError:
        return
    if session:
        session = DBManager.GameSession(
            id=session["id"],
            active=False
        )
        await DBManager.merge_rows([session])


async def get_team(team_id: str) -> Dict:
    try:
        return (
            await DBManager.get_rows(
                DBManager.TeamData, DBManager.TeamData.id == team_id
            )
        ).pop()
    except IndexError:
        return {}


async def get_teams() -> List[Dict]:
    return await DBManager.get_rows(DBManager.TeamData)


async def get_vm(vm_id: str) -> Dict:
    try:
        return (
            await DBManager.get_rows(
                DBManager.VirtualMachine, DBManager.VirtualMachine.id == vm_id
            )
        ).pop()
    except IndexError:
        return {}


async def store_challenge_secrets(team_id: str, secrets: List[str]):
    objects = [
        DBManager.ChallengeSecret(id=secret, team_id=team_id) for secret in secrets
    ]
    await DBManager.merge_rows(objects)


async def store_media_assets(asset_map: Dict):
    """
    asset_map: shortname: url key-value pairs
    """
    objects = [
        DBManager.MediaAsset(id=short_name, url=url)
        for short_name, url in asset_map.items()
    ]
    await DBManager.merge_rows(objects)


async def store_cache_snapshot(cache_snapshot: str):
    """
    cache_snapshot: JSON-formatted string
    """
    snapshot = DBManager.CacheSnapshot(id=0, snapshot=cache_snapshot)
    await DBManager.merge_rows([snapshot])


async def get_cache_snapshot() -> str | None:
    try:
        db_row = (
            await DBManager.get_rows(
                DBManager.CacheSnapshot, DBManager.CacheSnapshot.id == 0
            )
        ).pop()
        return db_row["snapshot"]
    except IndexError:
        return None


async def get_assigned_headless_urls() -> dict[str, str]:
    active_teams = await get_active_teams()

    result = {team["id"]: team["headless_url"] for team in active_teams}
    formatted_result = json.dumps(result, indent=2)
    logging.debug(formatted_result)
    return result


async def get_teams_with_gamespace_ids() -> dict[str, str]:
    # `is not` should be correct, but using it returns all teams
    # in the DB instead of just the ones with gamespace IDs.
    teams_with_gamespace_ids = await DBManager.get_rows(
        DBManager.TeamData, DBManager.TeamData.ship_gamespace_id != None
    )

    result = {
        team["id"]: team["ship_gamespace_id"] for team in teams_with_gamespace_ids
    }
    formatted_result = json.dumps(result, indent=2)
    logging.debug(formatted_result)
    return result
