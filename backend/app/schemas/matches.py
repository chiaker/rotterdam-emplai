from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MatchItem(BaseModel):
    """One scored pair in a match list response."""

    model_config = ConfigDict(from_attributes=True)

    vacancy_id: int
    resume_id: int
    score: int | None = Field(default=None, ge=0, le=100)
    explanation: str | None = None
    matching_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    error: str | None = None
    computed_at: datetime


class MatchList(BaseModel):
    """Top-N matches for a vacancy or resume."""

    items: list[MatchItem]
    note: str | None = None


class OrphanItem(BaseModel):
    """One vacancy or resume with no matches above threshold."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    best_score: int | None = None
    title: str | None = None
    candidate_name: str | None = None


class OrphanList(BaseModel):
    items: list[OrphanItem]
    threshold: int


class RecomputeResponse(BaseModel):
    """Returned after a manual recompute trigger."""

    vacancy_id: int | None = None
    resume_id: int | None = None
    scored: int = 0
    note: str | None = None
