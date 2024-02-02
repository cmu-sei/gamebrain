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
from datetime import datetime
import logging
import re

from urllib.parse import urlsplit, urlunsplit

from .gamedata.cache import GameStateManager
from .db import (
    get_active_teams,
    deactivate_team,
    deactivate_game_session,
    get_active_game_sessions,
)


ISO_FORMAT_FIX_RE = re.compile(r'\.(\d\d\d)\d*\+')
ISO_FORMAT_FIX_REPLACE = r'.\1+'

"""
The following two functions yoinked from here:
https://codereview.stackexchange.com/questions/13027/joining-url-path-components-intelligently

Because urllib.parse.urljoin does some weird stuff.
"""


def url_path_join(*parts):
    """Normalize url parts and join them with a slash."""
    schemes, netlocs, paths, queries, fragments = zip(
        *(urlsplit(part) for part in parts)
    )
    scheme, netloc, query, fragment = first_of_each(
        schemes, netlocs, queries, fragments
    )
    path = "/".join(x.strip("/") for x in paths if x)
    return urlunsplit((scheme, netloc, path, query, fragment))


def first_of_each(*sequences):
    return (next((x for x in sequence if x), "") for sequence in sequences)


def parse_datetime(date_time: str) -> datetime:
    """
    In Python 3.11 the datetime strings we get in our environment are
    able to be parsed with datetime.fromisoformat.
    This does not work in 3.10.
    """
    try:
        # Should work in 3.11+.
        return datetime.fromisoformat(date_time)
    except ValueError:
        ...

    date_time = ISO_FORMAT_FIX_RE.sub(
        ISO_FORMAT_FIX_REPLACE,
        date_time
    )

    try:
        return datetime.fromisoformat(date_time)
    except ValueError:
        message = (
            "parse_datetime: "
            f"Tried to parse {date_time} with datetime.fromisoformat "
            "as a last resort, and failed."
        )
        raise ValueError(message)


class TeamLocks:
    """
    The point of this is to have a per-team lock, but the structure holding
    the per-team lock also needs a lock.
    """

    global_lock = asyncio.Lock()
    team_locks: dict[str, asyncio.Lock] = {}

    def __init__(self, team_id: str):
        self.team_id = team_id

    async def __aenter__(self):
        async with self.global_lock:
            if self.team_id not in self.team_locks:
                self.team_locks[self.team_id] = asyncio.Lock()
            self.team_lock = self.team_locks[self.team_id]
        await self.team_lock.acquire()
        logging.debug(f"Acquired team lock for {self.team_id}.")

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.team_lock.release()
        logging.debug(f"Released team lock for {self.team_id}.")


async def cleanup_team(team_id: str):
    await GameStateManager.pc4_update_team_urls(team_id, {})
    await GameStateManager.uninit_team(team_id)
    await deactivate_team(team_id)


async def cleanup_dead_sessions(nuke: bool = False):
    sessions = await get_active_game_sessions()
    for session in sessions:
        session_active_teams = [
            team for team in session["teams"] if team["active"]
        ]
        if session_active_teams and not nuke:
            continue
        for team in session_active_teams:
            await cleanup_team(team["id"])
        await deactivate_game_session(session["id"])


async def nuke_active_sessions():
    await cleanup_dead_sessions(True)
