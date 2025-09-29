import os, httpx, json
from typing import Any, Dict, List

BASE = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
KEY = os.getenv("LLM_API_KEY", "")
MODEL_PLANNER = os.getenv("LLM_MODEL_PLANNER", "gpt-4o-mini")
MODEL_WRITER = os.getenv("LLM_MODEL_WRITER", "gpt-4o-mini")

HEADERS = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

async def _chat(model: str, messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
    async with httpx.AsyncClient(timeout=60) as cx:
        r = await cx.post(f"{BASE}/chat/completions", headers=HEADERS, json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
        })
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]

async def plan_outline(topic: str, n: int) -> List[Dict[str, str]]:
    system = "Produce <=N paragraph outline with brief. JSON list of {idx, heading, brief}."
    user = f"Topic: {topic}\nN={n}"
    out = await _chat(MODEL_PLANNER, [{"role":"system","content":system},{"role":"user","content":user}], 0.1)
    try:
        return json.loads(out)
    except Exception:
        # fallback: naive outline
        return [{"idx": i+1, "heading": f"Section {i+1}", "brief": f"Cover aspect {i+1} of {topic}"} for i in range(n)]

async def propose_query(brief: str, seen: list[str]) -> Dict[str, str]:
    sys = "Given brief and seen URLs, output JSON {query, rationale}."
    usr = f"Brief: {brief}\nSeen: {seen[:5]}"
    out = await _chat(MODEL_PLANNER, [{"role":"system","content":sys},{"role":"user","content":usr}], 0.2)
    try:
        return json.loads(out)
    except Exception:
        return {"query": brief, "rationale": "fallback"}

async def reflect(brief: str, snippets: list[str]) -> Dict[str, str]:
    sys = "Find missing angles. Return JSON {notes, next_query|null}."
    usr = f"Brief: {brief}\nSnippets: {snippets[:5]}"
    out = await _chat(MODEL_PLANNER, [{"role":"system","content":sys},{"role":"user","content":usr}], 0.2)
    try:
        return json.loads(out)
    except Exception:
        return {"notes": "fallback", "next_query": None}

async def write_paragraph(brief: str, pages: list[dict]) -> Dict[str, any]:
    sys = "Write 150-220 words with inline [n] citations. Return JSON {draftMd, citations, quality} where citations is a map of n->{url,title}."
    usr = f"Brief: {brief}\nSources: {[{'title':p.get('title'), 'url':p.get('url')} for p in pages]}"
    out = await _chat(MODEL_WRITER, [{"role":"system","content":sys},{"role":"user","content":usr}], 0.3)
    import json
    try:
        return json.loads(out)
    except Exception:
        cites = {i+1: {"url": p.get("url",""), "title": p.get("title","")} for i,p in enumerate(pages[:5])}
        return {"draftMd": f"{brief}\n\n" + "\n".join([f"[{i}]" for i in cites.keys()]), "citations": cites, "quality": 0.5}

async def aggregate_report(topic: str, paragraphs: list[dict]) -> str:
    sys = "Stitch paragraphs into a markdown report with ToC and conclusion. Output markdown only."
    usr = f"Topic: {topic}\nParagraphs: {[p['draftMd'] for p in paragraphs]}"
    return await _chat(MODEL_WRITER, [{"role":"system","content":sys},{"role":"user","content":usr}], 0.2)
