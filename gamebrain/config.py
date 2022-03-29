import os.path

from pydantic import BaseModel, validator
import yaml


class IdentitySettingsModel(BaseModel):
    base_url: str
    token_endpoint: str
    jwks_endpoint: str
    client_id: str
    client_secret: str
    jwt_audience: str
    jwt_issuer: str
    token_user: str
    token_password: str


class GameboardSettingsModel(BaseModel):
    base_gb_url: str


class TopomojoSettingsModel(BaseModel):
    base_api_url: str


class SettingsModel(BaseModel):
    ca_cert_path: str
    identity: IdentitySettingsModel
    topomojo: TopomojoSettingsModel
    gameboard: GameboardSettingsModel

    @validator('ca_cert_path')
    def path_exists(cls, v):
        if not os.path.isfile(v):
            raise ValueError(
                f"ca_cert_path: {v} does not exist or is not a file. Check the path and try again.")
        return v


class Settings:
    _settings = None

    @classmethod
    def _init_settings(cls, settings_path=None):
        with open(settings_path) as f:
            settings = yaml.safe_load(f)

        cls._settings = SettingsModel(**settings)

    @classmethod
    def get_settings(cls, settings_path=None):
        if not cls._settings:
            cls._init_settings(settings_path)
        return cls._settings


def get_settings(settings_path=None):
    return Settings.get_settings(settings_path)
