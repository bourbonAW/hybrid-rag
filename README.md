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
| `/api/v1/documents/upload` | POST | Upload document (PDF/MD/TXT) |
| `/api/v1/documents/{id}/status` | GET | Check processing status |
| `/api/v1/documents/{id}/tree` | GET | Get document tree structure |
| `/api/v1/documents/{id}/search` | POST | Search document |
| `/api/v1/documents/{id}` | DELETE | Delete document |

## Example Usage

```bash
# Upload PDF
curl -X POST -F "file=@document.pdf" http://localhost:8000/api/v1/documents/upload

# Search document
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
