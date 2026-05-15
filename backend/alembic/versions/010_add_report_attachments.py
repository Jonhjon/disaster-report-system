"""add report_attachments table

Revision ID: 010
Revises: 009
Create Date: 2026-05-14

新增 report_attachments 表，用於儲存民眾通報附帶的照片：
- report_id 為 nullable：上傳時尚未綁定 Report，提交通報時才更新
- created_at + idx_attachments_created_at：供孤兒附件清理排程使用
- ON DELETE CASCADE：Report 刪除時連同附件 row 一併移除（實體檔由 service 另行清理）
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "report_attachments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("disaster_reports.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_attachments_report_id", "report_attachments", ["report_id"]
    )
    op.create_index(
        "idx_attachments_created_at", "report_attachments", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_attachments_created_at", table_name="report_attachments")
    op.drop_index("idx_attachments_report_id", table_name="report_attachments")
    op.drop_table("report_attachments")
