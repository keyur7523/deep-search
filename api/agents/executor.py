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
        stuck_check_count = 0
        max_stuck_checks = 30  # Maximum ~60 seconds of waiting before giving up

        try:
            await self._update_run_status("running")

            # Main execution loop
            while self.running:
                # Get tasks that are ready to execute
                pending = await get_pending_tasks(self.run_id, limit=5)

                if not pending:
                    # No more tasks - check if we're done or stuck
                    all_tasks = await db().agentTasks.find({
                        "runId": ObjectId(self.run_id)
                    }).to_list(length=None)

                    if not all_tasks:
                        logger.info("No tasks found - completing run")
                        await self._update_run_status("done")
                        break

                    # Check task statuses
                    done_count = sum(1 for t in all_tasks if t["status"] == "done")
                    failed_count = sum(1 for t in all_tasks if t["status"] == "failed")
                    running_count = sum(1 for t in all_tasks if t["status"] == "running")
                    pending_count = sum(1 for t in all_tasks if t["status"] == "pending")

                    logger.info(f"Task status: done={done_count}, failed={failed_count}, running={running_count}, pending={pending_count}")

                    # All tasks complete
                    if done_count == len(all_tasks):
                        logger.info("All tasks complete")
                        await self._update_run_status("done")
                        break

                    # Some tasks failed - stop execution
                    if failed_count > 0 and running_count == 0 and pending_count == 0:
                        logger.error(f"{failed_count} tasks failed - stopping execution")
                        await self._update_run_status("failed")
                        break

                    # Stuck check: no pending tasks returned but pending tasks exist
                    # This can happen when parent tasks failed
                    if pending_count > 0 and failed_count > 0:
                        logger.error("Pending tasks blocked by failed parent tasks - stopping")
                        await self._update_run_status("failed")
                        break

                    # Safety: prevent infinite loop with stuck check counter
                    stuck_check_count += 1
                    if stuck_check_count >= max_stuck_checks:
                        logger.error(f"Executor stuck for {stuck_check_count * 2}s - forcing exit")
                        await self._update_run_status("failed")
                        break

                    logger.warning(f"No runnable tasks (attempt {stuck_check_count}/{max_stuck_checks}) - waiting...")
                    await asyncio.sleep(2)
                    continue

                # Reset stuck counter when we have work to do
                stuck_check_count = 0

                # Execute pending tasks sequentially to avoid API rate limits
                # (Semantic Scholar and other APIs have strict rate limits)
                for task in pending[:3]:
                    await self._execute_task(task)

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