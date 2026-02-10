# PageIndex API Service

Format-Adaptive RAG API service powered by [PageIndex](https://github.com/VectifyAI/PageIndex) - a reasoning-based document understanding framework that achieves 98.7% accuracy on FinanceBench.

## Features

- 📄 **Multi-format support**: PDF, Markdown, TXT
- 🎯 **PageIndex Integration**: Advanced TOC detection, verification loops, and adaptive tree building
- 🌳 **Hierarchical Tree Index**: Preserves document structure with reasoning-based navigation
- 🔍 **Global Multi-Document Search**: LLM-powered document selection and answer synthesis
- 💾 **Persistent Metadata**: SQLite storage survives service restarts
- 🚀 **Async Processing**: Background document indexing with status tracking

## What's PageIndex?

PageIndex is a **vectorless RAG system** that uses LLM reasoning instead of embedding similarity. Key advantages:
- **TOC-aware**: Detects and uses table of contents for accurate structure extraction
- **Self-verifying**: Validates extracted sections against actual content
- **Adaptive**: Automatically subdivides large sections based on configurable thresholds
- **High accuracy**: 98.7% on FinanceBench benchmark

## Quick Start

### Prerequisites
- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager
- OpenAI API key (or compatible API)

### Installation

```bash
# Clone with submodules
git clone --recursive https://github.com/yourusername/pageIndexPractice.git
cd pageIndexPractice

# Or if already cloned
git submodule update --init --recursive

# Install dependencies
uv sync

# Set environment variables
cp .env.example .env
# Edit .env with your configuration:
# OPENAI_API_KEY=your_key_here
# OPENAI_BASE_URL=https://api.openai.com/v1  # or custom endpoint
# OPENAI_MODEL=gpt-4o-2024-11-20

# Run server
uv run uvicorn main:app --reload
```

The service will:
- Start on `http://localhost:8000`
- Create `data/documents.db` for metadata storage
- Create `storage/` for document files and indexes

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/search` | POST | **🌟 Global search** across all documents (recommended) |
| `/api/v1/documents/upload` | POST | Upload document (PDF/MD/TXT) |
| `/api/v1/documents/{id}/status` | GET | Check processing status |
| `/api/v1/documents/{id}/tree` | GET | Get document tree structure |
| `/api/v1/documents/{id}/search` | POST | Search within a specific document |
| `/api/v1/documents/{id}` | DELETE | Delete document |

## Example Usage

### Global Search (Recommended)
When you have a question but don't know which document contains the answer:

```bash
# Upload multiple documents
curl -X POST -F "file=@report_2023.pdf" http://localhost:8000/api/v1/documents/upload
curl -X POST -F "file=@report_2024.pdf" http://localhost:8000/api/v1/documents/upload

# Global search finds relevant documents automatically
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What were the revenue trends?",
    "top_k_documents": 3,
    "top_k_results_per_doc": 2
  }'
```

**Response includes:**
- Comprehensive answer synthesized from multiple documents
- Source citations (document name + page references)
- Document selection reasoning

### Single Document Workflow

```bash
# 1. Upload document
curl -X POST -F "file=@document.pdf" http://localhost:8000/api/v1/documents/upload
# Returns: {"document_id": "abc-123", "status": "pending"}

# 2. Check status (processing happens in background)
curl http://localhost:8000/api/v1/documents/abc-123/status

# 3. View extracted tree structure
curl http://localhost:8000/api/v1/documents/abc-123/tree

# 4. Search within document
curl -X POST http://localhost:8000/api/v1/documents/abc-123/search \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the main conclusion?"}'
```

## Architecture

### Document Processing Flow
```
PDF Upload → PageIndex page_index()
              ↓
         TOC Detection (3 modes)
              ↓
    Verification & Error Correction
              ↓
     Recursive Subdivision
              ↓
   Tree Structure + Node Summaries
              ↓
      SQLite + JSON Storage
```

### Search Flow
```
User Query
    ↓
Phase 1: Document Selection
  (LLM analyzes all doc summaries)
    ↓
Phase 2: Parallel Retrieval
  (Tree-based search in top-k docs)
    ↓
Phase 3: Answer Synthesis
  (LLM aggregates multi-source content)
    ↓
Final Answer + Citations
```

## Configuration

### PageIndex Configuration
Edit `config/pageindex_config.yaml`:

```yaml
model: "gpt-4o-2024-11-20"
toc_check_page_num: 20              # Check first N pages for TOC
max_page_num_each_node: 10          # Auto-split nodes exceeding this
max_token_num_each_node: 20000      # Token threshold for subdivision
if_add_node_summary: "yes"          # Generate node summaries
if_add_doc_description: "yes"       # Generate doc descriptions (for global search)
```

### Environment Variables
```bash
# Required
OPENAI_API_KEY=your_key_here

# Optional
OPENAI_BASE_URL=https://api.openai.com/v1  # Custom endpoint
OPENAI_MODEL=gpt-4o-2024-11-20             # Model to use
STORAGE_PATH=./storage                      # Document storage
MAX_FILE_SIZE=104857600                     # 100MB limit
```

## Testing

```bash
# Run all tests
uv run pytest -v

# Test PageIndex integration
uv run pytest tests/test_pageindex_import.py -v

# Run integration tests
uv run pytest -v -m integration

# Skip integration tests
uv run pytest -v -m "not integration"
```

## Project Structure

```
pageIndexPractice/
├── lib/
│   └── pageindex/          # Git submodule (PageIndex core)
├── services/
│   ├── pageindex_wrapper.py      # PageIndex integration layer
│   ├── document_service.py       # Document processing orchestrator
│   ├── search_service.py         # Single-document search
│   ├── global_search_service.py  # Multi-document search
│   └── legacy/                   # Old implementations (backup)
├── models/
│   ├── database.py               # SQLAlchemy models
│   ├── document_store.py         # Persistent metadata storage
│   └── schemas.py                # Pydantic models
├── config/
│   └── pageindex_config.yaml     # PageIndex configuration
├── data/                          # SQLite database (gitignored)
├── storage/                       # Document files & indexes (gitignored)
└── tests/
```

## Development

### Built With
- **Python 3.13+** with `uv` for dependency management
- **FastAPI** for async REST API
- **PageIndex** (git submodule) for document understanding
- **SQLAlchemy + SQLite** for metadata persistence
- **OpenAI API** for LLM/VLM inference
- **PyMuPDF** for PDF processing
- **Pydantic** for data validation

### Adding PageIndex Updates

```bash
# Update PageIndex submodule to latest
cd lib/pageindex
git pull origin main
cd ../..
git add lib/pageindex
git commit -m "Update PageIndex submodule"

# Lock to specific version
cd lib/pageindex
git checkout v1.2.3
cd ../..
git add lib/pageindex
git commit -m "Lock PageIndex to v1.2.3"
```

## Performance

- **Tree Building**: Depends on document complexity and LLM API latency
- **Search**: Sub-second for cached trees, 2-5s for LLM reasoning
- **Global Search**: 5-15s depending on number of documents and parallel retrieval

**Optimization Tips:**
- Tree structures are cached in memory after first load
- Use `top_k_documents` parameter to limit document selection
- PageIndex's adaptive subdivision ensures balanced tree depth

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
- [CLAUDE.md](CLAUDE.md) - Guide for Claude Code instances

## License

MIT License

This project uses [PageIndex](https://github.com/VectifyAI/PageIndex) which is also MIT licensed.
