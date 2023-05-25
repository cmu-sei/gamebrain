from datetime import datetime

from pydantic import BaseModel


class GameEngineQuestionView(BaseModel):
    answer: str | None
    example: str | None
    hint: str | None
    isCorrect: bool
    isGraded: bool
    penalty: float
    text: str | None
    weight: float


class GameEngineChallengeView(BaseModel):
    text: str | None
    maxPoints: int
    maxAttempts: int
    attempt: int
    score: float
    sectionCount: int
    sectionIndex: int
    sectionScore: float
    sectionText:  str | None
    lastScoreTime: datetime
    questions: [GameEngineQuestionView] | None


class GameEngineVmState(BaseModel):
    id: str | None
    name: str | None
    isolationId: str | None
    isRunning: bool
    isVisible: bool


class GameEnginePlayer(BaseModel):
    gamespaceId: str | None
    subjectId: str | None
    subjectName: str | None
    permission: str
    isManager: bool


class GameEngineGameState(BaseModel):
    id: str | None
    name: str | None
    managerId: str | None
    managerName: str | None
    markdown: str | None
    audience: str | None
    launchpointUrl: str | None
    isActive: bool
    hasDeployedGamespace: bool

    players: list[GameEnginePlayer] | None
    vms: list[GameEngineVmState] | None
    challenge: GameEngineChallengeView

    whenCreated: datetime
    startTime: datetime
    endTime: datetime
    expirationTime: datetime
