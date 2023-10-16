from datetime import datetime

from pydantic import BaseModel


class DeploymentGame(BaseModel):
    id: str
    name: str


class DeploymentSession(BaseModel):
    sessionBegin: datetime
    sessionEnd: datetime
    now: datetime


class DeploymentGamespace(BaseModel):
    id: str
    vmUris: list[str]


class DeploymentTeam(BaseModel):
    id: str
    name: str
    gamespaces: list[DeploymentGamespace]


class Deployment(BaseModel):
    game: DeploymentGame
    session: DeploymentSession
    teams: list[DeploymentTeam]
