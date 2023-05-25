from typing import Any

from pydantic import BaseModel


class GameEngineGameState(BaseModel):
    id: str
    name: str
    managerId: str
    managerName: str
    markdown: str
    audience: str
    launchpointUrl: str
    isActive: bool

    players: list[Any]
    vms: list[Any]
    challenge: Any
    # The following fields are .NET DateTimeOffset format, which does not
    # automatically get parsed by datetime.datetime.fromisoformat(). It may
    # be necessary to create a constructor to validate these if they get used.
    whenCreated: str
    startTime: str
    endTime: str
    expirationTime: str
