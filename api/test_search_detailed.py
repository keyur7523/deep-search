# test_search_detailed.py
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

async def test_serpapi_directly():
    serp_key = os.getenv("SERPAPI_KEY")
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google",
        "q": "DNA structure",
        "num": 3,
        "api_key": serp_key
    }
    
    print("Testing SerpAPI direct call...")
    print(f"URL: {url}")
    print(f"Query: DNA structure")
    
    try:
        async with httpx.AsyncClient(timeout=20) as cx:
            r = await cx.get(url, params=params)
            print(f"Status: {r.status_code}")
            data = r.json()
            
            if "error" in data:
                print(f"❌ API Error: {data['error']}")
            
            results = data.get("organic_results", [])
            print(f"Results: {len(results)}")
            
            if results:
                print(f"\nFirst result:")
                print(f"  Title: {results[0].get('title', 'No title')}")
                print(f"  Link: {results[0].get('link', 'No link')}")
            else:
                print(f"\nFull response keys: {list(data.keys())}")
                
    except Exception as e:
        print(f"❌ Exception: {e}")

asyncio.run(test_serpapi_directly())