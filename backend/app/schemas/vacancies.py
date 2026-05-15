from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class VacancyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    title: str
    raw_text: str
    source_format: str
    hard_skills: list[dict[str, Any]]
    soft_skills: list[dict[str, Any]]
    experience: dict[str, Any]
    location: str | None
    work_format: str | None
    work_hours: str | None
    other_requirements: dict[str, Any]
    created_at: datetime


class VacancyListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    source_format: str
    location: str | None
    work_format: str | None
    created_at: datetime
