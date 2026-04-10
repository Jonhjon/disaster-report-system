"""add users table

Revision ID: 007
Revises: 006
Create Date: 2026-04-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# bcrypt hash of "admin123"
ADMIN_PASSWORD_HASH = "$2b$12$XfgLO4vrkAEa4dgn6w8yX.6yic.Zs8/Tde3.nXCPMjjRCI2FsOIJK"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("username", sa.String(50), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(100)),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()")),
    )

    op.execute(
        f"INSERT INTO users (username, hashed_password, display_name) "
        f"VALUES ('admin', '{ADMIN_PASSWORD_HASH}', '系統管理員')"
    )


def downgrade() -> None:
    op.drop_table("users")
