"""rename status values: active->open, monitoring->in_progress

Revision ID: 005
Revises: 004
Create Date: 2026-04-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 移除舊 CHECK 約束
    op.drop_constraint("ck_status_values", "disaster_events", type_="check")

    # 遷移現有資料
    op.execute("UPDATE disaster_events SET status = 'open' WHERE status = 'active'")
    op.execute("UPDATE disaster_events SET status = 'in_progress' WHERE status = 'monitoring'")

    # 變更欄位 server_default
    op.alter_column(
        "disaster_events",
        "status",
        server_default="open",
        existing_type=sa.String(20),
        existing_nullable=False,
    )

    # 新增新 CHECK 約束
    op.create_check_constraint(
        "ck_status_values",
        "disaster_events",
        "status IN ('open', 'in_progress', 'resolved')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_status_values", "disaster_events", type_="check")

    op.execute("UPDATE disaster_events SET status = 'active' WHERE status = 'open'")
    op.execute("UPDATE disaster_events SET status = 'monitoring' WHERE status = 'in_progress'")

    op.alter_column(
        "disaster_events",
        "status",
        server_default="active",
        existing_type=sa.String(20),
        existing_nullable=False,
    )

    op.create_check_constraint(
        "ck_status_values",
        "disaster_events",
        "status IN ('active', 'monitoring', 'resolved')",
    )
