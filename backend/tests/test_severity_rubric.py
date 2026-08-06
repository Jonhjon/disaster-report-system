"""severity 五步 rubric 的確定性 oracle 測試。

這支測試不呼叫 LLM、不碰資料庫。它把 SEVERITY_RUBRIC 的五步規則忠實實作成一支
純函式 `severity_from_rubric`，作為：
  1. 論文用的「標準答案產生器」（給定輸入 → 唯一可解釋的分級）；
  2. E2E LLM 擷取測試（tests/e2e/test_e2e_report_extraction.py）的期望值來源。

⚠️ 此函式「不掛在系統執行路徑」上——線上分級仍由 LLM 依 prompt 內的 SEVERITY_RUBRIC 推斷。
   兩者若需一致，以本函式為規格書、prompt 為其自然語言版本。
"""
from __future__ import annotations

import pytest

from app.schemas.llm_tools import SubmitDisasterReportPayload


# 災害類型基準（Step 2 floor）
TYPE_FLOOR = {
    "trapped": 3,
    "landslide": 3,
    "fire": 2,
    "road_collapse": 2,
    "building_damage": 2,
    "flooding": 2,
    "small_landslide": 1,
    "utility_damage": 1,
    "other": 1,
}


def _death_level(d: int) -> int:
    if d >= 3:
        return 5
    if d >= 1:
        return 4
    return 0


def _band_8_3(x: int) -> int:
    """重傷 / 受困維度：>=8 →5, 3–7 →4, 1–2 →3。"""
    if x >= 8:
        return 5
    if x >= 3:
        return 4
    if x >= 1:
        return 3
    return 0


def _injured_level(x: int) -> int:
    """受傷（injured，含輕傷）維度：>=5 →3, 1–4 →2。"""
    if x >= 5:
        return 3
    if x >= 1:
        return 2
    return 0


def _agg_level(x: int) -> int:
    """加總（死亡+重傷+受困）維度：>=15 →5, 8–14 →4, 3–7 →3, 1–2 →2。"""
    if x >= 15:
        return 5
    if x >= 8:
        return 4
    if x >= 3:
        return 3
    if x >= 1:
        return 2
    return 0


def severity_from_rubric(
    disaster_type: str,
    casualties: int,
    injured: int,
    severe_injured: int,
    trapped: int,
    *,
    has_floor4_kw: bool = False,
    has_floor3_kw: bool = False,
    has_plus1_kw: bool = False,
) -> int:
    """依 SEVERITY_RUBRIC 五步驟由通報內容推出 severity（1~5）。"""
    # Step 1 — 人命傷亡級別（各維度取最高；加總不含輕傷）
    aggregate = casualties + severe_injured + trapped
    l_cas = max(
        _death_level(casualties),
        _band_8_3(severe_injured),
        _band_8_3(trapped),
        _injured_level(injured),
        _agg_level(aggregate),
        1,  # 任何事件至少 1
    )
    # Step 2 — 災害類型基準 floor
    l_type = TYPE_FLOOR.get(disaster_type, 1)
    # Step 3 — 取較高
    l_base = max(l_cas, l_type)
    # Step 4a — 關鍵字 floor（floor4 優先於 floor3）
    kw_floor = 4 if has_floor4_kw else (3 if has_floor3_kw else 0)
    l_floor = max(l_base, kw_floor)
    # Step 4b — 加重 +1（整體最多 +1）
    severity = l_floor + (1 if has_plus1_kw else 0)
    # Step 5 — 夾在 [1, 5]
    return max(1, min(5, severity))


# (id, type, 死, 傷, 重傷, 困, floor4, floor3, +1, 期望)
CASES = [
    # --- L1：無傷亡 + 低危類型 ---
    ("utility_no_cas", "utility_damage", 0, 0, 0, 0, False, False, False, 1),
    ("small_landslide_no_cas", "small_landslide", 0, 0, 0, 0, False, False, False, 1),
    ("other_all_zero", "other", 0, 0, 0, 0, False, False, False, 1),
    # --- L2：類型基準或少量輕傷 ---
    ("flooding_baseline", "flooding", 0, 0, 0, 0, False, False, False, 2),
    ("fire_small_no_cas", "fire", 0, 0, 0, 0, False, False, False, 2),
    ("other_2_light_injured", "other", 0, 2, 0, 0, False, False, False, 2),
    ("utility_large_scale_kw", "utility_damage", 0, 0, 0, 0, False, False, True, 2),
    # --- L3：重傷/受困 1–2、injured≥5、或類型/關鍵字升級 ---
    ("fire_5_injured", "fire", 0, 5, 0, 0, False, False, False, 3),
    ("building_1_severe", "building_damage", 0, 1, 1, 0, False, False, False, 3),
    ("landslide_baseline", "landslide", 0, 0, 0, 0, False, False, False, 3),
    ("trapped_await_rescue_kw", "trapped", 0, 0, 0, 0, False, True, False, 3),
    ("flooding_widearea_kw", "flooding", 0, 0, 0, 0, False, False, True, 3),
    # --- L4：死亡 1–2、重傷/受困 3–7、加總 8–14、floor4 關鍵字 ---
    ("fire_1_death", "fire", 1, 0, 0, 0, False, False, False, 4),
    ("road_3_trapped", "road_collapse", 0, 0, 0, 3, False, True, False, 4),
    ("building_collapse_kw", "building_damage", 0, 0, 0, 0, True, False, False, 4),
    ("fire_6injured_4severe", "fire", 0, 6, 4, 0, False, False, False, 4),
    ("landslide_1_death", "landslide", 1, 0, 0, 0, False, False, False, 4),
    # --- L5：死亡≥3、重傷/受困≥8、加總≥15 ---
    ("building_3_deaths", "building_damage", 3, 0, 0, 0, False, False, False, 5),
    ("trapped_8", "trapped", 0, 0, 0, 8, False, True, False, 5),
    ("gas_blast_agg15", "fire", 2, 9, 7, 6, False, True, False, 5),
    # --- 邊界：Step 5 clamp 上限 ---
    ("clamp_upper", "fire", 5, 0, 0, 0, False, False, True, 5),
]


@pytest.mark.parametrize(
    "case_id, dtype, cas, inj, sev, trap, f4, f3, p1, expected",
    CASES,
    ids=[c[0] for c in CASES],
)
def test_severity_from_rubric(case_id, dtype, cas, inj, sev, trap, f4, f3, p1, expected):
    got = severity_from_rubric(
        dtype, cas, inj, sev, trap,
        has_floor4_kw=f4, has_floor3_kw=f3, has_plus1_kw=p1,
    )
    assert got == expected, f"[{case_id}] 期望 {expected}, 實得 {got}"


# 各維度「級距臨界值(off-by-one)」測試。
# 用 other 類型（floor=1）隔離傷亡維度，避免類型基準遮蔽門檻；無關鍵字。
# (id, type, 死, 傷, 重傷, 困, f4, f3, +1, 期望)
BOUNDARY_CASES = [
    # 死亡 4→5 臨界（2 vs 3）
    ("death_2", "other", 2, 0, 0, 0, False, False, False, 4),
    ("death_3", "other", 3, 0, 0, 0, False, False, False, 5),
    # 重傷 3→4 臨界（2 vs 3）、5 臨界（7 vs 8）；injured 需 ≥ severe
    ("severe_2", "other", 0, 2, 2, 0, False, False, False, 3),
    ("severe_3", "other", 0, 3, 3, 0, False, False, False, 4),
    ("severe_7", "other", 0, 7, 7, 0, False, False, False, 4),
    ("severe_8", "other", 0, 8, 8, 0, False, False, False, 5),
    # 受困 3→4 臨界（2 vs 3）、5 臨界（7 vs 8）
    ("trapped_2", "other", 0, 0, 0, 2, False, False, False, 3),
    ("trapped_3", "other", 0, 0, 0, 3, False, False, False, 4),
    ("trapped_7", "other", 0, 0, 0, 7, False, False, False, 4),
    ("trapped_8b", "other", 0, 0, 0, 8, False, False, False, 5),
    # 受傷(輕傷) 2→3 臨界（4 vs 5），且不因輕傷多而超過 3
    ("injured_4", "other", 0, 4, 0, 0, False, False, False, 2),
    ("injured_5", "other", 0, 5, 0, 0, False, False, False, 3),
    ("injured_100", "other", 0, 100, 0, 0, False, False, False, 3),
    # 加總 4→5 臨界（14 vs 15），各維度個別未達 5、由加總驅動
    ("agg_14", "other", 2, 7, 7, 5, False, False, False, 4),
    ("agg_15", "other", 2, 7, 7, 6, False, False, False, 5),
    # 關鍵字邊界
    ("floor4_beats_floor3", "other", 0, 0, 0, 0, True, True, False, 4),   # 兩 floor 並存取高
    ("floor_below_base_no_lower", "other", 3, 0, 0, 0, False, True, False, 5),  # floor3 < 既有5，不下修
    ("plus1_then_clamp", "other", 3, 0, 0, 0, False, False, True, 5),     # 5 +1 → clamp 5
    ("floor4_plus1", "other", 0, 0, 0, 0, True, False, True, 5),          # floor4 +1 = 5
]


@pytest.mark.parametrize(
    "case_id, dtype, cas, inj, sev, trap, f4, f3, p1, expected",
    BOUNDARY_CASES,
    ids=[c[0] for c in BOUNDARY_CASES],
)
def test_severity_threshold_boundaries(case_id, dtype, cas, inj, sev, trap, f4, f3, p1, expected):
    """級距臨界值：驗證每個門檻的 off-by-one 轉換正確。"""
    got = severity_from_rubric(
        dtype, cas, inj, sev, trap,
        has_floor4_kw=f4, has_floor3_kw=f3, has_plus1_kw=p1,
    )
    assert got == expected, f"[{case_id}] 期望 {expected}, 實得 {got}"


def test_severity_always_in_range():
    """任意輸入組合，輸出必為 1~5 整數，與 DB / schema 約束一致。"""
    for dtype in TYPE_FLOOR:
        for cas in (0, 1, 3, 20):
            for extra in (0, 2, 10):
                got = severity_from_rubric(
                    dtype, cas, extra, extra, extra,
                    has_floor4_kw=True, has_plus1_kw=True,
                )
                assert isinstance(got, int)
                assert 1 <= got <= 5


def test_severe_injured_cannot_exceed_injured_via_schema():
    """重傷是受傷子集：schema 會把超額的 severe_injured 夾成 injured（rubric 上游保護）。"""
    payload = SubmitDisasterReportPayload.model_validate({
        "disaster_type": "building_damage",
        "description": "落石砸傷",
        "location_text": "台北市信義區松仁路100號",
        "severity": 4,
        "casualties": 0,
        "injured": 3,
        "severe_injured": 5,   # 超過受傷總數
        "trapped": 0,
        "reporter_name": "王大明",
        "reporter_phone": "0912345678",
    })
    assert payload.severe_injured == 3  # 已被夾擠
    # 夾擠後代入 rubric：重傷 3 → 級別 4
    assert severity_from_rubric(
        payload.disaster_type, payload.casualties, payload.injured,
        payload.severe_injured, payload.trapped,
    ) == 4
