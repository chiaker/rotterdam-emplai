"""initial schema: users, vacancies, resumes, matches

Revision ID: 20260515_0001
Revises:
Create Date: 2026-05-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260515_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "vacancies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("source_format", sa.String(length=16), nullable=False),
        sa.Column(
            "hard_skills",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "soft_skills",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "experience",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("work_format", sa.String(length=32), nullable=True),
        sa.Column("work_hours", sa.String(length=64), nullable=True),
        sa.Column(
            "other_requirements",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], ondelete="CASCADE", name="fk_vacancies_owner_id"
        ),
    )
    op.create_index("ix_vacancies_owner_id", "vacancies", ["owner_id"])
    op.create_index(
        "ix_vacancies_hard_skills_gin", "vacancies", ["hard_skills"], postgresql_using="gin"
    )
    op.create_index(
        "ix_vacancies_soft_skills_gin", "vacancies", ["soft_skills"], postgresql_using="gin"
    )

    op.create_table(
        "resumes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("candidate_name", sa.String(length=255), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("source_format", sa.String(length=16), nullable=False),
        sa.Column(
            "hard_skills",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "soft_skills",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "experience",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("preferred_work_format", sa.String(length=32), nullable=True),
        sa.Column(
            "other_traits",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], ondelete="CASCADE", name="fk_resumes_owner_id"
        ),
    )
    op.create_index("ix_resumes_owner_id", "resumes", ["owner_id"])
    op.create_index(
        "ix_resumes_hard_skills_gin", "resumes", ["hard_skills"], postgresql_using="gin"
    )
    op.create_index(
        "ix_resumes_soft_skills_gin", "resumes", ["soft_skills"], postgresql_using="gin"
    )

    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vacancy_id", sa.Integer(), nullable=False),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column(
            "matching_skills",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "missing_skills",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("error", sa.String(length=255), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["vacancy_id"], ["vacancies.id"], ondelete="CASCADE", name="fk_matches_vacancy_id"
        ),
        sa.ForeignKeyConstraint(
            ["resume_id"], ["resumes.id"], ondelete="CASCADE", name="fk_matches_resume_id"
        ),
        sa.UniqueConstraint("vacancy_id", "resume_id", name="uq_matches_vacancy_resume"),
    )
    op.create_index("ix_matches_vacancy_score", "matches", ["vacancy_id", "score"])
    op.create_index("ix_matches_resume_score", "matches", ["resume_id", "score"])


def downgrade() -> None:
    op.drop_index("ix_matches_resume_score", table_name="matches")
    op.drop_index("ix_matches_vacancy_score", table_name="matches")
    op.drop_table("matches")

    op.drop_index("ix_resumes_soft_skills_gin", table_name="resumes")
    op.drop_index("ix_resumes_hard_skills_gin", table_name="resumes")
    op.drop_index("ix_resumes_owner_id", table_name="resumes")
    op.drop_table("resumes")

    op.drop_index("ix_vacancies_soft_skills_gin", table_name="vacancies")
    op.drop_index("ix_vacancies_hard_skills_gin", table_name="vacancies")
    op.drop_index("ix_vacancies_owner_id", table_name="vacancies")
    op.drop_table("vacancies")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
