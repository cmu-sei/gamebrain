import asyncio
from collections import Counter
import json
import logging

from . import db
from .clients import topomojo
from .gamedata.cache import GameStateManager, TeamID


class BackgroundCleanupTask:
    settings: "SettingsModel"

    _revisit_dict: Counter

    @classmethod
    async def init(cls, settings: "SettingsModel"):
        cls.settings = settings
        cls._revisit_dict = Counter()

        return await cls._cleanup_task()

    @staticmethod
    def log_teams_without_headless(teams_without_headless: list[str]):
        logging.warning(
            "The following teams have gamespace IDs, but are not assigned to a game server.\n"
            "This should not happen.\n"
            f"{json.dumps(teams_without_headless)}"
        )

    @staticmethod
    def log_teams_without_gamespace(teams_without_gamespace: list[str]):
        logging.warning(
            "The following teams are assigned to a game server, but have no tracked gamespace ID.\n"
            "If there's no more than one occurrence per team over a few minutes, it's not likely a problem.\n"
            f"{json.dumps(teams_without_gamespace)}"
        )

    @classmethod
    async def _cleanup_team(cls, team_id: TeamID):
        await db.expire_team_gamespace(team_id)
        await GameStateManager.update_team_urls(team_id, {})

    @classmethod
    async def _cleanup_task(cls):
        while True:
            await asyncio.sleep(60)

            teams_with_gamespace_ids = await db.get_teams_with_gamespace_ids()
            teams_with_headless_clients = await db.get_assigned_headless_urls()

            teams_without_headless = set(teams_with_gamespace_ids.keys()) - set(
                teams_with_headless_clients.keys()
            )
            teams_without_gamespace = set(teams_with_headless_clients.keys()) - set(
                teams_with_gamespace_ids.keys()
            )

            if teams_without_headless:
                cls.log_teams_without_headless(list(teams_without_headless))

            if teams_without_gamespace:
                cls.log_teams_without_gamespace(list(teams_without_gamespace))

            for team_id, gamespace_id in teams_with_gamespace_ids.items():
                gamespace_info = await topomojo.get_gamespace(gamespace_id)
                if not gamespace_info:
                    logging.warning(
                        f"Tried to get Gamespace info for {gamespace_id}, "
                        "but received no data from TopoMojo."
                    )
                    continue
                # Explicitly test against False in case "isActive" is missing for whatever reason.
                if gamespace_info.get("isActive") == False:
                    logging.info(
                        f"Team {team_id} had an inactive gamespace. "
                        "Removing internal tracking and unassigning their game server..."
                    )
                    await cls._cleanup_team(team_id)

            for team_id in teams_without_gamespace:
                if cls._revisit_dict[team_id] >= 10:
                    logging.error(
                        f"Team {team_id} had a game server assigned to them, "
                        "but had no gamespace assigned after many checks. "
                        "Unassigning the team's game server..."
                    )
                    await cls._cleanup_team(team_id)
                    del cls._revisit_dict[team_id]
                    continue
                cls._revisit_dict[team_id] += 1
