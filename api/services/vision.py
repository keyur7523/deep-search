"""
Computer Vision services for analyzing diagrams, charts, and images
COMPLETE IMPLEMENTATION with Azure Computer Vision
"""
import os, httpx, asyncio, logging
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

AZ_KEY = os.getenv("AZURE_VISION_KEY", "")
AZ_EP = os.getenv("AZURE_VISION_ENDPOINT", "").rstrip("/")


async def _client():
    """Create HTTP client with Azure credentials"""
    return httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        headers={"Ocp-Apim-Subscription-Key": AZ_KEY}
    )


async def analyze_image_azure(image_url: str) -> Optional[Dict[str, Any]]:
    """
    Analyze image using Azure Computer Vision API
    Extracts description, objects, tags, colors
    """
    if not AZ_KEY or not AZ_EP:
        logger.debug("Azure Vision credentials not configured")
        return None
    
    url = f"{AZ_EP}/vision/v3.2/analyze"
    params = {"visualFeatures": "Description,Objects,Tags,Color"}
    
    try:
        async with await _client() as cx:
            r = await cx.post(url, params=params, json={"url": image_url})
            if r.status_code >= 400:
                logger.warning(f"analyze_image_azure {r.status_code} {r.text[:200]}")
                return None
            return r.json()
    except Exception as e:
        logger.error(f"Azure Vision analyze error: {e}")
        return None


async def extract_text_azure(image_url: str) -> Optional[str]:
    """
    Extract text from images using Azure OCR (Read API)
    Two-step process: submit + poll for results
    """
    if not AZ_KEY or not AZ_EP:
        return None
    
    submit_url = f"{AZ_EP}/vision/v3.2/read/analyze"
    
    try:
        async with await _client() as cx:
            # Step 1: Submit for processing
            submit_resp = await cx.post(submit_url, json={"url": image_url})
            if submit_resp.status_code >= 400:
                logger.warning(f"read submit {submit_resp.status_code} {submit_resp.text[:200]}")
                return None
            
            operation_location = submit_resp.headers.get("Operation-Location", "")
            if not operation_location:
                logger.warning("No Operation-Location header in OCR response")
                return None
            
            # Step 2: Poll for results
            for attempt in range(10):
                await asyncio.sleep(0.8)
                result_resp = await cx.get(operation_location)
                result_json = result_resp.json()
                
                status = result_json.get("status", "")
                if status == "succeeded":
                    # Extract all text lines
                    lines = []
                    for read_result in result_json.get("analyzeResult", {}).get("readResults", []):
                        for line in read_result.get("lines", []):
                            lines.append(line.get("text", ""))
                    
                    extracted = "\n".join(lines).strip()
                    logger.info(f"✅ OCR extracted {len(extracted)} chars from {image_url[:60]}")
                    return extracted
                
                elif status == "failed":
                    logger.warning(f"OCR failed for {image_url[:60]}")
                    return None
            
            logger.warning(f"OCR timeout for {image_url[:60]}")
            return None
    
    except Exception as e:
        logger.error(f"Azure OCR error: {e}")
        return None


async def extract_image_urls_from_html(html: str, base_url: str) -> List[str]:
    """
    Extract image URLs from HTML content
    Filters for diagrams, charts, and figures
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("BeautifulSoup not installed, cannot extract images from HTML")
        return []
    
    try:
        soup = BeautifulSoup(html, "html.parser")
        urls = []
        
        # Find figures and images
        for element in soup.find_all(["figure", "img"]):
            src = None
            
            if element.name == "img":
                src = element.get("src")
            elif element.name == "figure":
                img_tag = element.find("img")
                if img_tag:
                    src = img_tag.get("src")
            
            if not src:
                continue
            
            # Handle protocol-relative and relative URLs
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                from urllib.parse import urljoin
                src = urljoin(base_url, src)
            
            # Filter for likely diagrams/charts
            alt = (element.get("alt", "") or "").lower()
            src_lower = src.lower()
            
            diagram_keywords = ["diagram", "figure", "chart", "graph", "plot", "illustration"]
            
            if any(kw in alt for kw in diagram_keywords) or any(kw in src_lower for kw in diagram_keywords):
                urls.append(src)
        
        # Deduplicate and cap at 5
        unique_urls = []
        seen = set()
        for url in urls:
            if url not in seen and url.startswith("http"):
                seen.add(url)
                unique_urls.append(url)
        
        return unique_urls[:5]
    
    except Exception as e:
        logger.error(f"Error extracting images from HTML: {e}")
        return []


async def analyze_source_visuals(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Complete visual analysis pipeline for a source
    Returns list of visual assets with captions, OCR text, tags
    """
    html = source.get("html", "")
    base_url = source.get("url", "")
    
    if not html:
        return []
    
    # Extract image URLs
    image_urls = await extract_image_urls_from_html(html, base_url)
    if not image_urls:
        return []
    
    logger.info(f"🖼️  Found {len(image_urls)} potential diagrams in {base_url[:60]}")
    
    # Analyze each image
    assets = []
    for img_url in image_urls:
        try:
            # Get description and metadata
            meta = await analyze_image_azure(img_url) or {}
            
            # Get OCR text
            ocr_text = await extract_text_azure(img_url) or ""
            
            # Extract caption
            caption = ""
            if meta.get("description", {}).get("captions"):
                caption = meta["description"]["captions"][0].get("text", "")
            
            # Extract objects and tags
            objects = [obj.get("object", "") for obj in meta.get("objects", [])]
            tags = [tag.get("name", "") for tag in meta.get("tags", [])]
            
            asset = {
                "kind": "image",
                "url": img_url,
                "caption": caption,
                "ocrText": ocr_text,
                "objects": objects,
                "tags": tags,
                "confidence": meta.get("description", {}).get("captions", [{}])[0].get("confidence", 0.0) if meta.get("description") else 0.0
            }
            
            assets.append(asset)
            logger.info(f"✅ Analyzed visual: {caption[:60] if caption else img_url[:60]}")
        
        except Exception as e:
            logger.warning(f"⚠️ Failed to analyze image {img_url[:60]}: {e}")
            continue
    
    return assets


async def analyze_diagram_with_llm(image_url: str, context: str = "") -> Optional[Dict[str, Any]]:
    """
    Analyze diagrams using GPT-4 Vision or Claude Vision
    Provides deep semantic understanding of visual content
    """
    llm_base = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    llm_key = os.getenv("LLM_API_KEY")
    vision_model = os.getenv("LLM_VISION_MODEL", "gpt-4o")
    
    if not llm_key:
        logger.debug("LLM API key not set for vision analysis")
        return None
    
    # Prepare prompt
    prompt = f"""Analyze this diagram/figure in detail. Provide:
1. Overall description of what the image shows
2. Key data points, trends, or findings visible
3. Text labels, axis labels, and annotations present
4. Scientific or technical insights that can be derived
5. How this relates to: {context}

Focus on extracting factual information that would be useful in a research report."""
    
    url = f"{llm_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {llm_key}",
        "Content-Type": "application/json"
    }
    
    body = {
        "model": vision_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ],
        "max_tokens": 500
    }
    
    try:
        async with httpx.AsyncClient(timeout=30) as cx:
            r = await cx.post(url, headers=headers, json=body)
            r.raise_for_status()
            result = r.json()
        
        analysis = result["choices"][0]["message"]["content"]
        
        logger.info(f"🔍 LLM Vision analyzed diagram: {image_url[:60]}")
        return {
            "source": "llm_vision",
            "analysis": analysis,
            "model": vision_model,
            "image_url": image_url
        }
    
    except Exception as e:
        logger.error(f"❌ LLM Vision error: {e}")
        return None
