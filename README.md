# PageIndex API Service

Format-Adaptive PageIndex RAG API service supporting PDF (Vision-based) and Markdown/Text (Text-based).

## Features

- 📄 **Multi-format support**: PDF, Markdown, TXT
- 🧠 **Vision-based RAG**: PDF → page images → VLM understanding
- 📝 **Text-based RAG**: Markdown/TXT → direct text parsing → LLM
- 🌳 **Tree Index**: Hierarchical document structure
- 🔍 **Reasoning Retrieval**: LLM-based tree search
- 🚀 **Async processing**: Background document indexing

## Quick Start

```bash
# Install dependencies (using uv)
uv sync

# Set environment variables
cp .env.example .env
# Edit .env with your OpenAI API key and optionally base URL
# OPENAI_BASE_URL can be customized for OpenAI-compatible APIs

# Run server
uv run uvicorn main:app --reload
```

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
When you don't know which document contains the answer:

```bash
# Global search across all documents
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the main topic?",
    "top_k_documents": 3,
    "top_k_results_per_doc": 2
  }'
```

The system will:
1. **Select** the most relevant documents using LLM reasoning
2. **Retrieve** relevant content from each document in parallel
3. **Synthesize** a comprehensive answer from multiple sources

### Single Document Search
When you know the specific document:

```bash
# Upload PDF
curl -X POST -F "file=@document.pdf" http://localhost:8000/api/v1/documents/upload

# Search within specific document
curl -X POST http://localhost:8000/api/v1/documents/{id}/search \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the main topic?"}'
```

## Architecture

```
PDF → Page Images → VLM → Tree Index
MD/TXT → Text → LLM → Tree Index
              ↓
        Tree Search (LLM reasoning)
              ↓
        Answer Generation
```

## Testing

```bash
# Run all tests
uv run pytest -v

# Run integration tests
uv run pytest -v -m integration
```

## Development

Built with:
- Python 3.13+ with uv for dependency management
- FastAPI for async REST API
- OpenAI API (gpt-4o-mini) for vision and text understanding
- PyMuPDF for PDF to image conversion
- Pydantic for data validation

## License

MIT
