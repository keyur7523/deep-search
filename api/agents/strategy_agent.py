from typing import Dict, Any
from .base import BaseAgent
from services.llm import call_llm
from bson import ObjectId
from models.db import db
import json

class StrategyAgent(BaseAgent):
    """
    Plans research strategy and creates initial task tree.
    """
    
    def __init__(self):
        super().__init__("Strategy")
    
    async def execute(
        self, 
        payload: Dict[str, Any], 
        task_id: str, 
        run_id: str
    ) -> Dict[str, Any]:
        """
        Analyze topic and create research plan with tasks.
        """
        topic = payload.get("topic", "")
        config = payload.get("config", {})
        
        await self.think(
            f"Analyzing research topic: {topic}",
            task_id,
            run_id
        )
        
        # Get project context
        run = await db().runs.find_one({"_id": ObjectId(run_id)})
        project = await db().projects.find_one({"_id": run["projectId"]})
        
        # Build strategy prompt
        strategy_prompt = self._build_strategy_prompt(topic, project, config)
        
        await self.action(
            "Creating research strategy using LLM",
            task_id,
            run_id
        )
        
        # Call LLM to generate strategy
        response = await call_llm(
            messages=[
                {"role": "system", "content": "You are a research strategy expert."},
                {"role": "user", "content": strategy_prompt}
            ],
            temperature=0.7
        )
        
        # Parse strategy
        strategy = self._parse_strategy(response)
        
        await self.result(
            f"Created strategy with {len(strategy['search_queries'])} search queries",
            task_id,
            run_id,
            meta={"query_count": len(strategy['search_queries'])}
        )
        
        # Create search tasks
        for idx, query in enumerate(strategy['search_queries']):
            await self.create_child_task(
                run_id,
                task_id,
                "SEARCH",
                {
                    "query": query,
                    "index": idx,
                    "searchType": "academic_crossref"
                    #"searchType": config.get("searchProvider", "hybrid")
                }
            )
        
        return {
            "strategy": strategy,
            "queries_created": len(strategy['search_queries'])
        }
    
    def _build_strategy_prompt(
        self, 
        topic: str, 
        project: Dict, 
        config: Dict
    ) -> str:
        """Build prompt for strategy generation"""
        return f"""Create a comprehensive research strategy for this topic:

Topic: {topic}

Goal: {project.get('goalMd', 'Comprehensive research report')}

Requirements:
- Maximum paragraphs: {config.get('maxParagraphs', 6)}
- Minimum citations: {config.get('minCitations', 10)}
- Deep mode: {config.get('deepMode', False)}

Generate a JSON response with:
{{
  "approach": "Brief description of research approach",
  "search_queries": ["query1", "query2", ...],
  "key_aspects": ["aspect1", "aspect2", ...]
}}

Provide 3-5 diverse search queries that will comprehensively cover the topic.
Make queries specific and varied (mix of broad and narrow angles).
"""
    
    def _parse_strategy(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into strategy dict"""
        try:
            # Try to extract JSON from response
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                return json.loads(json_str)
        except:
            pass
        
        # Fallback: create basic strategy
        return {
            "approach": "Multi-angle research approach",
            "search_queries": [
                response[:100] if response else "general research query"
            ],
            "key_aspects": []
        }