from typing import Dict, Any, List
from .base import BaseAgent
from services.llm import call_llm
from services.text_processing import correct_spelling, remove_duplicate_headings
from bson import ObjectId
from models.db import db
import logging

logger = logging.getLogger(__name__)

class SynthesisAgent(BaseAgent):
    """
    Synthesizes research into final report sections.
    """
    
    def __init__(self):
        super().__init__("Synthesis")
    
    async def execute(
        self, 
        payload: Dict[str, Any], 
        task_id: str, 
        run_id: str
    ) -> Dict[str, Any]:
        """
        Create report section from sources.
        """
        source_ids = payload.get("source_ids", [])
        query = payload.get("query", "")
        quality_score = payload.get("quality_score", 0.0)
        
        await self.think(
            f"Synthesizing report from {len(source_ids)} sources",
            task_id,
            run_id
        )
        
        # Load sources with content
        sources = await self._load_sources_with_content(source_ids)
        
        if not sources:
            await self.result(
                "No sources available for synthesis",
                task_id,
                run_id
            )
            return {"paragraph": "", "citations": []}
        
        await self.action(
            f"Writing synthesis based on {len(sources)} sources",
            task_id,
            run_id
        )
        
        # Generate synthesis
        synthesis = await self._generate_synthesis(query, sources, run_id)
        
        # Store as paragraph
        paragraph_doc = {
            "runId": ObjectId(run_id),
            "taskId": ObjectId(task_id),
            "query": query,
            "draftMd": synthesis["text"],
            "citations": synthesis["citations"],
            "quality": quality_score,
            "source_count": len(sources)
        }
        
        result = await db().paragraphs.insert_one(paragraph_doc)
        paragraph_id = str(result.inserted_id)
        
        await self.result(
            f"Created paragraph ({len(synthesis['text'])} chars, {len(synthesis['citations'])} citations)",
            task_id,
            run_id,
            meta={
                "paragraph_id": paragraph_id,
                "char_count": len(synthesis["text"]),
                "citation_count": len(synthesis["citations"])
            }
        )
        
        return {
            "paragraph_id": paragraph_id,
            "text_length": len(synthesis["text"]),
            "citations": synthesis["citations"]
        }
    
    async def _load_sources_with_content(self, source_ids: List[str]) -> List[Dict]:
        """Load sources with full text content"""
        logger.info(f"Loading {len(source_ids)} sources for synthesis")
        sources = []
        for source_id in source_ids:
            try:
                source = await db().sources.find_one({"_id": ObjectId(source_id)})
                if source:
                    # Use text if available, otherwise fall back to snippet (abstract)
                    text = source.get("text") or source.get("snippet", "")
                    logger.info(f"Source {source_id}: text={len(source.get('text', '') or '')} chars, snippet={len(source.get('snippet', '') or '')} chars")
                    if text:
                        source["text"] = text  # Ensure text field is set
                        sources.append(source)
                    else:
                        logger.warning(f"Source {source_id} has no text or snippet")
                else:
                    logger.warning(f"Source {source_id} not found in database")
            except Exception as e:
                logger.error(f"Error loading source {source_id}: {e}")
                continue
        logger.info(f"Loaded {len(sources)} sources with content")
        return sources
    
    async def _generate_synthesis(
        self, 
        query: str, 
        sources: List[Dict],
        run_id: str
    ) -> Dict[str, Any]:
        """Generate synthesized text with citations"""
        
        # Get run config
        run = await db().runs.find_one({"_id": ObjectId(run_id)})
        config = run.get("config", {})
        
        # Build synthesis prompt - collect ALL sources first, then create prompt
        source_texts = []
        for idx, source in enumerate(sources[:10]):  # Max 10 sources
            text_excerpt = source.get("text", "")[:2000]  # First 2000 chars
            source_texts.append(f"[Source {idx+1}] {source.get('title', 'Unknown')}\n{text_excerpt}\n")

        # CRITICAL FIX: Prompt must be OUTSIDE the loop to include ALL sources
        # Previously this was inside the loop, causing only the last source to be used
        all_sources_text = ''.join(source_texts)
        logger.info(f"Building synthesis prompt with {len(source_texts)} sources ({len(all_sources_text)} chars)")

        prompt = f"""Write a comprehensive paragraph synthesizing ONLY these sources on: "{query}"

Sources:
{all_sources_text}

CRITICAL REQUIREMENTS:
- Write 200-400 words using ONLY information from the provided sources above
- DO NOT add information, statistics, or studies not explicitly in the sources
- Cite sources as [1], [2], etc. - ONLY cite sources that exist above (you have {len(source_texts)} sources)
- If sources are insufficient to fully answer the query, acknowledge this limitation
- Be objective and evidence-based - no speculation
- If you cannot find information in the sources, say "Sources did not address..."

Write the synthesis paragraph now:"""
        
        response = await call_llm(
            messages=[
                {"role": "system", "content": "You are an expert research writer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        # Extract citations
        import re
        citations = {}
        for match in re.finditer(r'\[(\d+)\]', response):
            citation_num = int(match.group(1))
            if 0 < citation_num <= len(sources):
                source = sources[citation_num - 1]
                citations[str(citation_num)] = {
                    "url": source.get("url", ""),
                    "title": source.get("title", "Unknown"),
                    "type": source.get("type", "web")
                }
        
        # Apply spell correction to synthesized text
        corrected_response = correct_spelling(response)

        # Remove any duplicate headings that may have been generated
        corrected_response = remove_duplicate_headings(corrected_response)

        logger.info(f"Synthesis text processed: {len(response)} -> {len(corrected_response)} chars")

        return {
            "text": corrected_response,
            "citations": citations
        }