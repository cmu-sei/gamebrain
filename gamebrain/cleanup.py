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
from datetime import datetime, timezone, timedelta
import logging

from . import db
from .clients import topomojo
from .gamedata.cache import GameStateManager, TeamID


CLEANUP_TIME = timedelta(minutes=1)


class BackgroundCleanupTask:
    settings: "SettingsModel"

    _revisit_dict: dict[TeamID, datetime]

    @classmethod
    async def init(cls, settings: "SettingsModel"):
        cls.settings = settings
        cls._revisit_dict = {}

        return await cls._cleanup_task()

    @classmethod
    async def _cleanup_team(cls, team_id: TeamID):
        await db.deactivate_team(team_id)
        await GameStateManager.update_team_urls(team_id, {})
        await GameStateManager.uninit_team(team_id)

    @classmethod
    async def _cleanup_session(cls):
        session = await db.get_active_game_session()
        if session is None:
            return
        logging.info("No teams were active, but there is an active session. Cleaning up...")
        await db.deactivate_game_session()
        await GameStateManager.uninit_challenges()
        await GameStateManager.stop_game_timers()

    @classmethod
    async def handle_active_team_without_gamespace(
            cls,
            team_id: str,
            current_time: datetime
    ):
        first_failure_time = cls._revisit_dict.get(team_id)
        if not first_failure_time:
            cls._revisit_dict[team_id] = current_time
            logging.warning(
                f"Team {team_id} is considered active, "
                "but does not have a gamespace ID. "
                "It's possible that this check was done after "
                "a headless assignment but before deployment "
                "finished, so this is only a problem if it "
                "doesn't resolve shortly."
            )
        elif (current_time - first_failure_time) > CLEANUP_TIME:
            logging.error(
                f"Team {team_id} had a game server assigned to them, "
                f"but had no gamespace assigned after {str(CLEANUP_TIME)}. "
                "Deactivating the team..."
            )
            await cls._cleanup_team(team_id)
            del cls._revisit_dict[team_id]

    @classmethod
    async def _cleanup_body(cls):
        current_time = datetime.now(tz=timezone.utc)

        for team in await db.get_active_teams():
            team_id = team["id"]
            gamespace_id = team.get("ship_gamespace_id")
            if not gamespace_id:
                await cls.handle_active_team_without_gamespace(
                    team_id,
                    current_time
                )
                continue

            # If the team was added to the revisit dict in the
            # previous check, it should be removed.
            try:
                del cls._revisit_dict[team_id]
            except KeyError:
                ...

            gamespace_info = await topomojo.get_gamespace(gamespace_id)
            if not gamespace_info:
                logging.warning(
                    f"_cleanup_body: Tried to get Gamespace info for {gamespace_id}, "
                    "but received no data from TopoMojo."
                )
                continue
            # Explicitly test against False in case "isActive" is missing for whatever reason.
            if gamespace_info.get("isActive") is False:
                logging.info(
                    f"_cleanup_body: Team {team_id} had an inactive gamespace. "
                    "Removing internal tracking and unassigning their game server..."
                )
                await cls._cleanup_team(team_id)

            # Send a gamespace cleanup request after its expiration time.
            expire_str = gamespace_info.get("expirationTime")
            try:
                expiration = datetime.fromisoformat(expire_str)
            except Exception as e:
                logging.error(
                    "_cleanup_body: Tried to parse gamespace expiration time "
                    f"for team {team_id} but got exception {e} instead."
                )
            else:
                if expiration < current_time:
                    await topomojo.complete_gamespace(gamespace_id)
        # For-else is a thing.
        else:
            # If no teams are active, end any active session.
            await cls._cleanup_session()

    @classmethod
    async def _cleanup_task(cls):
        while True:
            try:
                await asyncio.sleep(30)

                await cls._cleanup_body()

            except Exception as e:
                logging.exception(f"Cleanup task exception: {str(e)}")
