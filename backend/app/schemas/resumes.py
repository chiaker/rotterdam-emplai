from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ResumeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    candidate_name: str | None
    raw_text: str
    source_format: str
    hard_skills: list[dict[str, Any]]
    soft_skills: list[dict[str, Any]]
    experience: dict[str, Any]
    location: str | None
    preferred_work_format: str | None
    other_traits: dict[str, Any]
    created_at: datetime


class ResumeListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_name: str | None
    source_format: str
    location: str | None
    preferred_work_format: str | None
    created_at: datetime
