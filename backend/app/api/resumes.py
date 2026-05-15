from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.db.models import Resume
from app.schemas.resumes import ResumeListItem, ResumeResponse
from app.services.parser import ParserError, parse

router = APIRouter(prefix="/api/resumes", tags=["resumes"])


@router.post(
    "",
    response_model=ResumeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить резюме из файла (txt/pdf/docx)",
)
async def upload_resume(
    db: DbSession,
    current_user: CurrentUser,
    file: UploadFile = File(...),
) -> Resume:
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

    candidate_name = Path(file.filename).stem[:255] or None

    resume = Resume(
        owner_id=current_user.id,
        candidate_name=candidate_name,
        raw_text=text,
        source_format=source_format,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    return resume


@router.get("", response_model=list[ResumeListItem])
async def list_resumes(db: DbSession, current_user: CurrentUser) -> list[Resume]:
    result = await db.execute(
        select(Resume)
        .where(Resume.owner_id == current_user.id)
        .order_by(Resume.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    resume_id: int, db: DbSession, current_user: CurrentUser
) -> Resume:
    result = await db.execute(
        select(Resume).where(
            Resume.id == resume_id, Resume.owner_id == current_user.id
        )
    )
    resume = result.scalar_one_or_none()
    if resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )
    return resume


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    resume_id: int, db: DbSession, current_user: CurrentUser
) -> None:
    result = await db.execute(
        select(Resume).where(
            Resume.id == resume_id, Resume.owner_id == current_user.id
        )
    )
    resume = result.scalar_one_or_none()
    if resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )
    await db.delete(resume)
    await db.commit()
