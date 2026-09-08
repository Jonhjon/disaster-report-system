"""add resolved_at to disaster_events

Revision ID: 015
Revises: 014
Create Date: 2026-08-06

統計頁的「結案耗時」需要一個只在結案當下寫入的時戳。updated_at 有 onupdate，
且事件合併時會被手動覆寫，用它推算會系統性高估。

刻意不回填既有的已結案事件：沒有可信的資料來源可推回真正的結案時間，
硬填會讓統計數字看起來精確但其實是編造的。既有資料維持 NULL，
由統計端另計為 legacy_excluded_count 並在畫面上揭露。
"""
from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "disaster_events",
        sa.Column(
            "resolved_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("disaster_events", "resolved_at")
