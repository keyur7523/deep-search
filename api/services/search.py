import asyncio
import os, httpx, urllib.parse
from typing import List, Dict, Optional, Callable, Awaitable
import logging

logger = logging.getLogger(__name__)

# Type alias for search functions
SearchFunction = Callable[[str, int], Awaitable[List[Dict]]]    

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


async def parallel_multi_source_search(
    query: str,
    sources: List[str] = None,
    results_per_source: int = 5,
    timeout: float = 20.0
) -> Dict[str, List[Dict]]:
    """
    Run searches across multiple sources in parallel.

    Efficiently searches multiple providers simultaneously and returns
    results organized by source.

    Args:
        query: Search query string
        sources: List of source names to search. Options:
                 - "web" (SerpAPI or Brave)
                 - "scholar" (Google Scholar via SerpAPI)
                 - "crossref" (CrossRef academic)
                 - "semantic_scholar" (Semantic Scholar API)
                 - "arxiv" (arXiv preprints)
                 - "pubmed" (PubMed biomedical)
                 Default: ["web", "scholar", "crossref"]
        results_per_source: Number of results to fetch per source
        timeout: Timeout for each search in seconds

    Returns:
        Dict mapping source name to list of search results.
        Failed searches return empty lists.

    Example:
        results = await parallel_multi_source_search(
            "machine learning optimization",
            sources=["scholar", "arxiv", "crossref"],
            results_per_source=10
        )
        # results = {"scholar": [...], "arxiv": [...], "crossref": [...]}
    """
    if sources is None:
        sources = ["web", "scholar", "crossref"]

    # Map source names to search functions
    search_functions: Dict[str, SearchFunction] = {
        "web": _serpapi,
        "brave": _brave,
        "scholar": _scholar,
        "crossref": _crossref_search,
    }

    # Dynamically import academic searches if requested
    academic_sources = {"semantic_scholar", "arxiv", "pubmed"}
    if academic_sources & set(sources):
        from .academic import (
            semantic_scholar_search,
            arxiv_search,
            pubmed_search
        )
        search_functions["semantic_scholar"] = semantic_scholar_search
        search_functions["arxiv"] = arxiv_search
        search_functions["pubmed"] = pubmed_search

    # Filter to valid sources
    valid_sources = [s for s in sources if s in search_functions]
    if not valid_sources:
        logger.warning(f"No valid sources specified: {sources}")
        return {}

    async def search_with_timeout(source: str) -> tuple[str, List[Dict]]:
        func = search_functions[source]
        try:
            results = await asyncio.wait_for(
                func(query, results_per_source),
                timeout=timeout
            )
            # Add source tag to each result
            for r in results:
                r["_source"] = source
            logger.info(f"Parallel search: {source} returned {len(results)} results")
            return (source, results)
        except asyncio.TimeoutError:
            logger.warning(f"Parallel search timeout: {source}")
            return (source, [])
        except Exception as e:
            logger.warning(f"Parallel search error ({source}): {e}")
            return (source, [])

    # Run all searches in parallel
    tasks = [search_with_timeout(source) for source in valid_sources]
    results_tuples = await asyncio.gather(*tasks, return_exceptions=True)

    # Build result dict
    results: Dict[str, List[Dict]] = {}
    for item in results_tuples:
        if isinstance(item, Exception):
            logger.error(f"Search task exception: {item}")
            continue
        source, source_results = item
        results[source] = source_results

    total = sum(len(r) for r in results.values())
    logger.info(f"Parallel multi-source search complete: {total} total results from {len(results)} sources")

    return results


async def unified_search(
    query: str,
    total_results: int = 20,
    academic_weight: float = 0.7,
    timeout: float = 20.0
) -> List[Dict]:
    """
    Unified search combining academic and web sources with deduplication.

    Intelligently distributes search budget across sources based on
    academic_weight parameter, runs searches in parallel, then
    deduplicates and scores results.

    Args:
        query: Search query string
        total_results: Total number of results to return
        academic_weight: Proportion of results from academic sources (0.0-1.0)
        timeout: Timeout for searches

    Returns:
        Combined, deduplicated, scored list of search results
    """
    # Calculate results allocation
    academic_count = int(total_results * academic_weight)
    web_count = total_results - academic_count

    # Select sources based on weight
    sources = []
    results_per_source = {}

    if academic_count > 0:
        # Split academic results across multiple sources
        per_academic = max(3, academic_count // 3)
        sources.extend(["semantic_scholar", "scholar", "crossref"])
        for s in ["semantic_scholar", "scholar", "crossref"]:
            results_per_source[s] = per_academic

    if web_count > 0:
        sources.append("web")
        results_per_source["web"] = web_count

    # Run parallel search
    source_results = await parallel_multi_source_search(
        query,
        sources=sources,
        results_per_source=max(results_per_source.values()) if results_per_source else 5,
        timeout=timeout
    )

    # Combine and deduplicate
    combined = []
    seen_urls = set()
    seen_titles = set()

    # Prioritize by source order (academic first)
    source_priority = ["semantic_scholar", "scholar", "crossref", "arxiv", "pubmed", "web", "brave"]

    for source in source_priority:
        if source not in source_results:
            continue

        for result in source_results[source]:
            url = result.get("url", "")
            title = result.get("title", "").lower().strip()

            # Deduplicate by URL and title similarity
            if url and url not in seen_urls and title not in seen_titles:
                seen_urls.add(url)
                seen_titles.add(title)
                combined.append(result)

    # Score results if they don't have scores
    from .academic import score_source_quality
    for result in combined:
        if "score" not in result or result.get("score", 0) == 0:
            result["score"] = score_source_quality(result)

    # Sort by score and return top results
    combined.sort(key=lambda x: x.get("score", 0), reverse=True)

    return combined[:total_results]
