"""Typer CLI for ingest + match flows.

Reuses the same services as the HTTP API, so output is identical to what
Swagger returns. Useful for offline demos and quick sanity checks.

Run: `python -m app.cli --help`
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from sqlalchemy import select

from app.db.models import Resume, User, Vacancy
from app.db.session import AsyncSessionLocal
from app.services.enrichment import enrich_document
from app.services.matcher import (
    score_resumes_for_vacancy,
    score_vacancies_for_resume,
)
from app.services.parser import ParserError, parse

app = typer.Typer(help="EmplAI offline CLI for ingest and match flows.")


async def _get_or_create_cli_user() -> User:
    """Anonymous CLI user — owns everything ingested via CLI."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == "cli@local"))
        user = result.scalar_one_or_none()
        if user is not None:
            return user
        user = User(email="cli@local", hashed_password="!cli-only-no-login")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def _ingest_file(path: Path, kind: str) -> dict:
    raw_bytes = path.read_bytes()
    try:
        text, source_format = parse(path.name, raw_bytes)
    except ParserError as exc:
        return {"error": f"parser: {exc}"}

    enrichment = await enrich_document(text, kind=kind)  # type: ignore[arg-type]
    ex = enrichment.extraction
    user = await _get_or_create_cli_user()

    async with AsyncSessionLocal() as db:
        if kind == "vacancy":
            row = Vacancy(
                owner_id=user.id,
                title=(ex.title if ex else path.stem)[:500] or "Без названия",
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
        else:
            row = Resume(
                owner_id=user.id,
                candidate_name=(ex.candidate_name if ex and ex.candidate_name else path.stem)[:255],
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
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return {
            "id": row.id,
            "extraction_status": row.extraction_status,
            "source_format": row.source_format,
            "title": getattr(row, "title", None) or getattr(row, "candidate_name", None),
        }


@app.command("ingest-vacancy")
def ingest_vacancy(path: Path) -> None:
    """Parse + extract + embed + save a vacancy file."""
    result = asyncio.run(_ingest_file(path, "vacancy"))
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command("ingest-resume")
def ingest_resume(path: Path) -> None:
    """Parse + extract + embed + save a resume file."""
    result = asyncio.run(_ingest_file(path, "resume"))
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


async def _match_vacancy(vacancy_id: int, top: int) -> dict:
    user = await _get_or_create_cli_user()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Vacancy).where(
                Vacancy.id == vacancy_id, Vacancy.owner_id == user.id
            )
        )
        vacancy = result.scalar_one_or_none()
        if vacancy is None:
            return {"error": "vacancy not found"}
        if vacancy.extraction_status != "ok":
            return {"error": f"extraction_status={vacancy.extraction_status}"}

        scored = await score_resumes_for_vacancy(db, vacancy, user.id)
        return {"vacancy_id": vacancy_id, "newly_scored": scored, "top": top}


async def _match_resume(resume_id: int, top: int) -> dict:
    user = await _get_or_create_cli_user()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Resume).where(
                Resume.id == resume_id, Resume.owner_id == user.id
            )
        )
        resume = result.scalar_one_or_none()
        if resume is None:
            return {"error": "resume not found"}
        if resume.extraction_status != "ok":
            return {"error": f"extraction_status={resume.extraction_status}"}

        scored = await score_vacancies_for_resume(db, resume, user.id)
        return {"resume_id": resume_id, "newly_scored": scored, "top": top}


@app.command("match-vacancy")
def match_vacancy(vacancy_id: int, top: int = typer.Option(10, "--top")) -> None:
    """Run vector→hard-filter→LLM scoring for a vacancy."""
    result = asyncio.run(_match_vacancy(vacancy_id, top))
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command("match-resume")
def match_resume(resume_id: int, top: int = typer.Option(10, "--top")) -> None:
    """Run vector→hard-filter→LLM scoring for a resume."""
    result = asyncio.run(_match_resume(resume_id, top))
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command("demo")
def demo(
    vacancies_dir: Path = typer.Option(
        Path("/app/demo_files/Вакансии"), "--vacancies-dir"
    ),
    resumes_dir: Path = typer.Option(
        Path("/app/demo_files/Резюме"), "--resumes-dir"
    ),
    max_vacancies: int = typer.Option(3, "--max-vacancies"),
    max_resumes: int = typer.Option(10, "--max-resumes"),
) -> None:
    """End-to-end demo: ingest N vacancies + M resumes, run matching."""

    async def _run() -> None:
        # Filter to txt by default — fastest for demo
        vac_files = sorted(p for p in vacancies_dir.glob("*.txt"))[:max_vacancies]
        res_files = sorted(p for p in resumes_dir.glob("*.txt"))[:max_resumes]

        typer.echo(f"Ingesting {len(vac_files)} vacancies + {len(res_files)} resumes...")

        vacancy_ids: list[int] = []
        for p in vac_files:
            typer.echo(f"  vacancy: {p.name}")
            r = await _ingest_file(p, "vacancy")
            if "id" in r:
                vacancy_ids.append(r["id"])

        for p in res_files:
            typer.echo(f"  resume:  {p.name}")
            await _ingest_file(p, "resume")

        typer.echo("\nMatching each vacancy against all resumes...")
        for vid in vacancy_ids:
            r = await _match_vacancy(vid, top=10)
            typer.echo(f"  vacancy {vid}: {r}")

    asyncio.run(_run())


if __name__ == "__main__":
    app()
