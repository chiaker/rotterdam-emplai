"""pgvector-backed retrieval queries for vacancy↔resume matching.

Provides two directions of vector pre-filter (top-K by hybrid cosine similarity
across embedding_doc / embedding_skills / embedding_experience), plus two
orphan-aggregation queries that find docs whose best score is below threshold
or which have no scored matches yet.

All queries are scoped by owner_id so users only see their own data.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Resume, Vacancy

VECTOR_WEIGHT_DOC = 0.4
VECTOR_WEIGHT_SKILLS = 0.4
VECTOR_WEIGHT_EXPERIENCE = 0.2


@dataclass(frozen=True, slots=True)
class Candidate:
    """One row from a vector pre-filter query."""

    id: int
    sim_doc: float
    sim_skills: float
    sim_experience: float
    combined_sim: float


_FIND_RESUMES_SQL = text(
    """
    WITH v AS (
      SELECT embedding_doc, embedding_skills, embedding_experience
        FROM vacancies WHERE id = :vacancy_id
    )
    SELECT r.id AS id,
           1 - (r.embedding_doc        <=> v.embedding_doc)        AS sim_doc,
           1 - (r.embedding_skills     <=> v.embedding_skills)     AS sim_skills,
           1 - (r.embedding_experience <=> v.embedding_experience) AS sim_experience,
           :w_doc    * (1 - (r.embedding_doc        <=> v.embedding_doc))
         + :w_skills * (1 - (r.embedding_skills     <=> v.embedding_skills))
         + :w_exp    * (1 - (r.embedding_experience <=> v.embedding_experience))
           AS combined_sim
      FROM resumes r, v
     WHERE r.owner_id = :owner_id
       AND r.extraction_status = 'ok'
       AND r.embedding_doc        IS NOT NULL
       AND r.embedding_skills     IS NOT NULL
       AND r.embedding_experience IS NOT NULL
     ORDER BY combined_sim DESC
     LIMIT :k
    """
)


_FIND_VACANCIES_SQL = text(
    """
    WITH r AS (
      SELECT embedding_doc, embedding_skills, embedding_experience
        FROM resumes WHERE id = :resume_id
    )
    SELECT v.id AS id,
           1 - (v.embedding_doc        <=> r.embedding_doc)        AS sim_doc,
           1 - (v.embedding_skills     <=> r.embedding_skills)     AS sim_skills,
           1 - (v.embedding_experience <=> r.embedding_experience) AS sim_experience,
           :w_doc    * (1 - (v.embedding_doc        <=> r.embedding_doc))
         + :w_skills * (1 - (v.embedding_skills     <=> r.embedding_skills))
         + :w_exp    * (1 - (v.embedding_experience <=> r.embedding_experience))
           AS combined_sim
      FROM vacancies v, r
     WHERE v.owner_id = :owner_id
       AND v.extraction_status = 'ok'
       AND v.embedding_doc        IS NOT NULL
       AND v.embedding_skills     IS NOT NULL
       AND v.embedding_experience IS NOT NULL
     ORDER BY combined_sim DESC
     LIMIT :k
    """
)


async def find_candidate_resumes(
    db: AsyncSession, *, vacancy_id: int, owner_id: int, k: int
) -> list[Candidate]:
    """Top-K resumes nearest to the given vacancy by hybrid cosine similarity."""
    rows = await db.execute(
        _FIND_RESUMES_SQL,
        {
            "vacancy_id": vacancy_id,
            "owner_id": owner_id,
            "k": k,
            "w_doc": VECTOR_WEIGHT_DOC,
            "w_skills": VECTOR_WEIGHT_SKILLS,
            "w_exp": VECTOR_WEIGHT_EXPERIENCE,
        },
    )
    return [Candidate(**dict(r._mapping)) for r in rows]


async def find_candidate_vacancies(
    db: AsyncSession, *, resume_id: int, owner_id: int, k: int
) -> list[Candidate]:
    """Top-K vacancies nearest to the given resume by hybrid cosine similarity."""
    rows = await db.execute(
        _FIND_VACANCIES_SQL,
        {
            "resume_id": resume_id,
            "owner_id": owner_id,
            "k": k,
            "w_doc": VECTOR_WEIGHT_DOC,
            "w_skills": VECTOR_WEIGHT_SKILLS,
            "w_exp": VECTOR_WEIGHT_EXPERIENCE,
        },
    )
    return [Candidate(**dict(r._mapping)) for r in rows]


_ORPHAN_VACANCIES_SQL = text(
    """
    SELECT v.id
      FROM vacancies v
      LEFT JOIN matches m ON m.vacancy_id = v.id
     WHERE v.owner_id = :owner_id
       AND v.extraction_status = 'ok'
     GROUP BY v.id, v.created_at
    HAVING COALESCE(MAX(m.score), 0) < :threshold
     ORDER BY v.created_at DESC
     LIMIT :limit
    """
)


_ORPHAN_RESUMES_SQL = text(
    """
    SELECT r.id
      FROM resumes r
      LEFT JOIN matches m ON m.resume_id = r.id
     WHERE r.owner_id = :owner_id
       AND r.extraction_status = 'ok'
     GROUP BY r.id, r.created_at
    HAVING COALESCE(MAX(m.score), 0) < :threshold
     ORDER BY r.created_at DESC
     LIMIT :limit
    """
)


async def find_orphan_vacancy_ids(
    db: AsyncSession, *, owner_id: int, threshold: int, limit: int
) -> list[int]:
    """Vacancies whose best match score is below threshold (or have no matches yet)."""
    rows = await db.execute(
        _ORPHAN_VACANCIES_SQL,
        {"owner_id": owner_id, "threshold": threshold, "limit": limit},
    )
    return [int(r[0]) for r in rows]


async def find_orphan_resume_ids(
    db: AsyncSession, *, owner_id: int, threshold: int, limit: int
) -> list[int]:
    """Resumes whose best match score is below threshold (or have no matches yet)."""
    rows = await db.execute(
        _ORPHAN_RESUMES_SQL,
        {"owner_id": owner_id, "threshold": threshold, "limit": limit},
    )
    return [int(r[0]) for r in rows]


async def load_vacancies_by_ids(
    db: AsyncSession, ids: list[int], owner_id: int
) -> dict[int, Vacancy]:
    """Load vacancies by ID, scoped to owner. Returns a dict for ordered re-lookup."""
    if not ids:
        return {}
    from sqlalchemy import select

    result = await db.execute(
        select(Vacancy).where(Vacancy.id.in_(ids), Vacancy.owner_id == owner_id)
    )
    return {v.id: v for v in result.scalars().all()}


async def load_resumes_by_ids(
    db: AsyncSession, ids: list[int], owner_id: int
) -> dict[int, Resume]:
    """Load resumes by ID, scoped to owner. Returns a dict for ordered re-lookup."""
    if not ids:
        return {}
    from sqlalchemy import select

    result = await db.execute(
        select(Resume).where(Resume.id.in_(ids), Resume.owner_id == owner_id)
    )
    return {r.id: r for r in result.scalars().all()}
