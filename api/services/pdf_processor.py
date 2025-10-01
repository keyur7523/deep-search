"""
PDF processing service for extracting text, figures, tables, and citations
Supports academic paper analysis
"""
import os, httpx, logging, tempfile
from typing import Dict, List, Any, Optional
from pathlib import Path

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


def extract_pdf_content(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Extract comprehensive content from PDF
    Returns text, figures, tables, metadata
    """
    try:
        import io
        import fitz  # PyMuPDF
        
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        result = {
            "text": "",
            "metadata": {},
            "figures": [],
            "tables": [],
            "references": [],
            "page_count": len(doc)
        }
        
        # Extract metadata
        result["metadata"] = {
            "title": doc.metadata.get("title", ""),
            "author": doc.metadata.get("author", ""),
            "subject": doc.metadata.get("subject", ""),
            "keywords": doc.metadata.get("keywords", "")
        }
        
        # Extract text from all pages
        full_text = []
        for page_num, page in enumerate(doc, 1):
            page_text = page.get_text()
            full_text.append(page_text)
            
            # Extract images from this page
            image_list = page.get_images()
            for img_idx, img in enumerate(image_list):
                xref = img[0]
                try:
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    result["figures"].append({
                        "page": page_num,
                        "number": len(result["figures"]) + 1,
                        "xref": xref,
                        "format": image_ext,
                        "size": len(image_bytes),
                        "bytes": image_bytes  # For later analysis
                    })
                except Exception as e:
                    logger.debug(f"Could not extract image {img_idx} from page {page_num}: {e}")
        
        result["text"] = "\n\n".join(full_text)
        
        # Extract references section (heuristic)
        text_lower = result["text"].lower()
        ref_markers = ["references", "bibliography", "works cited"]
        for marker in ref_markers:
            if f"\n{marker}\n" in text_lower:
                ref_idx = text_lower.index(f"\n{marker}\n")
                refs_text = result["text"][ref_idx:]
                result["references"] = _parse_references(refs_text[:5000])  # Limit to first 5k chars
                break
        
        doc.close()
        logger.info(f"✅ Extracted PDF: {len(result['text'])} chars, {len(result['figures'])} figures")
        return result
    
    except ImportError:
        logger.error("❌ PyMuPDF (fitz) not installed. Install with: pip install PyMuPDF")
        return {"error": "PyMuPDF not available"}
    
    except Exception as e:
        logger.error(f"❌ PDF extraction error: {e}")
        return {"error": str(e)}


def _parse_references(refs_text: str) -> List[str]:
    """
    Parse references section into individual citations
    Basic heuristic-based parsing
    """
    import re
    
    # Split by common patterns (numbered lists, line breaks)
    lines = refs_text.split("\n")
    references = []
    current_ref = ""
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check if this looks like a new reference (numbered or authored)
        if re.match(r"^\d+[\.\)]\s+", line) or re.match(r"^[A-Z][a-z]+,\s+[A-Z]", line):
            if current_ref:
                references.append(current_ref.strip())
            current_ref = line
        else:
            current_ref += " " + line
    
    if current_ref:
        references.append(current_ref.strip())
    
    return references[:50]  # Cap at 50 references


async def process_academic_pdf(pdf_url: str, temp_storage_bucket: Optional[str] = None) -> Dict[str, Any]:
    """
    Complete PDF processing pipeline for academic papers
    1. Download PDF
    2. Extract text, figures, metadata
    3. Upload figures to temp storage (optional)
    4. Return structured data
    """
    # Download
    pdf_bytes = await download_pdf(pdf_url)
    if not pdf_bytes:
        return {"error": "Failed to download PDF"}
    
    # Extract content
    content = extract_pdf_content(pdf_bytes)
    if "error" in content:
        return content
    
    # Optionally upload figures to S3 for vision analysis
    if temp_storage_bucket and content.get("figures"):
        from services.s3util import upload_figure
        for fig in content["figures"]:
            # Upload figure and get public URL
            try:
                fig_url = await upload_figure(
                    fig["bytes"], 
                    f"figure_{fig['number']}.{fig['format']}", 
                    bucket=temp_storage_bucket
                )
                fig["url"] = fig_url
                del fig["bytes"]  # Remove raw bytes after upload
            except Exception as e:
                logger.warning(f"⚠️ Failed to upload figure {fig['number']}: {e}")
    
    return content


# === Table Extraction (Advanced) ===
def extract_tables_from_pdf(pdf_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Extract tables from PDF using camelot or tabula
    More accurate than PyMuPDF for tabular data
    """
    try:
        import camelot
        
        # Save to temp file (camelot requires file path)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        
        # Extract tables
        tables = camelot.read_pdf(tmp_path, pages="all", flavor="lattice")
        
        result = []
        for idx, table in enumerate(tables, 1):
            result.append({
                "number": idx,
                "page": table.page,
                "accuracy": table.parsing_report.get("accuracy", 0),
                "data": table.df.to_dict(),  # pandas DataFrame
                "csv": table.df.to_csv()
            })
        
        # Cleanup
        os.unlink(tmp_path)
        
        logger.info(f"✅ Extracted {len(result)} tables from PDF")
        return result
    
    except ImportError:
        logger.warning("⚠️ camelot-py not installed. Tables will not be extracted.")
        return []
    
    except Exception as e:
        logger.error(f"❌ Table extraction error: {e}")
        return []


# === Enhanced Text Extraction with Structure ===
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
    
    # Common section headers
    patterns = {
        "abstract": [r"\nabstract\n", r"\nabstract:\n"],
        "introduction": [r"\nintroduction\n", r"\n1\.\s*introduction\n"],
        "methods": [r"\nmethods\n", r"\nmethodology\n", r"\nmaterials and methods\n"],
        "results": [r"\nresults\n", r"\nresults and discussion\n"],
        "discussion": [r"\ndiscussion\n"],
        "conclusion": [r"\nconclusion\n", r"\nconclusions\n"]
    }
    
    for section, pats in patterns.items():
        for pat in pats:
            match = re.search(pat, text_lower)
            if match:
                start = match.end()
                # Find next section or end
                next_headers = [p for s, ps in patterns.items() if s != section for p in ps]
                end = len(text)
                for nh in next_headers:
                    next_match = re.search(nh, text_lower[start:])
                    if next_match:
                        end = min(end, start + next_match.start())
                
                sections[section] = text[start:end].strip()[:2000]  # Cap at 2k chars
                break
    
    return sections

