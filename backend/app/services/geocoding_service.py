import os

import httpx


async def extract_structured_address(text: str) -> str:
    """Use Claude haiku to convert informal location text into a searchable address.

    Falls back to the original text when the API key is unavailable or on any error.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
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
                        "請從以下地點描述中擷取可用於地圖查詢的台灣地址"
                        "（例如「台北市信義區松高路」），只輸出地址，不要任何解釋：\n"
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


async def geocode_address(address: str) -> dict | None:
    """Convert address text to coordinates.

    Flow:
      1. Claude haiku extracts a searchable address from informal text
      2. TGOS API (Taiwan government geocoding, ~90% accuracy)
      3. Nominatim / OpenStreetMap (fallback)

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
    return None
