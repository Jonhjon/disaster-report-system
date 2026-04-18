"""add clarification support

Revision ID: 008
Revises: 007
Create Date: 2026-04-17

新增內容：
- disaster_events.completeness JSONB 欄位（儲存 {score, missing}）
- disaster_events.status 允許 'pending_clarification'
- disaster_reports 新增聯絡方式欄位（reporter_line_user_id / reporter_email / preferred_channel）
- 新增 chat_sessions 資料表（對話續接）
- 新增 clarification_requests 資料表（追問推播紀錄）
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # (1) disaster_events 新增 completeness 欄位
    op.add_column(
        "disaster_events",
        sa.Column(
            "completeness",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    # (2) disaster_events.status CHECK 放寬接受 pending_clarification
    op.drop_constraint("ck_status_values", "disaster_events", type_="check")
    op.create_check_constraint(
        "ck_status_values",
        "disaster_events",
        "status IN ('pending_clarification','reported','in_progress','resolved')",
    )

    # (3) disaster_reports 擴充聯絡方式
    op.add_column(
        "disaster_reports",
        sa.Column("reporter_line_user_id", sa.String(50), nullable=True),
    )
    op.add_column(
        "disaster_reports",
        sa.Column("reporter_email", sa.String(200), nullable=True),
    )
    op.add_column(
        "disaster_reports",
        sa.Column("preferred_channel", sa.String(20), nullable=True),
    )

    # (4) chat_sessions 資料表
    op.create_table(
        "chat_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "session_token",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            unique=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("disaster_events.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("disaster_reports.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "messages",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "pending_questions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_active_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('active','awaiting_user','closed')",
            name="ck_session_status",
        ),
    )
    op.create_index(
        "idx_sessions_token", "chat_sessions", ["session_token"]
    )
    op.create_index(
        "idx_sessions_event", "chat_sessions", ["event_id"]
    )

    # (5) clarification_requests 資料表
    op.create_table(
        "clarification_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("disaster_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_sessions.id"),
            nullable=True,
        ),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("recipient", sa.String(200), nullable=False),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("message_body", sa.Text, nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("provider_message_id", sa.String(200), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("replied_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "channel IN ('sms','line','email')",
            name="ck_clarif_channel",
        ),
        sa.CheckConstraint(
            "status IN ('pending','sent','delivered','failed','replied')",
            name="ck_clarif_status",
        ),
    )
    op.create_index(
        "idx_clarif_event", "clarification_requests", ["event_id"]
    )
    op.create_index(
        "idx_clarif_provider_id",
        "clarification_requests",
        ["provider_message_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_clarif_provider_id", table_name="clarification_requests")
    op.drop_index("idx_clarif_event", table_name="clarification_requests")
    op.drop_table("clarification_requests")

    op.drop_index("idx_sessions_event", table_name="chat_sessions")
    op.drop_index("idx_sessions_token", table_name="chat_sessions")
    op.drop_table("chat_sessions")

    op.drop_column("disaster_reports", "preferred_channel")
    op.drop_column("disaster_reports", "reporter_email")
    op.drop_column("disaster_reports", "reporter_line_user_id")

    op.drop_constraint("ck_status_values", "disaster_events", type_="check")
    op.create_check_constraint(
        "ck_status_values",
        "disaster_events",
        "status IN ('reported','in_progress','resolved')",
    )

    op.drop_column("disaster_events", "completeness")
