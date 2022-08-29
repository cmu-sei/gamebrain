import asyncio
import os.path
from typing import Optional, Literal

import httpx
import redis.asyncio as redis
import yaml
from pydantic import BaseModel, validator

from .gamedata.cache import GameStateManager
import gamebrain.db as db
from .util import url_path_join


class JwtAudiencesModel(BaseModel):
    gamebrain_api_unpriv: str
    gamebrain_api_priv: str
    gamebrain_api_admin: str
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
    base_api_url: str


class TopomojoSettingsModel(BaseModel):
    base_url: str
    base_api_url: str


class DbSettingsModel(BaseModel):
    connection_string: str
    drop_app_tables: Optional[bool]
    echo_sql: Optional[bool]


class RedisSettingsModel(BaseModel):
    connection_string: Optional[str]
    channel_name: Optional[str] = "gamebrain-default"


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


class GameSettingsModel(BaseModel):
    ship_workspace_id: str
    event_actions: list[EventActionsSettingsModel]
    gamespace_duration_minutes: Optional[int] = 60


class SettingsModel(BaseModel):
    ca_cert_path: str
    app_root_prefix: Optional[str] = "/gamebrain"
    identity: IdentitySettingsModel
    topomojo: TopomojoSettingsModel
    gameboard: GameboardSettingsModel
    db: DbSettingsModel
    redis: Optional[RedisSettingsModel] = RedisSettingsModel()
    game: GameSettingsModel

    @validator('ca_cert_path')
    def path_exists(cls, v):
        if not os.path.isfile(v):
            raise ValueError(
                f"ca_cert_path: {v} does not exist or is not a file. Check the path and try again.")
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

    task_queue = None
    updater_task = None

    @classmethod
    async def init(cls):
        settings = get_settings()
        await db.DBManager.init_db(settings.db.connection_string, settings.db.drop_app_tables, settings.db.echo_sql)
        cls._init_jwks()
        cls._init_redis()
        cls._init_updater_task()
        # TODO: Implement a check for test vs normal operation.
        await GameStateManager.test_init()

    @classmethod
    def _init_jwks(cls):
        settings = get_settings()
        cls.jwks = httpx.get(
            url_path_join(settings.identity.base_url, settings.identity.jwks_endpoint),
            verify=settings.ca_cert_path
        ).json()

    @classmethod
    def _init_redis(cls):
        settings = get_settings()
        if settings.redis.connection_string:
            cls.redis = redis.Redis.from_url(settings.redis.connection_string)
        else:
            cls.redis = redis.Redis()

    @classmethod
    async def _updater_task(cls):
        while True:
            update = await cls.task_queue.get()
            # TODO: Do the actual update

    @classmethod
    def _init_updater_task(cls):
        cls.task_queue = asyncio.Queue()
        cls.updater_task = asyncio.create_task(cls._updater_task())

    @classmethod
    def get_jwks(cls):
        return cls.jwks

