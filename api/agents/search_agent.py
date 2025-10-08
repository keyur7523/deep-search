from typing import Dict, Any, List
from .base import BaseAgent
from services.search import hybrid_search
from services.academic import search_serpapi, search_crossref
from services.extract import extract_content
from bson import ObjectId
from models.db import db
import logging

logger = logging.getLogger(__name__)

class SearchAgent(BaseAgent):
    """
    Executes search queries and extracts content.
    """
    
    def __init__(self):
        super().__init__("Search")
    
    async def execute(
        self, 
        payload: Dict[str, Any], 
        task_id: str, 
        run_id: str
    ) -> Dict[str, Any]:
        """
        Execute search query and store results.
        """
        query = payload.get("query", "")
        search_type = payload.get("searchType", "hybrid")
        max_results = payload.get("maxResults", 8)

        try:
            await self.think(
                f"Searching for: {query}",
                task_id,
                run_id,
                meta={"query": query, "searchType": search_type}
            )

            # Execute search based on type
            results = []
            try:
                if search_type == "academic_serpapi":
                    results = await self._search_academic_serpapi(query, max_results)
                elif search_type == "academic_crossref":
                    results = await self._search_academic_crossref(query, max_results)
                elif search_type == "web":
                    results = await self._search_web(query, max_results)
                else:  # hybrid (default)
                    results = await self._search_hybrid(query, max_results)

                logger.info(f"Search returned {len(results)} results for: {query}")

                await self.action(
                    f"Found {len(results)} results",
                    task_id,
                    run_id,
                    meta={"result_count": len(results)}
                )

            except Exception as search_error:
                logger.error(f"Search execution failed: {search_error}", exc_info=True)
                await self.result(
                    f"Search failed: {str(search_error)}",
                    task_id,
                    run_id,
                    meta={"error": str(search_error)}
                )
                return {"sources": [], "error": str(search_error), "sources_found": 0, "source_ids": []}

            if not results:
                await self.result(
                    "No results found",
                    task_id,
                    run_id
                )
                return {"sources": [], "sources_found": 0, "source_ids": []}

            # Store sources in database
            logger.info(f"Attempting to store {len(results)} sources")
            source_ids = await self._store_sources(results, run_id, task_id)
            logger.info(f"Successfully stored {len(source_ids)} sources")

            await self.result(
                f"Stored {len(source_ids)} sources",
                task_id,
                run_id,
                meta={"source_count": len(source_ids)}
            )

            # Create quality check task
            await self.create_child_task(
                run_id,
                task_id,
                "QUALITY_CHECK",
                {
                    "source_ids": source_ids,
                    "query": query,
                    "expected_count": max_results
                }
            )

            return {
                "sources_found": len(results),
                "source_ids": source_ids,
                "query": query
            }

        except Exception as e:
            logger.error(f"SearchAgent.execute failed: {e}", exc_info=True)
            await self.result(
                f"Task failed: {str(e)}",
                task_id,
                run_id,
                meta={"error": str(e)}
            )
            return {"sources": [], "error": str(e), "sources_found": 0, "source_ids": []}

    
    async def _search_hybrid(self, query: str, max_results: int) -> List[Dict]:
        """Search using Semantic Scholar (free)"""
        from services.academic import semantic_scholar_search
        results = await semantic_scholar_search(query, top=max_results)
        return results

    async def _search_academic_serpapi(self, query: str, max_results: int) -> List[Dict]:
        """Search academic sources via Semantic Scholar (SerpAPI unavailable)"""
        from services.academic import semantic_scholar_search
        results = await semantic_scholar_search(query, top=max_results)
        return results

    async def _search_academic_crossref(self, query: str, max_results: int) -> List[Dict]:
        """Search using Semantic Scholar"""
        from services.academic import semantic_scholar_search
        results = await semantic_scholar_search(query, top=max_results)
        return results
    
    async def _search_web(self, query: str, max_results: int) -> List[Dict]:
        """Web-only search using Brave"""
        from services.search import brave_search
        results = await brave_search(query, count=max_results)
        return results
    
    async def _store_sources(
        self, 
        results: List[Dict], 
        run_id: str,
        task_id: str
    ) -> List[str]:
        """Store search results as sources in database"""
        from .utils import sanitize_for_mongodb
    
        source_ids = []
    
        for result in results:
            url = result.get("url", "")
            if not url:
                continue
            
            try:
                # For academic sources, use the snippet/abstract directly
                # Don't try to scrape Semantic Scholar pages
                if result.get("source") == "semantic_scholar":
                    content_text = result.get("snippet", "")
                else:
                    # For other sources, try to extract
                    content = await extract_content(url)
                    content_text = content.get("text", "")
    
                # Sanitize the entire result to avoid any MongoDB integer issues
                safe_result = sanitize_for_mongodb(result)
    
                source_doc = {
                    "runId": ObjectId(run_id),
                    "taskId": ObjectId(task_id),
                    "url": url,
                    "title": safe_result.get("title", "Untitled"),
                    "type": safe_result.get("type", "web"),
                    "authors": safe_result.get("authors", ""),
                    "year": str(safe_result.get("year", "")) if safe_result.get("year") else "",
                    "venue": safe_result.get("venue", ""),
                    "citations": safe_result.get("citations", 0),
                    "score": float(safe_result.get("score", 0.0)),
                    "text": content_text,
                    "snippet": safe_result.get("snippet", "")
                }
    
                res = await db().sources.insert_one(source_doc)
                source_ids.append(str(res.inserted_id))
    
                await self.action(
                    f"Stored source: {source_doc['title'][:50]}",
                    task_id,
                    run_id
                )
    
            except Exception as e:
                logger.warning(f"Failed to store source from {url}: {e}")
                continue
            
        return source_ids