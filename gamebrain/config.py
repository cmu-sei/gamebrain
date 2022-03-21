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

class GameboardSettingsModel(BaseModel):
    base_gb_url: str
    players_endpoint: str
    specs_endpoint: str

class TopomojoSettingsModel(BaseModel):
    base_api_url: str
    workspace_endpoint: str

class SettingsModel(BaseModel):
    ca_cert_path: str
    identity: IdentitySettingsModel
    topomojo: TopomojoSettingsModel
    gameboard: GameboardSettingsModel

    @validator('ca_cert_path')
    def path_exists(cls, v):
        if not os.path.isfile(v):
            raise ValueError(f"ca_cert_path: {ca_cert_path} does not exist or is not a file. Check the path and try again.")
        return v

def load_settings(settings_path):
    with open(settings_path) as f:
        settings = yaml.safe_load(f)

    return SettingsModel(**settings)
