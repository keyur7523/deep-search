# api/test_agentic_pipeline.py

import asyncio
import sys
from models.db import db, init_agent_collections
from agents.research_agentic import start_agentic_run
from bson import ObjectId

async def test_agentic_pipeline():
    """
    Test the complete agentic pipeline with a simple topic.
    """
    print("=" * 60)
    print("Testing Agentic Pipeline")
    print("=" * 60)
    
    try:
        # Initialize collections
        print("\n1. Initializing agent collections...")
        await init_agent_collections()
        print("   ✅ Collections initialized")
        
        # Create test project
        print("\n2. Creating test project...")
        project_doc = {
            "userId": "test-user",
            "title": "History of DNA discovery",
            "goalMd": "Research the history of DNA discovery",
            "maxParagraphs": 3,
            "createdAt": asyncio.get_event_loop().time()
        }
        project_result = await db().projects.insert_one(project_doc)
        project_id = project_result.inserted_id
        print(f"   ✅ Project created: {project_id}")
        
        # Create test run
        print("\n3. Creating test run...")
        run_doc = {
            "projectId": project_id,
            "status": "queued",
            "mode": "agentic",
            "config": {
                "deepMode": False,
                "minCitations": 5,
                "searchProvider": "hybrid"
            },
            "createdAt": asyncio.get_event_loop().time()
        }
        run_result = await db().runs.insert_one(run_doc)
        run_id = str(run_result.inserted_id)
        print(f"   ✅ Run created: {run_id}")
        
        # Start agentic pipeline
        print("\n4. Starting agentic pipeline...")
        print("   (This will take 30-60 seconds)")
        
        await start_agentic_run(run_id)

        # Check events to see what happened
        print("\n📋 Agent Events:")
        events = await db().agentEvents.find(
            {"runId": ObjectId(run_id)}
        ).sort("timestamp", 1).to_list(length=None)
        
        for event in events:
            print(f"   [{event['agent']}] {event['kind']}: {event['text'][:100]}")
        
        # Check task results
        print("\n📋 Task Details:")
        tasks = await db().agentTasks.find(
            {"runId": ObjectId(run_id)}
        ).to_list(length=None)
        
        for task in tasks:
            print(f"   {task['type']}: {task['status']}")
            if task.get('result'):
                result = task['result']
                if task['type'] == 'SEARCH':
                    print(f"      Sources found: {result.get('sources_found', 0)}")
                    print(f"      Source IDs: {len(result.get('source_ids', []))}")
                elif task['type'] == 'STRATEGY':
                    print(f"      Queries created: {result.get('queries_created', 0)}")
                elif task['type'] == 'QUALITY_CHECK':
                    print(f"      Decision: {result.get('decision', 'unknown')}")
                    print(f"      Score: {result.get('score', 0)}")
                elif task['type'] == 'SYNTHESIS':
                    print(f"      Paragraph ID: {result.get('paragraph_id', 'none')}")
        
        # Check results
        print("\n5. Checking results...")
        
        # Check run status
        run = await db().runs.find_one({"_id": ObjectId(run_id)})
        print(f"   Run status: {run.get('status')}")
        
        # Check tasks created
        tasks = await db().agentTasks.find(
            {"runId": ObjectId(run_id)}
        ).to_list(length=None)
        print(f"   ✅ Tasks created: {len(tasks)}")
        for task in tasks:
            print(f"      - {task['type']}: {task['status']}")
        
        # Check events
        events = await db().agentEvents.find(
            {"runId": ObjectId(run_id)}
        ).to_list(length=None)
        print(f"   ✅ Events logged: {len(events)}")
        
        # Check sources
        sources = await db().sources.find(
            {"runId": ObjectId(run_id)}
        ).to_list(length=None)
        print(f"   ✅ Sources found: {len(sources)}")
        
        # Check paragraphs
        paragraphs = await db().paragraphs.find(
            {"runId": ObjectId(run_id)}
        ).to_list(length=None)
        print(f"   ✅ Paragraphs created: {len(paragraphs)}")
        
        if paragraphs:
            for i, para in enumerate(paragraphs):
                text_len = len(para.get("draftMd", ""))
                citations = len(para.get("citations", {}))
                print(f"      - Paragraph {i+1}: {text_len} chars, {citations} citations")
        
        # Check final report
        final_run = await db().runs.find_one({"_id": ObjectId(run_id)})
        if final_run.get("report"):
            report_len = len(final_run["report"])
            print(f"   ✅ Final report: {report_len} chars")
        else:
            print("   ⚠️  No final report generated")
        
        print("\n" + "=" * 60)
        print("Test completed!")
        print("=" * 60)
        
        # Cleanup
        print("\n6. Cleaning up test data...")
        await db().projects.delete_one({"_id": project_id})
        await db().runs.delete_one({"_id": ObjectId(run_id)})
        await db().agentTasks.delete_many({"runId": ObjectId(run_id)})
        await db().agentEvents.delete_many({"runId": ObjectId(run_id)})
        await db().sources.delete_many({"runId": ObjectId(run_id)})
        await db().paragraphs.delete_many({"runId": ObjectId(run_id)})
        print("   ✅ Test data cleaned up")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_agentic_pipeline())
    sys.exit(0 if success else 1)