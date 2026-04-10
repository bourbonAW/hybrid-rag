from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class DocumentStatus(StrEnum):
    """Document processing status enum."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(BaseModel):
    """Document metadata model."""

    id: str = Field(..., description="Document UUID")
    filename: str
    format: Literal["pdf", "md", "docx", "txt"]
    status: DocumentStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    error_message: str | None = None
    # New fields for content deduplication and index tracking
    content_hash: str | None = None
    available_indexes: list[str] = Field(default_factory=list)
    failed_indexes: dict[str, str] = Field(default_factory=dict)
    file_size: int | None = None


class TreeNode(BaseModel):
    """Tree node model representing document structure."""

    id: str = Field(..., description="Node ID like '0001', '0001.001'")
    level: int = Field(..., ge=0)
    title: str
    content: str
    page_start: int
    page_end: int
    children: list["TreeNode"] = []
    summary: str | None = None


TreeNode.model_rebuild()


class SearchResult(BaseModel):
    """Search result item model."""

    node_id: str
    title: str
    content: str
    relevance_score: float
    page_refs: list[int]
    reasoning_path: list[str]


class SearchRequest(BaseModel):
    """Search request model."""

    query: str
    top_k: int = 3
    include_context: bool = True


class SearchResponse(BaseModel):
    """Search response model."""

    query: str
    results: list[SearchResult]
    total_nodes: int
    processing_time_ms: float


class DocumentUploadResponse(BaseModel):
    """Document upload response model."""

    document_id: str
    status: str
    message: str
    is_duplicate: bool = False
    original_document_id: str | None = None


class DocumentStatusResponse(BaseModel):
    """Document status response model."""

    document_id: str
    status: str
    filename: str
    format: str
    created_at: str  # ISO format
    completed_at: str | None = None
    error_message: str | None = None
    content_hash: str | None = None
    available_indexes: list[str] = []
    failed_indexes: dict[str, str] = {}
    file_size: int | None = None


class GlobalSearchRequest(BaseModel):
    """Global search request model."""

    query: str
    top_k_documents: int = 3
    top_k_results_per_doc: int = 2
    strategy: Literal[
        "auto", "pageindex", "lightrag", "hirag", "hybrid", "hybrid_search"
    ] = Field(
        default="auto",
        description=(
            "搜索策略: auto=自动选择, pageindex=仅PageIndex深度分析, "
            "lightrag=仅LightRAG快速检索, hirag=仅HiRAG层次化检索, "
            "hybrid=LightRAG+PageIndex混合策略, hybrid_search=BM25+Vector语义检索"
        ),
    )


class DocumentSource(BaseModel):
    """Document source reference model.

    PageIndex strategy fills: section_title, page_refs, node_id.
    Hybrid Search strategy fills: chunk_index, score, text_preview.
    All strategy-specific fields are optional.
    """

    document_id: str
    document_name: str
    # PageIndex fields
    section_title: str | None = None
    page_refs: list[int] = Field(default_factory=list)
    node_id: str | None = None
    # Hybrid Search fields
    chunk_index: int | None = None
    score: float | None = None
    text_preview: str | None = None


class GlobalSearchResponse(BaseModel):
    """Global search response model."""

    query: str
    final_answer: str
    sources: list[DocumentSource]
    document_selection_reasoning: str
    total_documents_searched: int
    processing_time_ms: float
    # New fields for strategy transparency
    strategy_used: dict[str, str] = Field(default_factory=dict)
    fallback_reasons: list[str] = Field(default_factory=list)
