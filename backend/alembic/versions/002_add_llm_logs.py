"""add llm_logs table

Revision ID: 002
Revises: 001
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="success"),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("output", sa.Text(), nullable=True),
    )
    op.create_index("ix_llm_logs_timestamp", "llm_logs", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_llm_logs_timestamp", "llm_logs")
    op.drop_table("llm_logs")
