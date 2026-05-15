"""Extract structured entities from raw vacancy/resume text using Claude tool_use.

Two Pydantic schemas (VacancyExtraction / ResumeExtraction) define the expected
output. We force Claude to call the matching tool via `tool_choice`, validate
the returned dict against the schema, and return a typed result.

On failure (network / quota / invalid JSON after retry), we raise ExtractorError
so callers can fall back to `extraction_status='failed'` without crashing.
"""
from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from app.services.claude import ClaudeError, call_tool_use, text_block
from app.services.text_utils import MAX_EXTRACTOR_CHARS, truncate_by_sentence

logger = logging.getLogger(__name__)


class ExtractorError(Exception):
    """Raised when Claude extraction fails or returns invalid data."""


SkillLevel = Literal["junior", "middle", "senior", "expert"]
WorkFormat = Literal["remote", "office", "hybrid"]


class Skill(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    level: SkillLevel | None = None
    required: bool = True


class ExperienceRequirement(BaseModel):
    years_min: int | None = Field(default=None, ge=0, le=50)
    years_max: int | None = Field(default=None, ge=0, le=50)
    domains: list[str] = Field(default_factory=list)


class Position(BaseModel):
    title: str = Field(max_length=200)
    company: str | None = Field(default=None, max_length=200)
    years: float | None = Field(default=None, ge=0, le=50)
    description: str = Field(default="", max_length=2000)


class CandidateExperience(BaseModel):
    total_years: float | None = Field(default=None, ge=0, le=80)
    positions: list[Position] = Field(default_factory=list)


class VacancyExtraction(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    hard_skills: list[Skill] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    experience: ExperienceRequirement = Field(default_factory=ExperienceRequirement)
    location: str | None = Field(default=None, max_length=200)
    work_format: WorkFormat | None = None
    work_hours: str | None = Field(default=None, max_length=100)
    other_requirements: dict[str, Any] = Field(default_factory=dict)


class ResumeExtraction(BaseModel):
    candidate_name: str | None = Field(default=None, max_length=200)
    hard_skills: list[Skill] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    experience: CandidateExperience = Field(default_factory=CandidateExperience)
    location: str | None = Field(default=None, max_length=200)
    preferred_work_format: WorkFormat | None = None
    other_traits: dict[str, Any] = Field(default_factory=dict)


_VACANCY_SYSTEM = """Ты помощник рекрутёра. Извлеки структурированные сущности из текста вакансии.

Правила:
- Если поле не упомянуто в тексте — оставь null или пустой массив, не выдумывай.
- Названия hard_skills приводи к каноническому английскому виду (Python, не "питон"; PostgreSQL, не "постгрес").
- soft_skills и domains — на русском, как в тексте.
- Уровень навыка (level) указывай только если он явно назван в вакансии.
- Если требования по опыту даны диапазоном — заполни и years_min, и years_max.
- Всегда вызывай инструмент extract_vacancy с результатом.
"""

_RESUME_SYSTEM = """Ты помощник рекрутёра. Извлеки структурированные сущности из текста резюме.

Правила:
- Если поле не упомянуто в тексте — оставь null или пустой массив, не выдумывай.
- Названия hard_skills приводи к каноническому английскому виду (Python, не "питон"; PostgreSQL, не "постгрес").
- soft_skills и описания позиций — на русском, как в тексте.
- total_years — суммарный коммерческий стаж; positions — отдельные места работы.
- candidate_name — ФИО кандидата, если есть в тексте.
- Всегда вызывай инструмент extract_resume с результатом.
"""


def _tool_def(name: str, description: str, schema_cls: type[BaseModel]) -> dict[str, Any]:
    schema = schema_cls.model_json_schema()
    schema.pop("title", None)  # noisy, not needed
    return {"name": name, "description": description, "input_schema": schema}


_VACANCY_TOOL = _tool_def(
    "extract_vacancy",
    "Извлекает структурированные поля вакансии из её текста",
    VacancyExtraction,
)

_RESUME_TOOL = _tool_def(
    "extract_resume",
    "Извлекает структурированные поля резюме из его текста",
    ResumeExtraction,
)


async def extract_vacancy(raw_text: str) -> VacancyExtraction:
    """Extract structured fields from a vacancy's raw text via Claude tool_use."""
    return await _extract(raw_text, _VACANCY_SYSTEM, _VACANCY_TOOL, VacancyExtraction)


async def extract_resume(raw_text: str) -> ResumeExtraction:
    """Extract structured fields from a resume's raw text via Claude tool_use."""
    return await _extract(raw_text, _RESUME_SYSTEM, _RESUME_TOOL, ResumeExtraction)


async def _extract(
    raw_text: str,
    system_prompt: str,
    tool: dict[str, Any],
    schema_cls: type[BaseModel],
) -> Any:
    truncated = truncate_by_sentence(raw_text, MAX_EXTRACTOR_CHARS)
    try:
        result = await call_tool_use(
            system_blocks=[text_block(system_prompt, cache=True)],
            user_content=truncated,
            tool=tool,
            max_tokens=2048,
        )
    except ClaudeError as exc:
        logger.warning("claude call failed during extraction: %s", exc)
        raise ExtractorError(str(exc)) from exc

    try:
        return schema_cls.model_validate(result)
    except ValidationError as exc:
        logger.warning("claude returned invalid extraction: %s", exc)
        raise ExtractorError(f"validation failed: {exc}") from exc
