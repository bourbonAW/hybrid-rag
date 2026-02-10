from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import List, Optional, Literal
from enum import Enum


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(BaseModel):
    id: str = Field(..., description="Document UUID")
    filename: str
    format: Literal["pdf", "md", "docx", "txt"]
    status: DocumentStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class TreeNode(BaseModel):
    id: str = Field(..., description="Node ID like '0001', '0001.001'")
    level: int = Field(..., ge=0)
    title: str
    content: str
    page_start: int
    page_end: int
    children: List["TreeNode"] = []
    summary: Optional[str] = None


TreeNode.model_rebuild()


class SearchResult(BaseModel):
    node_id: str
    title: str
    content: str
    relevance_score: float
    page_refs: List[int]
    reasoning_path: List[str]


class SearchRequest(BaseModel):
    query: str
    top_k: int = 3
    include_context: bool = True


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total_nodes: int
    processing_time_ms: float
