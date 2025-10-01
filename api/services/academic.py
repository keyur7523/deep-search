"""
Academic research services for deep scholarly analysis
Integrates with Semantic Scholar, arXiv, PubMed, and Crossref
"""
import os, httpx, logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# === Semantic Scholar API (Free, no key required) ===
async def semantic_scholar_search(query: str, top: int = 10) -> List[Dict]:
    """
    Search Semantic Scholar for peer-reviewed papers
    Free API, high-quality academic sources with citations
    """
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": top,
        "fields": "title,authors,year,abstract,citationCount,venue,openAccessPdf,url,externalIds"
    }
    headers = {"User-Agent": "DeepResearch/1.0"}
    
    try:
        async with httpx.AsyncClient(timeout=15) as cx:
            r = await cx.get(url, params=params, headers=headers)
            r.raise_for_status()
            data = r.json()
        
        results = []
        for paper in data.get("data", [])[:top]:
            authors = [a.get("name", "") for a in paper.get("authors", [])[:3]]
            author_text = ", ".join(authors) + (" et al." if len(paper.get("authors", [])) > 3 else "")
            
            results.append({
                "title": paper.get("title", ""),
                "url": paper.get("url", ""),
                "snippet": paper.get("abstract", "")[:500] if paper.get("abstract") else "",
                "authors": author_text,
                "year": paper.get("year", ""),
                "citations": paper.get("citationCount", 0),
                "venue": paper.get("venue", ""),
                "pdf_url": paper.get("openAccessPdf", {}).get("url") if paper.get("openAccessPdf") else None,
                "doi": paper.get("externalIds", {}).get("DOI"),
                "arxiv_id": paper.get("externalIds", {}).get("ArXiv"),
                "type": "academic",
                "source": "semantic_scholar",
                "score": paper.get("citationCount", 0) / 100.0  # Citation-based score
            })
        
        logger.info(f"📚 Semantic Scholar found {len(results)} papers for: {query[:50]}")
        return results
    
    except Exception as e:
        logger.error(f"❌ Semantic Scholar error: {e}")
        return []


# === PubMed API (Free, no key required) ===
async def pubmed_search(query: str, top: int = 10) -> List[Dict]:
    """
    Search PubMed for biomedical and life sciences literature
    Ideal for health/medical topics
    """
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    try:
        # Step 1: Search for IDs
        search_url = f"{base_url}/esearch.fcgi"
        search_params = {
            "db": "pubmed",
            "term": query,
            "retmax": top,
            "retmode": "json",
            "sort": "relevance"
        }
        
        async with httpx.AsyncClient(timeout=15) as cx:
            r = await cx.get(search_url, params=search_params)
            r.raise_for_status()
            search_data = r.json()
        
        pmids = search_data.get("esearchresult", {}).get("idlist", [])
        if not pmids:
            return []
        
        # Step 2: Fetch details
        fetch_url = f"{base_url}/esummary.fcgi"
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "json"
        }
        
        async with httpx.AsyncClient(timeout=15) as cx:
            r = await cx.get(fetch_url, params=fetch_params)
            r.raise_for_status()
            fetch_data = r.json()
        
        results = []
        for pmid in pmids:
            paper = fetch_data.get("result", {}).get(pmid, {})
            if not paper:
                continue
            
            authors = paper.get("authors", [])[:3]
            author_text = ", ".join([a.get("name", "") for a in authors])
            if len(paper.get("authors", [])) > 3:
                author_text += " et al."
            
            results.append({
                "title": paper.get("title", ""),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "snippet": paper.get("source", "") + " - " + paper.get("elocationid", ""),
                "authors": author_text,
                "year": paper.get("pubdate", "").split()[0] if paper.get("pubdate") else "",
                "venue": paper.get("fulljournalname", ""),
                "pmid": pmid,
                "doi": paper.get("elocationid", "").replace("doi: ", "") if "doi" in paper.get("elocationid", "").lower() else None,
                "type": "academic",
                "source": "pubmed",
                "score": 0.8  # High-quality medical source
            })
        
        logger.info(f"🏥 PubMed found {len(results)} papers for: {query[:50]}")
        return results
    
    except Exception as e:
        logger.error(f"❌ PubMed error: {e}")
        return []


# === arXiv API (Free, no key required) ===
async def arxiv_search(query: str, top: int = 10) -> List[Dict]:
    """
    Search arXiv for preprints (physics, math, CS, etc.)
    Best for cutting-edge research
    """
    url = "http://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": top,
        "sortBy": "relevance"
    }
    
    try:
        async with httpx.AsyncClient(timeout=15) as cx:
            r = await cx.get(url, params=params)
            r.raise_for_status()
            xml = r.text
        
        # Parse XML (basic extraction)
        import re
        results = []
        entries = re.findall(r"<entry>(.*?)</entry>", xml, re.S)
        
        for entry in entries[:top]:
            title_match = re.search(r"<title>(.*?)</title>", entry, re.S)
            link_match = re.search(r'<id>(.*?)</id>', entry)
            summary_match = re.search(r"<summary>(.*?)</summary>", entry, re.S)
            authors = re.findall(r"<name>(.*?)</name>", entry)
            published = re.search(r"<published>(.*?)</published>", entry)
            
            if title_match and link_match:
                author_text = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
                year = published.group(1).split("-")[0] if published else ""
                
                arxiv_id = link_match.group(1).split("/")[-1]
                
                results.append({
                    "title": title_match.group(1).strip().replace("\n", " "),
                    "url": link_match.group(1),
                    "snippet": summary_match.group(1).strip()[:500] if summary_match else "",
                    "authors": author_text,
                    "year": year,
                    "arxiv_id": arxiv_id,
                    "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                    "type": "academic",
                    "source": "arxiv",
                    "score": 0.7  # Preprint, slightly lower than peer-reviewed
                })
        
        logger.info(f"📄 arXiv found {len(results)} papers for: {query[:50]}")
        return results
    
    except Exception as e:
        logger.error(f"❌ arXiv error: {e}")
        return []


# === Enhanced Academic Search ===
async def deep_academic_search(query: str, top: int = 20, topic_type: str = "general") -> List[Dict]:
    """
    Multi-source academic search combining Semantic Scholar, PubMed, and arXiv
    Automatically prioritizes based on topic type
    """
    import asyncio
    
    # Determine source priority based on topic
    if any(term in query.lower() for term in ["blood", "pressure", "medical", "health", "disease", "treatment", "clinical"]):
        topic_type = "medical"
    elif any(term in query.lower() for term in ["algorithm", "machine learning", "neural", "computing", "AI"]):
        topic_type = "cs"
    
    # Allocate search budget
    if topic_type == "medical":
        tasks = [
            pubmed_search(query, top // 2),
            semantic_scholar_search(query, top // 2)
        ]
    elif topic_type == "cs":
        tasks = [
            arxiv_search(query, top // 2),
            semantic_scholar_search(query, top // 2)
        ]
    else:
        tasks = [
            semantic_scholar_search(query, top * 2 // 3),
            arxiv_search(query, top // 3)
        ]
    
    # Run all searches in parallel
    results_list = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Combine and deduplicate
    combined = []
    seen_titles = set()
    seen_urls = set()
    
    for results in results_list:
        if isinstance(results, Exception):
            logger.warning(f"Academic search exception: {results}")
            continue
        
        for result in results:
            title_lower = result.get("title", "").lower()
            url = result.get("url", "")
            
            # Deduplicate by title similarity and URL
            if title_lower not in seen_titles and url not in seen_urls:
                combined.append(result)
                seen_titles.add(title_lower)
                seen_urls.add(url)
    
    # Sort by quality score (citations, source reputation)
    combined.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    logger.info(f"📚 Deep academic search found {len(combined)} unique papers")
    return combined[:top]


# === Quality Scoring ===
def score_source_quality(source: Dict[str, Any]) -> float:
    """
    Score source quality based on academic indicators
    Returns 0.0 - 1.0
    """
    score = 0.5  # Base score
    
    # Academic sources get boost
    if source.get("type") == "academic":
        score += 0.2
    
    # Citation count (normalized)
    citations = source.get("citations", 0)
    if citations > 0:
        score += min(0.2, citations / 500.0)
    
    # Recent publications get boost
    year = source.get("year", "")
    if year and year.isdigit():
        year_int = int(year)
        if year_int >= 2020:
            score += 0.1
    
    # Peer-reviewed venues
    venue = source.get("venue", "").lower()
    prestigious_venues = ["nature", "science", "cell", "lancet", "jama", "nejm", "pnas"]
    if any(v in venue for v in prestigious_venues):
        score += 0.2
    
    # PDF available = easier to extract comprehensive content
    if source.get("pdf_url"):
        score += 0.1
    
    return min(1.0, score)

