import lib  # 配置 Python path for PageIndex
import shutil
import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from config import settings
from models.schemas import (
    DocumentStatus, SearchRequest, SearchResponse,
    GlobalSearchRequest, GlobalSearchResponse
)
from models.document_store import DocumentStore
from services.document_service import DocumentService
from services.search_service import SearchService
from services.global_search_service import GlobalSearchService
from services.legacy.llm_client import LLMClient  # 暂时保留用于 SearchService

# Global instances
doc_store: DocumentStore = None
doc_service: DocumentService = None
search_service: SearchService = None
global_search_service: GlobalSearchService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup."""
    global doc_store, doc_service, search_service, global_search_service

    settings.storage_path.mkdir(parents=True, exist_ok=True)

    doc_store = DocumentStore()
    doc_service = DocumentService(doc_store)  # 不再需要 api_key 参数

    # search_service 和 global_search_service 暂时保留 LLMClient
    # 因为它们只是读取 tree.json，不需要重建逻辑
    llm = LLMClient(settings.openai_api_key, settings.openai_model, settings.openai_base_url)
    search_service = SearchService(None, llm)  # vlm 参数设为 None
    global_search_service = GlobalSearchService(doc_store, doc_service, search_service, llm)

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


@app.post("/api/v1/search", response_model=GlobalSearchResponse)
async def global_search(request: GlobalSearchRequest):
    """
    全局多文档搜索 - 自动选择相关文档并综合答案

    这个端点会：
    1. 从所有文档中选择最相关的文档
    2. 并行检索每个文档的相关内容
    3. 用 LLM 综合生成最终答案

    适用场景：用户不知道答案在哪个文档中
    """
    result = await global_search_service.search(
        query=request.query,
        top_k_documents=request.top_k_documents,
        top_k_results_per_doc=request.top_k_results_per_doc
    )

    return GlobalSearchResponse(**result.to_dict())


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "pageindex-api"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
