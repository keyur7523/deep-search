# api/agents/research_agentic.py

import asyncio
from .executor import TaskExecutor
from .strategy_agent import StrategyAgent
from .search_agent import SearchAgent
from .quality_agent import QualityAgent
from .synthesis_agent import SynthesisAgent
from models.db import db, create_agent_task
from services.text_processing import clean_report_text
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

async def start_agentic_run(run_id: str):
    """
    Entry point for agentic research pipeline.
    
    This creates the initial strategy task and starts the executor.
    """
    logger.info(f"Starting agentic run: {run_id}")
    
    try:
        # Get run and project info
        run = await db().runs.find_one({"_id": ObjectId(run_id)})
        if not run:
            raise ValueError(f"Run not found: {run_id}")
        
        project = await db().projects.find_one({"_id": run["projectId"]})
        if not project:
            raise ValueError(f"Project not found: {run['projectId']}")
        
        topic = project.get("title", "")
        config = run.get("config", {})
        
        # Create initial strategy task
        strategy_task_id = await create_agent_task(
            run_id,
            "STRATEGY",
            {
                "topic": topic,
                "config": config
            }
        )
        
        logger.info(f"Created initial strategy task: {strategy_task_id}")
        
        # Create and configure executor
        executor = TaskExecutor(run_id)
        
        # Register all agents
        executor.register_agent("STRATEGY", StrategyAgent())
        executor.register_agent("SEARCH", SearchAgent())
        executor.register_agent("QUALITY_CHECK", QualityAgent())
        executor.register_agent("SYNTHESIS", SynthesisAgent())
        
        # Execute
        await executor.execute_run()
        
        # After execution, compile final report
        await _compile_final_report(run_id)
        
        logger.info(f"Agentic run complete: {run_id}")
        
    except Exception as e:
        logger.error(f"Agentic run failed: {e}")
        await db().runs.update_one(
            {"_id": ObjectId(run_id)},
            {"$set": {"status": "failed", "error": str(e)}}
        )

async def _compile_final_report(run_id: str):
    """Compile all paragraphs into final report"""

    # Get all paragraphs for this run
    paragraphs = await db().paragraphs.find({
        "runId": ObjectId(run_id)
    }).sort("query", 1).to_list(length=None)

    logger.info(f"Found {len(paragraphs)} paragraphs for run {run_id}")
    for i, para in enumerate(paragraphs):
        logger.info(f"  Paragraph {i+1}: query='{para.get('query', '')[:50]}', chars={len(para.get('draftMd', ''))}")

    if not paragraphs:
        logger.warning(f"No paragraphs found for run {run_id}")
        return
    
    # Combine into markdown report
    report_parts = []
    all_citations = {}
    citation_counter = 1
    
    for para in paragraphs:
        text = para.get("draftMd", "")
        
        # Renumber citations
        import re
        def replace_citation(match):
            nonlocal citation_counter
            old_num = match.group(1)
            para_citations = para.get("citations", {})
            if old_num in para_citations:
                citation = para_citations[old_num]
                all_citations[str(citation_counter)] = citation
                result = f"[{citation_counter}]"
                citation_counter += 1
                return result
            return match.group(0)
        
        text = re.sub(r'\[(\d+)\]', replace_citation, text)
        report_parts.append(text)
    
    # Build final markdown
    final_report = "\n\n".join(report_parts)

    # Add references section
    if all_citations:
        final_report += "\n\n## References\n\n"
        for num, citation in sorted(all_citations.items(), key=lambda x: int(x[0])):
            final_report += f"{num}. {citation.get('title', 'Unknown')} - {citation.get('url', '')}\n"

    # Apply text cleaning: spell-check and remove duplicate headings
    original_length = len(final_report)
    final_report = clean_report_text(final_report)
    logger.info(f"Text cleaning applied: {original_length} -> {len(final_report)} chars")

    # Store report
    await db().runs.update_one(
        {"_id": ObjectId(run_id)},
        {"$set": {
            "report": final_report,
            "citations": all_citations,
            "status": "done"
        }}
    )
    
    logger.info(f"Compiled final report for run {run_id}: {len(final_report)} chars")