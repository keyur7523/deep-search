import os, httpx, urllib.parse
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)    

def _get_provider():
    return os.getenv("SEARCH_PROVIDER", "serpapi")

def _get_serp_key():
    return os.getenv("SERPAPI_KEY", "")

def _get_brave_key():
    return os.getenv("BRAVE_API_KEY", "")

async def web_search(query: str, top: int = 8, provider: str = None) -> List[Dict]:
    provider = provider or _get_provider()
    
    # Check if we have API keys for the requested provider
    if provider == "brave" and not _get_brave_key():
        provider = "crossref"  # Use free academic search instead of mock
    elif provider in ["serpapi", "scholar", "hybrid"] and not _get_serp_key():
        provider = "crossref"  # Use free academic search instead of mock
    
    if provider == "brave":
        return await _brave(query, top)
    elif provider == "scholar":
        return await _scholar(query, top)
    elif provider == "hybrid":
        return await _hybrid_search(query, top)
    elif provider == "crossref":
        return await _crossref_search(query, top)
    elif provider == "mock":
        return _mock_search(query, top)
    return await _serpapi(query, top)

async def _hybrid_search(query: str, top: int) -> List[Dict]:
    """Combine web search and Google Scholar for comprehensive research"""
    import asyncio

    logger.info(f"🔍 Starting hybrid search for: '{query}' (top={top})")
    
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

async def hybrid_search(query: str, limit: int = 8) -> List[Dict]:
    """
    Public wrapper for hybrid search.
    Used by the agent system.
    """
    return await _hybrid_search(query, limit)

async def brave_search(query: str, count: int = 8) -> List[Dict]:
    """
    Public wrapper for Brave search.
    Used by the agent system.
    """
    return await _brave(query, count)

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
    logger.info(f"🔍 SerpAPI returned {len(out)} results")
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
    logger.info(f"🔍 Brave returned {len(results)} results")
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

    logger.info(f"🔍 Google Scholar returned {len(out)} results")
    return out

def _mock_search(query: str, top: int = 8) -> List[Dict]:
    """Mock search for testing when API keys are not available"""
    import time
    print(f"🔧 Using mock search for query: {query}")
    time.sleep(1)  # Simulate search delay
    
    # Generate mock results based on query
    mock_results = []
    for i in range(min(top, 5)):
        mock_results.append({
            "title": f"Research Article {i+1}: {query}",
            "url": f"https://example.com/article{i+1}",
            "snippet": f"This is a comprehensive research article about {query}. It covers key aspects, methodologies, and findings related to the topic.",
            "score": 0.9 - (i * 0.1),
            "type": "academic" if i < 3 else "web",
            "authors": f"Researcher {i+1}, et al.",
            "year": 2023,
            "citations": 10 + i * 5
        })
    
    return mock_results

async def _crossref_search(query: str, top: int = 8) -> List[Dict]:
    """Search CrossRef for academic papers (free, no API key required)"""
    import httpx
    import urllib.parse
    
    try:
        # Search CrossRef API
        search_query = urllib.parse.quote(query)
        url = f"https://api.crossref.org/works?query={search_query}&rows={top}&sort=relevance"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code != 200:
                return []
            
            data = response.json()
            works = data.get("message", {}).get("items", [])
            
            results = []
            for work in works:
                title = work.get("title", [""])[0] if work.get("title") else "Untitled"
                authors = work.get("author", [])
                author_names = [f"{a.get('given', '')} {a.get('family', '')}" for a in authors[:3]]
                author_text = ", ".join(author_names) + (" et al." if len(authors) > 3 else "")
                
                # Get publication year
                pub_date = work.get("published-print", work.get("published-online", {}))
                year = pub_date.get("date-parts", [[None]])[0][0] if pub_date else None
                
                # Get DOI URL
                doi = work.get("DOI", "")
                url = f"https://doi.org/{doi}" if doi else ""
                
                # Get abstract
                abstract = work.get("abstract", "")
                if abstract:
                    # Remove HTML tags and limit length
                    import re
                    abstract = re.sub(r'<[^>]+>', '', abstract)
                    abstract = abstract[:300] + "..." if len(abstract) > 300 else abstract
                
                results.append({
                    "title": title,
                    "url": url,
                    "snippet": abstract or f"Academic paper about {query}",
                    "score": 0.9,
                    "type": "academic",
                    "authors": author_text,
                    "year": year,
                    "citations": work.get("is-referenced-by-count", 0),
                    "doi": doi,
                    "journal": work.get("container-title", [""])[0] if work.get("container-title") else ""
                })
            
            return results
            
    except Exception as e:
        print(f"Error searching CrossRef: {e}")
        return []
