import asyncio
import json
import logging
import os.path
import ssl
from typing import Optional, Literal

import httpx
import yaml
from pydantic import BaseModel, validator

from .clients import topomojo
from .dispatch import GamespaceStatusTask
from .gamedata.cache import (
    GameStateManager,
    GameDataCache,
)
import gamebrain.db as db
from .pubsub import PubSub
from .util import url_path_join


class JwtAudiencesModel(BaseModel):
    gamebrain_api_unpriv: str
    gamebrain_api_priv: str
    gamestate_api: str


class IdentitySettingsModel(BaseModel):
    base_url: str
    token_endpoint: str
    jwks_endpoint: str
    client_id: str
    client_secret: str
    jwt_issuer: str
    token_user: str
    token_password: str
    jwt_audiences: JwtAudiencesModel


class GameboardSettingsModel(BaseModel):
    # base_url is used to construct VM console URLs
    base_url: str
    base_api_url: str


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


class GameSettingsModel(BaseModel):
    event_actions: list[EventActionsSettingsModel]
    gamespace_duration_minutes: Optional[int] = 60
    ship_network_vm_name: Optional[str] = ""

    antenna_vm_name: Optional[str] = ""
    grading_vm_name: Optional[str] = ""
    grading_vm_file_path: Optional[str] = ""
    red_raider_vm_name: Optional[str] = ""
    red_raider_file_path: Optional[str] = ""
    final_destination_name: Optional[str] = ""
    final_destination_file_path: Optional[str] = ""

    gamestate_test_mode: Optional[bool] = False
    game_id: str

    headless_client_urls: dict[Hostname, ServerPublicUrl]


class SettingsModel(BaseModel):
    ca_cert_path: str = None
    app_root_prefix: Optional[str] = "/gamebrain"
    identity: IdentitySettingsModel
    topomojo: TopomojoSettingsModel
    gameboard: GameboardSettingsModel
    db: DbSettingsModel
    game: GameSettingsModel
    profiling: bool = False
    gamebrain_admin_api_key: str

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

    @classmethod
    async def init(cls):
        logging.basicConfig(level=logging.INFO)
        settings = get_settings()
        if settings.db.drop_app_tables:
            logging.info("db.drop_app_tables setting is ON, dropping tables.")
        await db.DBManager.init_db(
            settings.db.connection_string,
            settings.db.drop_app_tables,
            settings.db.echo_sql,
        )
        topomojo.ModuleSettings.settings = settings
        cls._init_jwks()
        cls._init_db_sync_task()
        cls._init_grader_task()
        await PubSub.init(settings)

        if settings.game.gamestate_test_mode:
            from .tests.generate_test_gamedata import construct_data

            initial_cache = construct_data()
            logging.info(
                "game.gamestate_test_mode setting is ON, constructing initial data from test constructor."
            )
        elif stored_cache := await db.get_cache_snapshot():
            initial_cache = GameDataCache(**stored_cache)
            logging.info("Initializing game data cache from saved snapshot.")
        else:
            with open("initial_state.json") as f:
                initial_cache = GameDataCache(**json.load(f))
            logging.info("Initializing game data cache from initial_state.json.")
        await GameStateManager.init(initial_cache, settings)

    @classmethod
    def _init_jwks(cls):
        settings = get_settings()
        ssl_context = ssl.create_default_context()
        if settings.ca_cert_path:
            ssl_context.load_verify_locations(cafile=settings.ca_cert_path)
        cls.jwks = httpx.get(
            url_path_join(settings.identity.base_url, settings.identity.jwks_endpoint),
            verify=ssl_context,
        ).json()

    @classmethod
    async def _db_sync_task(cls):
        while True:
            await asyncio.sleep(10)
            snapshot = await GameStateManager.snapshot_data()
            await db.store_cache_snapshot(snapshot)

    @classmethod
    def _init_db_sync_task(cls):
        cls.db_sync_task = asyncio.create_task(cls._db_sync_task())

    @classmethod
    def _init_grader_task(cls):
        cls.grader_task = asyncio.create_task(GamespaceStatusTask.init(get_settings()))

    @classmethod
    def get_jwks(cls):
        return cls.jwks
