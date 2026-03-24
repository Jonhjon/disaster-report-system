"""
追問引導精確化測試
測試 _location_hint() 根據 location_text 缺少的成分回傳針對性追問
測試 _location_is_precise() 判斷地址是否精確到建築物等級
"""
import pytest

from app.api.chat import _location_hint, _location_is_precise


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


_GOOGLE_PLACES_COORDS = {
    "source": "google_places",
    "latitude": 23.5,
    "longitude": 121.0,
    "display_name": "test",
}

_NOMINATIM_COORDS = {
    "source": "nominatim",
    "latitude": 23.9,
    "longitude": 121.5,
    "display_name": "test",
}


@pytest.mark.parametrize("text,coords,expected", [
    # 完整（縣市 + 路 + 號）→ 精確
    ("花蓮縣吉安鄉慶北三街123號",    None,                  True),
    ("台北市信義區市府路45號",        None,                  True),
    ("新北市板橋區中山路一段100號",   None,                  True),
    # Google Places 找到具體商家 → 精確（即使沒門牌）
    ("花蓮縣吉安鄉慶北三街7-ELEVEN", _GOOGLE_PLACES_COORDS, True),
    ("台北市信義區某商店",            _GOOGLE_PLACES_COORDS, True),
    # 缺門牌且非 Google Places → 不精確
    ("花蓮縣吉安鄉慶北三街",         None,                  False),
    ("花蓮縣吉安鄉慶北三街",         _NOMINATIM_COORDS,     False),
    # 缺縣市
    ("吉安慶北三街123號",             None,                  False),
    # 缺路名
    ("花蓮縣123號",                   None,                  False),
    # 空字串
    ("",                              None,                  False),
])
def test_location_is_precise(text, coords, expected):
    assert _location_is_precise(text, coords) == expected, (
        f"location_text={text!r}, coords source={coords and coords.get('source')!r} → 期望 {expected}"
    )
