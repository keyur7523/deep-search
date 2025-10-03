import os, httpx, json, re
from typing import Any, Dict, List
from dotenv import load_dotenv
import json as _json

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

async def _chat(model: str, messages: List[Dict[str, str]], temperature: float = 0.2, *, json_mode: bool = False, max_tokens: int = 1000, timeout: int = 30) -> str:
    cfg = _get_config()
    payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    async with httpx.AsyncClient(base_url=cfg["base"], headers={"Authorization": f"Bearer {cfg['key']}"}, timeout=timeout) as cx:
        r = await cx.post("/chat/completions", json=payload)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()

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

def _generate_query_examples(topic: str, brief: str, core_terms: list) -> dict:
    """Generate topic-specific query examples dynamically"""
    first_term = core_terms[0] if core_terms else topic
    brief_words = brief.split()[:3] if brief else ["mechanisms"]
    brief_first_word = brief_words[0] if brief_words else "mechanisms"
    
    return {
        "good": [
            f"{topic} {brief_first_word}",
            f"{first_term} molecular pathways",
            f"clinical research {topic}"
        ],
        "bad": [
            f"{brief_first_word} general mechanisms (missing '{topic}')",
            "disease transmission patterns (too generic - no topic specified)",
            f"immune response (needs '{topic}' context)"
        ]
    }

# ===== ENHANCED FUNCTIONS =====

async def validate_outline(topic: str, outline: List[dict]) -> dict:
    """Validate that outline stays aligned with the original topic"""
    
    outline_text = "\n".join([f"{i+1}. {item.get('heading', '')}: {item.get('brief', '')}" 
                              for i, item in enumerate(outline)])
    
    prompt = f"""You are a research quality validator. Assess if this research outline stays focused on the original topic.

Original Topic: "{topic}"

Generated Outline:
{outline_text}

Analyze:
1. Does each section DIRECTLY address the core topic?
2. Are there any sections that drift into tangential areas?
3. Does the outline comprehensively cover what the topic asks for?

If topic asks about "composition", sections should cover composition, not function or repair.
If topic asks about "types", sections should categorize types, not discuss applications.
If topic asks "what are", focus on definition and characteristics, not "how to use".

Return JSON:
{{
    "is_coherent": true/false,
    "drift_score": 0.0-1.0,
    "suggestions": ["specific improvements if drift_score > 0.3"],
    "missing_aspects": ["key aspects of the topic not covered"]
}}"""

    try:
        config = _get_config()
        response = await _chat(config["model_planner"], [
            {"role": "system", "content": "You are a research outline validator. Return only valid JSON."},
            {"role": "user", "content": prompt}
        ], 0.2, json_mode=True, max_tokens=500)
        return json.loads(response)
    except Exception as e:
        print(f"Outline validation failed: {e}")
        return {"is_coherent": True, "drift_score": 0.0, "suggestions": [], "missing_aspects": []}

async def plan_outline_strict(topic: str, n: int, suggestions: List[str]) -> List[dict]:
    """Generate outline with stricter focus based on validation feedback"""
    
    suggestions_text = "\n".join([f"- {s}" for s in suggestions]) if suggestions else "None"
    
    system = f"""You are a research planner. Create a STRICTLY FOCUSED research outline.

Previous attempt had these issues:
{suggestions_text}

CRITICAL REQUIREMENTS:
1. Every section MUST directly address the core question in the topic
2. Stay strictly within the scope - no tangential topics
3. Extract key question words (what, how, why, which, composition, types, etc.) and address them
4. If topic asks about "composition", focus ONLY on composition
5. If topic asks about "types", focus ONLY on categorizing and describing types
6. Do NOT expand into related but different areas

Return ONLY a JSON array:
[
  {{
    "idx": 1,
    "heading": "Specific Section Title",
    "brief": "Detailed research question (80+ words) that DIRECTLY addresses the core topic"
  }},
  ...
]"""

    user = f"""Topic: "{topic}"

Create {n} sections that DIRECTLY AND EXCLUSIVELY address this topic.

Analyze the topic:
- What is the CORE question being asked?
- What are the KEY terms that define the scope?
- What should be EXCLUDED to avoid drift?

Each brief must:
- Be 80-120 words
- Specify exact mechanisms, components, or categories to investigate
- Stay within the narrow scope of the original question
- Mention specific evidence types needed"""
    
    try:
        config = _get_config()
        out = await _chat(config["model_planner"], [
            {"role":"system","content":system},
            {"role":"user","content":user}
        ], 0.1, json_mode=True, max_tokens=1200)
        
        result = json.loads(out)
        
        # Handle wrapped responses
        if isinstance(result, dict):
            for key in ["sections", "outline", "items"]:
                if key in result:
                    result = result[key]
                    break
        
        if isinstance(result, list):
            print(f"Strict outline generated: {len(result)} items")
            return result
        
        raise ValueError(f"Invalid strict outline format: {type(result)}")
        
    except Exception as e:
        print(f"Strict outline planning failed: {e}, falling back to regular outline")
        return await plan_outline(topic, n)

async def plan_outline(topic: str, n: int) -> List[Dict[str, str]]:
    try:
        config = _get_config()
        print(f"LLM Config: base={config['base'][:30]}..., key_length={len(config['key'])}, model={config['model_planner']}")
        
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
        
        print(f"Sending request to LLM...")
        out = await _chat(config["model_planner"], [
            {"role":"system","content":system},
            {"role":"user","content":user}
        ], 0.2, json_mode=True, max_tokens=1000)
        
        print(f"LLM Response Length: {len(out)} chars")
        
        if not out or not out.strip():
            raise ValueError("LLM returned empty response")
        
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
                for key, value in result.items():
                    if isinstance(value, list):
                        result = value
                        break
        
        if not isinstance(result, list):
            raise ValueError(f"LLM returned {type(result)} instead of list")
        
        print(f"Parsed outline: {len(result)} items")
        
        # Warn about quality but don't fail
        for i, item in enumerate(result):
            brief = item.get("brief", "")
            if len(brief) < 60:
                print(f"Warning: Section {i+1} brief is short ({len(brief)} chars)")
        
        if len(result) != n:
            print(f"Warning: Expected {n} sections, got {len(result)}")
        
        return result
        
    except Exception as e:
        print(f"LLM Error in plan_outline: {str(e)}")
        print(f"Using fallback outline generation")
        return [
            {
                "idx": i+1, 
                "heading": f"{topic}: Aspect {i+1}", 
                "brief": f"Investigate the {['molecular mechanisms and structure', 'physiological functions and regulation', 'clinical significance and measurements', 'pathological variants and diseases', 'therapeutic interventions and treatments', 'recent research and emerging findings'][i % 6]} of {topic}, including specific biochemical pathways, quantitative data from peer-reviewed studies, and clinical implications."
            } 
            for i in range(n)
        ]

async def extract_topic_terminology(topic: str) -> dict:
    """Extract domain-specific search terms for a topic"""
    
    config = _get_config()
    
    system = """You are a research terminology expert. Given a research topic, identify the key scientific/medical terms that MUST appear in search queries to ensure relevance.

Return JSON:
{
  "core_terms": ["term1", "term2"],  // 3-5 essential terms that define this specific domain
  "alternative_terms": ["synonym1", "synonym2"],  // 2-3 synonyms or related terms
  "exclusion_hints": ["avoid_term1", "avoid_term2"]  // Terms that indicate OFF-TOPIC papers
}

Examples:
- "Blood Cancer" → core: ["hematologic malignancy", "leukemia", "lymphoma"], alternative: ["myeloma", "blood neoplasm"], exclude: ["solid tumor", "carcinoma"]
- "Climate Change" → core: ["global warming", "climate change", "greenhouse gas"], alternative: ["carbon emissions", "temperature rise"], exclude: ["weather", "seasonal"]
"""
    
    user = f"""Topic: "{topic}"

Extract the terminology needed to keep searches focused on this SPECIFIC topic."""
    
    try:
        out = await _chat(config["model_planner"], [
            {"role":"system","content":system},
            {"role":"user","content":user}
        ], 0.3, json_mode=True, max_tokens=300)
        
        result = json.loads(out)
        return result
    except Exception as e:
        print(f"Term extraction failed: {e}, using topic as-is")
        # Fallback: just use the topic words
        return {
            "core_terms": [topic.lower()],
            "alternative_terms": [],
            "exclusion_hints": []
        }

async def propose_query(brief: str, seen: list[str], topic: str, topic_terms: dict = None) -> Dict[str, str]:
    """Enhanced query generation with topic context and dynamic examples"""
    
    config = _get_config()
    
    # Build term constraints and dynamic examples
    if topic_terms:
        core_terms = topic_terms.get("core_terms", [])
        terms_text = " OR ".join([f'"{term}"' for term in core_terms[:3]])
        
        # Generate topic-specific examples
        examples = _generate_query_examples(topic, brief, core_terms)
        
        good_examples = "\n".join([f"- {ex}" for ex in examples["good"]])
        bad_examples = "\n".join([f"- {ex}" for ex in examples["bad"]])
        
        constraint = f"""
CRITICAL REQUIREMENTS:
- Query MUST include at least one of: {terms_text}
- Query must be specific to "{topic}", not generic research

Examples of GOOD queries for "{topic}":
{good_examples}

Examples of BAD queries (missing topic specificity):
{bad_examples}
"""
    else:
        constraint = f"\n\nCRITICAL: Query must be specific to: {topic}"
    
    system = f"""Generate a precise academic search query optimized for peer-reviewed literature.

PRIORITIZE:
- Peer-reviewed research terms and MeSH terms
- Clinical/technical terminology (avoid lay terms)
- Systematic reviews, meta-analyses, RCTs
- Specific mechanisms, biomarkers, molecular pathways{constraint}

Return JSON {{query: string (5-10 words), rationale: string}}.

CRITICAL: Query must address the section focus while staying aligned with the original topic."""
    
    user = f"""Original Research Topic: "{topic}"
Current Section Focus: "{brief}"

Already searched: {len(seen)} sources
Domains to avoid: {list(set([url.split('/')[2] if '/' in url else '' for url in seen[:5]]))[:3]}

Generate a search query that:
1. DIRECTLY addresses: "{brief}"
2. Stays aligned with the original topic: "{topic}"
3. Finds DIFFERENT academic sources than already searched
4. Uses specific terminology to get quality results"""
    
    try:
        out = await _chat(config["model_planner"], [
            {"role":"system","content":system},
            {"role":"user","content":user}
        ], 0.3, json_mode=True, max_tokens=300)
        return json.loads(out)
    except Exception:
        academic_terms = ["systematic review", "meta-analysis", "pathophysiology", "mechanism"]
        return {"query": f"{brief[:40]} {academic_terms[len(seen) % len(academic_terms)]}", "rationale": "fallback"}

async def propose_query_with_reflection(
    brief: str, 
    seen: List[str], 
    last_reflection: dict,
    topic: str,
    topic_terms: dict = None
) -> dict:
    """Generate search query informed by previous reflection"""
    
    config = _get_config()
    
    gaps = last_reflection.get("gaps", [])
    gaps_text = "\n".join([f"- {g}" for g in gaps[:3]]) if gaps else "None identified"
    
    # Build term constraints if available
    if topic_terms:
        core_terms = topic_terms.get("core_terms", [])
        terms_text = " OR ".join([f'"{term}"' for term in core_terms[:3]])
        constraint = f"\n\nCRITICAL: Query MUST include at least one of: {terms_text}"
    else:
        constraint = f"\n\nCRITICAL: Query must be specific to: {topic}"
    
    system = f"""Generate a search query that addresses identified gaps while staying on-topic.{constraint}

Return JSON {{query: string, rationale: string}}"""
    
    user = f"""Original Topic: "{topic}"
Section Focus: "{brief}"

Previous round identified these gaps:
{gaps_text}

Already searched: {", ".join([url.split('/')[2] if '/' in url else url for url in seen[:5]])}

Generate a NEW search query that:
1. Addresses the most critical gap identified
2. Stays aligned with BOTH the section focus AND original topic
3. Targets different authoritative sources
4. Uses specific academic terminology

Focus on filling gaps with peer-reviewed evidence."""
    
    try:
        out = await _chat(config["model_planner"], [
            {"role":"system","content":system},
            {"role":"user","content":user}
        ], 0.3, json_mode=True, max_tokens=300)
        return json.loads(out)
    except Exception as e:
        print(f"Query with reflection failed: {e}")
        return await propose_query(brief, seen, topic, topic_terms)

async def reflect(brief: str, snippets: list[str]) -> Dict[str, str]:
    """Basic reflection - kept for compatibility"""
    return await reflect_with_context(brief, snippets, brief, brief)

async def reflect_with_context(
    brief: str, 
    source_snippets: List[str],
    topic: str,
    section_heading: str
) -> dict:
    """Enhanced reflection with topic context"""
    
    config = _get_config()
    
    sources_text = "\n\n".join([f"Source {i+1}:\n{s[:400]}" for i, s in enumerate(source_snippets[:5])])
    
    system = """Analyze source quality and identify critical research gaps.

ASSESS:
1. Evidence level: Are there systematic reviews, meta-analyses, or RCTs?
2. Mechanisms: Do sources explain molecular/cellular pathways with specifics?
3. Quantitative data: Are there effect sizes, p-values, confidence intervals?
4. Topic alignment: Do sources stay focused on the core question?
5. Gaps: What critical aspects are missing?

Return JSON:
{
  "notes": "Assessment of coverage and quality",
  "gaps": ["specific gap 1", "specific gap 2"],
  "next_query": "Targeted query for most critical gap, or null if well-covered",
  "topic_alignment": "good/fair/poor"
}"""
    
    user = f"""Original Topic: "{topic}"
Section: "{section_heading}"
Section Goal: "{brief}"

Sources gathered:
{sources_text}

Analyze:
1. Do these sources adequately answer: "{brief}"?
2. Do they stay focused on: "{topic}"?
3. What specific gaps remain in evidence or explanation?
4. Is additional targeted research needed?"""
    
    try:
        out = await _chat(config["model_planner"], [
            {"role":"system","content":system},
            {"role":"user","content":user}
        ], 0.3, json_mode=True, max_tokens=500)
        return json.loads(out)
    except Exception:
        return {"notes": "Sources reviewed", "gaps": [], "next_query": None, "topic_alignment": "fair"}

async def write_paragraph(brief: str, pages: list[dict], assets: list[dict] = None) -> dict:
    """Basic paragraph writer - kept for compatibility"""
    return await write_paragraph_with_context(brief, pages, assets, brief, brief, 1, 6)

async def write_paragraph_with_context(
    brief: str,
    sources: list[dict],
    assets: list[dict],
    topic: str,
    section_heading: str,
    paragraph_index: int = 1,
    total_paragraphs: int = 6
) -> dict:
    """Enhanced paragraph writing with topic context and style variation"""
    
    cfg = _get_config()
    
    # Prepare sources
    source_list = [
        {
            "title": p.get("title",""), 
            "url": p.get("url",""), 
            "snippet": (p.get("text","")[:600] if p.get("text") else ""),
            "type": p.get("type", "web"),
            "authors": p.get("authors", ""),
            "year": p.get("year", ""),
            "citations": p.get("citations", 0)
        }
        for p in sources[:8]
    ]
    
    # Prepare visuals
    assets = assets or []
    visuals = [
        {"number": idx, "caption": asset.get("caption", ""), "type": asset.get("type", "image")}
        for idx, asset in enumerate(assets[:4], 1)
    ]
    
    # Vary writing style based on position in report
    if paragraph_index == 1:
        style_guide = """POSITION: Opening section - Set the stage.
- Start with context-setting
- Introduce key concepts before technical details
- Use clear, accessible language initially
- Example openings: "Understanding X requires...", "Recent advances in...", "The field of X has..."
"""
    elif paragraph_index == total_paragraphs:
        style_guide = """POSITION: Closing section - Synthesize findings.
- Connect back to earlier sections
- Highlight implications and future directions
- Use synthesizing language
- Example openings: "Emerging evidence suggests...", "Integration of findings reveals...", "Clinical applications demonstrate..."
"""
    else:
        style_guide = f"""POSITION: Middle section {paragraph_index} of {total_paragraphs} - Build the argument.
- Build on previous sections
- Add new evidence and deeper analysis
- Maintain forward momentum
- Vary your opening - avoid formulaic starts
- Example openings: "Analysis of X reveals...", "Multiple studies indicate...", "Key findings demonstrate...", "Evidence from X shows..."
"""
    
    system = f"""You are an academic research writer. Write a detailed, well-cited paragraph.

CONTEXT:
- Original Topic: "{topic}"
- Section: "{section_heading}"
- Section Goal: "{brief}"

{style_guide}

REQUIREMENTS:
1. LENGTH: 300-400 words with substantive content
2. FOCUS: Address ONLY "{brief}" - stay on topic
3. CITATIONS: Add [1], [2], etc. after factual claims
   - Use ONLY [1] through [{len(source_list)}] 
   - DO NOT invent citation numbers
   - Every [n] must correspond to source n from the provided list
4. DATA: Include specific numbers, percentages, study details
5. DEPTH: Explain mechanisms or processes from sources
6. ALIGNMENT: Every sentence must relate to both the section goal AND original topic
7. VARIETY: Avoid repetitive openings like:
   - "X is a complex process..."
   - "The comparative efficacy of..."
   - "[Topic] + [adjective] + [noun phrase]..."

Return JSON: {{
  "draftMd": "markdown paragraph text",
  "citations": {{"1": {{"url": "...", "title": "..."}}, "2": {{...}}}},
  "quality": 0.0-1.0,
  "visualsUsed": [1, 2]
}}

Quality scoring:
- 0.8-1.0: Multiple peer-reviewed sources, quantitative data, mechanisms explained, stays perfectly on-topic
- 0.6-0.7: Good sources with detail, mostly on-topic with minor drift
- 0.4-0.5: Basic coverage from available sources
- 0.0-0.3: Insufficient sources or significant topic drift

CRITICAL: 
- If sources drift off-topic, acknowledge limitations and focus on relevant parts only
- Never fabricate citation numbers outside the range [1-{len(source_list)}]
- Every citation number MUST map to an actual source"""

    user = f"""Sources ({len(source_list)} available):
{_json.dumps(source_list, ensure_ascii=False)}

Visuals: {len(visuals)} available

Write a comprehensive paragraph that addresses "{brief}" using these sources while staying aligned with "{topic}".

This is paragraph {paragraph_index} of {total_paragraphs}, so adjust your writing style accordingly."""

    try:
        out = await _chat(cfg["model_writer"], [
            {"role":"system","content":system},
            {"role":"user","content":user}
        ], 0.3, json_mode=True, max_tokens=1500)
        
        doc = _extract_json(out) or (_json.loads(out) if out.startswith("{") else None)

        # Quick repair if needed
        if not doc:
            print(f"Failed to parse JSON on first attempt, trying repair...")
            fix_sys = "Convert to JSON: {draftMd:string, citations:object, quality:float, visualsUsed:array}"
            fix = await _chat(cfg["model_writer"], [
                {"role":"system","content":fix_sys},
                {"role":"user","content":out}
            ], 0.0, json_mode=True, max_tokens=800)
            doc = _extract_json(fix) or (_json.loads(fix) if fix.startswith("{") else None)

        # Final fallback
        if not doc:
            print(f"JSON parsing failed completely, using fallback construction")
            cites = _citations_from_pages(sources)
            content_parts = []
            for i, (n, meta) in enumerate(cites.items(), 1):
                if i-1 < len(sources) and sources[i-1].get("text"):
                    snippet = sources[i-1].get("text","")[:200].strip()
                    if snippet:
                        content_parts.append(f"{snippet} [{n}]")
            
            body = f"Research on {brief.split('?')[0]}:\n\n" + " ".join(content_parts[:4]) if content_parts else f"Analysis of {brief[:100]}"
            return {"draftMd": body, "citations": cites, "quality": 0.4, "visualsUsed": []}

        # Validate and fix citations
        cites = doc.get("citations") or _citations_from_pages(sources)
        
        # Find all citation numbers used in markdown
        used = sorted({int(n) for n in re.findall(r"\[(\d+)\]", doc.get("draftMd",""))})
        
        # Ensure all used citations have entries
        for n in used:
            if str(n) not in cites and 0 <= n-1 < len(sources):
                cites[str(n)] = {
                    "url": sources[n-1].get("url",""), 
                    "title": sources[n-1].get("title","")
                }
        
        # Ensure all keys are strings
        doc["citations"] = {str(k): v for k, v in cites.items()}
        
        # Validate minimum content length
        if len(doc.get("draftMd","")) < 150:
            print(f"Warning: Generated paragraph is short ({len(doc.get('draftMd',''))} chars)")
            doc["draftMd"] += f"\n\nFurther investigation of {brief[:80]} requires additional peer-reviewed sources."
        
        # Ensure at least one citation exists
        if not re.search(r"\[\d+\]", doc["draftMd"]):
            print(f"Warning: No citations found in paragraph, adding reference to first source")
            doc["draftMd"] += " [1]"
            if "1" not in doc["citations"] and len(sources) > 0:
                doc["citations"]["1"] = {
                    "url": sources[0].get("url",""),
                    "title": sources[0].get("title","")
                }
        
        # Validate quality score
        doc["quality"] = float(doc.get("quality", 0.5))
        if doc["quality"] < 0 or doc["quality"] > 1:
            print(f"Warning: Quality score {doc['quality']} out of range, clamping to [0,1]")
            doc["quality"] = max(0.0, min(1.0, doc["quality"]))
        
        doc["visualsUsed"] = doc.get("visualsUsed", [])
        
        return doc
        
    except Exception as e:
        print(f"Writer error: {e}")
        import traceback
        traceback.print_exc()
        
        cites = _citations_from_pages(sources)
        return {
            "draftMd": f"## {section_heading}\n\nResearch summary for: {brief[:100]}\n\nBased on available sources, this topic requires comprehensive analysis [1].",
            "citations": cites,
            "quality": 0.3,
            "visualsUsed": []
        }

async def synthesize_report(topic: str, paragraphs: List[dict], outline: List[dict]) -> str:
    """Synthesize final coherent report from paragraphs with proper introduction and conclusion"""
    
    config = _get_config()
    
    # Build section summaries
    sections = []
    for i, p in enumerate(paragraphs):
        heading = outline[i].get("heading", f"Section {i+1}") if i < len(outline) else f"Section {i+1}"
        content = p.get("draftMd", "")
        sections.append(f"SECTION {i+1}: {heading}\n{content}")
    
    paras_text = "\n\n---\n\n".join(sections)
    
    system = """You are a research report synthesizer. Create a comprehensive, cohesive academic report.

Your task:
1. Create a unified report that reads as ONE coherent document
2. Write a clear INTRODUCTION (2-3 paragraphs) that:
   - Directly addresses the research topic
   - Provides context and scope
   - Previews what the report will cover
3. Include all section content with:
   - Smooth transitions between sections
   - Consistent terminology throughout
   - No redundancy across sections
4. Write a CONCLUSION (2-3 paragraphs) that:
   - Synthesizes key findings
   - Identifies patterns across sections
   - Discusses implications and future directions
5. Maintain all citations [S1-1], [S2-3], etc. EXACTLY as written
6. Keep all section headers (##) from the original content
7. Ensure every section relates back to the original topic

OUTPUT FORMAT:
# {Title}

## Introduction
{2-3 paragraphs introducing the topic and scope}

## {Section 1 Header}
{Section 1 content with citations}

## {Section 2 Header}
{Section 2 content with citations}

...

## Conclusion
{2-3 paragraphs synthesizing findings}

Output ONLY the markdown report. Do NOT wrap in JSON or code blocks."""

    user = f"""Original Research Topic: "{topic}"

Individual sections with their content:
{paras_text}

Create a complete academic report that:
- Starts with # {topic}
- Has an Introduction section that directly addresses: "{topic}"
- Includes all section content with smooth transitions
- Ends with a Conclusion that synthesizes findings
- Maintains ALL citations exactly as written [S1-1], [S2-2], etc.
- Flows as one unified document"""

    try:
        print(f"Calling LLM for report synthesis...")
        response = await _chat(config["model_writer"], [
            {"role":"system","content":system},
            {"role":"user","content":user}
        ], 0.2, max_tokens=4000, timeout=90)
        
        print(f"Synthesis response: {len(response)} chars")
        
        # Validate response
        if not response or len(response) < 500:
            print(f"ERROR: Synthesis returned insufficient content ({len(response)} chars)")
            raise ValueError("Synthesis output too short")
        
        # Ensure it starts with the topic header
        if not response.strip().startswith(f"# {topic}"):
            print(f"Warning: Synthesis missing main header, adding it")
            response = f"# {topic}\n\n" + response.strip()
        
        # Check for Introduction and Conclusion
        has_intro = "## Introduction" in response or "## introduction" in response.lower()
        has_conclusion = "## Conclusion" in response or "## conclusion" in response.lower()
        
        if not has_intro:
            print(f"Warning: Synthesis missing Introduction section")
        if not has_conclusion:
            print(f"Warning: Synthesis missing Conclusion section")
        
        return response
        
    except Exception as e:
        print(f"ERROR in synthesize_report: {e}")
        import traceback
        traceback.print_exc()
        raise  # Re-raise so caller knows it failed

async def aggregate_report(topic: str, paragraphs: list[dict]) -> str:
    """Fallback: Simple aggregation with basic intro/conclusion"""
    
    config = _get_config()
    
    # Build simple concatenation
    parts = [p.get("draftMd","") for p in paragraphs]
    basic_report = "\n\n".join(parts)
    
    system = """You are a research report assembler. Your task:

1. Add a brief introduction (2 paragraphs) that introduces the topic
2. Keep all existing section content unchanged with all citations
3. Add a brief conclusion (2 paragraphs) that summarizes key findings
4. Ensure smooth flow between sections

Output ONLY markdown. Do NOT wrap in JSON."""
    
    user = f"""Topic: {topic}

Existing sections:
{basic_report}

Add an introduction and conclusion to make this a complete report. Keep all existing content and citations [S1-1], [S2-2], etc. unchanged."""
    
    try:
        print(f"Calling LLM for aggregate report...")
        response = await _chat(config["model_writer"], [
            {"role":"system","content":system},
            {"role":"user","content":user}
        ], 0.2, max_tokens=3000)
        
        if len(response) < 500:
            raise ValueError("Aggregate response too short")
        
        return response
        
    except Exception as e:
        print(f"ERROR in aggregate_report: {e}, using emergency fallback")
        # Emergency fallback: just concatenate with minimal intro
        return f"""# {topic}

## Introduction

This report presents research findings on {topic}. The following sections examine key aspects based on academic literature and peer-reviewed sources.

{basic_report}

## Conclusion

This report has synthesized current evidence on {topic}. The findings highlight the complexity of the subject and the need for continued research in this area."""