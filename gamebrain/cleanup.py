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

import asyncio
from collections import Counter
from datetime import datetime, timezone
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
            try:
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

                current_time = datetime.now(tz=timezone.utc)

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

                    # Send a gamespace cleanup request after its expiration time.
                    expire_str = gamespace_info.get("expirationTime")
                    try:
                        expiration = datetime.fromisoformat(expire_str)
                    except Exception as e:
                        logging.error(f"_cleanup_task: Tried to parse gamespace expiration time for team {team_id} but got exception {e} instead.")
                    else:
                        if expiration < current_time:
                            topomojo.complete_gamespace(gamespace_id)

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
            except Exception as e:
                logging.exception(f"Cleanup task exception: {str(e)}")
