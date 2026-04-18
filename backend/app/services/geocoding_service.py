import json
import logging
import re

import httpx

from app.config import settings
from app.services.api_clients import get_anthropic_client

logger = logging.getLogger(__name__)

# Taiwan bounding box
_TW_LAT = (21.5, 25.5)
_TW_LON = (119.5, 122.5)

# Road-name characters — presence means the query is a street address, not a named place
# Excludes "道" to avoid false positives like "道明國中"
_ROAD_WORDS = ["路", "街", "大道", "巷", "弄"]

# 場所後綴詞 — 建築物內部空間，本身非獨立 POI
_PLACE_SUFFIXES = [
    "教室", "操場", "宿舍", "停車場", "大廳", "走廊",
    "餐廳", "圖書館", "辦公室", "會議室", "球場", "廣場",
    "入口", "出口", "地下室", "頂樓",
]

# Google Places types considered too vague for precise geocoding
VAGUE_TYPES = {
    "locality",
    "administrative_area_level_1",
    "administrative_area_level_2",
    "administrative_area_level_3",
    "country",
    "colloquial_area",
    "political",
}
MODEL = settings.CLAUDE_MODEL
# In-memory geocoding cache (process-level, resets on restart)
_geocode_cache: dict[str, dict] = {}
_CACHE_MAX = 500


def _in_taiwan(lat: float, lon: float) -> bool:
    """Return True if the coordinate falls within Taiwan's bounding box."""
    return _TW_LAT[0] <= lat <= _TW_LAT[1] and _TW_LON[0] <= lon <= _TW_LON[1]


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """計算兩座標之間的距離（公尺）。"""
    from math import asin, cos, radians, sin, sqrt
    R = 6_371_000
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * R * asin(sqrt(a))


def _strip_place_suffix(text: str) -> str | None:
    """若 text 結尾有場所後綴詞，回傳剝除後的核心名稱；否則回傳 None。"""
    for suffix in _PLACE_SUFFIXES:
        if text.endswith(suffix):
            core = text[: -len(suffix)].strip()
            return core if core else None
    return None


_NEARBY_KEYWORDS = re.compile(r".+(?:附近|旁邊|對面|靠近|旁|周邊|邊上|隔壁).+")


async def _extract_landmark_pattern(text: str) -> dict | None:
    """偵測「目標 + 空間關係詞 + 地標」模式。
    回傳 {"target": str, "landmark": str, "area": str | None} 或 None。
    """
    if not _NEARBY_KEYWORDS.search(text):
        return None  # 快速跳過，不呼叫 LLM
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        return None

    client = get_anthropic_client()
    prompt = (
        "你是地址解析器，專門識別「在某地標附近找某目標」的查詢模式。\n\n"
        "判斷規則：\n"
        "1. 必須同時有空間關係詞（附近、旁邊、對面、靠近、旁、周邊、邊上、隔壁）"
        "且連接兩個不同的具名場所\n"
        "2. 若只是一般地址描述（關係詞描述位置而非連接兩場所），回傳 null\n"
        "3. target = 使用者想找的目標場所；landmark = 參考地標\n"
        "4. area = 縣市/區域名稱（找不到則為 null）\n\n"
        "只輸出 JSON，不含說明：\n"
        '- 符合模式：{"target": "...", "landmark": "...", "area": "...或null"}\n'
        "- 不符合模式：null\n\n"
        "範例：\n"
        '「肯德基附近的麥當勞」→ {"target": "麥當勞", "landmark": "肯德基", "area": null}\n'
        '「花蓮市中心靠近肯德基的麥當勞」→ {"target": "麥當勞", "landmark": "肯德基", "area": "花蓮市"}\n'
        '「台北市大安區的7-11」→ null\n'
        '「麥當勞對面的星巴克」→ {"target": "星巴克", "landmark": "麥當勞", "area": null}\n\n'
        f"地點描述：\n{text}"
    )
    try:
        message = await client.messages.create(
            model=MODEL,
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        if raw.lower() == "null" or not raw:
            return None
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1].lstrip("json").strip() if len(parts) > 1 else raw
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        target = data.get("target", "").strip()
        landmark = data.get("landmark", "").strip()
        if not target or not landmark:
            return None
        area = data.get("area")
        area = area.strip() if isinstance(area, str) and area else None
        return {"target": target, "landmark": landmark, "area": area}
    except Exception:
        return None


async def extract_structured_address(text: str) -> str:
    """Use Claude haiku to convert informal location text into a searchable address.

    Falls back to the original text when the API key is unavailable or on any error.
    """
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        return text

    client = get_anthropic_client()
    try:
        message = await client.messages.create(
            # model="claude-haiku-4-5-20251001",
            model=MODEL,
            max_tokens=100,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "請從以下地點描述中擷取可用於地圖查詢的字串。\n"
                        "規則：\n"
                        "1. 地址盡量包含縣市＋區＋路段（例如「花蓮縣花蓮市中央路三段」）\n"
                        "2. 若有提及特定建築物或商店（如 7-11、全家、學校、捷運站、醫院等），"
                        "請附加在地址後面（7-11 請標準化為 7-ELEVEN，全家標準化為 FamilyMart）\n"
                        "3. 若有提及附近地標（如學校、大學、火車站、公園、醫院等），"
                        "也一併保留在查詢字串中，這對定位非常重要\n"
                        "4. 只輸出查詢字串，不要任何說明或標點\n"
                        "範例：花蓮縣花蓮市中央路三段 慈濟大學 7-ELEVEN / 台北市信義區市府路45號 / 新北市板橋火車站 全家\n"
                        "地點描述：\n"
                        + text
                    ),
                }
            ],
        )
        extracted = message.content[0].text.strip()
        return extracted if extracted else text
    except Exception:
        return text


async def extract_address_components(text: str) -> dict:
    """Use Claude haiku to parse location text into structured address components.

    Returns a dict like {"county": "花蓮縣", "city": "花蓮市", "street": "中央路三段"}.
    Falls back to an empty dict when the API key is unavailable or parsing fails.
    """
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        return {}

    client = get_anthropic_client()
    try:
        message = await client.messages.create(
            # model="claude-haiku-4-5-20251001",
            model=MODEL,
            max_tokens=150,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "從以下地址文字擷取結構化成分，回傳 JSON 物件。\n"
                        "欄位說明（均為可選）：\n"
                        "- county: 縣或直轄市（如「花蓮縣」、「台北市」）\n"
                        "- city: 市或鄉鎮區（如「花蓮市」、「信義區」）\n"
                        "- street: 路段（如「中央路三段」）\n"
                        "只輸出 JSON，不含說明。範例：\n"
                        '{"county": "花蓮縣", "city": "花蓮市", "street": "中央路三段"}\n'
                        "地址：\n" + text
                    ),
                }
            ],
        )
        raw = message.content[0].text.strip()
        return json.loads(raw)
    except Exception:
        return {}


async def geocode_tgos(address: str) -> dict | None:
    """Query Taiwan TGOS address geocoding API.

    Returns {"latitude": float, "longitude": float, "display_name": str} or None.
    """
    url = "https://addr.tgos.tw/addr/api/addrquery/"
    params = {"Addr": address, "Alias": "2", "Pnum": "1", "Page": "0"}
    headers = {"User-Agent": "DisasterReportSystem/1.0"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers, timeout=10)
            if response.status_code != 200:
                return None
            data = response.json()
            addr_list = data.get("AddressList", []) if isinstance(data, dict) else []
            if not addr_list:
                return None
            first = addr_list[0]
            lon = float(first.get("X", 0))
            lat = float(first.get("Y", 0))
            if lat and lon:
                if not _in_taiwan(lat, lon):
                    return None
                return {
                    "latitude": lat,
                    "longitude": lon,
                    "display_name": first.get("FULL_ADDR", address),
                }
    except Exception:
        pass
    return None


async def geocode_google_places(query: str) -> dict | None:
    """Search for a specific business/POI using Google Places Text Search API.

    Better than Geocoding API for finding specific stores, restaurants, etc.
    Returns {"latitude": float, "longitude": float, "display_name": str, "source": "google_places"} or None.
    Rejects results whose types are entirely within VAGUE_TYPES (e.g. locality, country).
    """
    api_key = settings.GOOGLE_MAPS_API_KEY
    if not api_key:
        return None
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {"query": query, "key": api_key, "region": "tw", "language": "zh-TW"}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10)
            data = response.json()
            if data.get("status") == "OK" and data.get("results"):
                result = data["results"][0]
                # Reject vague results (e.g. county/city level matches)
                result_types = set(result.get("types", []))
                if result_types and result_types.issubset(VAGUE_TYPES):
                    return None
                loc = result["geometry"]["location"]
                lat = loc["lat"]
                lon = loc["lng"]
                if not _in_taiwan(lat, lon):
                    return None
                return {
                    "latitude": lat,
                    "longitude": lon,
                    "display_name": result.get("formatted_address", query),
                    "source": "google_places",
                }
    except Exception:
        pass
    return None


async def geocode_nearby_search(
    keyword: str,
    lat: float,
    lon: float,
    radius: int = 500,
) -> dict | None:
    """在指定座標附近搜尋 POI，使用 Google Places Nearby Search API。"""
    api_key = settings.GOOGLE_MAPS_API_KEY
    if not api_key:
        return None
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lon}",
        "radius": radius,
        "keyword": keyword,
        "key": api_key,
        "language": "zh-TW",
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10)
            data = response.json()
            if data.get("status") == "OK" and data.get("results"):
                result = data["results"][0]
                result_types = set(result.get("types", []))
                if result_types and result_types.issubset(VAGUE_TYPES):
                    return None
                loc = result["geometry"]["location"]
                r_lat, r_lon = loc["lat"], loc["lng"]
                if not _in_taiwan(r_lat, r_lon):
                    return None
                return {
                    "latitude": r_lat,
                    "longitude": r_lon,
                    "display_name": result.get("vicinity", result.get("name", keyword)),
                    "source": "google_nearby",
                }
    except Exception:
        pass
    return None


async def geocode_nearby_candidates(
    keyword: str,
    lat: float,
    lon: float,
    radius: int = 500,
    limit: int = 4,
) -> list[dict]:
    """在指定座標附近搜尋多筆 POI，按距離排序。

    回傳 list[{"name", "address", "latitude", "longitude", "distance_m"}]
    供消歧義流程使用。空列表表示無符合結果。
    """
    api_key = settings.GOOGLE_MAPS_API_KEY
    if not api_key:
        return []
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lon}",
        "radius": radius,
        "keyword": keyword,
        "key": api_key,
        "language": "zh-TW",
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10)
            data = response.json()
            if data.get("status") != "OK" or not data.get("results"):
                return []
            candidates = []
            for result in data["results"][: limit * 2]:
                result_types = set(result.get("types", []))
                if result_types and result_types.issubset(VAGUE_TYPES):
                    continue
                loc = result["geometry"]["location"]
                r_lat, r_lon = loc["lat"], loc["lng"]
                if not _in_taiwan(r_lat, r_lon):
                    continue
                dist = _haversine_m(lat, lon, r_lat, r_lon)
                candidates.append({
                    "name": result.get("name", keyword),
                    "address": result.get("vicinity", ""),
                    "latitude": r_lat,
                    "longitude": r_lon,
                    "distance_m": round(dist),
                })
            candidates.sort(key=lambda c: c["distance_m"])
            return candidates[:limit]
    except Exception:
        return []


async def geocode_google(address: str) -> dict | None:
    """Query Google Maps Geocoding API.

    Returns {"latitude": float, "longitude": float, "display_name": str, "source": "google"} or None.
    """
    api_key = settings.GOOGLE_MAPS_API_KEY
    if not api_key:
        return None
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": api_key, "region": "TW", "language": "zh-TW"}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10)
            data = response.json()
            if data.get("status") == "OK" and data.get("results"):
                result = data["results"][0]
                loc = result["geometry"]["location"]
                lat = loc["lat"]
                lon = loc["lng"]
                if not _in_taiwan(lat, lon):
                    return None
                return {
                    "latitude": lat,
                    "longitude": lon,
                    "display_name": result.get("formatted_address", address),
                    "source": "google",
                }
    except Exception:
        pass
    return None


async def _geocode_address_impl(address: str) -> dict | None:
    """Internal geocoding implementation without cache.

    Flow:
      1. Claude haiku extracts a searchable address from informal text
      2. TGOS API (Taiwan government geocoding, ~90% accuracy)
      3. Nominatim / OpenStreetMap — free-text then structured queries
      4. Google Places Text Search (specific businesses/POIs)
      5. Google Maps Geocoding API (address-level fallback)

    Returns {"latitude": float, "longitude": float, "display_name": str} or None.
    """
    # Step 1: LLM-assisted address extraction
    searchable = await extract_structured_address(address)

    # Step 0: Two-stage geocoding for "A附近的B" landmark pattern
    landmark_info = await _extract_landmark_pattern(address)
    if landmark_info is not None:
        target = landmark_info["target"]
        landmark = landmark_info["landmark"]
        area = landmark_info["area"]
        landmark_query = f"{area} {landmark}".strip() if area else landmark
        landmark_result = await geocode_google_places(landmark_query)
        if landmark_result is not None:
            target_query = f"{area} {target}".strip() if area else target
            for radius in (500, 1500):
                candidates = await geocode_nearby_candidates(
                    keyword=target_query,
                    lat=landmark_result["latitude"],
                    lon=landmark_result["longitude"],
                    radius=radius,
                )
                if not candidates:
                    continue
                closest = candidates[0]  # 已按距離排序，第一筆最近
                result = {
                    "latitude": closest["latitude"],
                    "longitude": closest["longitude"],
                    "display_name": closest["address"] or closest["name"],
                    "source": "google_nearby",
                }
                if len(candidates) > 1:
                    result["candidates"] = candidates  # 多個候選，供消歧義使用
                return result
    # landmark 找不到或 Nearby Search 全部失敗 → fallback 繼續現有流程

    # Step 1.5: Named-place fast path
    # If no road-name characters present, treat as a named place (school, store, landmark)
    # and try Google Places first so _location_is_precise() sees source="google_places".
    if not any(w in address for w in _ROAD_WORDS):
        named_place_queries = [address]
        if searchable != address:
            named_place_queries.append(searchable)
        for q in named_place_queries:
            result = await geocode_google_places(q)
            if result:
                return result
        # 剝除場所後綴後重試（例如「三育基督學院教室」→「三育基督學院」）
        core = _strip_place_suffix(address)
        if core:
            result = await geocode_google_places(core)
            if result:
                return result

    # Step 2: TGOS (try LLM-extracted query first, then original)
    # TODO: TGOS endpoint (https://addr.tgos.tw/addr/api/addrquery/) returns 404 — disabled until a valid endpoint is found
    # tgos_queries = [searchable]
    # if address != searchable:
    #     tgos_queries.append(address)
    # for q in tgos_queries:
    #     result = await geocode_tgos(q)
    #     if result:
    #         return result

    # Step 3: Nominatim fallback — free-text queries
    url = "https://nominatim.openstreetmap.org/search"
    headers = {
        "User-Agent": "DisasterReportSystem/1.0",
        "Accept-Language": "zh-TW,zh;q=0.9",
    }
    nominatim_queries = [searchable, searchable + " 台灣"]
    if address != searchable:
        nominatim_queries += [address, address + " 台灣"]

    # Step 3b: Structured Nominatim query from parsed components
    components = await extract_address_components(searchable)
    structured_params: dict | None = None
    if components:
        structured_params = {k: v for k, v in components.items() if v}

    try:
        async with httpx.AsyncClient() as client:
            # Free-text queries
            for query in nominatim_queries:
                params = {
                    "q": query,
                    "format": "json",
                    "limit": 1,
                    "countrycodes": "tw",
                    "addressdetails": 1,
                }
                response = await client.get(url, params=params, headers=headers, timeout=10)
                if response.status_code == 200:
                    results = response.json()
                    if results:
                        lat = float(results[0]["lat"])
                        lon = float(results[0]["lon"])
                        if _in_taiwan(lat, lon):
                            return {
                                "latitude": lat,
                                "longitude": lon,
                                "display_name": results[0].get("display_name", ""),
                            }

            # Structured query (if components were extracted)
            if structured_params:
                params = {
                    **structured_params,
                    "format": "json",
                    "limit": 1,
                    "countrycodes": "tw",
                    "addressdetails": 1,
                }
                response = await client.get(url, params=params, headers=headers, timeout=10)
                if response.status_code == 200:
                    results = response.json()
                    if results:
                        lat = float(results[0]["lat"])
                        lon = float(results[0]["lon"])
                        if _in_taiwan(lat, lon):
                            return {
                                "latitude": lat,
                                "longitude": lon,
                                "display_name": results[0].get("display_name", ""),
                            }
    except Exception:
        pass

    # Step 4: Google Places Text Search (for specific businesses/POIs)
    # Original text first (preserves landmark context), then LLM-extracted
    places_queries = []
    if address != searchable:
        places_queries.append(address)
    places_queries.append(searchable)

    for q in places_queries:
        result = await geocode_google_places(q)
        if result:
            return result

    # Step 5: Google Geocoding fallback (address-level)
    for q in places_queries:
        result = await geocode_google(q)
        if result:
            return result

    return None


async def geocode_address(address: str) -> dict | None:
    """Convert address text to coordinates, with in-memory caching.

    Caches successful results up to _CACHE_MAX entries.
    Failed lookups (None) are never cached so they are retried on next call.
    """
    if address in _geocode_cache:
        return _geocode_cache[address]
    result = await _geocode_address_impl(address)
    if result and len(_geocode_cache) < _CACHE_MAX:
        _geocode_cache[address] = result
    return result
