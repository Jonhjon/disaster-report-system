"""E2E：通報輸入 → LLM 擷取的參數化自動化測試。

資料來源：同目錄的 e2e_report_cases.json（A 類 9 種災害類型 × severity 1~5，
以及 C 類邊界/防呆）。每筆給一段自然語言通報輸入，跑真實 LLM，斷言擷取欄位與 severity。

⚠️ 需要真實 Anthropic API（severity 由 LLM 即時推斷）。預設 CI 跳過；本機執行：
     RUN_LLM_EVALS=1 pytest tests/e2e -m llm -s
   （-s 才看得到每筆 print 的擷取結果。）

severity 為 LLM 推斷、非完全確定性：預設容忍 ±1（可在案例以 severity_tolerance 覆寫）。
擷取欄位（disaster_type / 傷亡數字）採 exact 比對，只驗證案例 expect 內列出的欄位。

特殊流程（合併、地址消歧義、地點精確度追問、時間未知/概略、附件、已驗證電話）已由既有
確定性測試覆蓋，見 docs/e2e-test-data.md「B 類」對照，不在此重複。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from app.schemas.llm_tools import SubmitDisasterReportPayload
from app.services import llm_service


# Windows 主控台預設 cp950，印 ≥ / ≤ 等符號會 UnicodeEncodeError；強制 UTF-8 輸出。
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover - 某些環境 stdout 無 reconfigure
    pass


CASES = json.loads(
    (Path(__file__).parent / "e2e_report_cases.json").read_text(encoding="utf-8")
)

pytestmark = [
    pytest.mark.llm,
    pytest.mark.skipif(
        os.getenv("RUN_LLM_EVALS") != "1",
        reason="需真實 Anthropic API；設 RUN_LLM_EVALS=1 才執行",
    ),
]


async def _extract(user_message: str) -> SubmitDisasterReportPayload | None:
    """跑真實 LLM，回傳它從一段通報輸入擷取到的 submit_disaster_report payload。

    LLM 若因資訊不足改成追問（未呼叫工具），回傳 None。
    """
    messages = [{"role": "user", "content": user_message}]
    async for chunk in llm_service.stream_chat(
        messages, verified_phone=None, device_location=None
    ):
        if chunk.get("type") == "tool_use" and chunk.get("tool") == "submit_disaster_report":
            data = chunk["data"]
            return (
                data
                if isinstance(data, SubmitDisasterReportPayload)
                else SubmitDisasterReportPayload.model_validate(data)
            )
    return None


_RESULT_FIELDS = [
    "disaster_type", "casualties", "injured", "severe_injured", "trapped", "severity",
]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
async def test_e2e_report_extraction(case):
    # 即時輸出：開始
    print(f"\n▶ [{case['id']}] {case.get('covers', '')}", flush=True)

    payload = await _extract(case["message"])
    assert payload is not None, (
        f"[{case['id']}] LLM 未提交通報（輸入資訊可能不足，被追問）：{case.get('covers')}"
    )
    dumped = payload.model_dump()

    # 即時輸出：完整擷取結果（含所有數值欄位，方便失敗時診斷）
    result = {k: dumped.get(k) for k in _RESULT_FIELDS}
    print(f"  [{case['id']}] 擷取結果：{result}", flush=True)

    # 擷取欄位：exact（只驗證案例 expect 內列出的欄位）
    for key, want in case.get("expect", {}).items():
        assert dumped[key] == want, (
            f"[{case['id']}] {key}: 期望 {want}, 實得 {dumped[key]}"
        )

    # severity：容忍 ±tolerance（LLM 非完全確定性）
    tol = case.get("severity_tolerance", 1)
    got = dumped["severity"]
    assert abs(got - case["severity"]) <= tol, (
        f"[{case['id']}] severity: 期望 {case['severity']}±{tol}, 實得 {got}"
    )
    print(f"  [{case['id']}] ✔ 通過（severity={got}）", flush=True)
