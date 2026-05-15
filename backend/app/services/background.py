"""Fire-and-forget background scoring kicked off after upload.

Uses its own AsyncSession (the request session is closed by the time these run).
Catches all exceptions and logs them — never propagates to the request.
"""
from __future__ import annotations

import logging
from typing import Literal

from sqlalchemy import select

from app.db.models import Resume, Vacancy
from app.db.session import AsyncSessionLocal
from app.services.matcher import score_resumes_for_vacancy, score_vacancies_for_resume

logger = logging.getLogger(__name__)


async def score_after_upload(
    kind: Literal["vacancy", "resume"], doc_id: int, owner_id: int
) -> None:
    """Run vector → hard-filter → LLM scoring for the freshly uploaded doc."""
    try:
        async with AsyncSessionLocal() as db:
            if kind == "vacancy":
                result = await db.execute(
                    select(Vacancy).where(
                        Vacancy.id == doc_id, Vacancy.owner_id == owner_id
                    )
                )
                vacancy = result.scalar_one_or_none()
                if not vacancy or vacancy.extraction_status != "ok":
                    return
                scored = await score_resumes_for_vacancy(db, vacancy, owner_id)
                logger.info("scored %d resumes for vacancy=%s", scored, doc_id)
            else:
                result = await db.execute(
                    select(Resume).where(
                        Resume.id == doc_id, Resume.owner_id == owner_id
                    )
                )
                resume = result.scalar_one_or_none()
                if not resume or resume.extraction_status != "ok":
                    return
                scored = await score_vacancies_for_resume(db, resume, owner_id)
                logger.info("scored %d vacancies for resume=%s", scored, doc_id)
    except Exception:
        logger.exception("background scoring failed for %s=%s", kind, doc_id)
