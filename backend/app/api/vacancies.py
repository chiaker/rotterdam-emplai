from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.db.models import Vacancy
from app.schemas.vacancies import VacancyListItem, VacancyResponse
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

    title = Path(file.filename).stem[:500] or "Без названия"

    vacancy = Vacancy(
        owner_id=current_user.id,
        title=title,
        raw_text=text,
        source_format=source_format,
    )
    db.add(vacancy)
    await db.commit()
    await db.refresh(vacancy)
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
