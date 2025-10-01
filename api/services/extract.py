import hashlib, httpx, trafilatura, logging
from typing import Dict, Optional
from readability import Document
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()

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
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as cx:
            logger.info(f"Fetching: {url[:80]}")
            r = await cx.get(url, headers=headers)
            r.raise_for_status()
            html = r.text
            
            if not html or len(html) < 100:
                logger.warning(f"Empty or tiny response from {url[:80]}")
                return None
            
    except httpx.TimeoutException:
        logger.warning(f"Timeout fetching {url[:80]}")
        return None
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP {e.response.status_code} from {url[:80]}")
        return None
    except Exception as e:
        logger.warning(f"Error fetching {url[:80]}: {type(e).__name__}")
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