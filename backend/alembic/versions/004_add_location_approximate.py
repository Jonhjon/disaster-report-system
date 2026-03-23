"""add location_approximate to disaster_events

Revision ID: 004
Revises: 003
Create Date: 2026-03-20
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "disaster_events",
        sa.Column("location_approximate", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("disaster_events", "location_approximate")
