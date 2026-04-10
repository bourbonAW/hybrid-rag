# AGENTS.md - AI Coding Agent Guide

This file provides comprehensive guidance for AI coding agents working with the Hybrid RAG API Service codebase.

## Project Overview

**Hybrid RAG API Service** is a Multi-Strategy RAG (Retrieval-Augmented Generation) API that processes documents (PDF, DOCX, Markdown, TXT) using 4 different indexing strategies and enables intelligent search with automatic strategy selection.

**Core Value Proposition:**
- **Multi-Strategy Retrieval**: PageIndex (TOC-tree) + LightRAG (entity graph) + HiRAG (hierarchical) + Hybrid Search (BM25+Vector)
- **Automatic Strategy Selection**: Routes queries to optimal retrieval strategy based on query characteristics
- **Format-Adaptive**: Supports PDF, DOCX, Markdown, TXT with format-specific optimization
- **High Accuracy**: Combines multiple retrieval approaches for comprehensive coverage

**Architecture Pattern:**
```
Document Upload → Format Detection → Parallel Multi-Index Building → Unified Search API
                                    ↓
                    PageIndex: TOC-tree structure (S3+S5+S8)
                    LightRAG: Entity graph (S4)
                    HiRAG: Hierarchical knowledge graph (S8)
                    Hybrid Search: BM25 + Dense Vector (S1+S2)
```

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.13+ |
| Web Framework | FastAPI (async) |
| Package Manager | uv |
| Document Processing | PageIndex (git submodule) |
| Vector Database | Qdrant (embedded) |
| Graph Storage | NetworkX |
| Database | SQLAlchemy + SQLite |
| LLM | OpenAI API |
| Local Embedding | FastEmbed (BAAI/bge-small) |
| Data Validation | Pydantic v2 |
| Testing | pytest + pytest-asyncio |

## Project Structure

```
pageIndexPractice/
├── lib/                         # Third-party library wrappers
│   ├── __init__.py              # Configures Python path for submodules
│   ├── pageindex/               # Git submodule (PageIndex core library)
│   │   ├── pageindex/
│   │   │   ├── page_index.py    # PDF processing (page_index function)
│   │   │   └── page_index_md.py # Markdown processing (md_to_tree function)
│   │   └── ...
│   ├── pageindex_wrapper/       # PageIndex integration layer
│   │   ├── __init__.py
│   │   ├── wrapper.py           # Async wrappers for PageIndex
│   │   └── config.yaml
│   ├── lightrag/                # LightRAG wrapper (entity graph RAG)
│   │   ├── __init__.py
│   │   ├── wrapper.py
│   │   └── config.yaml
│   ├── hirag_wrapper/           # HiRAG wrapper (hierarchical RAG)
│   │   ├── __init__.py
│   │   ├── wrapper.py
│   │   └── config.yaml
│   └── hybrid_search/           # Hybrid Search wrapper (BM25 + Vector)
│       ├── __init__.py
│       └── wrapper.py
├── services/
│   ├── __init__.py
│   ├── llm_client.py            # OpenAI LLM client for answer generation
│   ├── document_service.py      # Document processing orchestrator (4-index parallel build)
│   ├── search_service.py        # Single-document tree search
│   └── global_search_service.py # Multi-document search with strategy selection
├── models/
│   ├── __init__.py
│   ├── schemas.py               # Pydantic models (Document, TreeNode, etc.)
│   ├── database.py              # SQLAlchemy models
│   └── document_store.py        # Async document metadata storage
├── tests/                       # Test suite
├── docs/                        # Documentation
├── data/                        # SQLite database (gitignored)
├── storage/                     # Document files & indexes (gitignored)
│   ├── lightrag/                # LightRAG working directory
│   ├── hirag/                   # HiRAG working directory
│   └── hybrid_search/           # Qdrant vector database
├── main.py                      # FastAPI application entry point
├── config.py                    # Pydantic-settings configuration (.env)
└── pyproject.toml               # Project dependencies (uv)
```

## Development Commands

### Environment Setup
```bash
# Install dependencies
uv sync

# Setup environment variables
cp .env.example .env
# Edit .env with OPENAI_API_KEY
```

### Running the Service
```bash
# Development server with auto-reload
uv run uvicorn main:app --reload

# Production
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

### Testing
```bash
# Run all tests
uv run pytest -v

# Run specific test file
uv run pytest tests/test_document_service.py -v

# Run single test
uv run pytest tests/test_main.py::test_upload_document -v

# Skip integration tests (default)
uv run pytest -v -m "not integration"

# Run only integration tests
uv run pytest -v -m integration
```

### Code Quality
```bash
# Format code
uv run ruff check --fix .
uv run ruff format .

# Type check
uv run mypy .

# Run pre-commit hooks
uv run pre-commit run --all-files
```

### Submodule Management
```bash
# Initialize submodules (required after fresh clone)
git submodule update --init --recursive

# Update PageIndex to latest
cd lib/pageindex && git pull origin main

# Update HiRAG to latest
cd lib/hirag && git pull origin main
```

## Configuration

### Environment Variables (.env)
```bash
# Required
OPENAI_API_KEY=your_key_here

# Optional (with defaults)
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
STORAGE_PATH=./storage
MAX_FILE_SIZE=104857600  # 100MB
```

### Wrapper Configurations
Each wrapper in `lib/` has its own `config.yaml`:

**PageIndex** (`lib/pageindex_wrapper/config.yaml`):
```yaml
model: "gpt-4o-2024-11-20"
toc_check_page_num: 20
max_page_num_each_node: 10
max_token_num_each_node: 20000
if_add_node_id: "yes"
if_add_node_summary: "yes"
if_add_doc_description: "yes"
if_add_node_text: "no"
```

**LightRAG** (`lib/lightrag/config.yaml`):
- Embedding: text-embedding-3-large (3072 dims)
- Chunk size: 1200 tokens
- Working dir: `./storage/lightrag`

**HiRAG** (`lib/hirag_wrapper/config.yaml`):
- Embedding: text-embedding-3-large (3072 dims)
- Hierarchical mode enabled
- Working dir: `./storage/hirag`

**Hybrid Search** (`lib/hybrid_search/config.yaml`):
- Dense: BAAI/bge-small-en-v1.5 (384 dims, local)
- Sparse: Qdrant/bm42-all-minilm-l6-v2-attentions (local)
- Chunk size: 512 tokens
- RRF fusion

## Code Organization & Module Responsibilities

### lib/ - Third-Party Library Wrappers

All wrappers provide consistent interface:
- `__init__(config_path=None)` - Initialize with config
- `async initialize()` - Async initialization (if needed)
- `async index_document(doc_id, text, metadata)` - Build index
- `async search(query, ...)` - Execute search
- `async close()` - Cleanup resources

**PageIndexWrapper** (`lib/pageindex_wrapper/`)
- TOC-tree structure for hierarchical documents
- Vision-based PDF processing
- Markdown header parsing
- Output: Tree structure with node IDs like "0001", "0001.0001"

**LightRAGWrapper** (`lib/lightrag/`)
- Entity graph construction
- Community detection
- Hybrid retrieval: local (entity) + global (community)
- Best for: Fast factual retrieval, entity-centric queries

**HiRAGWrapper** (`lib/hirag_wrapper/`)
- Hierarchical knowledge graph (GMM clustering)
- Multi-level communities (G0, G1, G2...)
- Three-phase retrieval: local + global + bridge
- Best for: Complex hierarchical queries

**HybridSearchWrapper** (`lib/hybrid_search/`)
- Dense: BAAI/bge-small-en-v1.5 (local, 384 dims)
- Sparse: BM42 (local, learned BM25)
- RRF fusion (Reciprocal Rank Fusion)
- Best for: Keyword matching, exact phrases

### services/ - Business Logic

**LLMClient** (`services/llm_client.py`)
- OpenAI API client for answer generation
- Used by SearchService and GlobalSearchService
- Not for embedding (wrappers use local models or OpenAI embedding)

**DocumentService** (`services/document_service.py`)
- Orchestrates parallel multi-index building
- For each document, builds all 4 indexes concurrently
- Tracks available/failed indexes per document
- Routes: PDF → PageIndex, DOCX → MD → PageIndex, MD/TXT → PageIndex
- Also triggers LightRAG, HiRAG, Hybrid Search indexing

**SearchService** (`services/search_service.py`)
- Single-document tree search (PageIndex only)
- LLM-based node selection + answer generation

**GlobalSearchService** (`services/global_search_service.py`) ⭐ Primary Interface
- **Strategy Selection**: Auto-routes queries based on characteristics
  - Keyword queries → Hybrid Search
  - Hierarchical queries → HiRAG
  - Short factual → LightRAG
  - Deep analytical → PageIndex
- **Three-phase pipeline**:
  1. Document Selection: LLM ranks documents by relevance
  2. Parallel Retrieval: Execute chosen strategy on top-k docs
  3. Answer Synthesis: LLM aggregates results with citations

### models/ - Data Layer

**Key Pydantic Models** (`models/schemas.py`):
- `Document` - tracks upload metadata, processing status, available_indexes
- `TreeNode` - hierarchical structure with id format like "0001", "0001.0001"
- `SearchRequest`/`SearchResponse` - API request/response models
- `GlobalSearchRequest`/`GlobalSearchResponse` - Multi-document search
- `DocumentStatus` - enum (PENDING, PROCESSING, COMPLETED, FAILED)

**DocumentStore** (`models/document_store.py`):
- SQLite-backed persistent storage
- Tracks: content_hash, available_indexes, failed_indexes
- Async CRUD operations via SQLAlchemy

## API Endpoints

### Global Search (Primary Interface)
```
POST /api/v1/search
```
Multi-document global search with automatic strategy selection.

Request:
```json
{
  "query": "search query",
  "strategy": "auto",
  "top_k_documents": 3,
  "top_k_results_per_doc": 2
}
```

Strategies:
- `auto` - Automatic selection (default)
- `pageindex` - TOC-tree deep analysis
- `lightrag` - Entity graph fast retrieval
- `hirag` - Hierarchical knowledge retrieval
- `hybrid_search` - BM25 + Vector semantic search
- `hybrid` - LightRAG + PageIndex combined

### Document Management
All endpoints prefixed with `/api/v1/documents/`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/upload` | POST | Upload document, returns `document_id`, starts background processing |
| `/{doc_id}/status` | GET | Check processing status and available indexes |
| `/{doc_id}/tree` | GET | Retrieve hierarchical tree structure (requires COMPLETED) |
| `/{doc_id}/search` | POST | Search within specific document |
| `/{doc_id}` | DELETE | Delete document and all associated indexes |

### Health Check
```
GET /health
```

## Testing Strategy

### Test Structure
- **Unit tests**: Mocked dependencies, isolated component testing
- **Integration tests**: Marked with `@pytest.mark.integration`, test full flows

### Important Testing Pattern
When testing FastAPI endpoints, mock the global services in `main.py`:
```python
import main
main.doc_store = mock_store_instance
main.doc_service = mock_service_instance
main.search_service = mock_service_instance
```

### Mocking OpenAI API
Always mock `AsyncOpenAI` class at the module level:
```python
from unittest.mock import patch, AsyncMock

with patch('services.llm_client.AsyncOpenAI') as mock:
    mock_instance = MagicMock()
    mock.return_value = mock_instance
```

## Code Style Guidelines

### Language
- **Comments**: Primarily in Chinese (简体中文)
- **Docstrings**: Chinese with reStructuredText-style Args/Returns
- **Variable names**: Mix of English and Chinese context-dependent

### Patterns
- **Async-first**: All I/O operations use `async`/`await`
- **Type hints**: Use `typing` module (Dict, List, Optional, etc.)
- **Pydantic v2**: Use `model_config = ConfigDict()` pattern
- **Error handling**: Explicit try/except with meaningful error messages
- **Path handling**: Use `pathlib.Path` instead of string paths

### Code Quality Tools

| 工具 | 用途 | 命令 |
|------|------|------|
| **Ruff** | Linter + Formatter | `uv run ruff check .` / `uv run ruff format .` |
| **MyPy** | 类型检查 | `uv run mypy .` |
| **Pre-commit** | Git hooks | `uv run pre-commit install` |

### Example Pattern
```python
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class TreeNode(BaseModel):
    """树节点模型"""
    id: str = Field(..., description="节点 ID like '0001', '0001.001'")
    level: int = Field(..., ge=0)
    title: str
    children: List["TreeNode"] = []

TreeNode.model_rebuild()  # Required for self-referencing
```

## Data Flow

### Document Processing Flow
```
1. Upload → DocumentStore.create() returns doc_id
   - Calculates content_hash for deduplication
   - Checks for duplicate content
2. File saved to ./storage/temp_{doc_id}_{filename}
3. Background task → DocumentService.process_document()
4. Parallel index building:
   - PageIndex: TOC-tree from PDF/Markdown
   - LightRAG: Entity graph
   - HiRAG: Hierarchical graph
   - Hybrid Search: BM25 + Dense vectors
5. Update document with available_indexes/failed_indexes
6. Status: PENDING → PROCESSING → COMPLETED/FAILED
```

### Global Search Flow
```
1. Strategy Selection (if auto)
   - Keyword indicators → hybrid_search
   - Hierarchical keywords → hirag
   - Short query → lightrag
   - Default → hybrid

2. Document Selection
   - Retrieve all COMPLETED documents
   - LLM analyzes summaries, ranks by relevance
   - Returns top-k candidates

3. Parallel Retrieval
   - For each doc: execute selected strategy
   - PageIndex: tree traversal
   - LightRAG/HiRAG: graph search
   - Hybrid Search: BM25+Vector RRF
   - Runs in parallel using asyncio.gather()

4. Answer Synthesis
   - Aggregate content from multiple sources
   - LLM synthesizes comprehensive answer
   - Includes source citations (doc name + page refs)
```

## Storage Architecture

```
storage/
├── {doc_id}/                    # Per-document storage
│   ├── original.{ext}          # Original uploaded file
│   └── tree.json               # PageIndex tree structure
├── lightrag/                   # LightRAG working directory
│   ├── kv_store.json
│   ├── vector_store.json
│   └── graph.pkl
├── hirag/                      # HiRAG working directory
│   ├── graph.pkl
│   └── entities.json
└── hybrid_search/              # Qdrant vector database
    └── qdrant_db/
        └── storage.sqlite
```

## Security Considerations

- **API Keys**: Store in `.env` file, never commit to git
- **File Uploads**: Size limits enforced (`MAX_FILE_SIZE`, default 100MB)
- **Path Traversal**: Document IDs are UUIDs, storage paths validated via Path joining
- **SQL Injection**: SQLAlchemy ORM used throughout, no raw SQL
- **Local Embedding**: FastEmbed models run locally, data never leaves machine

## Common Development Tasks

### Adding New Document Format
1. Update `get_format_from_filename()` in `main.py`
2. Add format to `Document.format` Literal type in `schemas.py`
3. Implement processing method in `DocumentService`
4. Route in `process_document()` method

### Adding New RAG Backend
1. Create `lib/new_wrapper/` directory
2. Implement wrapper class with standard interface
3. Add `config.yaml` for wrapper-specific settings
4. Update `DocumentService` to call new indexer
5. Update `GlobalSearchService` to include in strategy selection

### Adding New API Endpoint
1. Add Pydantic models to `schemas.py` if needed
2. Implement endpoint in `main.py`
3. Add corresponding tests in `tests/`

## Troubleshooting

### Database Issues
```bash
# Reset database (loses all metadata)
rm data/documents.db
# Service will recreate on next startup
```

### Submodule Issues
```bash
# Reinitialize submodule
git submodule deinit -f lib/pageindex
git submodule deinit -f lib/hirag
git submodule update --init --recursive
```

### Import Errors
```bash
# Verify lib/__init__.py configures Python path
python -c "import lib; from pageindex.page_index import page_index"
python -c "import lib; from hirag import HiRAG"
```

### Clear All Data
```bash
# Remove all indexes and metadata
rm -rf storage/*
rm -f data/documents.db
```

## Related Documentation

- [PageIndex Official Docs](https://docs.pageindex.ai/)
- [PageIndex GitHub](https://github.com/VectifyAI/PageIndex)
- [HiRAG GitHub](https://github.com/hhy-huang/HiRAG)
- [LightRAG GitHub](https://github.com/HKUDS/LightRAG)
- [API Exploration Report](docs/pageindex_api_exploration.md)
- [Chunking Strategy Mapping](docs/chunking_strategy_mapping.md)
- [CLAUDE.md](CLAUDE.md) - Additional Claude Code specific guidance
