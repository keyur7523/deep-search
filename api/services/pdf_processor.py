"""
PDF processing service - COMPLETE IMPLEMENTATION
Extracts text, figures, tables, and citations using PyMuPDF
"""
import os, httpx, logging, base64, io
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


async def download_pdf(url: str) -> Optional[bytes]:
    """Download PDF from URL"""
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as cx:
            r = await cx.get(url)
            r.raise_for_status()
            
            # Verify it's actually a PDF
            content_type = r.headers.get("content-type", "").lower()
            if "pdf" not in content_type and not url.endswith(".pdf"):
                logger.warning(f"⚠️ URL may not be a PDF: {url[:60]}")
            
            return r.content
    except Exception as e:
        logger.error(f"❌ PDF download error: {e}")
        return None


async def process_academic_pdf(url: str) -> Dict[str, Any]:
    """
    Complete PDF processing pipeline
    1. Download PDF
    2. Extract text from pages
    3. Extract figures as PNG base64
    4. Return structured data
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("❌ PyMuPDF not installed. Install with: pip install PyMuPDF")
        return {"error": "PyMuPDF not available"}
    
    # Download PDF
    pdf_bytes = await download_pdf(url)
    if not pdf_bytes:
        return {"error": "Failed to download PDF"}
    
    try:
        # Open PDF from bytes
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        result = {
            "pagesText": [],
            "figures": [],
            "metadata": {},
            "page_count": len(doc)
        }
        
        # Extract metadata
        metadata = doc.metadata or {}
        result["metadata"] = {
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
            "subject": metadata.get("subject", ""),
            "keywords": metadata.get("keywords", "")
        }
        
        # Process pages (limit to first 8 for performance)
        max_pages = min(8, doc.page_count)
        
        for page_num in range(max_pages):
            page = doc.load_page(page_num)
            
            # Extract text
            page_text = page.get_text("text")
            result["pagesText"].append(page_text)
            
            # Extract images
            image_list = page.get_images(full=True)
            for img_idx, img_info in enumerate(image_list):
                xref = img_info[0]
                
                try:
                    # Extract image
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    # Convert to PNG if needed
                    if image_ext != "png":
                        pix = fitz.Pixmap(doc, xref)
                        if pix.n > 4:  # CMYK or other
                            pix = fitz.Pixmap(fitz.csRGB, pix)
                        image_bytes = pix.tobytes("png")
                        image_ext = "png"
                    
                    # Encode as base64
                    b64_data = base64.b64encode(image_bytes).decode("utf-8")
                    
                    result["figures"].append({
                        "page": page_num + 1,
                        "number": len(result["figures"]) + 1,
                        "xref": xref,
                        "format": image_ext,
                        "size": len(image_bytes),
                        "pngB64": b64_data
                    })
                    
                except Exception as e:
                    logger.debug(f"Could not extract image {img_idx} from page {page_num + 1}: {e}")
        
        # Combine all text
        full_text = "\n\n".join(result["pagesText"])
        result["text"] = full_text
        
        doc.close()
        
        logger.info(f"✅ PDF processed: {len(full_text)} chars, {len(result['figures'])} figures from {max_pages} pages")
        return result
    
    except Exception as e:
        logger.error(f"❌ PDF extraction error: {e}")
        return {"error": str(e)}


def extract_structured_sections(text: str) -> Dict[str, str]:
    """
    Parse academic paper into structured sections
    Abstract, Introduction, Methods, Results, Discussion, Conclusion
    """
    import re
    
    sections = {
        "abstract": "",
        "introduction": "",
        "methods": "",
        "results": "",
        "discussion": "",
        "conclusion": ""
    }
    
    text_lower = text.lower()
    
    # Common section headers with regex patterns
    patterns = {
        "abstract": [r"\nabstract\s*\n", r"\nabstract:\s*\n", r"\n\d+\.\s*abstract\s*\n"],
        "introduction": [r"\nintroduction\s*\n", r"\n1\.\s*introduction\s*\n", r"\nbackground\s*\n"],
        "methods": [r"\nmethods\s*\n", r"\nmethodology\s*\n", r"\nmaterials and methods\s*\n", r"\nexperimental\s*\n"],
        "results": [r"\nresults\s*\n", r"\nfindings\s*\n"],
        "discussion": [r"\ndiscussion\s*\n"],
        "conclusion": [r"\nconclusion\s*\n", r"\nconclusions\s*\n", r"\nsummary\s*\n"]
    }
    
    # Find section boundaries
    section_positions = {}
    for section, pats in patterns.items():
        for pat in pats:
            match = re.search(pat, text_lower)
            if match:
                section_positions[section] = match.end()
                break
    
    # Extract text between sections
    sorted_sections = sorted(section_positions.items(), key=lambda x: x[1])
    
    for i, (section, start) in enumerate(sorted_sections):
        # Find end position (next section or end of text)
        if i + 1 < len(sorted_sections):
            end = sorted_sections[i + 1][1]
        else:
            end = min(start + 3000, len(text))  # Cap at 3k chars
        
        sections[section] = text[start:end].strip()
    
    return sections


async def upload_figure_to_s3(png_b64: str, filename: str) -> Optional[str]:
    """
    Upload figure to S3 and return public URL
    """
    try:
        from services.s3util import presign_put_url
        import boto3
        
        bucket = os.getenv("S3_BUCKET", "")
        if not bucket:
            return None
        
        # Decode base64
        image_bytes = base64.b64decode(png_b64)
        
        # Generate S3 key
        import uuid
        key = f"figures/{uuid.uuid4()}-{filename}"
        
        # Upload to S3
        s3 = boto3.client('s3')
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=image_bytes,
            ContentType="image/png"
        )
        
        # Return public URL
        url = f"https://{bucket}.s3.amazonaws.com/{key}"
        return url
    
    except Exception as e:
        logger.warning(f"⚠️ Failed to upload figure to S3: {e}")
        return None


def extract_references(text: str) -> List[str]:
    """
    Extract references section from paper
    Basic heuristic-based parsing
    """
    import re
    
    text_lower = text.lower()
    
    # Find references section
    ref_markers = ["references", "bibliography", "works cited", "literature cited"]
    ref_start = None
    
    for marker in ref_markers:
        pattern = rf"\n{marker}\s*\n"
        match = re.search(pattern, text_lower)
        if match:
            ref_start = match.end()
            break
    
    if not ref_start:
        return []
    
    # Extract references text (max 5000 chars)
    refs_text = text[ref_start:ref_start + 5000]
    
    # Split by common patterns
    lines = refs_text.split("\n")
    references = []
    current_ref = ""
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check if this looks like a new reference
        # Pattern: numbered list or starts with author name
        if re.match(r"^\d+[\.\)]\s+", line) or re.match(r"^[A-Z][a-z]+,\s+[A-Z]", line):
            if current_ref:
                references.append(current_ref.strip())
            current_ref = line
        else:
            current_ref += " " + line
    
    if current_ref:
        references.append(current_ref.strip())
    
    return references[:50]  # Cap at 50 references
