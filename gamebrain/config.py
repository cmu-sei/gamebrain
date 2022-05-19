import os.path
from typing import Optional, List, Literal, Union

import yaml
from pydantic import BaseModel, validator


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
    action: Union[ChangeNetArgumentsModel, DispatchCommandModel]


class GameSettingsModel(BaseModel):
    ship_workspace_id: str
    event_actions: List[EventActionsSettingsModel]
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
