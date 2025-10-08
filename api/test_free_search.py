# test_free_search.py
import asyncio
from services.academic import semantic_scholar_search, deep_academic_search

async def test():
    print("Testing Semantic Scholar (free)...")
    results = await semantic_scholar_search("DNA structure", 3)
    print(f"Found {len(results)} results")
    
    if results:
        print(f"  Title: {results[0].get('title', 'No title')}")
    
    print("\nTesting deep academic search (free)...")
    results = await deep_academic_search("DNA structure", 5)
    print(f"Found {len(results)} results")

asyncio.run(test())