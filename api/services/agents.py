"""
Agentic services for diagram generation and data visualization
Enhanced with source-based diagram generation
"""
import os, logging, re, json
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import httpx

load_dotenv()
logger = logging.getLogger(__name__)


def _get_config():
    return {
        "base": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        "key": os.getenv("LLM_API_KEY", ""),
        "model": os.getenv("LLM_MODEL_PLANNER", "gpt-4o-mini"),
    }


async def _chat(model: str, messages: List[Dict], temperature: float = 0.2) -> str:
    """Simple chat completion"""
    cfg = _get_config()
    url = f"{cfg['base']}/chat/completions"
    headers = {"Authorization": f"Bearer {cfg['key']}"}
    body = {"model": model, "messages": messages, "temperature": temperature}
    
    async with httpx.AsyncClient(timeout=30) as cx:
        r = await cx.post(url, headers=headers, json=body)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()


# === Enhanced Diagram Agent ===

def _validate_mermaid(code: str) -> bool:
    """
    Enhanced mermaid syntax validation
    """
    if not code or len(code) < 20:
        return False
    
    # Check for valid mermaid diagram types
    valid_types = ["flowchart", "graph", "sequenceDiagram", "classDiagram", "stateDiagram", "erDiagram"]
    has_valid_type = any(diagram_type in code for diagram_type in valid_types)
    
    # Check for basic syntax elements
    has_arrows = "-->" in code or "---" in code or "-.->" in code or "==>" in code
    has_nodes = code.count("[") >= 2 or code.count("(") >= 2 or code.count("{") >= 2
    
    # Check it's not just a template
    placeholder_patterns = ["Node1", "Node2", "NodeA", "NodeB", "Step1", "Step2"]
    has_placeholders = sum(1 for p in placeholder_patterns if p in code) > 3
    
    return has_valid_type and has_arrows and has_nodes and not has_placeholders


async def generate_diagram(topic: str, context: str, sources: List[Dict]) -> Optional[Dict[str, Any]]:
    """
    Enhanced DiagramAgent: Generate diagrams based on actual mechanistic content from sources
    Only creates diagrams when sources contain specific pathways, processes, or relationships
    """
    cfg = _get_config()
    
    # Step 1: Extract mechanistic content from sources
    mechanistic_content = []
    for source in sources[:6]:  # Check top 6 sources
        text = source.get("text", "")[:1500]  # Increased from 1000 to 1500 chars
        title = source.get("title", "")
        
        # Look for mechanistic indicators in text
        mechanism_keywords = [
            "pathway", "mechanism", "cascade", "signaling", "receptor", 
            "binding", "activation", "inhibition", "phosphorylation",
            "transcription", "translation", "secretion", "enzyme",
            "protein", "ligand", "substrate", "process", "cycle"
        ]
        
        # Count mechanistic terms
        mechanism_score = sum(1 for kw in mechanism_keywords if kw in text.lower())
        
        # Extract sentences with mechanistic content
        sentences = text.split(". ")
        mechanistic_sentences = []
        for sent in sentences[:15]:  # Check first 15 sentences
            sent_lower = sent.lower()
            if any(kw in sent_lower for kw in mechanism_keywords):
                # Check for specific entities (proteins, molecules, receptors)
                has_entities = bool(re.search(r'\b[A-Z][a-z]*[0-9]?\b', sent))  # AT1, IP3, PLC, etc.
                if has_entities or mechanism_score > 2:
                    mechanistic_sentences.append(sent.strip())
        
        if mechanistic_sentences:
            mechanistic_content.append({
                "title": title[:80],
                "sentences": mechanistic_sentences[:5],  # Top 5 mechanistic sentences
                "score": mechanism_score
            })
    
    # Only proceed if we have substantial mechanistic content
    if len(mechanistic_content) < 2:
        logger.info(f"Insufficient mechanistic content for diagram (found {len(mechanistic_content)} sources with mechanisms)")
        return None
    
    # Sort by mechanism score
    mechanistic_content.sort(key=lambda x: x["score"], reverse=True)
    
    system = """You are a scientific diagram specialist. Generate mermaid flowchart diagrams ONLY when sources describe clear, specific molecular/cellular mechanisms.

STRICT REQUIREMENTS:
1. Extract ACTUAL entities from source text (proteins, receptors, molecules, enzymes)
2. Show SPECIFIC relationships described in sources (activation, inhibition, binding, phosphorylation)
3. Use exact terminology from sources (e.g., "AT1 receptor", "IP3", "PLC", "calcium")
4. Label edges with verbs from sources (activates, inhibits, binds to, produces, releases)
5. Create 6-12 nodes showing the complete pathway
6. Use subgraphs for different cellular compartments if mentioned

DO NOT:
- Use generic placeholders (Node1, Step1, etc.)
- Invent relationships not in sources
- Create diagrams without specific molecular detail
- Make assumptions about mechanisms

If sources lack specific mechanistic detail with named entities and relationships, respond: NO_DIAGRAM

OUTPUT FORMAT:
```
flowchart TD
    A[Specific Entity Name] -->|action verb| B[Next Entity]
    B -->|action| C[Result]
```

Use:
- Rectangles [Entity] for proteins, receptors, molecules
- Rounded (Process) for cellular processes
- Diamond {Decision} for branching pathways
- --> for activation
- -.-> for indirect effects
- --x for inhibition
"""
    
    # Format mechanistic content for prompt
    content_text = []
    for idx, content in enumerate(mechanistic_content[:4], 1):  # Top 4 sources
        content_text.append(f"\nSource {idx}: {content['title']}")
        for sent in content['sentences']:
            content_text.append(f"  - {sent}")
    
    user = f"""Topic: {context}

Mechanistic content from peer-reviewed sources:
{''.join(content_text)}

Task: Generate a mermaid flowchart showing the SPECIFIC molecular pathway described in these sources.

Use ONLY entities and relationships explicitly mentioned. Include:
- Receptor names (e.g., AT1, AT2)
- Signaling proteins (e.g., Gq, PLC, PKC)
- Second messengers (e.g., IP3, DAG, Ca2+)
- Cellular outcomes

If sources don't provide enough molecular detail, respond NO_DIAGRAM."""
    
    try:
        response = await _chat(cfg["model"], [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ], temperature=0.15)  # Very low temperature for accuracy
        
        # Check for no diagram
        if "NO_DIAGRAM" in response.upper():
            logger.info("DiagramAgent: Sources lack sufficient mechanistic detail")
            return None
        
        # Extract mermaid code
        mermaid_code = response.strip()
        
        # Remove markdown fences
        mermaid_code = re.sub(r"^```(?:mermaid)?\s*", "", mermaid_code, flags=re.MULTILINE)
        mermaid_code = re.sub(r"```\s*$", "", mermaid_code)
        mermaid_code = mermaid_code.strip()
        
        # Validate
        if not _validate_mermaid(mermaid_code):
            logger.warning("DiagramAgent generated invalid or placeholder mermaid syntax")
            return None
        
        # Check for placeholders that slipped through
        if any(placeholder in mermaid_code for placeholder in ["Node1", "Node2", "NodeA", "Step1", "Entity1"]):
            logger.warning("DiagramAgent used placeholder nodes - rejecting")
            return None
        
        logger.info(f"Generated source-based mechanism diagram: {len(mermaid_code)} chars, {mermaid_code.count('-->') + mermaid_code.count('-.->') + mermaid_code.count('--x')} relationships")
        return {
            "format": "mermaid",
            "code": mermaid_code,
            "type": "diagram"
        }
    
    except Exception as e:
        logger.error(f"DiagramAgent error: {e}")
        return None


# === Enhanced Chart Agent ===

async def extract_chart_data(paragraph: str, sources: List[Dict]) -> Optional[Dict[str, Any]]:
    """
    Enhanced ChartAgent: Extract quantitative data with validation
    """
    cfg = _get_config()
    
    # Pre-check: Does paragraph contain numbers?
    has_numbers = bool(re.search(r'\d+\.?\d*\s*(?:%|mmHg|mg/dL|points|fold|times)', paragraph))
    if not has_numbers:
        logger.info("ChartAgent: No quantitative data found in paragraph")
        return None
    
    system = """You are a data extraction specialist. Extract ONLY numeric data explicitly stated in the paragraph.

STRICT RULES:
1. Extract ONLY data with clear numeric values and labels
2. Must have at least 3 data points for meaningful visualization
3. Values must be comparable (same unit/scale)
4. Include confidence intervals or ranges if mentioned
5. Cite source for each data point if identifiable

Return JSON:
{
  "title": "Descriptive title from context",
  "type": "bar|line|scatter",
  "unit": "% | mmHg | mg/dL | etc",
  "rows": [
    {"label": "Clear label", "value": 25.5, "source": "citation #"},
    {"label": "Another label", "value": 30.2, "source": "citation #"}
  ]
}

BAR CHART: Comparisons between categories (treatments, groups, interventions)
LINE CHART: Trends over time or dose-response
SCATTER: Correlations between two variables

If insufficient data (<3 points) or values not comparable, return: {"noData": true}

Example good data:
- "ACE inhibitors reduced BP by 12.5 mmHg [1], ARBs by 11.8 mmHg [2], CCBs by 10.3 mmHg [3]"
- "Prevalence increased from 15% in 2010 to 23% in 2015 and 31% in 2020"

Example insufficient data:
- "Multiple studies showed improvements" (no numbers)
- "One study found 20% reduction" (only 1 data point)
"""
    
    user = f"""Paragraph:
{paragraph}

Source titles (for reference):
{json.dumps([s.get('title', '')[:60] for s in sources[:5]])}

Extract chart-worthy quantitative data or return {{"noData": true}}"""
    
    try:
        response = await _chat(cfg["model"], [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ], temperature=0.05)  # Very low temperature for precision
        
        # Parse JSON
        data = json.loads(response)
        
        # Check if no data
        if data.get("noData"):
            logger.info("ChartAgent: No chartable data found")
            return None
        
        # Strict validation
        rows = data.get("rows", [])
        if len(rows) < 3:
            logger.info(f"ChartAgent: Insufficient data points ({len(rows)} < 3)")
            return None
        
        # Validate each row
        for row in rows:
            if "label" not in row or "value" not in row:
                logger.warning("ChartAgent: Invalid row structure")
                return None
            if not isinstance(row["value"], (int, float)):
                logger.warning(f"ChartAgent: Non-numeric value: {row['value']}")
                return None
            if not row["label"] or len(row["label"]) < 2:
                logger.warning("ChartAgent: Invalid label")
                return None
        
        # Check values are in reasonable range (not all zeros or identical)
        values = [row["value"] for row in rows]
        if len(set(values)) == 1:
            logger.info("ChartAgent: All values identical - not useful for visualization")
            return None
        
        logger.info(f"ChartAgent extracted {len(rows)} data points: {data.get('title', 'Untitled')}")
        return {
            "format": "chart",
            "title": data.get("title", "Data Visualization"),
            "type": data.get("type", "bar"),
            "unit": data.get("unit", ""),
            "data": rows
        }
    
    except json.JSONDecodeError as e:
        logger.warning(f"ChartAgent returned invalid JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"ChartAgent error: {e}")
        return None


# === Enhanced Strategy Agent ===

async def should_generate_visuals(topic: str, section_brief: str, source_count: int) -> Dict[str, bool]:
    """
    Enhanced StrategyAgent: More selective about when to generate visuals
    Uses smarter heuristics based on content and source quality
    """
    decisions = {
        "diagram": False,
        "chart": False
    }
    
    # Require minimum sources
    if source_count < 3:
        logger.info(f"Insufficient sources ({source_count}) for visual generation")
        return decisions
    
    brief_lower = section_brief.lower()
    topic_lower = topic.lower()
    
    # === DIAGRAM DECISION ===
    # Strong indicators for mechanistic diagrams
    strong_mechanism_keywords = [
        "molecular mechanism", "signaling pathway", "cascade",
        "receptor activation", "enzyme activity", "metabolic pathway",
        "cell cycle", "signal transduction"
    ]
    
    # Moderate indicators
    moderate_mechanism_keywords = [
        "mechanism", "pathway", "process", "cycle", "regulation",
        "interaction", "binding", "activation", "inhibition"
    ]
    
    # Check for strong indicators
    has_strong = any(kw in brief_lower for kw in strong_mechanism_keywords)
    has_moderate = any(kw in brief_lower for kw in moderate_mechanism_keywords)
    
    # Also check topic
    topic_suggests_mechanism = any(kw in topic_lower for kw in ["mechanism", "pathway", "regulation", "signaling"])
    
    # Decision logic
    if has_strong:
        decisions["diagram"] = True
        logger.info("Strong mechanistic language detected - will attempt diagram")
    elif has_moderate and (topic_suggests_mechanism or source_count >= 5):
        decisions["diagram"] = True
        logger.info("Moderate mechanistic language + good context - will attempt diagram")
    
    # === CHART DECISION ===
    # Keywords suggesting quantitative data
    quantitative_keywords = [
        "percent", "percentage", "rate", "ratio", "incidence", "prevalence",
        "reduction", "increase", "decrease", "effect size", "odds ratio",
        "hazard ratio", "relative risk", "absolute risk", "confidence interval",
        "meta-analysis", "systematic review", "clinical trial", "rct",
        "measure", "measurement", "score", "scale", "index"
    ]
    
    comparison_keywords = [
        "compare", "comparison", "versus", "vs", "between", "among",
        "different", "vary", "variation", "range"
    ]
    
    temporal_keywords = [
        "trend", "over time", "progression", "change", "evolution",
        "follow-up", "longitudinal", "prospective"
    ]
    
    has_quantitative = any(kw in brief_lower for kw in quantitative_keywords)
    has_comparison = any(kw in brief_lower for kw in comparison_keywords)
    has_temporal = any(kw in brief_lower for kw in temporal_keywords)
    
    # Need both quantitative language AND sufficient sources
    if (has_quantitative or has_comparison or has_temporal) and source_count >= 4:
        decisions["chart"] = True
        logger.info("Quantitative/comparison language detected - will attempt chart")
    
    # DON'T overgenerate - at most one visual per section
    if decisions["diagram"] and decisions["chart"]:
        # Prioritize based on brief content
        if has_strong or sum(1 for kw in strong_mechanism_keywords if kw in brief_lower) > 0:
            decisions["chart"] = False
            logger.info("Prioritizing diagram over chart (stronger mechanistic focus)")
        else:
            decisions["diagram"] = False
            logger.info("Prioritizing chart over diagram (quantitative focus)")
    
    return decisions