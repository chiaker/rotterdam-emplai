from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.db.models import Resume
from app.schemas.resumes import ResumeListItem, ResumeResponse
from app.services.background import score_after_upload
from app.services.enrichment import enrich_document
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
    background_tasks: BackgroundTasks,
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

    enrichment = await enrich_document(text, kind="resume")
    ex = enrichment.extraction
    candidate_name = (
        (ex.candidate_name[:255] if ex is not None and ex.candidate_name else None)
        or Path(file.filename).stem[:255]
        or None
    )

    resume = Resume(
        owner_id=current_user.id,
        candidate_name=candidate_name,
        raw_text=text,
        source_format=source_format,
        hard_skills=[s.model_dump() for s in ex.hard_skills] if ex else [],
        soft_skills=list(ex.soft_skills) if ex else [],
        experience=ex.experience.model_dump() if ex else {},
        location=ex.location if ex else None,
        preferred_work_format=ex.preferred_work_format if ex else None,
        other_traits=ex.other_traits if ex else {},
        embedding_doc=enrichment.embedding_doc,
        embedding_skills=enrichment.embedding_skills,
        embedding_experience=enrichment.embedding_experience,
        extraction_status=enrichment.status,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)

    if resume.extraction_status == "ok":
        background_tasks.add_task(
            score_after_upload, "resume", resume.id, current_user.id
        )

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
