# Hybrid RAG API Service - Specification

## Overview

**Hybrid RAG** is a Format-Adaptive Retrieval-Augmented Generation (RAG) API service that provides intelligent document processing and multi-strategy semantic search capabilities. Unlike traditional single-approach RAG systems, Hybrid RAG integrates multiple retrieval strategies to optimize for different query types and document characteristics.

### Core Value Proposition

- **Multi-Strategy Retrieval**: Automatically selects optimal retrieval strategy based on query characteristics
- **Format-Agnostic Processing**: Supports PDF, DOCX, Markdown, and TXT with format-specific optimization
- **Hierarchical Understanding**: Combines TOC-tree analysis, entity graphs, and semantic chunking
- **Production-Ready API**: FastAPI-based async service with SQLite persistence

## User Stories

### US-1: Document Upload and Processing
As a user, I want to upload documents in various formats (PDF, DOCX, MD, TXT) so that the system can automatically process and index them for future search.

**Acceptance Criteria:**
- Support PDF, DOCX, Markdown, and TXT formats
- Automatic format detection from file extension
- **Content-based deduplication**: Calculate SHA-256 hash of file content
- If identical content exists, return existing document (don't reprocess)
- Background async processing with status tracking
- Persist document metadata in SQLite database (including content_hash)
- Store original files and generated indexes
- **File size limits**: PDF ≤100MB, DOCX ≤50MB, MD/TXT ≤20MB

### US-2: Multi-Strategy Document Search
As a user, I want to search across all uploaded documents using intelligent strategy selection so that I get the most relevant results for my specific query type.

**Acceptance Criteria:**
- Automatic strategy selection based on query characteristics
- Manual strategy override via API parameter
- Support for 5 search strategies: auto, pageindex, lightrag, hirag, hybrid_search
- **Strategy fallback**: If requested strategy unavailable, fallback to hybrid_search
- Parallel retrieval from multiple documents
- LLM-synthesized answers with source citations
- Response includes `strategy_used` per document for transparency

### US-3: Strategy-Aware Query Routing
As a user, I want the system to automatically route my queries to the most appropriate retrieval strategy so that I don't need to understand the technical differences.

**Acceptance Criteria:**
- Keyword/code queries → Hybrid Search (BM25 + Vector)
- Hierarchical/structural queries → HiRAG
- Short factual queries → LightRAG
- Complex cross-document queries → Hybrid (LightRAG + PageIndex)
- Deep analytical queries → PageIndex

### US-4: Real-time Processing Status
As a user, I want to check the processing status of my uploaded documents so that I know when they are ready for search.

**Acceptance Criteria:**
- Status endpoints: PENDING, PROCESSING, COMPLETED, FAILED
- Document metadata retrieval (filename, format, timestamps)
- Tree structure retrieval for completed documents
- Error message persistence for failed documents

### US-5: Document Management
As a user, I want to delete documents and their associated indexes so that I can manage storage and remove outdated content.

**Acceptance Criteria:**
- Delete document from metadata store
- Remove all associated index files
- Clean up storage directory
- Return confirmation of deletion

## Functional Requirements

### FR-1: Document Processing Pipeline

#### FR-1.1: Format-Specific Text Extraction
- **PDF**: Use PyMuPDF (fitz) for text extraction from page-based documents
- **DOCX**: Use python-docx with intelligent table grouping for Word documents
- **Markdown/TXT**: Direct text reading with encoding detection

#### FR-1.2: Parallel Multi-Index Building
The system shall build multiple indexes in parallel for each document:

| Index Type | Purpose | Trigger Condition |
|------------|---------|-------------------|
| PageIndex | TOC-tree structure for hierarchical navigation | All formats |
| LightRAG | Entity graph for fast factual retrieval | Text length > 1000 chars |
| HiRAG | Hierarchical knowledge graph for complex relationships | All documents |
| Hybrid Search | BM25 + Vector for keyword + semantic search | All documents |

#### FR-1.3: Document Chunking Strategy
- Recursive character-based chunking
- Chunk size: 512 tokens (configurable)
- Overlap: 50 tokens (configurable)
- Separators: Paragraph → Sentence → Word priority

### FR-2: Search Strategy Implementations

#### FR-2.1: PageIndex Strategy
- Parse TOC-tree structure from documents
- LLM-based tree traversal for relevant node identification
- Format-aware content retrieval (page images for PDF, text for others)
- Best for: Deep document analysis, structured content

#### FR-2.2: LightRAG Strategy
- Entity and relation extraction using LLM
- Community detection for entity clustering
- Hybrid retrieval: entity keywords + community summaries
- Best for: Fast factual retrieval, entity-centric queries

#### FR-2.3: HiRAG Strategy
- GMM-based entity clustering into hierarchical communities
- Multi-level knowledge graph (G0, G1, G2...)
- Three-phase retrieval: local + global + bridge
- Best for: Complex hierarchical queries, relationship analysis

#### FR-2.4: Hybrid Search Strategy
- BM25 sparse retrieval for keyword matching
- Dense vector retrieval for semantic similarity
- RRF (Reciprocal Rank Fusion) for result merging
- Best for: Code snippets, terminology, exact phrase matching

#### FR-2.5: Auto Strategy Selection
```python
def select_strategy(query: str) -> str:
    if is_keyword_query(query):      # code, id:, "phrase"
        return "hybrid_search"
    elif is_hierarchical_query(query):  # 层次, 结构, 关系
        return "hirag"
    elif len(query) < 20:            # short factual
        return "lightrag"
    else:                            # default
        return "hybrid_search"
```

### FR-3: API Interface

#### FR-3.1: Document Upload Endpoint
```
POST /api/v1/documents/upload
Content-Type: multipart/form-data

Response: {
  "document_id": "uuid",
  "status": "PROCESSING",
  "message": "Document uploaded and processing started"
}
```

#### FR-3.2: Global Search Endpoint
```
POST /api/v1/search
Content-Type: application/json

Request: {
  "query": "search query",
  "strategy": "auto",  // auto | pageindex | lightrag | hirag | hybrid_search | hybrid
  "top_k_documents": 3,
  "top_k_results_per_doc": 2
}

Response: {
  "query": "search query",
  "final_answer": "synthesized answer",
  "sources": [...],
  "document_selection_reasoning": "...",
  "total_documents_searched": 3,
  "processing_time_ms": 1250
}
```

#### FR-3.3: Status and Management Endpoints
- `GET /api/v1/documents/{doc_id}/status` - Check processing status
- `GET /api/v1/documents/{doc_id}/tree` - Get document tree structure
- `DELETE /api/v1/documents/{doc_id}` - Delete document and indexes
- `GET /health` - Service health check

### FR-4: Storage Architecture

#### FR-4.1: Directory Structure
```
storage/
├── {doc_id}/
│   ├── original.{ext}          # Original uploaded file
│   ├── tree.json               # PageIndex tree structure
│   └── pages/                  # PDF page images (if applicable)
├── lightrag/                   # LightRAG working directory
├── hirag/                      # HiRAG working directory
└── hybrid_search/              # Qdrant vector database
```

#### FR-4.2: Database Schema
- **documents** table: id, filename, format, status, timestamps, error_message
- **Async SQLite** via SQLAlchemy + aiosqlite

## Non-Functional Requirements

### NFR-1: Performance
- Document processing: Async background tasks
- Search response time: < 2s for typical queries
- Concurrent request handling: FastAPI async support
- Embedding model: FastEmbed with local caching

### NFR-2: Scalability
- Per-document collection isolation (Qdrant)
- Modular service architecture
- Optional external service integration (future)

### NFR-3: Code Quality
- Type hints throughout codebase
- ruff linting with strict rules
- mypy static type checking
- pytest async test coverage

### NFR-4: Data Integrity
- **Content Deduplication**: SHA-256 hash for duplicate detection
- **Partial Index Resilience**: Document COMPLETED if ≥1 index succeeds
- **Index Availability Tracking**: Store available vs failed indexes per document

### NFR-5: Resource Limits
- **File Size Limits**: PDF ≤100MB, DOCX ≤50MB, MD/TXT ≤20MB
- Return HTTP 413 for oversized files with clear error message

### NFR-4: Documentation
- API endpoint documentation
- Architecture decision records
- Integration guides for each RAG backend

## Out of Scope

The following features are explicitly out of scope for the current version:

1. **User authentication/authorization** - Single-user deployment assumed
2. **Distributed deployment** - Single-instance service
3. **Real-time collaborative editing** - Read-only document search
4. **Mobile-native applications** - Web API only
5. **Advanced analytics dashboard** - Basic API endpoints only

## Review & Acceptance Checklist

- [ ] Document upload works for all supported formats (PDF, DOCX, MD, TXT)
- [ ] Background processing completes successfully for each format
- [ ] All 5 search strategies produce valid results
- [ ] Auto strategy selection correctly routes queries
- [ ] API endpoints return proper error messages
- [ ] Document deletion cleans up all resources
- [ ] Health check endpoint returns healthy status
- [ ] Code passes ruff and mypy checks
- [ ] Integration tests pass for all strategies
- [ ] Content hash deduplication works correctly
- [ ] Strategy fallback behavior verified
- [ ] Partial index failure handled gracefully
- [ ] File size limits enforced

---

**Spec Version**: 1.0.0  
**Created**: 2025-03-15  
**Status**: Draft
