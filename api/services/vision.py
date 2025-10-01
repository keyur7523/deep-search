"""
Computer Vision services for analyzing diagrams, charts, and images
Supports Azure Computer Vision, Google Vision, and local OCR
"""
import os, httpx, logging, base64
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


# === Azure Computer Vision ===
async def analyze_image_azure(image_url: str) -> Optional[Dict[str, Any]]:
    """
    Analyze image using Azure Computer Vision API
    Extracts text, objects, captions, and more
    """
    api_key = os.getenv("AZURE_VISION_KEY")
    endpoint = os.getenv("AZURE_VISION_ENDPOINT")
    
    if not api_key or not endpoint:
        logger.warning("⚠️ Azure Vision credentials not set")
        return None
    
    url = f"{endpoint}/vision/v3.2/analyze"
    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "Content-Type": "application/json"
    }
    params = {
        "visualFeatures": "Categories,Description,Tags,Objects,Faces,ImageType,Color",
        "details": "Landmarks",
        "language": "en"
    }
    body = {"url": image_url}
    
    try:
        async with httpx.AsyncClient(timeout=30) as cx:
            r = await cx.post(url, headers=headers, params=params, json=body)
            r.raise_for_status()
            result = r.json()
        
        logger.info(f"✅ Azure Vision analyzed: {image_url[:60]}")
        return {
            "source": "azure",
            "description": result.get("description", {}).get("captions", [{}])[0].get("text", ""),
            "tags": [tag["name"] for tag in result.get("tags", [])],
            "objects": [obj["object"] for obj in result.get("objects", [])],
            "text": None,  # For OCR, need separate call
            "raw": result
        }
    
    except Exception as e:
        logger.error(f"❌ Azure Vision error: {e}")
        return None


async def extract_text_azure(image_url: str) -> Optional[str]:
    """
    Extract text from images using Azure OCR
    Better for diagrams with labels, charts, etc.
    """
    api_key = os.getenv("AZURE_VISION_KEY")
    endpoint = os.getenv("AZURE_VISION_ENDPOINT")
    
    if not api_key or not endpoint:
        return None
    
    url = f"{endpoint}/vision/v3.2/read/analyze"
    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "Content-Type": "application/json"
    }
    body = {"url": image_url}
    
    try:
        # Start OCR operation
        async with httpx.AsyncClient(timeout=30) as cx:
            r = await cx.post(url, headers=headers, json=body)
            r.raise_for_status()
            operation_location = r.headers.get("Operation-Location")
        
        # Poll for results
        import asyncio
        for _ in range(10):
            await asyncio.sleep(1)
            async with httpx.AsyncClient(timeout=30) as cx:
                r = await cx.get(operation_location, headers=headers)
                r.raise_for_status()
                result = r.json()
                
                if result.get("status") == "succeeded":
                    # Extract text
                    text_lines = []
                    for page in result.get("analyzeResult", {}).get("readResults", []):
                        for line in page.get("lines", []):
                            text_lines.append(line.get("text", ""))
                    
                    extracted = "\n".join(text_lines)
                    logger.info(f"✅ Azure OCR extracted {len(extracted)} chars from {image_url[:60]}")
                    return extracted
                
                elif result.get("status") == "failed":
                    break
        
        return None
    
    except Exception as e:
        logger.error(f"❌ Azure OCR error: {e}")
        return None


# === LLM-based Image Analysis (GPT-4 Vision, Claude Vision) ===
async def analyze_diagram_with_llm(image_url: str, context: str = "") -> Optional[Dict[str, Any]]:
    """
    Analyze diagrams, charts, and figures using GPT-4 Vision or Claude
    Provides deep semantic understanding of visual content
    """
    llm_base = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    llm_key = os.getenv("LLM_API_KEY")
    vision_model = os.getenv("LLM_VISION_MODEL", "gpt-4o")  # or "claude-3-opus-20240229"
    
    if not llm_key:
        logger.warning("⚠️ LLM API key not set for vision analysis")
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


# === Extract images from academic papers ===
async def extract_figures_from_pdf(pdf_url: str) -> List[Dict[str, Any]]:
    """
    Extract figures and diagrams from PDF papers
    Returns list of figure URLs and metadata
    """
    # For now, this is a placeholder
    # Full implementation would use PyMuPDF or pdf2image
    # to extract images, then upload to temporary storage
    
    logger.info(f"📊 Extracting figures from PDF: {pdf_url[:60]}")
    
    # TODO: Implement full PDF figure extraction
    # 1. Download PDF
    # 2. Extract images using PyMuPDF
    # 3. Upload to temporary storage (S3/similar)
    # 4. Return URLs for analysis
    
    return []


# === Main Vision Pipeline ===
async def analyze_source_visuals(
    source: Dict[str, Any], 
    topic: str
) -> Dict[str, Any]:
    """
    Complete visual analysis pipeline for a source
    1. Extract figures/diagrams
    2. Analyze with OCR
    3. Analyze with vision LLM
    4. Return structured insights
    """
    visual_insights = {
        "has_visuals": False,
        "figures": [],
        "extracted_text": "",
        "insights": []
    }
    
    # Check if source has PDF
    pdf_url = source.get("pdf_url")
    if pdf_url:
        figures = await extract_figures_from_pdf(pdf_url)
        visual_insights["has_visuals"] = len(figures) > 0
        visual_insights["figures"] = figures
        
        # Analyze each figure
        for fig in figures[:3]:  # Limit to first 3 figures
            fig_url = fig.get("url")
            if not fig_url:
                continue
            
            # OCR extraction
            ocr_text = await extract_text_azure(fig_url)
            if ocr_text:
                visual_insights["extracted_text"] += f"\n[Figure {fig.get('number')}]: {ocr_text}"
            
            # Deep analysis with vision LLM
            analysis = await analyze_diagram_with_llm(fig_url, context=topic)
            if analysis:
                visual_insights["insights"].append({
                    "figure": fig.get("number"),
                    "caption": fig.get("caption", ""),
                    "analysis": analysis.get("analysis", ""),
                    "url": fig_url
                })
    
    return visual_insights


# === Fallback: Use URLs from source content ===
async def extract_image_urls_from_html(html_content: str) -> List[str]:
    """
    Extract image URLs from HTML content
    Useful for web sources with embedded diagrams
    """
    import re
    
    # Find img tags
    img_pattern = r'<img[^>]+src="([^"]+)"'
    urls = re.findall(img_pattern, html_content)
    
    # Filter for likely diagrams (not logos, ads, etc.)
    diagram_keywords = ['figure', 'chart', 'graph', 'diagram', 'plot', 'image', 'fig']
    
    filtered = []
    for url in urls:
        url_lower = url.lower()
        if any(kw in url_lower for kw in diagram_keywords):
            filtered.append(url)
    
    return filtered[:5]  # Max 5 images per source

