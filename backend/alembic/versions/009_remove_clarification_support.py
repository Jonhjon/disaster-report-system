"""remove clarification support

Revision ID: 009
Revises: 008
Create Date: 2026-05-05

反向 008：完全移除 clarification 相關 schema。

執行內容：
1. 將 disaster_events.status='pending_clarification' 的 row 改為 'reported'
2. drop clarification_requests 與其 indexes
3. drop chat_sessions 與其 indexes
4. drop disaster_reports.{preferred_channel, reporter_email, reporter_line_user_id}
5. 收緊 disaster_events.ck_status_values CHECK 為 ('reported','in_progress','resolved')
6. drop disaster_events.completeness 欄位

downgrade 為 self-contained，複製 008 upgrade 等價邏輯，不引用 008 模組。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # (1) 收尾任何停在 pending_clarification 的事件
    op.execute(
        "UPDATE disaster_events SET status='reported' "
        "WHERE status='pending_clarification'"
    )

    # (2) clarification_requests（FK → chat_sessions / disaster_events，先刪）
    op.drop_index(
        "idx_clarif_provider_id", table_name="clarification_requests"
    )
    op.drop_index("idx_clarif_event", table_name="clarification_requests")
    op.drop_table("clarification_requests")

    # (3) chat_sessions
    op.drop_index("idx_sessions_event", table_name="chat_sessions")
    op.drop_index("idx_sessions_token", table_name="chat_sessions")
    op.drop_table("chat_sessions")

    # (4) disaster_reports 三個聯絡欄位
    op.drop_column("disaster_reports", "preferred_channel")
    op.drop_column("disaster_reports", "reporter_email")
    op.drop_column("disaster_reports", "reporter_line_user_id")

    # (5) disaster_events.status CHECK 收緊
    op.drop_constraint("ck_status_values", "disaster_events", type_="check")
    op.create_check_constraint(
        "ck_status_values",
        "disaster_events",
        "status IN ('reported','in_progress','resolved')",
    )

    # (6) disaster_events.completeness
    op.drop_column("disaster_events", "completeness")


def downgrade() -> None:
    # 反向重建 008 的所有 schema（self-contained）

    op.add_column(
        "disaster_events",
        sa.Column(
            "completeness",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    op.drop_constraint("ck_status_values", "disaster_events", type_="check")
    op.create_check_constraint(
        "ck_status_values",
        "disaster_events",
        "status IN ('pending_clarification','reported','in_progress','resolved')",
    )

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
    op.create_index("idx_sessions_token", "chat_sessions", ["session_token"])
    op.create_index("idx_sessions_event", "chat_sessions", ["event_id"])

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
