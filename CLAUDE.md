# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PageIndex API Service: A Format-Adaptive RAG (Retrieval-Augmented Generation) API that processes documents (PDF, Markdown, TXT) into hierarchical tree indexes and enables semantic search with LLM-based reasoning.

**Core Architecture Pattern:**
```
Document Upload → Format Detection → Background Processing → Tree Index → Semantic Search
                                    ↓
                    PDF: Vision Model (VLM) analyzes page images
                    Text: LLM parses markdown structure
```

## Development Commands

### Environment Setup
```bash
# Install dependencies (using uv)
uv sync

# Setup environment
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
# All tests
uv run pytest -v

# Specific test file
uv run pytest tests/test_document_service.py -v

# Single test
uv run pytest tests/test_main.py::test_upload_document -v

# Skip integration tests
uv run pytest -v -m "not integration"

# Only integration tests
uv run pytest -v -m integration
```

## Architecture & Component Responsibilities

### Service Layer (Format-Adaptive Strategy Pattern)

**DocumentService** (`services/document_service.py`)
- Orchestrates document processing with format-specific strategies
- Routes PDF → VLMClient (vision-based), Text → LLMClient (text-based)
- Manages storage lifecycle: `./storage/{doc_id}/` contains:
  - `original.{ext}` - uploaded file
  - `tree.json` - hierarchical index
  - `pages/` - PDF page images (for PDF only)
  - `content.txt` - full text (for text formats only)

**VLMClient** (`services/vlm_client.py`)
- Uses OpenAI Vision API to analyze PDF page images
- Extracts hierarchical structure from visual layout
- Methods: `build_tree_from_images()`, `search_tree()`, `answer_with_images()`

**LLMClient** (`services/llm_client.py`)
- Uses OpenAI text API to parse markdown/text structure
- Extracts hierarchy from headers and content
- Methods: `build_tree_from_markdown()`, `search_tree()`, `answer_with_text()`

**SearchService** (`services/search_service.py`)
- Performs LLM-based reasoning retrieval over tree indexes
- Two-phase search: 1) LLM identifies relevant nodes, 2) LLM generates answers
- Format-aware: uses VLM for PDFs (with page images), LLM for text

### Data Flow

**Document Processing (Async Background Task):**
1. Upload → `DocumentStore.create()` returns `doc_id`
2. File saved to `./storage/temp_{doc_id}_{filename}`
3. Background task → `DocumentService.process_document()`
4. Format detection → route to `_process_pdf()` or `_process_text()`
5. Tree structure saved to `{doc_id}/tree.json`
6. Status updated: PENDING → PROCESSING → COMPLETED/FAILED

**Search Flow:**
1. Check document status (must be COMPLETED)
2. Load tree from `{doc_id}/tree.json`
3. `SearchService.search()` → LLM reasoning → relevant nodes
4. For each node: retrieve content (images for PDF, text for MD)
5. LLM generates final answer with context

### Models & Schemas

**Key Pydantic Models** (`models/schemas.py`):
- `Document`: tracks upload metadata and processing status
- `TreeNode`: hierarchical structure with id format like "0001", "0001.0001"
- `SearchRequest`/`SearchResponse`: API request/response models
- `DocumentStatus`: enum (PENDING, PROCESSING, COMPLETED, FAILED)

**DocumentStore** (`models/document_store.py`):
- In-memory store (Dict[str, Document])
- Async CRUD operations
- Status lifecycle management

### Testing Strategy

**Test Structure:**
- Unit tests for each component (mocked dependencies)
- Integration tests with mocked OpenAI API calls
- Fixtures handle global service initialization (see `test_main.py`, `test_integration.py`)

**Important Testing Pattern:**
When testing FastAPI endpoints, mock the global services in `main.py`:
```python
import main
main.doc_store = mock_store_instance
main.doc_service = mock_service_instance
```

## Configuration & Environment

**Required Environment Variables** (`.env`):
- `OPENAI_API_KEY` - OpenAI API key (required)
- `OPENAI_MODEL` - Model to use (default: "gpt-4o-mini")
- `STORAGE_PATH` - Document storage directory (default: "./storage")
- `MAX_FILE_SIZE` - Max upload size in bytes (default: 100MB)

**Settings** (`config.py`):
- Uses `pydantic-settings` with `SettingsConfigDict`
- Auto-loads from `.env` file
- Singleton pattern: `settings = Settings()`

## API Endpoints

All endpoints prefixed with `/api/v1/documents/`:

- `POST /upload` - Upload document, returns `document_id`, starts background processing
- `GET /{doc_id}/status` - Check processing status and metadata
- `GET /{doc_id}/tree` - Retrieve hierarchical tree structure (requires COMPLETED)
- `POST /{doc_id}/search` - Search with query, returns ranked results with reasoning
- `DELETE /{doc_id}` - Delete document and all associated storage

## Key Dependencies

- **uv** - Python package manager (replaces pip/venv)
- **FastAPI** - Async web framework with lifespan context manager
- **OpenAI** - Vision and text APIs for document understanding
- **PyMuPDF (fitz)** - PDF to image conversion (200 DPI default)
- **Pydantic v2** - Data validation with `ConfigDict` pattern

## Common Patterns

**Adding New Document Format:**
1. Update `get_format_from_filename()` in `main.py`
2. Add format to `Document.format` Literal type in `schemas.py`
3. Implement processing method in `DocumentService`
4. Route in `process_document()` method

**Modifying Tree Structure:**
1. Update `TreeNode` model in `schemas.py`
2. Update prompts in VLMClient/LLMClient to match new structure
3. Update SearchService node parsing logic

**Testing with OpenAI API:**
- Always mock `AsyncOpenAI` class in tests
- Mock at the module level: `patch('services.vlm_client.AsyncOpenAI')`
- Mock response format: `mock_response.choices[0].message.content = '{"json": "data"}'`
