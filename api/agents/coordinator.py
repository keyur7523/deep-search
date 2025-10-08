# api/agents/coordinator.py

import re
from typing import Literal

def route_research_mode(
    topic: str, 
    config: dict
) -> Literal["simple", "agentic"]:
    """
    Determine whether to use simple or agentic pipeline.
    
    Args:
        topic: Research topic string
        config: Configuration dict with optional:
            - forceMode: "simple" | "agentic" to override
            - deepMode: bool for comprehensive research
            - minCitations: int minimum required citations
            - requireRecent: bool for time-sensitive topics
            - maxParagraphs: int complexity indicator
    
    Returns:
        "simple" or "agentic"
    """
    
    # User override
    force_mode = config.get("forceMode")
    if force_mode in ["simple", "agentic"]:
        return force_mode
    
    # Calculate complexity score
    score = _calculate_complexity_score(topic, config)
    
    # Threshold: < 0.35 = simple, >= 0.35 = agentic
    return "agentic" if score >= 0.35 else "simple"

def _calculate_complexity_score(topic: str, config: dict) -> float:
    """
    Score topic complexity on 0.0-1.0 scale.
    
    Factors:
    - Topic length and structure
    - Domain complexity (medicine, finance, law)
    - User requirements (deep mode, citations)
    - Novelty vs cached topics
    """
    score = 0.0
    
    # 1. Topic length complexity (max 0.15)
    word_count = len(topic.split())
    if word_count > 15:
        score += 0.15
    elif word_count > 10:
        score += 0.10
    elif word_count > 6:
        score += 0.05
    
    # 2. Topic structure complexity (max 0.15)
    # Multiple clauses, questions, or comparisons indicate complexity
    if "?" in topic:
        score += 0.05
    if " vs " in topic.lower() or " versus " in topic.lower():
        score += 0.10  # Comparative analysis
    if topic.count(",") >= 2:
        score += 0.05  # Multiple aspects
    
    # 3. Domain complexity (max 0.20)
    complex_domains = {
        "medicine": 0.20, "medical": 0.20, "clinical": 0.20,
        "genetic": 0.20, "genomic": 0.20, "molecular": 0.18,
        "finance": 0.18, "financial": 0.18, "economics": 0.15,
        "legal": 0.18, "law": 0.18, "regulatory": 0.15,
        "quantum": 0.20, "theoretical": 0.15,
        "neuroscience": 0.20, "cognitive": 0.18
    }
    
    topic_lower = topic.lower()
    domain_score = 0.0
    for domain, weight in complex_domains.items():
        if domain in topic_lower:
            domain_score = max(domain_score, weight)
    score += domain_score
    
    # 4. User requirements (max 0.30)
    if config.get("deepMode", False):
        score += 0.20
    
    min_citations = config.get("minCitations", 0)
    if min_citations > 30:
        score += 0.15
    elif min_citations > 20:
        score += 0.10
    elif min_citations > 10:
        score += 0.05
    
    if config.get("requireRecent", False):
        score += 0.10  # Recent papers require more filtering
    
    # 5. Scope indicator (max 0.10)
    max_paragraphs = config.get("maxParagraphs", 6)
    if max_paragraphs > 10:
        score += 0.10
    elif max_paragraphs > 8:
        score += 0.05
    
    # 6. Temporal/prediction topics (max 0.10)
    future_indicators = ["future", "prediction", "forecast", "trend", "emerging"]
    if any(indicator in topic_lower for indicator in future_indicators):
        score += 0.10
    
    return min(score, 1.0)  # Cap at 1.0

def explain_routing_decision(topic: str, config: dict) -> dict:
    """
    Return detailed explanation of why a mode was chosen.
    Useful for debugging and transparency.
    """
    score = _calculate_complexity_score(topic, config)
    mode = "agentic" if score >= 0.35 else "simple"
    
    return {
        "mode": mode,
        "score": round(score, 3),
        "threshold": 0.35,
        "factors": {
            "topicLength": len(topic.split()),
            "detectedDomains": _detect_domains(topic),
            "deepMode": config.get("deepMode", False),
            "minCitations": config.get("minCitations", 0),
            "requireRecent": config.get("requireRecent", False)
        },
        "reasoning": _generate_reasoning(score, topic, config)
    }

def _detect_domains(topic: str) -> list[str]:
    """Detect which complex domains are mentioned"""
    domains = ["medicine", "genetics", "finance", "law", "quantum", "neuroscience"]
    return [d for d in domains if d in topic.lower()]

def _generate_reasoning(score: float, topic: str, config: dict) -> str:
    """Generate human-readable explanation"""
    if config.get("forceMode"):
        return f"User forced {config['forceMode']} mode"
    
    if score >= 0.35:
        reasons = []
        if len(topic.split()) > 10:
            reasons.append("complex multi-part topic")
        if _detect_domains(topic):
            reasons.append(f"specialized domain ({', '.join(_detect_domains(topic))})")
        if config.get("deepMode"):
            reasons.append("deep research mode requested")
        if config.get("minCitations", 0) > 20:
            reasons.append(f"high citation requirement ({config['minCitations']})")
        
        return f"Agentic mode selected due to: {'; '.join(reasons)}"
    else:
        return "Simple mode sufficient for straightforward topic"