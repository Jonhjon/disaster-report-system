"""M-4：app.main 啟動時應統一配置 root logger（至少 INFO level、自訂 format）。

生產環境無 basicConfig 會導致 logger.info 無輸出；只靠 uvicorn --log-level 難追蹤。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


def test_root_logger_configured_with_info_level():
    """import app.main 後 root logger 應已配置且 level <= INFO。"""
    # import 會觸發 configure_logging
    import app.main  # noqa: F401

    root = logging.getLogger()
    assert root.handlers, "root logger 應至少有一個 handler（由 basicConfig 建立）"
    effective = root.getEffectiveLevel()
    assert effective <= logging.INFO, (
        f"root logger level={effective} 應 <= INFO（20）"
    )


def test_no_raw_print_in_app_source():
    """app/ 底下 .py 不應有 top-level print(。

    允許 `# print(...)` 註解；以簡單 lstrip 後 startswith 判斷。
    """
    app_dir = backend_dir / "app"
    offenders: list[str] = []
    for py in app_dir.rglob("*.py"):
        for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("print("):
                offenders.append(f"{py.relative_to(backend_dir)}:{i}: {stripped[:80]}")
    assert not offenders, "app/ 不應有 print() 呼叫：\n" + "\n".join(offenders)
