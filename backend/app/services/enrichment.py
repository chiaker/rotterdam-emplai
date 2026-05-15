"""Orchestrate Claude extraction + GigaChat embedding for one vacancy/resume.

Called synchronously from the upload endpoint. On any external-service failure
we still save the row (with `extraction_status='failed'`) so the user keeps
their raw text — they just won't show up in matching until re-uploaded.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from app.services.embedder import EmbedderError, get_embedder
from app.services.extractor import (
    ExtractorError,
    ResumeExtraction,
    VacancyExtraction,
    extract_resume,
    extract_vacancy,
)
from app.services.text_utils import (
    MAX_EMBED_DOC_CHARS,
    MAX_EMBED_EXP_CHARS,
    truncate_by_sentence,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EnrichmentResult:
    """Output of the enrichment pipeline for one document."""

    extraction: VacancyExtraction | ResumeExtraction | None
    embedding_doc: list[float] | None
    embedding_skills: list[float] | None
    embedding_experience: list[float] | None
    status: Literal["ok", "failed"]


def _vacancy_skills_text(ex: VacancyExtraction) -> str:
    hard = ", ".join(s.name for s in ex.hard_skills) if ex.hard_skills else ""
    soft = ", ".join(ex.soft_skills) if ex.soft_skills else ""
    parts = [ex.title]
    if hard:
        parts.append(f"Hard skills: {hard}")
    if soft:
        parts.append(f"Soft skills: {soft}")
    return ". ".join(parts)


def _vacancy_experience_text(ex: VacancyExtraction) -> str:
    e = ex.experience
    if e.years_min is None and e.years_max is None and not e.domains:
        return "Опыт не указан"
    if e.years_min and e.years_max:
        years = f"{e.years_min}-{e.years_max} лет"
    elif e.years_min:
        years = f"от {e.years_min} лет"
    elif e.years_max:
        years = f"до {e.years_max} лет"
    else:
        years = "опыт"
    domains = ", ".join(e.domains) if e.domains else ""
    return f"{years} опыта" + (f" в: {domains}" if domains else "")


def _resume_skills_text(ex: ResumeExtraction) -> str:
    hard = ", ".join(s.name for s in ex.hard_skills) if ex.hard_skills else ""
    soft = ", ".join(ex.soft_skills) if ex.soft_skills else ""
    parts = []
    if ex.candidate_name:
        parts.append(ex.candidate_name)
    if hard:
        parts.append(f"Hard skills: {hard}")
    if soft:
        parts.append(f"Soft skills: {soft}")
    return ". ".join(parts) if parts else "—"


def _resume_experience_text(ex: ResumeExtraction) -> str:
    e = ex.experience
    if not e.positions and not e.total_years:
        return "Опыт не указан"
    parts = []
    if e.total_years:
        parts.append(f"Общий стаж {e.total_years} лет.")
    for p in e.positions:
        line = p.title
        if p.company:
            line += f" в {p.company}"
        if p.years:
            line += f" ({p.years} лет)"
        if p.description:
            line += f": {p.description}"
        parts.append(line)
    return " ".join(parts)


def _build_chunks(
    raw_text: str,
    extraction: VacancyExtraction | ResumeExtraction | None,
    kind: Literal["vacancy", "resume"],
) -> list[str]:
    doc_chunk = truncate_by_sentence(raw_text, MAX_EMBED_DOC_CHARS)

    if extraction is None:
        # Fallback: three copies of the doc chunk (graceful degradation).
        fallback = truncate_by_sentence(raw_text, MAX_EMBED_EXP_CHARS)
        return [doc_chunk, fallback, fallback]

    if kind == "vacancy":
        assert isinstance(extraction, VacancyExtraction)
        skills_chunk = _vacancy_skills_text(extraction)
        exp_chunk = truncate_by_sentence(
            _vacancy_experience_text(extraction), MAX_EMBED_EXP_CHARS
        )
    else:
        assert isinstance(extraction, ResumeExtraction)
        skills_chunk = _resume_skills_text(extraction)
        exp_chunk = truncate_by_sentence(
            _resume_experience_text(extraction), MAX_EMBED_EXP_CHARS
        )
    return [doc_chunk, skills_chunk, exp_chunk]


async def enrich_document(
    raw_text: str, kind: Literal["vacancy", "resume"]
) -> EnrichmentResult:
    """Run Claude extract + GigaChat embed for one document.

    Always returns a result — on any failure, returns status='failed' with
    whichever pieces succeeded set to None. Never raises.
    """
    extraction: VacancyExtraction | ResumeExtraction | None = None
    try:
        if kind == "vacancy":
            extraction = await extract_vacancy(raw_text)
        else:
            extraction = await extract_resume(raw_text)
    except ExtractorError as exc:
        logger.warning("extractor failed for %s: %s", kind, exc)

    chunks = _build_chunks(raw_text, extraction, kind)
    try:
        embedder = get_embedder()
        vectors = await embedder.embed_batch(chunks)
    except EmbedderError as exc:
        logger.warning("embedder failed for %s: %s", kind, exc)
        return EnrichmentResult(extraction, None, None, None, "failed")

    if len(vectors) != 3:
        logger.warning("embedder returned %d vectors, expected 3", len(vectors))
        return EnrichmentResult(extraction, None, None, None, "failed")

    status: Literal["ok", "failed"] = "ok" if extraction is not None else "failed"
    return EnrichmentResult(extraction, vectors[0], vectors[1], vectors[2], status)
