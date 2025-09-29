import os, httpx, urllib.parse
from typing import List, Dict

PROVIDER = os.getenv("SEARCH_PROVIDER", "serpapi")
SERP = os.getenv("SERPAPI_KEY", "")
BRAVE = os.getenv("BRAVE_API_KEY", "")

async def web_search(query: str, top: int = 8) -> List[Dict]:
    if PROVIDER == "brave":
        return await _brave(query, top)
    return await _serpapi(query, top)

async def _serpapi(query: str, top: int) -> List[Dict]:
    if not SERP: return []
    url = "https://serpapi.com/search.json"
    params = {"engine":"google","q":query,"num":top,"api_key":SERP}
    async with httpx.AsyncClient(timeout=20) as cx:
        r = await cx.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    results = data.get("organic_results", [])[:top]
    out = []
    for r in results:
        out.append({"title": r.get("title",""), "url": r.get("link",""), "snippet": r.get("snippet",""), "score": 0})
    return out

async def _brave(query: str, top: int) -> List[Dict]:
    if not BRAVE: return []
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {"Accept":"application/json","X-Subscription-Token":BRAVE}
    params = {"q":query, "count": top}
    async with httpx.AsyncClient(timeout=20, headers=headers) as cx:
        r = await cx.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    results = data.get("web",{}).get("results",[])[:top]
    return [{"title": r.get("title",""), "url": r.get("url",""), "snippet": r.get("description",""), "score": 0} for r in results]
