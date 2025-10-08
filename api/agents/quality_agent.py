from typing import Dict, Any, List
from .base import BaseAgent
from services.llm import call_llm
from bson import ObjectId
from models.db import db
import json

class QualityAgent(BaseAgent):
    """
    Evaluates research quality and decides if more work is needed.
    """
    
    def __init__(self):
        super().__init__("Quality")
    
    async def execute(
        self, 
        payload: Dict[str, Any], 
        task_id: str, 
        run_id: str
    ) -> Dict[str, Any]:
        """
        Check if sources are sufficient for the query.
        """
        source_ids = payload.get("source_ids", [])
        query = payload.get("query", "")
        expected_count = payload.get("expected_count", 5)
        
        await self.think(
            f"Evaluating {len(source_ids)} sources for query: {query}",
            task_id,
            run_id
        )
        
        # Load sources
        sources = await self._load_sources(source_ids)
        
        if len(sources) == 0:
            await self.result(
                "No sources found after retries - cannot synthesize",
                task_id,
                run_id,
                meta={"decision": "abort"}
            )
            return {"decision": "abort", "reason": "no_sources_after_retry"}

            
            # Create retry search task
            await self.create_child_task(
                run_id,
                task_id,
                "SEARCH",
                {
                    "query": f"{query} (retry with broader terms)",
                    "searchType": "hybrid",
                    "maxResults": expected_count * 2
                }
            )
            
            return {"decision": "retry", "reason": "no_sources"}
        
        # Evaluate quality using LLM
        quality_assessment = await self._assess_quality(query, sources)
        
        await self.action(
            f"Quality score: {quality_assessment['score']:.2f}/1.0",
            task_id,
            run_id,
            meta={"score": quality_assessment['score']}
        )
        
        # Decision logic
        if quality_assessment['score'] >= 0.7:
            # Good enough - proceed to synthesis
            await self.result(
                "Quality sufficient - proceeding to synthesis",
                task_id,
                run_id,
                meta={"decision": "proceed"}
            )
            
            await self.create_child_task(
                run_id,
                task_id,
                "SYNTHESIS",
                {
                    "source_ids": source_ids,
                    "query": query,
                    "quality_score": quality_assessment['score']
                }
            )
            
            return {
                "decision": "proceed",
                "score": quality_assessment['score'],
                "sources_approved": len(sources)
            }
        
        elif quality_assessment['score'] >= 0.4:
            # Mediocre - get supplementary sources
            await self.result(
                "Quality acceptable but could improve - searching for supplementary sources",
                task_id,
                run_id,
                meta={"decision": "supplement"}
            )
            
            # Search for gaps
            gaps = quality_assessment.get('gaps', [])
            if gaps:
                for gap in gaps[:2]:  # Max 2 supplementary searches
                    await self.create_child_task(
                        run_id,
                        task_id,
                        "SEARCH",
                        {
                            "query": f"{query} {gap}",
                            "searchType": "hybrid",
                            "maxResults": 5
                        }
                    )
            
            # Still proceed to synthesis with current sources
            await self.create_child_task(
                run_id,
                task_id,
                "SYNTHESIS",
                {
                    "source_ids": source_ids,
                    "query": query,
                    "quality_score": quality_assessment['score'],
                    "gaps": gaps
                }
            )
            
            return {
                "decision": "supplement",
                "score": quality_assessment['score'],
                "gaps": gaps
            }
        
        else:
            # Poor quality - retry with different approach
            await self.result(
                "Quality insufficient - retrying with different search strategy",
                task_id,
                run_id,
                meta={"decision": "retry"}
            )
            
            await self.create_child_task(
                run_id,
                task_id,
                "SEARCH",
                {
                    "query": quality_assessment.get('suggested_query', query),
                    "searchType": "hybrid",
                    "maxResults": expected_count * 2
                }
            )
            
            return {
                "decision": "retry",
                "score": quality_assessment['score'],
                "reason": "insufficient_quality"
            }
    
    async def _load_sources(self, source_ids: List[str]) -> List[Dict]:
        """Load source documents from database"""
        sources = []
        for source_id in source_ids:
            try:
                source = await db().sources.find_one({"_id": ObjectId(source_id)})
                if source:
                    sources.append(source)
            except:
                continue
        return sources
    
    async def _assess_quality(self, query: str, sources: List[Dict]) -> Dict[str, Any]:
        """Use LLM to assess source quality"""
        
        # Build assessment prompt
        source_summaries = []
        for idx, source in enumerate(sources[:10]):  # Max 10 sources for assessment
            summary = {
                "index": idx + 1,
                "title": source.get("title", "Unknown"),
                "type": source.get("type", "web"),
                "snippet": source.get("snippet", source.get("text", "")[:300])
            }
            source_summaries.append(summary)
        
        prompt = f"""Assess the quality of these search results for the query: "{query}"

Sources:
{json.dumps(source_summaries, indent=2)}

Evaluate based on:
1. Relevance to query
2. Source diversity (different perspectives/types)
3. Credibility (academic vs web sources)
4. Coverage (does it address all aspects of the query?)

Respond with JSON:
{{
  "score": 0.0-1.0,
  "strengths": ["strength1", "strength2"],
  "gaps": ["gap1", "gap2"],
  "suggested_query": "alternative query if needed"
}}
"""
        
        try:
            response = await call_llm(
                messages=[
                    {"role": "system", "content": "You are a research quality evaluator."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            # Parse response
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                assessment = json.loads(response[start:end])
                return assessment
        except Exception as e:
            logger.error(f"Quality assessment failed: {e}")
        
        # Fallback assessment
        return {
            "score": 0.3 if len(sources) > 0 else 0.0,  # Low score on failure
            "strengths": [] if len(sources) == 0 else ["Some sources found"],
            "gaps": ["Quality assessment failed - manual review needed"],
            "suggested_query": query
        }