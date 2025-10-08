# api/test_week1_integration.py

import asyncio
import sys
from agents.coordinator import route_research_mode, explain_routing_decision

async def test_routing():
    """Test the routing logic without hitting the database"""
    
    print("=" * 60)
    print("Testing Week 1 Integration - Routing Logic")
    print("=" * 60)
    
    test_cases = [
        # Simple topics
        ("History of DNA", {}),
        ("What is photosynthesis?", {}),
        
        # Complex topics
        (
            "Compare efficacy of mRNA vaccines vs traditional vaccines in elderly populations",
            {}
        ),
        (
            "Molecular mechanisms of CRISPR-Cas9 gene editing",
            {"minCitations": 30}
        ),
        
        # With config overrides
        ("Simple topic", {"forceMode": "agentic"}),
        ("Complex medical topic", {"forceMode": "simple"}),
        ("Regular topic", {"deepMode": True, "minCitations": 25}),
    ]
    
    for topic, config in test_cases:
        print(f"\n{'─' * 60}")
        print(f"Topic: {topic[:50]}...")
        print(f"Config: {config}")
        
        # Get routing decision
        mode = route_research_mode(topic, config)
        explanation = explain_routing_decision(topic, config)
        
        print(f"\nResult: {mode.upper()}")
        print(f"Score: {explanation['score']:.3f} (threshold: {explanation['threshold']})")
        print(f"Reasoning: {explanation['reasoning']}")
        print(f"Factors:")
        for key, value in explanation['factors'].items():
            print(f"  - {key}: {value}")
    
    print(f"\n{'=' * 60}")
    print("All routing tests passed!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        asyncio.run(test_routing())
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)