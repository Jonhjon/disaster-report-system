"""add severe_injured to disaster_events

Revision ID: 012
Revises: 011
Create Date: 2026-07-29
"""
from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "disaster_events",
        sa.Column(
            "severe_injured",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("disaster_events", "severe_injured")
