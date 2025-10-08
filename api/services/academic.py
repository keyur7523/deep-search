"""
Academic research services for deep scholarly analysis
Integrates with Semantic Scholar, arXiv, PubMed, and Crossref
Enhanced with comprehensive journal ranking and quality scoring
"""
import os, httpx, logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import asyncio

load_dotenv()
logger = logging.getLogger(__name__)

def _safe_int(value: Any, default: int = 0, max_val: int = 2147483647) -> int:
    """Convert to safe MongoDB integer, capping at max value"""
    try:
        val = int(value) if value else default
        return min(max(val, -2147483648), max_val)
    except:
        return default

async def search_serpapi(query: str, num_results: int = 8) -> List[Dict]:
    """
    Wrapper for agent system compatibility.
    Uses Semantic Scholar as primary source.
    """
    return await semantic_scholar_search(query, num_results)

async def search_crossref(query: str, rows: int = 8) -> List[Dict]:
    """
    Wrapper for agent system compatibility.
    Uses deep academic search combining multiple sources.
    """
    return await deep_academic_search(query, rows)

# === Semantic Scholar API (Free, no key required) ===
async def semantic_scholar_search(query: str, top: int = 10) -> List[Dict]:
    """
    Search Semantic Scholar for peer-reviewed papers
    Free API, high-quality academic sources with citations
    """
    await asyncio.sleep(1)
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": top,
        "fields": "title,authors,year,abstract,citationCount,venue,openAccessPdf,url,externalIds,publicationTypes,fieldsOfStudy"
    }
    headers = {"User-Agent": "DeepResearch/1.0"}
    
    # Add API key if available (for higher rate limits)
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
        logger.info("Using Semantic Scholar API key")
    
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
                "citations": _safe_int(paper.get("citationCount", 0)),
                "venue": paper.get("venue", ""),
                "pdf_url": paper.get("openAccessPdf", {}).get("url") if paper.get("openAccessPdf") else None,
                "doi": paper.get("externalIds", {}).get("DOI"),
                "arxiv_id": paper.get("externalIds", {}).get("ArXiv"),
                "pmid": paper.get("externalIds", {}).get("PubMed"),
                "type": "academic",
                "source": "semantic_scholar",
                "publication_types": paper.get("publicationTypes", []),
                "fields": paper.get("fieldsOfStudy", [])
            })
        
        logger.info(f"Semantic Scholar found {len(results)} papers for: {query[:50]}")
        return results
    
    except Exception as e:
        logger.error(f"Semantic Scholar error: {e}")
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
                "citations": 0  # PubMed doesn't provide citation counts
            })
        
        logger.info(f"PubMed found {len(results)} papers for: {query[:50]}")
        return results
    
    except Exception as e:
        logger.error(f"PubMed error: {e}")
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
                    "venue": "arXiv preprint",
                    "citations": 0  # arXiv doesn't provide citation counts
                })
        
        logger.info(f"arXiv found {len(results)} papers for: {query[:50]}")
        return results
    
    except Exception as e:
        logger.error(f"arXiv error: {e}")
        return []


# === Enhanced Academic Search ===
async def deep_academic_search(query: str, top: int = 20, topic_type: str = "general") -> List[Dict]:
    """
    Multi-source academic search combining Semantic Scholar, PubMed, and arXiv
    Automatically prioritizes based on topic type
    Returns only high-quality sources with enhanced scoring
    """
    import asyncio
    
    # Determine source priority based on topic
    if any(term in query.lower() for term in ["blood", "pressure", "medical", "health", "disease", "treatment", "clinical", "patient", "diagnosis", "therapy"]):
        topic_type = "medical"
    elif any(term in query.lower() for term in ["algorithm", "machine learning", "neural", "computing", "AI", "software", "programming"]):
        topic_type = "cs"
    
    # Allocate search budget - prioritize best sources for topic
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
            semantic_scholar_search(query, int(top * 0.7)),
            pubmed_search(query, int(top * 0.2)),
            arxiv_search(query, int(top * 0.1))
        ]
    
    # Run all searches in parallel
    results_list = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Combine and deduplicate
    combined = []
    seen_titles = set()
    seen_urls = set()
    seen_dois = set()
    
    for results in results_list:
        if isinstance(results, Exception):
            logger.warning(f"Academic search exception: {results}")
            continue
        
        for result in results:
            title_lower = result.get("title", "").lower()
            url = result.get("url", "")
            doi = result.get("doi", "")
            
            # Deduplicate by title similarity, URL, and DOI
            if title_lower not in seen_titles and url not in seen_urls and (not doi or doi not in seen_dois):
                # Score the source
                result["score"] = score_source_quality(result)
                combined.append(result)
                seen_titles.add(title_lower)
                seen_urls.add(url)
                if doi:
                    seen_dois.add(doi)
    
    # Sort by quality score (high to low)
    combined.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    # Filter: only keep sources with score >= 0.4 (minimum quality threshold)
    high_quality = [s for s in combined if s.get("score", 0) >= 0.4]
    
    logger.info(f"Deep academic search found {len(combined)} unique papers, {len(high_quality)} high-quality (score >= 0.4)")
    return high_quality[:top]


# === ENHANCED Quality Scoring with Comprehensive Journal Rankings ===
def score_source_quality(source: Dict[str, Any]) -> float:
    """
    Enhanced quality scoring based on multiple academic indicators
    Returns 0.0 - 1.0 with strict criteria
    """
    score = 0.2  # Low base score - sources must earn quality points
    
    # Type check
    if source.get("type") != "academic":
        return min(0.45, score)  # Cap web sources
    
    score += 0.15  # Base academic bonus
    
    # === CITATION COUNT (Log scale with diminishing returns) ===
    citations = _safe_int(source.get("citations", 0))
    if citations > 0:
        # Logarithmic scoring: 10 citations = 0.05, 100 = 0.10, 1000 = 0.15, 10000+ = 0.20
        import math
        citation_score = min(0.20, 0.05 * math.log10(citations + 1))
        score += citation_score
    
    # === RECENCY (Last 5 years preferred) ===
    year = source.get("year", "")
    if year and str(year).isdigit():
        year_int = int(year)
        current_year = 2025
        age = current_year - year_int
        
        if 0 <= age <= 2:
            score += 0.15  # Very recent (2023-2025)
        elif age <= 5:
            score += 0.10  # Recent (2020-2022)
        elif age <= 10:
            score += 0.03  # Moderately recent
        else:
            score -= 0.05  # Penalty for old papers (unless seminal)
    
    # === VENUE/JOURNAL RANKING (Most impactful factor) ===
    venue = source.get("venue", "").lower()
    
    # TIER 0: Absolute top-tier (Nature/Science family)
    tier0_journals = [
        "nature",
        "science",
        "cell",
        "nature medicine",
        "nature biotechnology",
        "nature neuroscience",
        "nature genetics",
        "nature immunology",
        "science translational medicine"
    ]
    if any(j in venue for j in tier0_journals) and not "communications" in venue:
        score += 0.35
        logger.info(f"Tier 0 journal detected: {venue[:50]}")
    
    # TIER 1: Top medical journals
    elif any(j in venue for j in [
        "new england journal of medicine", "nejm",
        "lancet",
        "jama",
        "bmj", "british medical journal",
        "annals of internal medicine",
        "plos medicine"
    ]):
        score += 0.30
        logger.info(f"Tier 1 medical journal detected: {venue[:50]}")
    
    # TIER 2: Top specialty journals (by field)
    elif any(j in venue for j in [
        # Cardiology
        "circulation", "journal of the american college of cardiology", "jacc",
        "european heart journal", "hypertension",
        # Neuroscience
        "neuron", "nature neuroscience", "brain",
        # Immunology
        "immunity", "journal of immunology", "nature immunology",
        # Cancer
        "cancer cell", "journal of clinical oncology",
        # Molecular Biology
        "molecular cell", "cell metabolism", "genes & development",
        # Genetics
        "nature genetics", "american journal of human genetics",
        # General Medicine
        "pnas", "proceedings of the national academy"
    ]):
        score += 0.25
        logger.info(f"Tier 2 specialty journal detected: {venue[:50]}")
    
    # TIER 3: Good specialty journals
    elif any(j in venue for j in [
        "journal of clinical investigation", "blood",
        "diabetes", "kidney international",
        "american journal of", "european journal of",
        "clinical", "journal of"
    ]) and not any(predatory in venue for predatory in ["frontiers", "hindawi"]):
        score += 0.18
    
    # TIER 4: Reputable publishers (moderate quality)
    elif any(pub in venue for pub in [
        "plos", "bmc", "springer", "elsevier",
        "wiley", "oxford", "cambridge",
        "taylor & francis", "sage"
    ]) and not any(predatory in venue for predatory in ["frontiers", "hindawi", "mdpi"]):
        score += 0.12
    
    # TIER 5: arXiv preprints (not peer-reviewed yet, but cutting edge)
    elif "arxiv" in venue or source.get("source") == "arxiv":
        score += 0.05  # Lower score due to lack of peer review
    
    # Penalty for potentially predatory publishers
    if any(predatory in venue for predatory in ["frontiers in", "hindawi", "scientific reports"]):
        score -= 0.10
        logger.warning(f"Potentially predatory publisher: {venue[:50]}")
    
    # === PUBLICATION TYPE (Systematic reviews and meta-analyses are gold standard) ===
    pub_types = source.get("publication_types", [])
    if isinstance(pub_types, list):
        pub_types_lower = [pt.lower() for pt in pub_types]
        if any(pt in pub_types_lower for pt in ["meta-analysis", "systematic review"]):
            score += 0.20
            logger.info(f"Meta-analysis or systematic review detected")
        elif any(pt in pub_types_lower for pt in ["randomized controlled trial", "clinical trial"]):
            score += 0.15
            logger.info(f"RCT detected")
        elif any(pt in pub_types_lower for pt in ["review", "journal article"]):
            score += 0.05
    
    # === PDF AVAILABILITY (Full text accessible) ===
    if source.get("pdf_url"):
        score += 0.08
    
    # === ABSTRACT QUALITY (Longer abstracts = more detailed papers) ===
    snippet = source.get("snippet", "")
    if len(snippet) > 200:
        score += 0.05
    
    # === FIELD OF STUDY (Bonus for relevant fields) ===
    fields = source.get("fields", [])
    if isinstance(fields, list):
        fields_lower = [f.lower() for f in fields]
        if any(field in fields_lower for field in ["medicine", "biology", "neuroscience", "pharmacology"]):
            score += 0.03
    
    final_score = min(1.0, max(0.0, score))
    
    if final_score >= 0.7:
        logger.info(f"High-quality source (score={final_score:.2f}): {source.get('title', '')[:60]}")
    
    return final_score


# === Helper: Get top journals by field ===
def get_top_journals_by_field(field: str) -> List[str]:
    """
    Returns list of top journals for a specific field
    Useful for field-specific research
    """
    journals = {
        "cardiology": [
            "circulation", "journal of the american college of cardiology",
            "european heart journal", "hypertension", "jacc"
        ],
        "neuroscience": [
            "neuron", "nature neuroscience", "brain", "journal of neuroscience"
        ],
        "oncology": [
            "cancer cell", "journal of clinical oncology", "lancet oncology"
        ],
        "immunology": [
            "immunity", "nature immunology", "journal of immunology"
        ],
        "endocrinology": [
            "diabetes", "diabetes care", "journal of clinical endocrinology"
        ],
        "nephrology": [
            "kidney international", "journal of the american society of nephrology"
        ]
    }
    return journals.get(field.lower(), [])