import asyncio
import hashlib, httpx, trafilatura, logging
from typing import Dict, List, Optional
from readability import Document
from bs4 import BeautifulSoup

from .url_security import validate_web_search_url, URLSecurityError, sanitize_url_for_logging

logger = logging.getLogger(__name__)

# Concurrency limit for batch extraction to avoid overwhelming servers
MAX_CONCURRENT_EXTRACTIONS = 5

def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()

async def extract_content(url: str) -> Dict:
    """
    Wrapper for agent system compatibility.
    Maps to fetch_and_extract function.
    """
    result = await fetch_and_extract(url)
    if result:
        return result
    else:
        # Return empty dict if extraction failed
        return {
            "url": url,
            "title": "",
            "text": "",
            "html": "",
            "hash": ""
        }

async def fetch_and_extract(url: str) -> Optional[Dict]:
    """
    Enhanced extraction with multiple fallback strategies:
    1. Trafilatura (fast, good for news/articles)
    2. Readability (Mozilla's algorithm, good for paywalls)
    3. BeautifulSoup raw extraction (last resort)
    """

    # Skip obviously bad URLs
    if not url or not url.startswith("http"):
        return None

    # SECURITY: Validate URL to prevent SSRF attacks
    # This blocks requests to internal networks, localhost, cloud metadata, etc.
    try:
        validated_url = validate_web_search_url(url)
    except URLSecurityError as e:
        logger.warning(f"URL security check failed for {sanitize_url_for_logging(url)}: {e.reason}")
        return None

    # Better headers to avoid blocking
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    try:
        # Increased timeout, follow redirects
        # SECURITY: Use validated_url, disable redirects to prevent SSRF via redirect
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as cx:
            logger.info(f"Fetching: {sanitize_url_for_logging(validated_url)}")
            r = await cx.get(validated_url, headers=headers)

            # Handle redirects manually to validate each redirect target
            redirect_count = 0
            max_redirects = 5
            while r.is_redirect and redirect_count < max_redirects:
                redirect_count += 1
                redirect_url = r.headers.get("location", "")
                if not redirect_url:
                    break
                # Validate redirect URL
                try:
                    redirect_url = validate_web_search_url(redirect_url)
                except URLSecurityError as e:
                    logger.warning(f"Redirect blocked by security: {e.reason}")
                    return None
                r = await cx.get(redirect_url, headers=headers)

            r.raise_for_status()
            html = r.text

            if not html or len(html) < 100:
                logger.warning(f"Empty or tiny response from {sanitize_url_for_logging(validated_url)}")
                return None

    except httpx.TimeoutException:
        logger.warning(f"Timeout fetching {sanitize_url_for_logging(validated_url)}")
        return None
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP {e.response.status_code} from {sanitize_url_for_logging(validated_url)}")
        return None
    except Exception as e:
        logger.warning(f"Error fetching {sanitize_url_for_logging(validated_url)}: {type(e).__name__}")
        return None
    
    # Strategy 1: Trafilatura (best for clean extraction)
    text = trafilatura.extract(
        html, 
        include_comments=False, 
        include_tables=True,  # Keep tables for data
        include_images=False,
        no_fallback=False,
        favor_precision=False,  # Favor recall to get more content
        favor_recall=True
    )
    
    if text and len(text.strip()) > 200:
        logger.info(f"✅ Trafilatura extracted {len(text)} chars from {url[:80]}")
        return {
            "url": url, 
            "title": _extract_title(html), 
            "text": text.strip(), 
            "html": html[:50000],  # Store first 50KB for visual extraction
            "hash": _hash_text(text)
        }
    
    # Strategy 2: Readability (Mozilla's algorithm, better for complex sites)
    try:
        doc = Document(html)
        title = doc.title()
        content = doc.summary()
        
        # Extract text from HTML using BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)
        
        if text and len(text.strip()) > 200:
            logger.info(f"✅ Readability extracted {len(text)} chars from {url[:80]}")
            return {
                "url": url,
                "title": title,
                "text": text.strip(),
                "html": html[:50000],
                "hash": _hash_text(text)
            }
    except Exception as e:
        logger.debug(f"Readability failed on {url[:80]}: {e}")
    
    # Strategy 3: Raw BeautifulSoup (last resort, gets everything)
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
            script.decompose()
        
        # Get text from main content areas
        main_content = soup.find('main') or soup.find('article') or soup.find('body')
        if main_content:
            text = main_content.get_text(separator=' ', strip=True)
        else:
            text = soup.get_text(separator=' ', strip=True)
        
        # Clean up whitespace
        text = ' '.join(text.split())
        
        if text and len(text.strip()) > 200:
            logger.info(f"✅ BeautifulSoup extracted {len(text)} chars from {url[:80]}")
            return {
                "url": url,
                "title": _extract_title(html),
                "text": text.strip(),
                "html": html[:50000],
                "hash": _hash_text(text)
            }
    except Exception as e:
        logger.warning(f"BeautifulSoup failed on {url[:80]}: {e}")
    
    # All strategies failed
    logger.error(f"❌ All extraction strategies failed for {url[:80]}")
    return None

def _extract_title(html: str) -> str:
    """Extract title from HTML"""
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Try various title sources
        title = None
        
        # 1. <title> tag
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        
        # 2. og:title meta tag
        if not title:
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                title = og_title['content'].strip()
        
        # 3. First h1
        if not title:
            h1 = soup.find('h1')
            if h1:
                title = h1.get_text(strip=True)
        
        return title[:200] if title else ""
    except Exception:
        return ""


async def batch_extract(
    urls: List[str],
    max_concurrent: int = MAX_CONCURRENT_EXTRACTIONS,
    timeout_per_url: float = 30.0
) -> List[Optional[Dict]]:
    """
    Extract content from multiple URLs in parallel with controlled concurrency.

    Uses a semaphore to limit concurrent requests, preventing server overload
    and avoiding rate limits.

    Args:
        urls: List of URLs to extract content from
        max_concurrent: Maximum number of concurrent extractions (default 5)
        timeout_per_url: Timeout per URL extraction in seconds

    Returns:
        List of extraction results (same order as input URLs).
        Failed extractions return None.
    """
    if not urls:
        return []

    # Deduplicate while preserving order
    seen = set()
    unique_urls = []
    url_to_index = {}

    for i, url in enumerate(urls):
        if url and url not in seen:
            seen.add(url)
            unique_urls.append(url)
            url_to_index[url] = i

    logger.info(f"Batch extracting {len(unique_urls)} unique URLs (from {len(urls)} total)")

    # Semaphore to limit concurrency
    semaphore = asyncio.Semaphore(max_concurrent)

    async def extract_with_limit(url: str) -> tuple[str, Optional[Dict]]:
        async with semaphore:
            try:
                result = await asyncio.wait_for(
                    fetch_and_extract(url),
                    timeout=timeout_per_url
                )
                return (url, result)
            except asyncio.TimeoutError:
                logger.warning(f"Batch extraction timeout for {sanitize_url_for_logging(url)}")
                return (url, None)
            except Exception as e:
                logger.warning(f"Batch extraction error for {sanitize_url_for_logging(url)}: {e}")
                return (url, None)

    # Run all extractions concurrently (semaphore limits actual parallelism)
    tasks = [extract_with_limit(url) for url in unique_urls]
    results_tuples = await asyncio.gather(*tasks, return_exceptions=True)

    # Build result map
    result_map: Dict[str, Optional[Dict]] = {}
    for item in results_tuples:
        if isinstance(item, Exception):
            logger.warning(f"Batch extraction task exception: {item}")
            continue
        url, result = item
        result_map[url] = result

    # Build output in original order
    output = []
    for url in urls:
        output.append(result_map.get(url))

    success_count = sum(1 for r in output if r is not None)
    logger.info(f"Batch extraction complete: {success_count}/{len(urls)} successful")

    return output


async def parallel_search_and_extract(
    search_results: List[Dict],
    max_concurrent: int = MAX_CONCURRENT_EXTRACTIONS
) -> List[Dict]:
    """
    Extract content from search results in parallel.

    Enhances search results with full text content by extracting
    from each URL in parallel.

    Args:
        search_results: List of search result dicts with 'url' field
        max_concurrent: Maximum concurrent extractions

    Returns:
        Search results enhanced with 'text' and 'html' fields
    """
    if not search_results:
        return []

    urls = [r.get("url", "") for r in search_results]
    extractions = await batch_extract(urls, max_concurrent)

    # Merge extraction results into search results
    enhanced = []
    for result, extraction in zip(search_results, extractions):
        enhanced_result = result.copy()
        if extraction:
            enhanced_result["text"] = extraction.get("text", "")
            enhanced_result["html"] = extraction.get("html", "")
            enhanced_result["title"] = extraction.get("title") or result.get("title", "")
        else:
            # Keep original snippet if extraction failed
            enhanced_result["text"] = result.get("snippet", "")
        enhanced.append(enhanced_result)

    return enhanced