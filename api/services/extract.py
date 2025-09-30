import hashlib, httpx, trafilatura
from typing import Dict, Optional

def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()

async def fetch_and_extract(url: str) -> Optional[Dict]:
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as cx:
            r = await cx.get(url, headers={"User-Agent":"Mozilla/5.0 DeepResearchBot"})
            r.raise_for_status()
            html = r.text
    except Exception:
        return None
    text = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
    if not text.strip(): return None
    return {"url": url, "title": "", "text": text, "hash": _hash_text(text)}
