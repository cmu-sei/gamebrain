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
import datetime
import json
import logging
import os.path
import ssl
from typing import Optional, Literal

import httpx
import yaml
from pydantic import BaseModel, validator, ValidationError

from .clients import gameboard, topomojo
from .dispatch import GamespaceStatusTask
from .gamedata.cache import (
    GameStateManager,
    GameDataCacheSnapshot,
)
from .cleanup import BackgroundCleanupTask
import gamebrain.db as db
from .pubsub import PubSub
from .util import url_path_join


class JwtAudiencesModel(BaseModel):
    gamebrain_api_unpriv: str
    gamestate_api: str


class IdentitySettingsModel(BaseModel):
    base_url: str
    jwks_endpoint: str
    jwt_issuer: str
    jwt_audiences: JwtAudiencesModel


class GameboardSettingsModel(BaseModel):
    base_api_url: str
    x_api_key: str
    x_api_client: str


class TopomojoSettingsModel(BaseModel):
    base_api_url: str
    x_api_key: str
    x_api_client: str


class DbSettingsModel(BaseModel):
    connection_string: str
    drop_app_tables: Optional[bool]
    echo_sql: Optional[bool]


class ChangeNetArgumentsModel(BaseModel):
    action_type: Literal["change-net"]
    vm_name: str
    new_net: str


class DispatchCommandModel(BaseModel):
    action_type: Literal["dispatch"]
    vm_name: str
    command: str


class EventActionsSettingsModel(BaseModel):
    event_message_partial: str
    action: ChangeNetArgumentsModel | DispatchCommandModel


Hostname = str
ServerPublicUrl = str


class ChallengeTask(BaseModel):
    task_id: str
    vm_name: str
    dispatch_command: str

    def __hash__(self):
        return hash((self.task_id, self.vm_name, self.dispatch_command))


class GameSettingsModel(BaseModel):
    # Currently unused.
    event_actions: list[EventActionsSettingsModel] = []
    ship_network_vm_name: Optional[str] = ""

    antenna_retracted_network: Optional[str] = "deepspace:1"

    # Next 4 only used for PC4 games.
    grading_vm_name: Optional[str] = ""
    grading_vm_dispatch_command: Optional[str] = ""
    final_destination_name: Optional[str] = ""
    final_destination_file_path: Optional[str] = ""

    # Only used in PC4.
    challenge_tasks: list[ChallengeTask] = []

    headless_client_urls: dict[Hostname, ServerPublicUrl]


class SettingsModel(BaseModel):
    ca_cert_path: str = None
    app_root_prefix: Optional[str] = ""
    identity: IdentitySettingsModel
    topomojo: TopomojoSettingsModel
    gameboard: GameboardSettingsModel
    db: DbSettingsModel
    game: GameSettingsModel
    profiling: bool = False
    gamebrain_admin_api_key: str
    log_level: Literal["DEBUG", "INFO",
                       "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @validator("ca_cert_path")
    def path_exists(cls, v):
        if not os.path.isfile(v):
            raise ValueError(
                f"ca_cert_path: {v} does not exist or is not a file. Check the path and try again."
            )
        return v


class Settings:
    _settings = None

    @classmethod
    def init_settings(cls, settings_path):
        with open(settings_path) as f:
            settings = yaml.safe_load(f)

        cls._settings = SettingsModel(**settings)

    @classmethod
    def get_settings(cls):
        return cls._settings


def get_settings():
    return Settings.get_settings()


class Global:
    settings_path = "settings.yaml"
    jwks = None
    redis = None

    db_sync_task = None
    grader_task = None
    cleanup_task = None

    @classmethod
    async def init(cls):
        settings = get_settings()
        if settings.db.drop_app_tables:
            logging.info("db.drop_app_tables setting is ON, dropping tables.")
        await db.DBManager.init_db(
            settings.db.connection_string,
            settings.db.drop_app_tables,
            settings.db.echo_sql,
        )
        gameboard.ModuleSettings.settings = settings
        topomojo.ModuleSettings.settings = settings
        cls._init_jwks()
        await PubSub.init(settings)

        if stored_cache := await db.get_cache_snapshot():
            stored_cache_dict = json.loads(stored_cache)
            try:
                initial_cache = GameDataCacheSnapshot(**stored_cache_dict)
            except ValidationError as e:
                logging.error(
                    "Tried to load game state cache and failed validation. Got the following: "
                    f"{json.dumps(stored_cache_dict, indent=2)}"
                )
                raise e
            logging.info("Initializing game data cache from saved snapshot.")
        else:
            with open("initial_state.json") as f:
                initial_cache = GameDataCacheSnapshot(**json.load(f))
            logging.info(
                "Initializing game data cache from initial_state.json.")
        await GameStateManager.init(initial_cache, settings)
        await GameStateManager.start_game_timers()

        cls._init_db_sync_task()
        # cls._init_grader_task()
        cls._init_cleanup_task()
        # cls._init_video_freshness_task()

    @classmethod
    def _init_jwks(cls):
        settings = get_settings()
        ssl_context = ssl.create_default_context()
        if settings.ca_cert_path:
            ssl_context.load_verify_locations(cafile=settings.ca_cert_path)
        cls.jwks = httpx.get(
            url_path_join(settings.identity.base_url,
                          settings.identity.jwks_endpoint),
            verify=ssl_context,
        ).json()

    @classmethod
    async def _db_sync_task(cls):
        while True:
            snapshot = await GameStateManager.snapshot_data()
            try:
                await db.store_cache_snapshot(snapshot)
            except Exception as e:
                logging.exception(e)
            else:
                time = datetime.datetime.now(tz=datetime.timezone.utc)
                logging.debug(f"Saved cache snapshot at {time}.")
            await asyncio.sleep(10)

    @classmethod
    def _init_db_sync_task(cls):
        cls.db_sync_task = asyncio.create_task(cls._db_sync_task())
        cls.db_sync_task.add_done_callback(cls._handle_task_result)

    @classmethod
    def _init_grader_task(cls):
        cls.grader_task = asyncio.create_task(
            GamespaceStatusTask.init(get_settings()))
        cls.grader_task.add_done_callback(cls._handle_task_result)

    @classmethod
    def _init_cleanup_task(cls):
        cls.cleanup_task = asyncio.create_task(BackgroundCleanupTask.init())
        cls.cleanup_task.add_done_callback(cls._handle_task_result)

    # To prevent the videos from being knocked out of caching.
    @classmethod
    def _init_video_freshness_task(cls):
        cls.freshness_task = asyncio.create_task(
            GameStateManager.video_freshness_task())
        cls.freshness_task.add_done_callback(cls._handle_task_result)

    @staticmethod
    def _handle_task_result(task: asyncio.Task) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass  # Task cancellation should not be logged as an error.
        except Exception:  # pylint: disable=broad-except
            logging.exception("Exception raised by task = %r", task)

    @classmethod
    def get_jwks(cls):
        return cls.jwks
