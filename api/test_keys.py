# test_keys.py
import os
from dotenv import load_dotenv

load_dotenv()

serp = os.getenv("SERPAPI_KEY", "")
sem_scholar = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
brave = os.getenv("BRAVE_API_KEY", "")

print(f"SERPAPI_KEY: {'✅ SET (' + str(len(serp)) + ' chars)' if serp else '❌ NOT SET'}")
print(f"SEMANTIC_SCHOLAR_API_KEY: {'✅ SET (' + str(len(sem_scholar)) + ' chars)' if sem_scholar else '❌ NOT SET'}")
print(f"BRAVE_API_KEY: {'✅ SET (' + str(len(brave)) + ' chars)' if brave else '❌ NOT SET'}")

if serp:
    print(f"\nFirst 10 chars of SERPAPI_KEY: {serp[:10]}...")