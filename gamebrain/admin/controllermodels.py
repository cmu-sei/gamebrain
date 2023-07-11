from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DeploymentGame(BaseModel):
    id: UUID
    name: str


class DeploymentSession(BaseModel):
    sessionBegin: datetime
    sessionEnd: datetime
    now: datetime


class DeploymentGamespace(BaseModel):
    id: UUID
    vmUris: list[str]


class DeploymentTeam(BaseModel):
    id: UUID
    name: str
    gamespaces: list[DeploymentGamespace]


class Deployment(BaseModel):
    game: DeploymentGame
    session: DeploymentSession
    teams: list[DeploymentTeam]
