"""add geocoded_address to disaster_reports

Revision ID: 003
Revises: 002
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "disaster_reports",
        sa.Column("geocoded_address", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("disaster_reports", "geocoded_address")
