"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-02-25

"""
from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # disaster_events table
    op.create_table(
        "disaster_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("disaster_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location_text", sa.String(500), nullable=False),
        sa.Column(
            "location",
            geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("casualties", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("injured", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trapped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("report_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint("severity >= 1 AND severity <= 5", name="ck_severity_range"),
        sa.CheckConstraint(
            "status IN ('active', 'monitoring', 'resolved')", name="ck_status_values"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_events_location",
        "disaster_events",
        ["location"],
        postgresql_using="gist",
    )
    op.create_index("idx_events_disaster_type", "disaster_events", ["disaster_type"])
    op.create_index("idx_events_status", "disaster_events", ["status"])
    op.create_index("idx_events_occurred_at", "disaster_events", ["occurred_at"])
    op.create_index("idx_events_severity", "disaster_events", ["severity"])

    # disaster_reports table
    op.create_table(
        "disaster_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reporter_name", sa.String(100), nullable=True),
        sa.Column("reporter_phone", sa.String(20), nullable=True),
        sa.Column("raw_message", sa.Text(), nullable=False),
        sa.Column("extracted_data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "location",
            geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
        sa.Column("location_text", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["event_id"], ["disaster_events.id"], name="fk_reports_event_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_reports_event_id", "disaster_reports", ["event_id"])
    op.create_index(
        "idx_reports_location",
        "disaster_reports",
        ["location"],
        postgresql_using="gist",
    )
    op.create_index("idx_reports_created_at", "disaster_reports", ["created_at"])


def downgrade() -> None:
    op.drop_table("disaster_reports")
    op.drop_table("disaster_events")
