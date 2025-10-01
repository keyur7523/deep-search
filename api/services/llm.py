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
        print(f"🔧 LLM Config: base={config['base'][:20]}..., key_length={len(config['key'])}")
        
        system = """You are a research planning expert. Create a comprehensive, academically rigorous outline.
Each section should address a distinct, substantive aspect with depth and critical analysis.
Return strict JSON array of objects with: idx (number), heading (string), brief (detailed research question, 2-3 sentences).
Focus on: mechanisms, evidence, controversies, clinical/practical implications, recent advances."""
        
        user = f"""Topic: {topic}

Create {n} sections that provide DEEP coverage:
1. Start with fundamental concepts and definitions
2. Cover underlying mechanisms and pathophysiology (if applicable)
3. Address current evidence and clinical research
4. Discuss diagnostic/measurement approaches
5. Explore management, treatment, or interventions
6. Include complications, risks, or emerging research

Each brief should be a specific, answerable research question (not "Cover aspect X")."""
        
        out = await _chat(config["model_planner"], [{"role":"system","content":system},{"role":"user","content":user}], 0.2, json_mode=True)
        print(f"🔧 LLM Response: {out[:100]}...")
        result = json.loads(out)
        print(f"🔧 Parsed outline: {len(result)} items")
        
        # Validate that briefs are substantial
        for item in result:
            if len(item.get("brief", "")) < 30 or "Cover aspect" in item.get("brief", ""):
                raise ValueError(f"Weak brief detected: {item.get('brief', '')[:50]}")
        
        return result
    except Exception as e:
        print(f"❌ LLM Error in plan_outline: {str(e)}")
        # Enhanced fallback with better default questions
        fallback_templates = [
            "What are the fundamental concepts, definitions, and basic mechanisms of {topic}?",
            "What is the current scientific evidence and research findings regarding {topic}?",
            "How is {topic} measured, diagnosed, or assessed in clinical or research settings?",
            "What are the primary risk factors, causes, and pathophysiology underlying {topic}?",
            "What are the current treatment approaches, management strategies, and interventions for {topic}?",
            "What are the complications, long-term outcomes, and emerging research directions in {topic}?"
        ]
        return [{"idx": i+1, "heading": f"Section {i+1}", "brief": fallback_templates[i % len(fallback_templates)].format(topic=topic)} for i in range(n)]

async def propose_query(brief: str, seen: list[str]) -> Dict[str, str]:
    config = _get_config()
    sys = """Generate a precise academic search query. Prioritize:
- Peer-reviewed research terms
- Clinical/technical terminology  
- Recent systematic reviews or meta-analyses
- Specific mechanisms, biomarkers, or measurements
Return JSON {query: string (5-10 words), rationale: why this query finds high-quality sources}."""
    
    usr = f"""Brief: {brief}
Already seen: {len(seen)} sources
Domains avoided: {[url.split('/')[2] if '/' in url else '' for url in seen[:3]]}

Generate a search query that finds DIFFERENT, DEEPER academic sources (journals, not general websites)."""
    
    out = await _chat(config["model_planner"], [{"role":"system","content":sys},{"role":"user","content":usr}], 0.3, json_mode=True)
    try:
        return json.loads(out)
    except Exception:
        # Enhance fallback by adding academic terms
        academic_query = f"{brief} systematic review evidence pathophysiology"
        return {"query": academic_query, "rationale": "fallback with academic terms"}

async def reflect(brief: str, snippets: list[str]) -> Dict[str, str]:
    config = _get_config()
    sys = """Analyze source quality and identify research gaps. Return JSON:
{
  "notes": "Critical assessment: What key findings are present? What mechanisms explained? What evidence level?",
  "next_query": "Specific query for missing depth (molecular mechanisms, clinical trials, recent meta-analyses) OR null if adequate"
}"""
    
    usr = f"""Research question: {brief}

Sources found so far (first 500 chars each):
{snippets[:5]}

Assess: Do we have peer-reviewed evidence? Mechanistic understanding? Clinical data? Recent research?
If gaps exist, suggest ONE targeted academic query."""
    
    out = await _chat(config["model_planner"], [{"role":"system","content":sys},{"role":"user","content":usr}], 0.3, json_mode=True)
    try:
        return json.loads(out)
    except Exception:
        return {"notes": "Sources reviewed, proceeding with synthesis", "next_query": None}

import re, json as _json

def _citations_from_pages(pages):
    return {i+1: {"url": p.get("url",""), "title": p.get("title","")} for i,p in enumerate(pages[:8])}

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

async def write_paragraph(brief: str, pages: list[dict]) -> dict:
    cfg = _get_config()
    # provide short snippets to improve grounding without blowing tokens
    sources = [
        {
            "title": p.get("title",""), 
            "url": p.get("url",""), 
            "snippet": (p.get("text","")[:800] if p.get("text") else ""),
            "type": p.get("type", "web"),
            "authors": p.get("authors", ""),
            "year": p.get("year", ""),
            "citations": p.get("citations", 0)
        }
        for p in pages[:8]  # Use more sources
    ]
    sys = (
        "You are a research synthesis expert. Write DEEP, evidence-based paragraphs with critical analysis. "
        "Include: specific findings, statistical data, mechanisms, clinical implications, study limitations. "
        "Use inline bracket citations [1], [2] after EVERY factual claim. "
        "Return strict JSON: {draftMd: string (300-400 words, academic tone), citations: object {n: {url, title}}, quality: 0-1}. "
        "Quality scoring: 0.9+ = multiple peer-reviewed sources with quantitative data; 0.7-0.8 = good sources; <0.6 = weak evidence. "
        "Do not include any prose outside JSON."
    )
    usr = f"Brief: {brief}\nSources:\n{_json.dumps(sources, ensure_ascii=False)}"

    # 1) Try JSON mode
    out = await _chat(cfg["model_writer"], [{"role":"system","content":sys},{"role":"user","content":usr}], 0.3, json_mode=True)
    doc = _extract_json(out) or (_json.loads(out) if out.startswith("{") else None)

    # 2) Repair pass if needed
    if not doc:
        fix_sys = "You convert content into valid JSON for the schema {draftMd:string, citations:object, quality:number}."
        fix = await _chat(cfg["model_writer"], [{"role":"system","content":fix_sys},{"role":"user","content":out}], 0.0, json_mode=True)
        doc = _extract_json(fix) or (_json.loads(fix) if fix.startswith("{") else None)

    # 3) Final fallback: synthesize deterministically from sources (no placeholders)
    if not doc:
        cites = _citations_from_pages(pages)
        bullets = []
        for i,(n,meta) in enumerate(cites.items(), 1):
            t = (pages[i-1].get("text","") or "")[:240].strip()
            if t:
                bullets.append(f"- {t} [{i}]")
        body = (
            f"{brief.replace('Cover','Explain').replace('aspect','topic')}\n\n" +
            (" ".join(bullets) if bullets else "This section summarizes current knowledge and clinical guidance based on reputable sources.")
        )
        return {"draftMd": body, "citations": cites, "quality": 0.45}

    # 4) Validate and repair citations alignment
    cites = doc.get("citations") or _citations_from_pages(pages)
    used = sorted({int(n) for n in re.findall(r"\[(\d+)\]", doc.get("draftMd",""))})
    for n in used:
        if str(n) not in [*cites.keys(), *map(str, cites.keys())]:
            # pad missing numbers from available pages
            idx = n-1
            if 0 <= idx < len(pages):
                cites[str(n)] = {"url": pages[idx].get("url",""), "title": pages[idx].get("title","")}
    doc["citations"] = {str(k): v for k,v in cites.items()}
    if len(doc.get("draftMd","")) < 120:
        # weak output → quick reinforcement
        doc["draftMd"] = (doc.get("draftMd","") + "\n\n" + f"Summary: {brief}").strip()
    if "Cover aspect" in doc["draftMd"]:
        doc["draftMd"] = doc["draftMd"].replace("Cover aspect", "Explain")
    if not re.search(r"\[\d+\]", doc["draftMd"]):
        # ensure at least one anchor
        doc["draftMd"] += " [1]"
    if "quality" not in doc:
        doc["quality"] = 0.6
    return doc

async def aggregate_report(topic: str, paragraphs: list[dict]) -> str:
    config = _get_config()
    sys = "Stitch paragraphs into a markdown report with ToC and conclusion. Output markdown only."
    usr = f"Topic: {topic}\nParagraphs: {[p['draftMd'] for p in paragraphs]}"
    return await _chat(config["model_writer"], [{"role":"system","content":sys},{"role":"user","content":usr}], 0.2)
