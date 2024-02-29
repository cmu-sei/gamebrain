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
from .clients import gameboard
from .util import cleanup_team, cleanup_dead_sessions

CLEANUP_INTERVAL = timedelta(seconds=30)


class BackgroundCleanupTask:
    @classmethod
    async def init(cls):
        return await cls._cleanup_task()

    @classmethod
    async def _cleanup_body(cls):
        current_time = datetime.now(tz=timezone.utc)

        active_teams = await db.get_active_teams()
        for team in active_teams:
            team_id = team["id"]
            try:
                team_data = await gameboard.get_team(team_id)
            except gameboard.TeamDoesNotExist:
                logging.info(
                    f"get_team reports team {team_id} "
                    "does not exist. Cleaning up."
                )
                await cleanup_team(team_id)

            if not team_data:
                # Does not necessarily mean the team is inactive.
                # Gameboard may be down or unreachable.
                logging.info(
                    "get_team call did not return any team data for "
                    f"team {team_id}"
                )
                continue

            if current_time > team_data.sessionEnd:
                logging.info(
                    f"get_team session end has passed for {team_id}. "
                    "Cleaning up."
                )
                await cleanup_team(team_id)

        await cleanup_dead_sessions()

    @classmethod
    async def _cleanup_task(cls):
        while True:
            try:
                await asyncio.sleep(CLEANUP_INTERVAL.seconds)

                await cls._cleanup_body()

            except Exception as e:
                logging.exception(f"Cleanup task exception: {str(e)}")
