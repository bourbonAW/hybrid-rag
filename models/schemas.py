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


class GlobalSearchRequest(BaseModel):
    query: str
    top_k_documents: int = 3
    top_k_results_per_doc: int = 2
    strategy: Literal["auto", "pageindex", "lightrag", "hybrid"] = Field(
        default="auto",
        description="搜索策略: auto=自动选择, pageindex=仅PageIndex深度分析, lightrag=仅LightRAG快速检索, hybrid=混合策略"
    )


class DocumentSource(BaseModel):
    document_id: str
    document_name: str
    section_title: str
    page_refs: List[int]
    node_id: str


class GlobalSearchResponse(BaseModel):
    query: str
    final_answer: str
    sources: List[DocumentSource]
    document_selection_reasoning: str
    total_documents_searched: int
    processing_time_ms: float
