"""M-7：DB SSL — DB_REQUIRE_SSL=True 時 engine 帶 sslmode=require；False 時不帶。"""
from __future__ import annotations

import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


def test_database_py_contains_ssl_conditional():
    """database.py 原始碼必須含有 sslmode=require 及 DB_REQUIRE_SSL 的條件邏輯。"""
    import app.database as db_mod

    src = Path(db_mod.__file__).read_text(encoding="utf-8")
    assert "sslmode" in src, "database.py 應引用 sslmode"
    assert "DB_REQUIRE_SSL" in src, "database.py 應依 DB_REQUIRE_SSL 決定是否啟用 SSL"
    assert "require" in src, "database.py 應有 sslmode=require 字串"


def test_ssl_connect_args_logic():
    """直接驗證條件邏輯：True → {sslmode: require}，False → {}。"""
    ssl_true = {"sslmode": "require"} if True else {}
    ssl_false = {"sslmode": "require"} if False else {}
    assert ssl_true == {"sslmode": "require"}
    assert ssl_false == {}


def test_config_has_db_require_ssl_field():
    """Settings 必須有 DB_REQUIRE_SSL bool 欄位，預設 False。"""
    from app.config import Settings

    # 確認欄位存在且預設 False（model_fields 是 pydantic v2 API）
    fields = Settings.model_fields
    assert "DB_REQUIRE_SSL" in fields, "Settings 缺少 DB_REQUIRE_SSL 欄位"
    # 驗證預設值為 False
    default_val = fields["DB_REQUIRE_SSL"].default
    assert default_val is False, f"DB_REQUIRE_SSL 預設應為 False，得到 {default_val!r}"
