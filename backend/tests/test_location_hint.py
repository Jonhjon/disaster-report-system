"""
追問引導精確化測試
測試 _location_hint() 根據 location_text 缺少的成分回傳針對性追問
"""
import pytest

from app.api.chat import _location_hint


@pytest.mark.parametrize("location_text,expected_keyword", [
    # 缺縣市 → 詢問縣市
    ("建安街12巷5號",               "縣市"),
    ("中正路附近",                   "縣市"),
    ("7-11旁邊",                     "縣市"),
    ("學校門口",                      "縣市"),
    # 有縣市但缺路名 → 詢問路名
    ("花蓮縣",                       "路名"),
    ("台北市信義區",                  "路名"),
    ("新北市板橋區某處",              "路名"),
    # 有縣市+路名但缺門牌 → 詢問門牌
    ("台北市中正路",                  "門牌"),
    ("花蓮縣中央路三段",              "門牌"),
    ("新竹市光復路二段",              "門牌"),
    # 完整地址（縣市+路+號）→ 通用提示
    ("台北市信義區市府路1號",         "具體"),
    ("花蓮縣花蓮市中央路三段808號",   "具體"),
])
def test_location_hint(location_text, expected_keyword):
    hint = _location_hint(location_text)
    assert expected_keyword in hint, (
        f"location_text={location_text!r} → hint={hint!r}，期望包含 {expected_keyword!r}"
    )
