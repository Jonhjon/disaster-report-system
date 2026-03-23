import httpx

from app.config import settings


async def extract_structured_address(text: str) -> str:
    """Use Claude haiku to convert informal location text into a searchable address.

    Falls back to the original text when the API key is unavailable or on any error.
    """
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        return text

    import anthropic  # noqa: PLC0415

    client = anthropic.AsyncAnthropic(api_key=api_key)
    try:
        message = await client.messages.create(
            model="claude-haiku-4-5-20251001",
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
                loc = result["geometry"]["location"]
                return {
                    "latitude": loc["lat"],
                    "longitude": loc["lng"],
                    "display_name": result.get("formatted_address", query),
                    "source": "google_places",
                }
    except Exception:
        pass
    return None


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
                return {
                    "latitude": loc["lat"],
                    "longitude": loc["lng"],
                    "display_name": result.get("formatted_address", address),
                    "source": "google",
                }
    except Exception:
        pass
    return None


async def geocode_address(address: str) -> dict | None:
    """Convert address text to coordinates.

    Flow:
      1. Claude haiku extracts a searchable address from informal text
      2. TGOS API (Taiwan government geocoding, ~90% accuracy)
      3. Nominatim / OpenStreetMap (fallback)
      4. Google Places Text Search (specific businesses/POIs)
      5. Google Maps Geocoding API (address-level fallback)

    Returns {"latitude": float, "longitude": float, "display_name": str} or None.
    """
    # Step 1: LLM-assisted address extraction
    searchable = await extract_structured_address(address)

    # Step 2: TGOS (try LLM-extracted query first, then original)
    tgos_queries = [searchable]
    if address != searchable:
        tgos_queries.append(address)
    for q in tgos_queries:
        result = await geocode_tgos(q)
        if result:
            return result

    # Step 3: Nominatim fallback
    url = "https://nominatim.openstreetmap.org/search"
    headers = {
        "User-Agent": "DisasterReportSystem/1.0",
        "Accept-Language": "zh-TW,zh;q=0.9",
    }
    nominatim_queries = [searchable, searchable + " 台灣"]
    if address != searchable:
        nominatim_queries += [address, address + " 台灣"]

    try:
        async with httpx.AsyncClient() as client:
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
                        return {
                            "latitude": float(results[0]["lat"]),
                            "longitude": float(results[0]["lon"]),
                            "display_name": results[0].get("display_name", ""),
                        }
    except Exception:
        pass

    # Step 4: Google Places Text Search (for specific businesses/POIs)
    # 原始文字優先（保留地標等上下文），萃取字串次之
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
