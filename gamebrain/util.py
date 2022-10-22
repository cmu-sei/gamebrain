import asyncio
import logging

from urllib.parse import urlsplit, urlunsplit

from .gamedata.cache import TeamID

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


class TeamLocks:
    """
    The point of this is to have a per-team lock, but the structure holding the per-team lock also needs a lock.
    """
    global_lock = asyncio.Lock()
    team_locks: dict[TeamID, asyncio.Lock] = {}

    def __init__(self, team_id: TeamID):
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
