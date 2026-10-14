from datetime import date, datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator


def now() -> datetime:
    return datetime.now(timezone.utc)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResearchRequest(Model):
    topic: str = Field(min_length=1, max_length=2000)
    constraints: dict[str, str] = Field(default_factory=dict, max_length=20)
    as_of: date = Field(default_factory=lambda: datetime.now(ZoneInfo("Asia/Shanghai")).date())
    max_rounds: int = Field(default=3, ge=1, le=3)
    max_calls: int = Field(default=8, ge=1, le=8)

    @field_validator("topic", mode="before")
    @classmethod
    def trim_topic(cls, value):
        return value.strip() if isinstance(value, str) else value


class ResearchPlan(Model):
    questions: list[str] = Field(min_length=1, max_length=3)
    required_dimensions: list[str] = Field(min_length=1, max_length=20)


class Source(Model):
    id: str
    url: str
    title: str
    text: str = Field(min_length=1)
    retrieved_at: datetime = Field(default_factory=now)
    published_at: date | None = None
    source_type: str = "unknown"
    content_hash: str
    time_status: Literal["within_cutoff", "after_cutoff", "unknown"] = "unknown"
    version: str | None = None


class Evidence(Model):
    id: str
    source_id: str
    quote: str = Field(min_length=1)
    claim: str = Field(min_length=1)
    verdict: Literal["supported", "contradicted", "uncertain"]
    reason: str


class EvidenceBatch(Model):
    evidence: list[Evidence] = Field(default_factory=list, max_length=50)


class ResearchPacket(Model):
    context: str
    sources: list[Source] = Field(default_factory=list)
    usage: dict[str, int | float | bool | None] = Field(default_factory=dict)
    duration_ms: int = 0


class GapDecision(Model):
    complete: bool
    followups: list[str] = Field(default_factory=list, max_length=3)
    reason: str


class ReportClaim(Model):
    id: str
    text: str = Field(min_length=1)
    kind: Literal["fact", "recommendation", "uncertainty"]
    evidence_ids: list[str] = Field(default_factory=list)


class ComparisonRow(Model):
    label: str
    aspects: dict[str, list[str]]


class ResearchReport(Model):
    title: str
    summary_claim_ids: list[str]
    comparison: list[ComparisonRow] = Field(default_factory=list)
    claims: list[ReportClaim]
    limitation_claim_ids: list[str] = Field(default_factory=list)


class ReportValidation(Model):
    valid: bool
    errors: list[str] = Field(default_factory=list)


class ResearchState(Model):
    run_id: str
    request: ResearchRequest
    mode: Literal["live", "replay"] = "replay"
    plan: ResearchPlan | None = None
    stage: str = "created"
    round: int = 0
    calls: int = 0
    completed_steps: dict[str, ResearchPacket] = Field(default_factory=dict)
    round_questions: dict[str, list[str]] = Field(default_factory=dict)
    reviewed_steps: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    gap: GapDecision | None = None
    report: ResearchReport | None = None
    status: Literal["created", "running", "failed", "completed", "interrupted"] = "created"
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
