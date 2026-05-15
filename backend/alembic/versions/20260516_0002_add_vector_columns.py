"""add vector columns, extraction_status and pgvector extension

Revision ID: 20260516_0002
Revises: 20260515_0001
Create Date: 2026-05-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = "20260516_0002"
down_revision: Union[str, None] = "20260515_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 1024


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    for table in ("vacancies", "resumes"):
        op.add_column(table, sa.Column("embedding_doc", Vector(EMBEDDING_DIM), nullable=True))
        op.add_column(table, sa.Column("embedding_skills", Vector(EMBEDDING_DIM), nullable=True))
        op.add_column(
            table, sa.Column("embedding_experience", Vector(EMBEDDING_DIM), nullable=True)
        )
        op.add_column(
            table,
            sa.Column(
                "extraction_status",
                sa.String(length=16),
                nullable=False,
                server_default="pending",
            ),
        )

    op.create_index(
        "ix_vacancies_embedding_doc_hnsw",
        "vacancies",
        ["embedding_doc"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding_doc": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_resumes_embedding_doc_hnsw",
        "resumes",
        ["embedding_doc"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding_doc": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_resumes_embedding_doc_hnsw", table_name="resumes")
    op.drop_index("ix_vacancies_embedding_doc_hnsw", table_name="vacancies")
    for table in ("vacancies", "resumes"):
        op.drop_column(table, "extraction_status")
        op.drop_column(table, "embedding_experience")
        op.drop_column(table, "embedding_skills")
        op.drop_column(table, "embedding_doc")
