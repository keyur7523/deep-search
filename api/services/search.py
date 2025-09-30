import os, httpx, urllib.parse
from typing import List, Dict

def _get_provider():
    return os.getenv("SEARCH_PROVIDER", "serpapi")

def _get_serp_key():
    return os.getenv("SERPAPI_KEY", "")

def _get_brave_key():
    return os.getenv("BRAVE_API_KEY", "")

async def web_search(query: str, top: int = 8, provider: str = None) -> List[Dict]:
    provider = provider or _get_provider()
    if provider == "brave":
        return await _brave(query, top)
    elif provider == "scholar":
        return await _scholar(query, top)
    elif provider == "hybrid":
        return await _hybrid_search(query, top)
    return await _serpapi(query, top)

async def _hybrid_search(query: str, top: int) -> List[Dict]:
    """Combine web search and Google Scholar for comprehensive research"""
    import asyncio
    
    # Split results between web and academic sources
    web_count = max(1, top // 2)  # At least 1 web result
    scholar_count = top - web_count
    
    # Run both searches concurrently
    web_task = _serpapi(query, web_count)
    scholar_task = _scholar(query, scholar_count)
    
    web_results, scholar_results = await asyncio.gather(
        web_task, scholar_task, return_exceptions=True
    )
    
    # Handle exceptions gracefully
    if isinstance(web_results, Exception):
        web_results = []
    if isinstance(scholar_results, Exception):
        scholar_results = []
    
    # Combine and deduplicate results
    combined = []
    seen_urls = set()
    
    # Add academic sources first (higher priority)
    for result in scholar_results:
        if result.get("url") and result["url"] not in seen_urls:
            combined.append(result)
            seen_urls.add(result["url"])
    
    # Add web sources
    for result in web_results:
        if result.get("url") and result["url"] not in seen_urls:
            result["type"] = "web"  # Mark as web source
            combined.append(result)
            seen_urls.add(result["url"])
    
    return combined[:top]

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

async def _scholar(query: str, top: int) -> List[Dict]:
    """Search Google Scholar using SerpAPI's Google Scholar engine"""
    serp_key = _get_serp_key()
    if not serp_key: return []
    
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_scholar",
        "q": query,
        "num": top,
        "api_key": serp_key,
        "as_ylo": "2020",  # Papers from 2020 onwards for more recent research
        "sort": "relevance"  # Sort by relevance
    }
    
    async with httpx.AsyncClient(timeout=20) as cx:
        r = await cx.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    
    results = data.get("organic_results", [])[:top]
    out = []
    for r in results:
        # Extract author information
        authors = r.get("publication_info", {}).get("authors", [])
        author_names = [author.get("name", "") for author in authors[:3]]  # First 3 authors
        author_text = ", ".join(author_names) + (" et al." if len(authors) > 3 else "")
        
        # Extract publication year
        year = r.get("publication_info", {}).get("summary", "")
        if "Publication date" in year:
            year = year.split("Publication date")[1].split()[0] if "Publication date" in year else ""
        
        # Create enhanced snippet with academic context
        snippet = r.get("snippet", "")
        if author_text:
            snippet = f"[{author_text}] {snippet}"
        if year:
            snippet = f"({year}) {snippet}"
            
        out.append({
            "title": r.get("title", ""),
            "url": r.get("link", ""),
            "snippet": snippet,
            "score": 0,
            "type": "academic",  # Mark as academic source
            "authors": author_text,
            "year": year,
            "citations": r.get("inline_links", {}).get("cited_by", {}).get("total", 0)
        })
    
    return out
