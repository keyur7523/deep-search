from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from models.db import create_agent_event, create_agent_task
import logging

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """
    Base class for all agents.
    Provides common functionality for thinking, actions, and task creation.
    """
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    async def execute(
        self, 
        payload: Dict[str, Any], 
        task_id: str, 
        run_id: str
    ) -> Dict[str, Any]:
        """
        Execute the agent's task.
        
        Args:
            payload: Task-specific data
            task_id: Current task ID
            run_id: Parent run ID
            
        Returns:
            Result dictionary to store in task
        """
        pass
    
    async def think(
        self, 
        text: str, 
        task_id: str, 
        run_id: str,
        meta: Optional[Dict] = None
    ):
        """Log agent thinking"""
        await create_agent_event(
            run_id,
            task_id,
            self.name,
            "thinking",
            text,
            meta or {}
        )
        logger.info(f"[{self.name}] {text}")
    
    async def action(
        self, 
        text: str, 
        task_id: str, 
        run_id: str,
        meta: Optional[Dict] = None
    ):
        """Log agent action"""
        await create_agent_event(
            run_id,
            task_id,
            self.name,
            "action",
            text,
            meta or {}
        )
        logger.info(f"[{self.name}] ACTION: {text}")
    
    async def result(
        self, 
        text: str, 
        task_id: str, 
        run_id: str,
        meta: Optional[Dict] = None
    ):
        """Log agent result"""
        await create_agent_event(
            run_id,
            task_id,
            self.name,
            "result",
            text,
            meta or {}
        )
        logger.info(f"[{self.name}] RESULT: {text}")
    
    async def create_child_task(
        self,
        run_id: str,
        parent_task_id: str,
        task_type: str,
        payload: Dict[str, Any]
    ) -> str:
        """Create a new child task"""
        new_task_id = await create_agent_task(
            run_id,
            task_type,
            payload,
            parent_id=parent_task_id
        )
        logger.info(f"[{self.name}] Created child task: {task_type} ({new_task_id})")
        return new_task_id