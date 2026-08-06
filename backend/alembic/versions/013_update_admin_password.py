"""update admin password

Revision ID: 013
Revises: 012
Create Date: 2026-08-06
"""
from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None

# admin 帳號的 bcrypt 密碼雜湊（明文不入庫，備忘見本機 backend/.env）
NEW_ADMIN_PASSWORD_HASH = "$2b$12$Ahlv9VvJbLha2eCio2Ooj.H/.VchvehPPUyN/5ICGmhI4Pa9kxvyu"

# 舊雜湊（來自 migration 007），供 downgrade 還原
OLD_ADMIN_PASSWORD_HASH = "$2b$12$XfgLO4vrkAEa4dgn6w8yX.6yic.Zs8/Tde3.nXCPMjjRCI2FsOIJK"


def upgrade() -> None:
    op.execute(
        f"UPDATE users SET hashed_password = '{NEW_ADMIN_PASSWORD_HASH}' "
        f"WHERE username = 'admin'"
    )


def downgrade() -> None:
    op.execute(
        f"UPDATE users SET hashed_password = '{OLD_ADMIN_PASSWORD_HASH}' "
        f"WHERE username = 'admin'"
    )
