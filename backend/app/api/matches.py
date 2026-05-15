"""Match endpoints — 4 flows + manual recompute.

All endpoints are owner-scoped (a user only sees their own vacancies/resumes).
The first call for a given vacancy/resume triggers vector pre-filter + hard
filter + Claude scoring; subsequent calls read from the `matches` cache.

Orphan endpoints rely on background scoring kicked off at upload time. If a
doc has no rows in `matches` yet (e.g. user disabled background tasks or upload
failed), it's classified as orphan (`COALESCE(MAX(score), 0) < threshold`).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.db.models import Match, Resume, Vacancy
from app.schemas.matches import (
    MatchItem,
    MatchList,
    OrphanItem,
    OrphanList,
    RecomputeResponse,
)
from app.services.matcher import (
    score_resumes_for_vacancy,
    score_vacancies_for_resume,
)
from app.services.repository import (
    find_orphan_resume_ids,
    find_orphan_vacancy_ids,
)

router = APIRouter(prefix="/api/matches", tags=["matches"])


def _top_n(top: int | None) -> int:
    settings = get_settings()
    if top is None:
        return settings.DEFAULT_MATCH_TOP_N
    return min(max(top, 1), settings.MAX_MATCH_TOP_N)


async def _get_owned_vacancy(
    db: DbSession, vacancy_id: int, owner_id: int
) -> Vacancy:
    result = await db.execute(
        select(Vacancy).where(Vacancy.id == vacancy_id, Vacancy.owner_id == owner_id)
    )
    vacancy = result.scalar_one_or_none()
    if vacancy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found"
        )
    return vacancy


async def _get_owned_resume(
    db: DbSession, resume_id: int, owner_id: int
) -> Resume:
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.owner_id == owner_id)
    )
    resume = result.scalar_one_or_none()
    if resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )
    return resume


@router.get(
    "/vacancy/{vacancy_id}",
    response_model=MatchList,
    summary="Топ-N резюме под вакансию (score ≥ порог)",
)
async def matches_for_vacancy(
    vacancy_id: int,
    db: DbSession,
    current_user: CurrentUser,
    top: int = Query(default=None, ge=1, le=100),
) -> MatchList:
    settings = get_settings()
    vacancy = await _get_owned_vacancy(db, vacancy_id, current_user.id)

    if vacancy.extraction_status != "ok":
        return MatchList(
            items=[],
            note=f"vacancy extraction_status={vacancy.extraction_status}",
        )

    # Lazy fallback: if no scored pairs yet, kick off scoring inline.
    existing = await db.execute(
        select(Match).where(Match.vacancy_id == vacancy_id).limit(1)
    )
    if existing.scalar_one_or_none() is None:
        await score_resumes_for_vacancy(db, vacancy, current_user.id)

    result = await db.execute(
        select(Match)
        .where(
            Match.vacancy_id == vacancy_id,
            Match.score >= settings.MATCH_SCORE_THRESHOLD,
        )
        .order_by(Match.score.desc())
        .limit(_top_n(top))
    )
    items = [MatchItem.model_validate(m) for m in result.scalars().all()]
    return MatchList(items=items)


@router.get(
    "/resume/{resume_id}",
    response_model=MatchList,
    summary="Топ-K вакансий под резюме (score ≥ порог)",
)
async def matches_for_resume(
    resume_id: int,
    db: DbSession,
    current_user: CurrentUser,
    top: int = Query(default=None, ge=1, le=100),
) -> MatchList:
    settings = get_settings()
    resume = await _get_owned_resume(db, resume_id, current_user.id)

    if resume.extraction_status != "ok":
        return MatchList(
            items=[],
            note=f"resume extraction_status={resume.extraction_status}",
        )

    existing = await db.execute(
        select(Match).where(Match.resume_id == resume_id).limit(1)
    )
    if existing.scalar_one_or_none() is None:
        await score_vacancies_for_resume(db, resume, current_user.id)

    result = await db.execute(
        select(Match)
        .where(
            Match.resume_id == resume_id,
            Match.score >= settings.MATCH_SCORE_THRESHOLD,
        )
        .order_by(Match.score.desc())
        .limit(_top_n(top))
    )
    items = [MatchItem.model_validate(m) for m in result.scalars().all()]
    return MatchList(items=items)


@router.get(
    "/orphan-vacancies",
    response_model=OrphanList,
    summary="Вакансии без матчей ≥ порога",
)
async def orphan_vacancies(
    db: DbSession,
    current_user: CurrentUser,
    top: int = Query(default=None, ge=1, le=100),
) -> OrphanList:
    settings = get_settings()
    limit = _top_n(top)
    ids = await find_orphan_vacancy_ids(
        db,
        owner_id=current_user.id,
        threshold=settings.MATCH_SCORE_THRESHOLD,
        limit=limit,
    )
    if not ids:
        return OrphanList(items=[], threshold=settings.MATCH_SCORE_THRESHOLD)

    result = await db.execute(select(Vacancy).where(Vacancy.id.in_(ids)))
    by_id = {v.id: v for v in result.scalars().all()}
    items = [
        OrphanItem(id=i, title=by_id[i].title if i in by_id else None)
        for i in ids
        if i in by_id
    ]
    return OrphanList(items=items, threshold=settings.MATCH_SCORE_THRESHOLD)


@router.get(
    "/orphan-resumes",
    response_model=OrphanList,
    summary="Резюме без матчей ≥ порога",
)
async def orphan_resumes(
    db: DbSession,
    current_user: CurrentUser,
    top: int = Query(default=None, ge=1, le=100),
) -> OrphanList:
    settings = get_settings()
    limit = _top_n(top)
    ids = await find_orphan_resume_ids(
        db,
        owner_id=current_user.id,
        threshold=settings.MATCH_SCORE_THRESHOLD,
        limit=limit,
    )
    if not ids:
        return OrphanList(items=[], threshold=settings.MATCH_SCORE_THRESHOLD)

    result = await db.execute(select(Resume).where(Resume.id.in_(ids)))
    by_id = {r.id: r for r in result.scalars().all()}
    items = [
        OrphanItem(id=i, candidate_name=by_id[i].candidate_name if i in by_id else None)
        for i in ids
        if i in by_id
    ]
    return OrphanList(items=items, threshold=settings.MATCH_SCORE_THRESHOLD)


@router.post(
    "/recompute/vacancy/{vacancy_id}",
    response_model=RecomputeResponse,
    summary="Запустить скоринг для вакансии (минуя кэш только для новых пар)",
)
async def recompute_vacancy(
    vacancy_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> RecomputeResponse:
    vacancy = await _get_owned_vacancy(db, vacancy_id, current_user.id)
    if vacancy.extraction_status != "ok":
        return RecomputeResponse(
            vacancy_id=vacancy_id,
            scored=0,
            note=f"extraction_status={vacancy.extraction_status}",
        )
    scored = await score_resumes_for_vacancy(db, vacancy, current_user.id)
    return RecomputeResponse(vacancy_id=vacancy_id, scored=scored)


@router.post(
    "/recompute/resume/{resume_id}",
    response_model=RecomputeResponse,
    summary="Запустить скоринг для резюме (минуя кэш только для новых пар)",
)
async def recompute_resume(
    resume_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> RecomputeResponse:
    resume = await _get_owned_resume(db, resume_id, current_user.id)
    if resume.extraction_status != "ok":
        return RecomputeResponse(
            resume_id=resume_id,
            scored=0,
            note=f"extraction_status={resume.extraction_status}",
        )
    scored = await score_vacancies_for_resume(db, resume, current_user.id)
    return RecomputeResponse(resume_id=resume_id, scored=scored)
