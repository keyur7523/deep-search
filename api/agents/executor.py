import asyncio
from typing import Dict, Any, Optional
from bson import ObjectId
from models.db import (
    db, 
    get_pending_tasks, 
    update_task_status,
    create_agent_event,
    create_agent_task
)
import logging

logger = logging.getLogger(__name__)

class TaskExecutor:
    """
    Executes agent tasks in proper dependency order.
    Manages task queue and coordinates agent calls.
    """
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.agents: Dict[str, Any] = {}
        self.running = False
        
    def register_agent(self, task_type: str, agent_instance):
        """Register an agent handler for a task type"""
        self.agents[task_type] = agent_instance
        logger.info(f"Registered agent for task type: {task_type}")
    
    async def execute_run(self):
        """
        Main execution loop.
        Continuously processes pending tasks until none remain.
        """
        self.running = True
        logger.info(f"Starting task execution for run: {self.run_id}")
        
        try:
            await self._update_run_status("running")
            
            # Main execution loop
            while self.running:
                # Get tasks that are ready to execute
                pending = await get_pending_tasks(self.run_id, limit=5)
                
                if not pending:
                    # No more tasks - check if we're done
                    all_tasks = await db().agentTasks.find({
                        "runId": ObjectId(self.run_id)
                    }).to_list(length=None)
                    
                    all_done = all(t["status"] == "done" for t in all_tasks)
                    if all_done or not all_tasks:
                        logger.info("All tasks complete")
                        await self._update_run_status("done")
                        break
                    else:
                        # Tasks exist but none are pending - might be stuck
                        logger.warning("Tasks exist but none pending - checking for failures")
                        await asyncio.sleep(2)
                        continue
                
                # Execute pending tasks concurrently (up to 3 at a time)
                batch = pending[:3]
                await asyncio.gather(
                    *[self._execute_task(task) for task in batch],
                    return_exceptions=True
                )
                
                # Small delay between batches
                await asyncio.sleep(0.5)
                
        except Exception as e:
            logger.error(f"Executor error: {e}")
            await self._update_run_status("failed")
        finally:
            self.running = False
    
    async def _execute_task(self, task: Dict[str, Any]):
        """Execute a single task"""
        task_id = str(task["_id"])
        task_type = task["type"]
        
        try:
            logger.info(f"Executing task {task_id} ({task_type})")
            
            # Update to running
            await update_task_status(task_id, "running")
            
            # Get agent handler
            agent = self.agents.get(task_type)
            if not agent:
                raise ValueError(f"No agent registered for task type: {task_type}")
            
            # Execute agent
            result = await agent.execute(task["payload"], task_id, self.run_id)
            
            # Mark as done
            await update_task_status(task_id, "done", result)
            
            logger.info(f"Task {task_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            await update_task_status(task_id, "failed", {"error": str(e)})
            await create_agent_event(
                self.run_id,
                task_id,
                task_type,
                "error",
                f"Task failed: {str(e)}"
            )
    
    async def _update_run_status(self, status: str):
        """Update run document status"""
        await db().runs.update_one(
            {"_id": ObjectId(self.run_id)},
            {"$set": {"status": status}}
        )
    
    def stop(self):
        """Stop execution gracefully"""
        self.running = False