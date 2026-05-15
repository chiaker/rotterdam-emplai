from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.db.models import Vacancy
from app.schemas.vacancies import VacancyListItem, VacancyResponse
from app.services.background import score_after_upload
from app.services.enrichment import enrich_document
from app.services.parser import ParserError, parse

router = APIRouter(prefix="/api/vacancies", tags=["vacancies"])


@router.post(
    "",
    response_model=VacancyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить вакансию из файла (txt/pdf/docx)",
)
async def upload_vacancy(
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> Vacancy:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Missing filename"
        )

    raw_bytes = await file.read()
    try:
        text, source_format = parse(file.filename, raw_bytes)
    except ParserError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    enrichment = await enrich_document(text, kind="vacancy")
    ex = enrichment.extraction
    title = (
        (ex.title[:500] if ex is not None else None)
        or Path(file.filename).stem[:500]
        or "Без названия"
    )

    vacancy = Vacancy(
        owner_id=current_user.id,
        title=title,
        raw_text=text,
        source_format=source_format,
        hard_skills=[s.model_dump() for s in ex.hard_skills] if ex else [],
        soft_skills=list(ex.soft_skills) if ex else [],
        experience=ex.experience.model_dump() if ex else {},
        location=ex.location if ex else None,
        work_format=ex.work_format if ex else None,
        work_hours=ex.work_hours if ex else None,
        other_requirements=ex.other_requirements if ex else {},
        embedding_doc=enrichment.embedding_doc,
        embedding_skills=enrichment.embedding_skills,
        embedding_experience=enrichment.embedding_experience,
        extraction_status=enrichment.status,
    )
    db.add(vacancy)
    await db.commit()
    await db.refresh(vacancy)

    if vacancy.extraction_status == "ok":
        background_tasks.add_task(
            score_after_upload, "vacancy", vacancy.id, current_user.id
        )

    return vacancy


@router.get("", response_model=list[VacancyListItem])
async def list_vacancies(db: DbSession, current_user: CurrentUser) -> list[Vacancy]:
    result = await db.execute(
        select(Vacancy)
        .where(Vacancy.owner_id == current_user.id)
        .order_by(Vacancy.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{vacancy_id}", response_model=VacancyResponse)
async def get_vacancy(
    vacancy_id: int, db: DbSession, current_user: CurrentUser
) -> Vacancy:
    result = await db.execute(
        select(Vacancy).where(
            Vacancy.id == vacancy_id, Vacancy.owner_id == current_user.id
        )
    )
    vacancy = result.scalar_one_or_none()
    if vacancy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found"
        )
    return vacancy


@router.delete("/{vacancy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vacancy(
    vacancy_id: int, db: DbSession, current_user: CurrentUser
) -> None:
    result = await db.execute(
        select(Vacancy).where(
            Vacancy.id == vacancy_id, Vacancy.owner_id == current_user.id
        )
    )
    vacancy = result.scalar_one_or_none()
    if vacancy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found"
        )
    await db.delete(vacancy)
    await db.commit()
