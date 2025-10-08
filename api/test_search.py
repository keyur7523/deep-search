# test_search.py
import asyncio
from services.search import _serpapi, _scholar

async def test():
    print("Testing SerpAPI...")
    results = await _serpapi("DNA structure", 3)
    print(f"SerpAPI: {len(results)} results")
    
    print("\nTesting Scholar...")
    results = await _scholar("DNA structure", 3)
    print(f"Scholar: {len(results)} results")
    
    if results:
        print("\nSample result:")
        print(f"  Title: {results[0].get('title', 'No title')}")
        print(f"  URL: {results[0].get('url', 'No URL')}")

asyncio.run(test())