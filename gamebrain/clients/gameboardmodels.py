from datetime import datetime
from typing import Any

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
    sectionText: str | None
    lastScoreTime: datetime
    questions: list[GameEngineQuestionView] | None


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


class SimpleEntity(BaseModel):
    id: str = ""
    name: str = ""


class Score(BaseModel):
    completionScore: int
    manualBonusScore: int
    bonusScore: int
    totalScore: int


class GameScoreAutoChallengeBonus(BaseModel):
    id: str
    description: str
    pointValue: int


class ManualChallengeBonusViewModel(BaseModel):
    id: str
    description: str
    pointValue: int
    enteredOn: datetime
    enteredBy: SimpleEntity
    challengeId: str


class TeamChallengeScoreSummary(BaseModel):
    challenge: SimpleEntity
    spec: SimpleEntity
    team: SimpleEntity
    score: Score
    # Actual type is .NET System.TimeSpan, but I don't care.
    timeElapsed: Any
    bonuses: list[GameScoreAutoChallengeBonus]
    manualBonuses: list[ManualChallengeBonusViewModel]
    unclaimedBonuses: list[GameScoreAutoChallengeBonus]


class TeamGameScoreSummary(BaseModel):
    game: SimpleEntity
    team: SimpleEntity
    score: Score
    challengeScoreSummaries: list[TeamChallengeScoreSummary]
