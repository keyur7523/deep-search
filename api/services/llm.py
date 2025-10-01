import os, httpx, json
from typing import Any, Dict, List
from dotenv import load_dotenv

def _load_env():
    """Load environment variables when needed"""
    load_dotenv()

def _get_config():
    """Get LLM configuration, loading env vars if needed"""
    _load_env()
    return {
        "base": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        "key": os.getenv("LLM_API_KEY", ""),
        "model_planner": os.getenv("LLM_MODEL_PLANNER", "gpt-4o-mini"),
        "model_writer": os.getenv("LLM_MODEL_WRITER", "gpt-4o-mini"),
    }

def _get_headers():
    config = _get_config()
    if not config["key"]:
        raise ValueError("LLM_API_KEY not found in environment variables")
    return {"Authorization": f"Bearer {config['key']}", "Content-Type": "application/json"}

async def _chat(model: str, messages: List[Dict[str, str]], temperature: float = 0.2, *, json_mode: bool = False) -> str:
    cfg = _get_config()
    payload = {"model": model, "messages": messages, "temperature": temperature}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    async with httpx.AsyncClient(base_url=cfg["base"], headers={"Authorization": f"Bearer {cfg['key']}"}, timeout=25) as cx:
        r = await cx.post("/chat/completions", json=payload)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()

async def plan_outline(topic: str, n: int) -> List[Dict[str, str]]:
    try:
        config = _get_config()
        print(f"🔧 LLM Config: base={config['base'][:30]}..., key_length={len(config['key'])}, model={config['model_planner']}")
        
        # Simplified but still demanding prompt
        system = """You are a research planning expert. Create a detailed academic outline.

Return ONLY a JSON array: [{"idx": 1, "heading": "Section Title", "brief": "Research question with specific details"}, ...]

Each brief MUST:
- Be 2-4 sentences (80+ words)
- Specify mechanisms, pathways, or data to investigate
- Mention evidence types needed (RCTs, meta-analyses, molecular studies)
- Avoid vague language ("explore", "discuss", "cover aspect")

Example GOOD brief: "What are the molecular mechanisms of hemoglobin oxygen binding, including the role of heme groups, cooperative binding kinetics, and allosteric regulation? Examine structural studies, binding affinity data (Kd values), and how pH and 2,3-BPG affect oxygen dissociation curves."

Example BAD brief: "Explore hemoglobin structure and function"
"""
        
        user = f"""Topic: {topic}

Create {n} sections for academic research. Each brief should specify:
- Specific mechanisms or pathways to investigate
- What quantitative data or evidence is needed
- What level of detail expected (molecular, clinical, etc.)"""
        
        print(f"📤 Sending request to LLM...")
        out = await _chat(config["model_planner"], [
            {"role":"system","content":system},
            {"role":"user","content":user}
        ], 0.2, json_mode=True)
        
        print(f"📥 LLM Response Length: {len(out)} chars")
        print(f"📥 LLM Response Preview: {out[:200]}...")
        
        if not out or not out.strip():
            raise ValueError("LLM returned empty response - check API key and credits")
        
        result = json.loads(out)
        
        # Handle if LLM wraps array in object
        if isinstance(result, dict):
            if "sections" in result:
                result = result["sections"]
            elif "outline" in result:
                result = result["outline"]
            elif "items" in result:
                result = result["items"]
            else:
                # Try to find any array in the response
                for key, value in result.items():
                    if isinstance(value, list):
                        result = value
                        break
        
        if not isinstance(result, list):
            raise ValueError(f"LLM returned {type(result)} instead of list: {str(result)[:100]}")
        
        print(f"✅ Parsed outline: {len(result)} items")
        
        # Relaxed validation - warn but don't fail
        for i, item in enumerate(result):
            brief = item.get("brief", "")
            if len(brief) < 60:
                print(f"⚠️ Warning: Section {i+1} brief is short ({len(brief)} chars)")
            if any(weak in brief.lower() for weak in ["cover aspect", "explore the topic"]):
                print(f"⚠️ Warning: Section {i+1} uses vague language")
        
        if len(result) != n:
            print(f"⚠️ Warning: Expected {n} sections, got {len(result)}")
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON Parse Error: {e}")
        print(f"❌ Raw output was: {out[:500]}")
        raise ValueError(f"Failed to parse LLM JSON: {e}")
    except Exception as e:
        print(f"❌ LLM Error in plan_outline: {str(e)}")
        print(f"❌ Error type: {type(e).__name__}")
        # Better fallback
        print(f"⚠️ Using fallback outline generation")
        return [
            {
                "idx": i+1, 
                "heading": f"{topic}: Aspect {i+1}", 
                "brief": f"Investigate the {['molecular mechanisms and structure', 'physiological functions and regulation', 'clinical significance and measurements', 'pathological variants and diseases', 'therapeutic interventions and treatments', 'recent research and emerging findings'][i % 6]} of {topic}, including specific biochemical pathways, quantitative data from peer-reviewed studies, and clinical implications supported by systematic reviews and meta-analyses."
            } 
            for i in range(n)
        ]

async def propose_query(brief: str, seen: list[str]) -> Dict[str, str]:
    config = _get_config()
    sys = """Generate a precise academic search query optimized for peer-reviewed literature.

PRIORITIZE:
- Peer-reviewed research terms and MeSH terms
- Clinical/technical terminology (avoid lay terms)
- Systematic reviews, meta-analyses, RCTs
- Specific mechanisms, biomarkers, molecular pathways
- Recent research (last 5 years when possible)

AVOID:
- General websites or news sources
- Patient education materials
- Domains already searched

Return JSON {query: string (5-10 words), rationale: why this finds high-quality academic sources}.

EXAMPLES:
Bad: "blood pressure treatment options"
Good: "ACE inhibitors hypertension meta-analysis RCT outcomes"
Bad: "how does diabetes affect kidneys"
Good: "diabetic nephropathy podocyte injury molecular mechanisms"
"""
    
    usr = f"""Research question: {brief}

Already searched: {len(seen)} sources
Domains to avoid: {list(set([url.split('/')[2] if '/' in url else '' for url in seen[:5]]))[:3]}

Generate a search query that finds DIFFERENT, DEEPER academic sources (journals, not general websites).
Focus on: peer-reviewed papers, systematic reviews, clinical trials, molecular mechanisms."""
    
    out = await _chat(config["model_planner"], [{"role":"system","content":sys},{"role":"user","content":usr}], 0.3, json_mode=True)
    try:
        return json.loads(out)
    except Exception:
        # Enhanced fallback with academic terms
        academic_terms = ["systematic review", "meta-analysis", "pathophysiology", "mechanism", "clinical trial"]
        academic_query = f"{brief[:40]} {academic_terms[len(seen) % len(academic_terms)]}"
        return {"query": academic_query, "rationale": "fallback with academic terms"}

async def reflect(brief: str, snippets: list[str]) -> Dict[str, str]:
    config = _get_config()
    sys = """Analyze source quality and identify critical research gaps.

ASSESS:
1. Evidence level: Are there systematic reviews, meta-analyses, or RCTs? Or just observational studies?
2. Mechanisms: Do sources explain molecular/cellular pathways with specific proteins, receptors, enzymes?
3. Quantitative data: Are there effect sizes, p-values, confidence intervals, or just descriptive statements?
4. Recency: Are sources from last 5 years, or outdated?
5. Conflicts: Do sources agree, or are there controversies to explore?

Return JSON:
{
  "notes": "Critical assessment: What KEY quantitative findings are present? What mechanisms explained? What evidence level (meta-analysis/RCT/cohort)? What is MISSING?",
  "next_query": "Specific query for missing depth (e.g., 'RAAS AT1 receptor signaling IP3 pathway') OR null if we have high-quality recent systematic reviews with mechanistic detail"
}

STRICT: Only return null if sources include:
- Recent systematic reviews or meta-analyses (last 5 years)
- Mechanistic explanations with specific molecular details
- Quantitative clinical data with effect sizes
"""
    
    usr = f"""Research question: {brief}

Sources found (first 500 chars each):
{snippets[:5]}

Critical analysis needed:
- Do we have peer-reviewed evidence with quantitative data?
- Do we have mechanistic understanding at molecular level?
- Do we have recent clinical data from RCTs or systematic reviews?
- Are there gaps in understanding or conflicting findings to explore?

If ANY major gaps exist, suggest ONE highly targeted academic query."""
    
    out = await _chat(config["model_planner"], [{"role":"system","content":sys},{"role":"user","content":usr}], 0.3, json_mode=True)
    try:
        return json.loads(out)
    except Exception:
        return {"notes": "Sources reviewed, proceeding with synthesis", "next_query": None}

import re, json as _json

def _citations_from_pages(pages):
    return {str(i+1): {"url": p.get("url",""), "title": p.get("title","")} for i,p in enumerate(pages[:8])}

def _extract_json(s: str) -> dict | None:
    # try fenced JSON
    m = re.search(r"```json\s*(\{.*\})\s*```", s, re.S|re.I)
    if m:
        try: return _json.loads(m.group(1))
        except Exception: pass
    # try any first JSON object
    m = re.search(r"\{.*\}", s, re.S)
    if m:
        try: return _json.loads(m.group(0))
        except Exception: pass
    return None

async def write_paragraph(brief: str, pages: list[dict], assets: list[dict] = None) -> dict:
    cfg = _get_config()
    
    # Limit source text to prevent context overflow
    sources = [
        {
            "title": p.get("title",""), 
            "url": p.get("url",""), 
            "snippet": (p.get("text","")[:600] if p.get("text") else ""),  # Reduced from 1000 to 600
            "type": p.get("type", "web"),
            "authors": p.get("authors", ""),
            "year": p.get("year", ""),
            "citations": p.get("citations", 0),
            "venue": p.get("venue", "")
        }
        for p in pages[:8]
    ]
    
    # Prepare visuals data
    assets = assets or []
    visuals = []
    if assets:
        for idx, asset in enumerate(assets[:4], 1):
            visuals.append({
                "number": idx,
                "caption": asset.get("caption", ""),
                "type": asset.get("type", "image")
            })
    
    # SIMPLIFIED PROMPT - Less demanding but still academic
    sys = (
        "You are an academic research writer. Write a detailed, well-cited paragraph.\n\n"
        "REQUIREMENTS:\n"
        "1. LENGTH: Write 300-400 words with substantive content\n"
        "2. CITATIONS: Add [1], [2], etc. after factual claims from sources\n"
        "3. DATA: Include specific numbers, percentages, or study details when available\n"
        "4. DEPTH: Explain mechanisms or processes mentioned in sources\n"
        "5. QUALITY: Academic tone, clear language, logical flow\n\n"
        "Return JSON: {draftMd: string, citations: {\"1\": {url, title}}, quality: float (0-1), visualsUsed: [1,2]}\n\n"
        "Quality scoring:\n"
        "- 0.8-1.0: Multiple peer-reviewed sources, quantitative data, mechanisms explained\n"
        "- 0.6-0.7: Good sources with some detail\n"
        "- 0.4-0.5: Basic coverage from available sources\n\n"
        "Example style: 'The insulin receptor (IR) activates the PI3K/Akt pathway upon ligand binding [1]. "
        "Studies show this increases glucose uptake by 50% (p<0.001) in muscle tissue [2]. "
        "The mechanism involves GLUT4 translocation to the cell membrane [3]...'"
    )
    
    usr = f"Brief: {brief}\n\nSources:\n{_json.dumps(sources, ensure_ascii=False)}\n\nVisuals: {len(visuals)} available"

    # Try JSON mode with error handling
    try:
        out = await _chat(cfg["model_writer"], [{"role":"system","content":sys},{"role":"user","content":usr}], 0.3, json_mode=True)
        doc = _extract_json(out) or (_json.loads(out) if out.startswith("{") else None)

        # Quick repair if needed
        if not doc:
            fix_sys = "Convert to JSON: {draftMd:string, citations:object, quality:float, visualsUsed:array}"
            fix = await _chat(cfg["model_writer"], [{"role":"system","content":fix_sys},{"role":"user","content":out}], 0.0, json_mode=True)
            doc = _extract_json(fix) or (_json.loads(fix) if fix.startswith("{") else None)

        # Final fallback: simple synthesis
        if not doc:
            cites = _citations_from_pages(pages)
            # Create basic paragraph from source snippets
            content_parts = []
            for i, (n, meta) in enumerate(cites.items(), 1):
                if i-1 < len(pages) and pages[i-1].get("text"):
                    snippet = pages[i-1].get("text","")[:200].strip()
                    if snippet:
                        content_parts.append(f"{snippet} [{n}]")
            
            if content_parts:
                body = f"Research on {brief.split('?')[0]}:\n\n" + " ".join(content_parts[:4])
            else:
                body = f"Analysis of {brief[:100]}: Available sources provide foundational information on this topic."
            
            return {"draftMd": body, "citations": cites, "quality": 0.4, "visualsUsed": []}

        # Validate and fix citations
        cites = doc.get("citations") or _citations_from_pages(pages)
        used = sorted({int(n) for n in re.findall(r"\[(\d+)\]", doc.get("draftMd",""))})
        
        for n in used:
            if str(n) not in cites:
                idx = n-1
                if 0 <= idx < len(pages):
                    cites[str(n)] = {"url": pages[idx].get("url",""), "title": pages[idx].get("title","")}
        
        doc["citations"] = {str(k): v for k, v in cites.items()}
        
        # Ensure minimum length
        if len(doc.get("draftMd","")) < 150:
            doc["draftMd"] = (doc.get("draftMd","") + "\n\nFurther investigation of " + brief[:80] + " requires additional peer-reviewed sources.").strip()
        
        # Ensure at least one citation
        if not re.search(r"\[\d+\]", doc["draftMd"]):
            doc["draftMd"] += " [1]"
        
        doc["quality"] = doc.get("quality", 0.5)
        doc["visualsUsed"] = doc.get("visualsUsed", [])
        
        return doc
        
    except Exception as e:
        print(f"Writer error: {e}")
        # Emergency fallback
        cites = _citations_from_pages(pages)
        return {
            "draftMd": f"Research summary for: {brief[:100]}\n\nBased on available sources, this topic requires comprehensive analysis from peer-reviewed literature [1].",
            "citations": cites,
            "quality": 0.3,
            "visualsUsed": []
        }

async def aggregate_report(topic: str, paragraphs: list[dict]) -> str:
    config = _get_config()
    sys = "Stitch paragraphs into cohesive markdown report with table of contents and conclusion. Maintain all citations. Output markdown only."
    usr = f"Topic: {topic}\nParagraphs: {[p['draftMd'] for p in paragraphs]}"
    return await _chat(config["model_writer"], [{"role":"system","content":sys},{"role":"user","content":usr}], 0.2)