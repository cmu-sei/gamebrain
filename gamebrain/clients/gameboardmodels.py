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
    attempts: int
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


class SimpleSponsor(BaseModel):
    id: str
    name: str
    logo: str


class PlayerWithSponsor(BaseModel):
    id: str
    name: str
    sponsor: SimpleSponsor


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


class GameScoringConfigChallengeBonus(BaseModel):
    id: str
    description: str
    pointValue: float


class GameScoringConfigChallengeSpec(BaseModel):
    id: str
    name: str
    description: str | None
    completionScore: float
    possibleBonuses: list[GameScoringConfigChallengeBonus]
    maxPossibleScore: float


class GameScoreGameInfo(BaseModel):
    id: str
    name: str
    isTeamGame: bool
    specs: list[GameScoringConfigChallengeSpec]


class TeamChallengeScore(BaseModel):
    id: str
    specId: str
    name: str
    result: str
    score: Score
    # Actual type is .NET System.TimeSpan, but I don't care.
    timeElapsed: Any
    bonuses: list[GameScoreAutoChallengeBonus]
    manualBonuses: list[ManualChallengeBonusViewModel]
    unclaimedBonuses: list[GameScoreAutoChallengeBonus]


class GameScoreTeam(BaseModel):
    team: SimpleEntity
    players: list[PlayerWithSponsor]
    rank: int
    overallScore: Score
    totalTimeMs: int
    challenges: list[TeamChallengeScore]


class TeamGameScoreQueryResponse(BaseModel):
    gameInfo: GameScoreGameInfo
    score: GameScoreTeam
