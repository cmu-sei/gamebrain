import os.path

from pydantic import BaseModel, validator
import yaml


class IdentitySettingsModel(BaseModel):
    base_url: str
    token_endpoint: str
    client_id: str
    client_secret: str
    jwt_audience: str
    jwt_issuer: str

class TopomojoSettingsModel(BaseModel):
    base_api_url: str

class SettingsModel(BaseModel):
    ca_cert_path: str
    identity: IdentitySettingsModel
    topomojo: TopomojoSettingsModel

    @validator('ca_cert_path')
    def path_exists(cls, v):
        if not os.path.isfile(v):
            raise ValueError(f"ca_cert_path: {ca_cert_path} does not exist or is not a file. Check the path and try again.")
        return v

def load_settings(settings_path):
    with open(settings_path) as f:
        settings = yaml.safe_load(f)

    return SettingsModel(**settings)
