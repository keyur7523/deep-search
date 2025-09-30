import os, httpx, urllib.parse
from typing import List, Dict

def _get_provider():
    return os.getenv("SEARCH_PROVIDER", "serpapi")

def _get_serp_key():
    return os.getenv("SERPAPI_KEY", "")

def _get_brave_key():
    return os.getenv("BRAVE_API_KEY", "")

async def web_search(query: str, top: int = 8) -> List[Dict]:
    if _get_provider() == "brave":
        return await _brave(query, top)
    return await _serpapi(query, top)

async def _serpapi(query: str, top: int) -> List[Dict]:
    serp_key = _get_serp_key()
    if not serp_key: return []
    url = "https://serpapi.com/search.json"
    params = {"engine":"google","q":query,"num":top,"api_key":serp_key}
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
    brave_key = _get_brave_key()
    if not brave_key: return []
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {"Accept":"application/json","X-Subscription-Token":brave_key}
    params = {"q":query, "count": top}
    async with httpx.AsyncClient(timeout=20, headers=headers) as cx:
        r = await cx.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    results = data.get("web",{}).get("results",[])[:top]
    return [{"title": r.get("title",""), "url": r.get("url",""), "snippet": r.get("description",""), "score": 0} for r in results]
