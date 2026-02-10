import shutil
import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from config import settings
from models.schemas import DocumentStatus, SearchRequest, SearchResponse
from models.document_store import DocumentStore
from services.document_service import DocumentService
from services.search_service import SearchService
from services.vlm_client import VLMClient
from services.llm_client import LLMClient

# Global instances
doc_store: DocumentStore = None
doc_service: DocumentService = None
search_service: SearchService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup."""
    global doc_store, doc_service, search_service

    settings.storage_path.mkdir(parents=True, exist_ok=True)

    doc_store = DocumentStore()
    doc_service = DocumentService(doc_store, settings.openai_api_key)
    vlm = VLMClient(settings.openai_api_key, settings.openai_model, settings.openai_base_url)
    llm = LLMClient(settings.openai_api_key, settings.openai_model, settings.openai_base_url)
    search_service = SearchService(vlm, llm)

    yield

    # Cleanup if needed


app = FastAPI(
    title="PageIndex API Service",
    description="Format-Adaptive PageIndex RAG API",
    version="1.0.0",
    lifespan=lifespan
)


def get_format_from_filename(filename: str) -> str:
    """Extract format from filename."""
    ext = Path(filename).suffix.lower()
    format_map = {
        ".pdf": "pdf",
        ".md": "md",
        ".markdown": "md",
        ".txt": "txt",
        ".docx": "docx"
    }
    return format_map.get(ext)


@app.post("/api/v1/documents/upload", status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """Upload a document for processing."""
    file_format = get_format_from_filename(file.filename)
    if not file_format:
        raise HTTPException(400, f"Unsupported file format: {file.filename}")

    # Create document record
    doc = await doc_store.create(filename=file.filename, format=file_format)

    # Save uploaded file temporarily
    temp_path = settings.storage_path / f"temp_{doc.id}_{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Process in background
    background_tasks.add_task(
        doc_service.process_document,
        doc.id,
        str(temp_path),
        file_format
    )

    return {
        "document_id": doc.id,
        "status": doc.status.value,
        "message": "Document uploaded and processing started"
    }


@app.get("/api/v1/documents/{doc_id}/status")
async def get_document_status(doc_id: str):
    """Get document processing status."""
    doc = await doc_store.get(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    return {
        "document_id": doc.id,
        "status": doc.status.value,
        "filename": doc.filename,
        "format": doc.format,
        "created_at": doc.created_at.isoformat(),
        "completed_at": doc.completed_at.isoformat() if doc.completed_at else None,
        "error_message": doc.error_message
    }


@app.get("/api/v1/documents/{doc_id}/tree")
async def get_document_tree(doc_id: str):
    """Get document tree structure."""
    doc = await doc_store.get(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    if doc.status != DocumentStatus.COMPLETED:
        raise HTTPException(400, f"Document processing not completed: {doc.status.value}")

    tree = doc_service.get_tree(doc_id)
    if not tree:
        raise HTTPException(404, "Tree structure not found")

    return {"document_id": doc_id, "tree": tree}


@app.post("/api/v1/documents/{doc_id}/search", response_model=SearchResponse)
async def search_document(doc_id: str, request: SearchRequest):
    """Search within a document."""
    doc = await doc_store.get(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    if doc.status != DocumentStatus.COMPLETED:
        raise HTTPException(400, f"Document processing not completed: {doc.status.value}")

    tree = doc_service.get_tree(doc_id)
    if not tree:
        raise HTTPException(404, "Tree structure not found")

    storage_path = settings.storage_path / doc_id

    result = await search_service.search(
        query=request.query,
        tree=tree,
        doc_format=doc.format,
        storage_path=str(storage_path),
        top_k=request.top_k
    )

    return result


@app.delete("/api/v1/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document and its index."""
    doc = await doc_store.get(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    # Delete from store
    await doc_store.delete(doc_id)

    # Delete storage
    storage_dir = settings.storage_path / doc_id
    if storage_dir.exists():
        shutil.rmtree(storage_dir)

    return {"message": "Document deleted successfully"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "pageindex-api"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
