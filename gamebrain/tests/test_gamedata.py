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

import pytest
import pytest_asyncio

from ..gamedata import cache as gd_cache
from ..config import get_settings


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def fixture_load_testdata() -> gd_cache.GameStateManager:
    with open("initial_state.json") as f:
        initial_cache = gd_cache.GameDataCacheSnapshot(**json.load(f))
    await gd_cache.GameStateManager.init(initial_cache, get_settings())


@pytest.mark.asyncio
async def test_load_testdata(event_loop, fixture_load_testdata):
    ...


@pytest.mark.asyncio
async def test_cache_snapshot_invertible(event_loop, fixture_load_testdata):
    cache = gd_cache.GameStateManager._cache

    assert cache == cache.to_snapshot().to_internal()


@pytest.mark.asyncio
async def test_cache_modified_inequality(event_loop, fixture_load_testdata):
    cache_original = gd_cache.GameStateManager._cache
    # Convenient deep copy.
    cache_modified = cache_original.to_snapshot().to_internal()
    cache_modified.comm_map.__root__["newcomm"] = None

    assert cache_original != cache_modified


@pytest.mark.asyncio
async def test_new_team(event_loop, fixture_load_testdata):
    assert not await gd_cache.GameStateManager.check_team_exists("test_team")

    await gd_cache.GameStateManager.new_team("test_team")

    assert await gd_cache.GameStateManager.check_team_exists("test_team")


@pytest.mark.asyncio
async def test_codexes_start_incomplete(event_loop, fixture_load_testdata):
    await gd_cache.GameStateManager.new_team("test_team")

    codexes = await gd_cache.GameStateManager.get_team_codex_status("test_team")

    assert not any(codexes.values())
