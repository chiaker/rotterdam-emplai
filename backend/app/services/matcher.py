"""3-stage matcher: vector pre-filter → hard filter → Claude LLM scoring with cache.

The big optimisation lives in the LLM stage: vacancy data goes into a separate
`cache_control` block in the system prompt so all parallel scoring calls within
one match request share it (one cache write, N-1 cache reads). See PLAN.md
→ Token-cost analysis.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Match, Resume, Vacancy
from app.services.claude import ClaudeError, call_tool_use, text_block
from app.services.repository import (
    Candidate,
    find_candidate_resumes,
    find_candidate_vacancies,
    load_resumes_by_ids,
    load_vacancies_by_ids,
)
from app.services.text_utils import (
    MAX_SCORER_RES_CHARS,
    MAX_SCORER_VAC_CHARS,
    truncate_by_sentence,
)

logger = logging.getLogger(__name__)


# ---------- Schemas ----------


class Citation(BaseModel):
    source: Literal["vacancy", "resume"]
    quote: str = Field(min_length=1, max_length=300)


class MatchScore(BaseModel):
    score: int | None = Field(default=None, ge=0, le=100)
    explanation: str = Field(min_length=1, max_length=600)
    matching_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list, max_length=6)


@dataclass(frozen=True, slots=True)
class PairResult:
    """One scored vacancy↔resume pair (or an error)."""

    vacancy_id: int
    resume_id: int
    score: MatchScore | None
    error: str | None


_SCORE_TOOL = {
    "name": "score_match",
    "description": "Возвращает оценку соответствия резюме вакансии",
    "input_schema": MatchScore.model_json_schema(),
}

_SCORING_INSTRUCTIONS = """Ты помощник рекрутёра. На вход — одна вакансия и одно резюме кандидата.
Оцени соответствие по шкале 0-100 и обоснуй.

Правила:
- score >= 85 означает, что кандидата стоит пригласить на интервью.
- Каждый missing_skill реально отсутствует в резюме (проверь по тексту).
- Каждое утверждение в explanation подкреплено хотя бы одной цитатой в citations
  (короткий точный фрагмент из vacancy или resume, до 300 символов).
- explanation на русском, 2-4 предложения, без воды и оценочных эпитетов.
- Если данных в резюме недостаточно для уверенной оценки — поставь score=null
  и объясни почему в explanation.
- Всегда вызывай инструмент score_match с результатом, не пиши свободный текст.
"""


# ---------- Block builders ----------


def _format_skills(skills: list[dict[str, Any]] | None) -> str:
    if not skills:
        return "—"
    parts = []
    for s in skills:
        name = s.get("name")
        if not name:
            continue
        if s.get("level"):
            parts.append(f"{name} ({s['level']})")
        else:
            parts.append(str(name))
    return ", ".join(parts) if parts else "—"


def _format_soft(soft: list[Any] | None) -> str:
    if not soft:
        return "—"
    return ", ".join(str(s) for s in soft)


def _build_vacancy_block(v: Vacancy) -> str:
    exp = v.experience or {}
    years_min = exp.get("years_min")
    years_max = exp.get("years_max")
    if years_min and years_max:
        years_str = f"{years_min}-{years_max} лет"
    elif years_min:
        years_str = f"от {years_min} лет"
    else:
        years_str = "не указан"
    domains = exp.get("domains") or []

    hs = v.hard_skills or []
    required = [s for s in hs if s.get("required", True)]
    optional = [s for s in hs if not s.get("required", True)]

    return (
        f"Вакансия: {v.title}\n"
        f"Локация: {v.location or 'не указана'}\n"
        f"Формат: {v.work_format or 'не указан'}\n"
        f"Опыт: {years_str}; домены: {', '.join(domains) if domains else '—'}\n\n"
        f"Обязательные навыки: {_format_skills(required)}\n"
        f"Желательные навыки: {_format_skills(optional)}\n"
        f"Soft skills: {_format_soft(v.soft_skills)}\n\n"
        f"Полный текст вакансии:\n"
        f'"""\n{truncate_by_sentence(v.raw_text or "", MAX_SCORER_VAC_CHARS)}\n"""'
    )


def _build_resume_block(r: Resume) -> str:
    exp = r.experience or {}
    total_years = exp.get("total_years")
    years_str = f"{total_years} лет" if total_years else "не указан"

    positions = exp.get("positions") or []
    pos_brief = "; ".join(
        f"{p.get('title', '?')}"
        + (f" @ {p['company']}" if p.get("company") else "")
        + (f" ({p['years']} лет)" if p.get("years") else "")
        for p in positions[:5]
    )

    return (
        f"Резюме кандидата: {r.candidate_name or 'без имени'}\n"
        f"Локация: {r.location or 'не указана'}\n"
        f"Формат: {r.preferred_work_format or 'не указан'}\n"
        f"Общий стаж: {years_str}\n\n"
        f"Навыки из резюме: {_format_skills(r.hard_skills)}\n"
        f"Soft skills: {_format_soft(r.soft_skills)}\n"
        f"Опыт работы: {pos_brief or '—'}\n\n"
        f"Полный текст резюме:\n"
        f'"""\n{truncate_by_sentence(r.raw_text or "", MAX_SCORER_RES_CHARS)}\n"""\n\n'
        f"Оцени соответствие этого кандидата вакансии выше."
    )


# ---------- Hard filter ----------

_REMOTE_LITERALS = {"remote", "удалённо", "удаленно"}


def passes_hard_filter(v: Vacancy, r: Resume) -> bool:
    """True if the pair clears location / work_format / ≥1 skill overlap."""
    # (a) Location
    if v.location and v.location.strip().lower() not in _REMOTE_LITERALS:
        same_city = (
            r.location is not None
            and r.location.strip().lower() == v.location.strip().lower()
        )
        remote_ok = r.preferred_work_format == "remote"
        if not (same_city or remote_ok):
            return False

    # (b) Work format
    if v.work_format == "office" and r.preferred_work_format == "remote":
        return False

    # (c) ≥1 hard_skills overlap (lowercase + strip)
    v_skills = {
        s["name"].strip().lower()
        for s in (v.hard_skills or [])
        if isinstance(s, dict) and s.get("name")
    }
    r_skills = {
        s["name"].strip().lower()
        for s in (r.hard_skills or [])
        if isinstance(s, dict) and s.get("name")
    }
    if v_skills and not (v_skills & r_skills):
        return False

    return True


# ---------- LLM scoring ----------


async def _score_pair(
    vacancy: Vacancy,
    resume: Resume,
    semaphore: asyncio.Semaphore,
) -> PairResult:
    """Score one vacancy↔resume pair with the vacancy block cached."""
    async with semaphore:
        try:
            result = await call_tool_use(
                system_blocks=[
                    text_block(_SCORING_INSTRUCTIONS, cache=True),
                    text_block(_build_vacancy_block(vacancy), cache=True),
                ],
                user_content=_build_resume_block(resume),
                tool=_SCORE_TOOL,
                max_tokens=800,
            )
        except ClaudeError as exc:
            logger.warning(
                "claude scoring failed for vac=%s res=%s: %s",
                vacancy.id,
                resume.id,
                exc,
            )
            return PairResult(vacancy.id, resume.id, None, str(exc)[:200])

        try:
            score = MatchScore.model_validate(result)
        except ValidationError as exc:
            logger.warning(
                "invalid score payload for vac=%s res=%s: %s",
                vacancy.id,
                resume.id,
                exc,
            )
            return PairResult(vacancy.id, resume.id, None, f"validation: {exc}")

    return PairResult(vacancy.id, resume.id, score, None)


async def _upsert_match(
    db: AsyncSession, vacancy_id: int, resume_id: int, result: PairResult
) -> None:
    score = result.score
    values: dict[str, Any] = {
        "vacancy_id": vacancy_id,
        "resume_id": resume_id,
        "score": score.score if score else None,
        "explanation": score.explanation if score else None,
        "matching_skills": [s for s in (score.matching_skills if score else [])],
        "missing_skills": [s for s in (score.missing_skills if score else [])],
        "error": result.error,
    }
    stmt = pg_insert(Match).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["vacancy_id", "resume_id"],
        set_={
            "score": stmt.excluded.score,
            "explanation": stmt.excluded.explanation,
            "matching_skills": stmt.excluded.matching_skills,
            "missing_skills": stmt.excluded.missing_skills,
            "error": stmt.excluded.error,
        },
    )
    await db.execute(stmt)


async def _existing_match_resume_ids(
    db: AsyncSession, vacancy_id: int, resume_ids: list[int]
) -> set[int]:
    if not resume_ids:
        return set()
    result = await db.execute(
        select(Match.resume_id).where(
            Match.vacancy_id == vacancy_id, Match.resume_id.in_(resume_ids)
        )
    )
    return {row[0] for row in result.all()}


async def _existing_match_vacancy_ids(
    db: AsyncSession, resume_id: int, vacancy_ids: list[int]
) -> set[int]:
    if not vacancy_ids:
        return set()
    result = await db.execute(
        select(Match.vacancy_id).where(
            Match.resume_id == resume_id, Match.vacancy_id.in_(vacancy_ids)
        )
    )
    return {row[0] for row in result.all()}


# ---------- Public pipeline ----------


async def score_resumes_for_vacancy(
    db: AsyncSession, vacancy: Vacancy, owner_id: int
) -> int:
    """Run 3-stage pipeline for one vacancy; UPSERT new pairs into `matches`.

    Returns the number of newly scored pairs. Skips pairs already in `matches`
    (cache hit). Safe to call multiple times — idempotent at the UPSERT level.
    """
    settings = get_settings()

    candidates: list[Candidate] = await find_candidate_resumes(
        db, vacancy_id=vacancy.id, owner_id=owner_id, k=settings.VECTOR_PREFILTER_K
    )
    if not candidates:
        return 0

    resumes = await load_resumes_by_ids(db, [c.id for c in candidates], owner_id)
    eligible: list[Resume] = [
        resumes[c.id] for c in candidates if c.id in resumes
        and passes_hard_filter(vacancy, resumes[c.id])
    ][: settings.SCORING_TOP_K]
    if not eligible:
        return 0

    already_scored = await _existing_match_resume_ids(
        db, vacancy.id, [r.id for r in eligible]
    )
    fresh = [r for r in eligible if r.id not in already_scored]
    if not fresh:
        return 0

    sem = asyncio.Semaphore(settings.LLM_CONCURRENCY)
    results = await asyncio.gather(*[_score_pair(vacancy, r, sem) for r in fresh])

    for r, result in zip(fresh, results, strict=True):
        await _upsert_match(db, vacancy.id, r.id, result)
    await db.commit()
    return len(fresh)


async def score_vacancies_for_resume(
    db: AsyncSession, resume: Resume, owner_id: int
) -> int:
    """Mirror of `score_resumes_for_vacancy` for the reverse direction."""
    settings = get_settings()

    candidates = await find_candidate_vacancies(
        db, resume_id=resume.id, owner_id=owner_id, k=settings.VECTOR_PREFILTER_K
    )
    if not candidates:
        return 0

    vacancies = await load_vacancies_by_ids(db, [c.id for c in candidates], owner_id)
    eligible: list[Vacancy] = [
        vacancies[c.id] for c in candidates if c.id in vacancies
        and passes_hard_filter(vacancies[c.id], resume)
    ][: settings.SCORING_TOP_K]
    if not eligible:
        return 0

    already_scored = await _existing_match_vacancy_ids(
        db, resume.id, [v.id for v in eligible]
    )
    fresh = [v for v in eligible if v.id not in already_scored]
    if not fresh:
        return 0

    sem = asyncio.Semaphore(settings.LLM_CONCURRENCY)
    results = await asyncio.gather(*[_score_pair(v, resume, sem) for v in fresh])

    for v, result in zip(fresh, results, strict=True):
        await _upsert_match(db, v.id, resume.id, result)
    await db.commit()
    return len(fresh)
