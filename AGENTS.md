# AGENTS.md - AI Coding Agent Guide

This file provides comprehensive guidance for AI coding agents working with the PageIndex API Service codebase.

## Project Overview

**PageIndex API Service** is a Format-Adaptive RAG (Retrieval-Augmented Generation) API that processes documents (PDF, DOCX, Markdown, TXT) into hierarchical tree indexes and enables semantic search with LLM-based reasoning.

**Core Value Proposition:**
- Uses [PageIndex](https://github.com/VectifyAI/PageIndex) (a vectorless RAG system) instead of traditional embedding-based retrieval
- Achieves 98.7% accuracy on FinanceBench benchmark through reasoning-based document understanding
- Supports both single-document and multi-document (global) search workflows

**Architecture Pattern:**
```
Document Upload → Format Detection → Background Processing → Tree Index → Semantic Search
                                    ↓
                    PDF: Vision Model (VLM) analyzes page images
                    Text: LLM parses markdown structure
```

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.13+ |
| Web Framework | FastAPI (async) |
| Package Manager | uv |
| Document Processing | PageIndex (git submodule) |
| Database | SQLAlchemy + SQLite |
| LLM/VLM | OpenAI API |
| Data Validation | Pydantic v2 |
| Testing | pytest + pytest-asyncio |

## Project Structure

```
pageIndexPractice/
├── lib/
│   ├── __init__.py              # Configures Python path for PageIndex
│   └── pageindex/               # Git submodule (PageIndex core library)
│       ├── pageindex/
│       │   ├── page_index.py    # PDF processing (page_index function)
│       │   └── page_index_md.py # Markdown processing (md_to_tree function)
│       └── ...
├── services/
│   ├── __init__.py
│   ├── pageindex_wrapper.py     # PageIndex integration layer (async wrappers)
│   ├── document_service.py      # Document processing orchestrator
│   ├── search_service.py        # Single-document tree search
│   ├── global_search_service.py # Multi-document search (3-phase pipeline)
│   └── legacy/                  # Old implementations (backup/reference)
│       ├── llm_client.py        # OpenAI LLM client
│       └── vlm_client.py        # OpenAI Vision client (deprecated)
├── models/
│   ├── __init__.py
│   ├── schemas.py               # Pydantic models (Document, TreeNode, etc.)
│   ├── database.py              # SQLAlchemy models and init
│   └── document_store.py        # Async document metadata storage
├── config/
│   └── pageindex_config.yaml    # PageIndex configuration
├── tests/                       # Test suite
├── docs/                        # Documentation
├── data/                        # SQLite database (gitignored)
├── storage/                     # Document files & indexes (gitignored)
├── main.py                      # FastAPI application entry point
├── config.py                    # Pydantic-settings configuration
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

### Submodule Management
```bash
# Initialize submodule (required after fresh clone)
git submodule update --init --recursive

# Update PageIndex to latest
cd lib/pageindex && git pull origin main

# Lock to specific version
cd lib/pageindex && git checkout v1.2.3
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

### PageIndex Configuration (config/pageindex_config.yaml)
```yaml
model: "gpt-4o-2024-11-20"
toc_check_page_num: 20              # Check first N pages for TOC
max_page_num_each_node: 10          # Auto-split nodes exceeding this
max_token_num_each_node: 20000      # Token threshold for subdivision
if_add_node_id: "yes"               # Add node IDs like "0001", "0001.0001"
if_add_node_summary: "yes"          # Generate node summaries
if_add_doc_description: "yes"       # Generate doc descriptions (for global search)
if_add_node_text: "no"              # Don't store full text in tree (too large)
```

## Code Organization & Module Responsibilities

### Service Layer

**PageIndexWrapper** (`services/pageindex_wrapper.py`)
- Wraps PageIndex's sync/async functions for safe use in FastAPI async context
- Handles `page_index()` (PDF) - runs in thread pool to avoid event loop conflicts
- Handles `md_to_tree()` (Markdown) - native async
- Normalizes output format from PageIndex to API format

**DocumentService** (`services/document_service.py`)
- Orchestrates document processing with format-specific strategies
- Routes: PDF → `page_index()`, DOCX → convert to MD → `md_to_tree()`, MD/TXT → `md_to_tree()`
- Manages storage lifecycle: `./storage/{doc_id}/` contains:
  - `original.{ext}` - uploaded file
  - `tree.json` - hierarchical index
  - `pages/` - PDF page images (for PDF only)

**SearchService** (`services/search_service.py`)
- Performs LLM-based reasoning retrieval over single document tree indexes
- Two-phase search: 1) LLM identifies relevant nodes, 2) LLM generates answers
- Format-aware result retrieval (PDF vs text)

**GlobalSearchService** (`services/global_search_service.py`) ⭐ Primary Interface
- **Three-phase pipeline** for multi-document Q&A:
  1. **Document Selection**: LLM analyzes all document summaries, ranks by relevance
  2. **Parallel Retrieval**: Async retrieval from top-k documents simultaneously
  3. **Answer Synthesis**: LLM aggregates multiple sources into coherent answer with citations
- Automatically handles cross-document queries without manual document ID specification

### Models & Schemas

**Key Pydantic Models** (`models/schemas.py`):
- `Document` - tracks upload metadata and processing status
- `TreeNode` - hierarchical structure with id format like "0001", "0001.0001"
- `SearchRequest`/`SearchResponse` - API request/response models
- `GlobalSearchRequest`/`GlobalSearchResponse` - Multi-document search models
- `DocumentStatus` - enum (PENDING, PROCESSING, COMPLETED, FAILED)

**DocumentStore** (`models/document_store.py`):
- SQLite-backed persistent storage for document metadata
- Survives service restarts
- Async CRUD operations via SQLAlchemy

## API Endpoints

### Global Search (Primary Interface)
```
POST /api/v1/search
```
Multi-document global search - automatically selects relevant documents and synthesizes answers.

### Document Management
All endpoints prefixed with `/api/v1/documents/`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/upload` | POST | Upload document, returns `document_id`, starts background processing |
| `/{doc_id}/status` | GET | Check processing status and metadata |
| `/{doc_id}/tree` | GET | Retrieve hierarchical tree structure (requires COMPLETED) |
| `/{doc_id}/search` | POST | Search within specific document |
| `/{doc_id}` | DELETE | Delete document and all associated storage |

### Health Check
```
GET /health
```

## Testing Strategy

### Test Structure
- **Unit tests**: Mocked dependencies, isolated component testing
- **Integration tests**: Marked with `@pytest.mark.integration`, test full flows with mocked OpenAI API

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

with patch('services.legacy.llm_client.AsyncOpenAI') as mock:
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
- **Pydantic v2**: Use `model_config = ConfigDict()` pattern, `model_rebuild()` for self-referencing models
- **Error handling**: Explicit try/except with meaningful error messages
- **Path handling**: Use `pathlib.Path` instead of string paths

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
2. File saved to ./storage/temp_{doc_id}_{filename}
3. Background task → DocumentService.process_document()
4. Format detection → route to _process_pdf() or _process_text()
5. Tree structure saved to {doc_id}/tree.json
6. Status updated: PENDING → PROCESSING → COMPLETED/FAILED
```

### Global Search Flow
```
1. Phase 1: Document Selection
   - Retrieve all COMPLETED documents with summaries
   - LLM analyzes relevance and selects top-k documents
   - Returns ranked candidates with reasoning

2. Phase 2: Parallel Retrieval
   - For each selected document: execute tree-based search
   - Runs in parallel using asyncio.gather()
   - Collects relevant sections from all documents

3. Phase 3: Answer Synthesis
   - Aggregate content from multiple sources
   - LLM synthesizes comprehensive answer
   - Includes source citations (document name + page refs)
```

## Security Considerations

- **API Keys**: Store in `.env` file, never commit to git
- **File Uploads**: Size limits enforced (`MAX_FILE_SIZE`, default 100MB)
- **Path Traversal**: Document IDs are UUIDs, storage paths validated via Path joining
- **SQL Injection**: SQLAlchemy ORM used throughout, no raw SQL

## Common Development Tasks

### Adding New Document Format
1. Update `get_format_from_filename()` in `main.py`
2. Add format to `Document.format` Literal type in `schemas.py`
3. Implement processing method in `DocumentService`
4. Route in `process_document()` method

### Modifying Tree Structure
1. Update `TreeNode` model in `schemas.py`
2. Update prompts in LLMClient to match new structure
3. Update SearchService node parsing logic

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
git submodule update --init --recursive
```

### Import Errors
```bash
# Verify lib/__init__.py configures Python path
python -c "import lib; from pageindex.page_index import page_index"
```

## Related Documentation

- [PageIndex Official Docs](https://docs.pageindex.ai/)
- [PageIndex GitHub](https://github.com/VectifyAI/PageIndex)
- [API Exploration Report](docs/pageindex_api_exploration.md)
- [CLAUDE.md](CLAUDE.md) - Additional Claude Code specific guidance
