from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    vacancies: Mapped[list["Vacancy"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    resumes: Mapped[list["Resume"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class Vacancy(Base, TimestampMixin):
    __tablename__ = "vacancies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_format: Mapped[str] = mapped_column(String(16), nullable=False)

    hard_skills: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    soft_skills: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    experience: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    work_format: Mapped[str | None] = mapped_column(String(32), nullable=True)
    work_hours: Mapped[str | None] = mapped_column(String(64), nullable=True)
    other_requirements: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    owner: Mapped[User] = relationship(back_populates="vacancies")
    matches: Mapped[list["Match"]] = relationship(
        back_populates="vacancy", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_vacancies_hard_skills_gin", "hard_skills", postgresql_using="gin"),
        Index("ix_vacancies_soft_skills_gin", "soft_skills", postgresql_using="gin"),
    )


class Resume(Base, TimestampMixin):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_format: Mapped[str] = mapped_column(String(16), nullable=False)

    hard_skills: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    soft_skills: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    experience: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preferred_work_format: Mapped[str | None] = mapped_column(String(32), nullable=True)
    other_traits: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    owner: Mapped[User] = relationship(back_populates="resumes")
    matches: Mapped[list["Match"]] = relationship(
        back_populates="resume", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_resumes_hard_skills_gin", "hard_skills", postgresql_using="gin"),
        Index("ix_resumes_soft_skills_gin", "soft_skills", postgresql_using="gin"),
    )


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(
        ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False
    )
    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    matching_skills: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    missing_skills: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    vacancy: Mapped[Vacancy] = relationship(back_populates="matches")
    resume: Mapped[Resume] = relationship(back_populates="matches")

    __table_args__ = (
        UniqueConstraint("vacancy_id", "resume_id", name="uq_matches_vacancy_resume"),
        Index("ix_matches_vacancy_score", "vacancy_id", "score"),
        Index("ix_matches_resume_score", "resume_id", "score"),
    )
