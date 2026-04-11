from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ForecastCategory(str, Enum):
    CLOSED_WON = "closed_won"
    COMMIT = "commit"
    BEST_CASE = "best_case"
    PIPELINE = "pipeline"
    OMITTED = "omitted"
    CLOSED_LOST = "closed_lost"


class OpportunityStage(str, Enum):
    PROSPECTING = "Prospecting"
    QUALIFICATION = "Qualification"
    DISCOVERY = "Discovery"
    PROPOSAL = "Proposal"
    NEGOTIATION = "Negotiation"
    VERBAL = "Verbal Commit"
    CLOSED_WON = "Closed Won"
    CLOSED_LOST = "Closed Lost"


STAGE_ORDER = [
    OpportunityStage.PROSPECTING,
    OpportunityStage.QUALIFICATION,
    OpportunityStage.DISCOVERY,
    OpportunityStage.PROPOSAL,
    OpportunityStage.NEGOTIATION,
    OpportunityStage.VERBAL,
    OpportunityStage.CLOSED_WON,
]


class MeddpiccScore(BaseModel):
    metrics: bool = False
    economic_buyer: bool = False
    decision_criteria: bool = False
    decision_process: bool = False
    paper_process: bool = False
    identified_pain: bool = False
    champion: bool = False
    competition: bool = False

    def completeness(self) -> float:
        return sum(self.model_dump().values()) / 8.0

    def missing_pillars(self) -> list[str]:
        return [k for k, v in self.model_dump().items() if not v]


class Opportunity(BaseModel):
    id: str
    name: str
    account: str
    owner: str
    owner_email: str
    amount: float
    stage: OpportunityStage
    forecast_category: ForecastCategory
    close_date: date
    created_date: date
    last_activity_date: Optional[date] = None
    next_step: Optional[str] = None
    meddpicc: MeddpiccScore = Field(default_factory=MeddpiccScore)
    notes: Optional[str] = None


class SalesLeader(BaseModel):
    id: str
    name: str
    email: str
    team: str
    quarter_quota: float
    rep_ids: list[str] = Field(default_factory=list)


class DealUpdate(BaseModel):
    """What the leader told us on the call about a specific deal."""

    opportunity_id: str
    verbal_category: Optional[ForecastCategory] = None
    verbal_stage: Optional[OpportunityStage] = None
    verbal_close_date: Optional[date] = None
    verbal_amount: Optional[float] = None
    leader_confidence: Optional[int] = None  # 1-5
    risks: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    notes: Optional[str] = None


class FlagSeverity(str, Enum):
    INFO = "info"
    WARN = "warn"
    CRITICAL = "critical"


class ReconciliationFlag(BaseModel):
    opportunity_id: str
    code: str
    severity: FlagSeverity
    message: str


class ForecastRollup(BaseModel):
    closed_won: float = 0.0
    commit: float = 0.0
    best_case: float = 0.0
    pipeline: float = 0.0

    @property
    def committed_total(self) -> float:
        return self.closed_won + self.commit

    @property
    def best_case_total(self) -> float:
        return self.closed_won + self.commit + self.best_case


class DealSummary(BaseModel):
    opportunity_id: str
    name: str
    account: str
    sfdc_amount: float
    sfdc_stage: OpportunityStage
    sfdc_category: ForecastCategory
    sfdc_close_date: date
    update: Optional[DealUpdate] = None
    flags: list[ReconciliationFlag] = Field(default_factory=list)


class ForecastReport(BaseModel):
    leader: SalesLeader
    as_of: datetime
    quarter_label: str
    rollup: ForecastRollup
    gap_to_quota: float
    deals: list[DealSummary]
    top_risks: list[str]
    narrative: str = ""
