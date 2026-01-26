# api/models/schemas.py

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime

# ============= Existing Schemas =============

class OutlineItem(BaseModel):
    idx: int
    heading: str
    brief: str

class Citation(BaseModel):
    url: str
    title: str

class ParagraphOut(BaseModel):
    draftMd: str
    citations: Dict[int, Citation]
    quality: float

# ============= NEW: Agent Schemas =============

class AgentModeRequest(BaseModel):
    """Request to set or override agent mode for a run"""
    mode: Literal["simple", "agentic", "auto"] = "auto"

class CreateRunRequest(BaseModel):
    """Request to create a new research run with optional config"""
    projectId: str
    config: Dict[str, Any] = Field(default_factory=dict)
    idempotencyKey: Optional[str] = Field(
        default=None,
        min_length=16,
        max_length=64,
        description="Optional idempotency key to prevent duplicate run creation on retry. "
                    "If provided, the same key will return the same run_id for 24 hours."
    )

class AgentTaskResponse(BaseModel):
    """Response model for agent task data"""
    id: str
    type: str
    status: Literal["pending", "running", "done", "failed"]
    parentId: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime
    attempts: int = 0

class AgentGraphNode(BaseModel):
    """Node in task dependency graph"""
    id: str
    type: str
    status: Literal["pending", "running", "done", "failed"]
    label: str

class AgentGraphEdge(BaseModel):
    """Edge in task dependency graph"""
    source: str
    target: str

class AgentGraphResponse(BaseModel):
    """Full task graph for visualization"""
    nodes: List[AgentGraphNode]
    edges: List[AgentGraphEdge]

class AgentEventResponse(BaseModel):
    """Agent event for streaming to UI"""
    id: str
    agent: str
    kind: Literal["thinking", "action", "result", "error"]
    text: str
    meta: Dict[str, Any]
    timestamp: datetime

class RoutingFactors(BaseModel):
    """Factors that influenced routing decision"""
    topicLength: int
    detectedDomains: List[str]
    deepMode: bool
    minCitations: int
    requireRecent: bool

class RoutingExplanation(BaseModel):
    """Detailed explanation of why a mode was chosen"""
    mode: Literal["simple", "agentic"]
    score: float
    threshold: float
    factors: RoutingFactors
    reasoning: str

class CreateRunResponse(BaseModel):
    """Response when creating a run"""
    runId: str
    mode: Literal["simple", "agentic"]
    routing: RoutingExplanation