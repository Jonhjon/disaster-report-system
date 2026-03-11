import httpx


async def geocode_address(address: str) -> dict | None:
    """Convert address text to coordinates using Nominatim (OpenStreetMap).

    Returns {"latitude": float, "longitude": float, "display_name": str} or None if not found.
    Retries once with "台灣" appended to improve hit rate.
    """
    url = "https://nominatim.openstreetmap.org/search"
    headers = {
        "User-Agent": "DisasterReportSystem/1.0",
        "Accept-Language": "zh-TW,zh;q=0.9",
    }

    async with httpx.AsyncClient() as client:
        for query in [address, address + " 台灣"]:
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
                        "display_name": results[0]["display_name"],
                    }
    return None
