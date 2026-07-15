"""add occurred_at_approximate to disaster_events

Revision ID: 011
Revises: 010
Create Date: 2026-07-15
"""
from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "disaster_events",
        sa.Column(
            "occurred_at_approximate",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("disaster_events", "occurred_at_approximate")
