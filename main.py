import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile

from config import settings
from models.document_store import DocumentStore
from models.schemas import (
    DocumentStatus,
    GlobalSearchRequest,
    GlobalSearchResponse,
    SearchRequest,
    SearchResponse,
)
from services.document_service import DocumentService, calculate_content_hash
from services.global_search_service import GlobalSearchService
from services.llm_client import LLMClient
from services.search_service import SearchService

# Import LightRAG wrapper
try:
    from lib.lightrag import LightRAGWrapper

    LIGHTRAG_AVAILABLE = True
except ImportError:
    LIGHTRAG_AVAILABLE = False
    LightRAGWrapper = None

# Import HiRAG wrapper
try:
    from lib.hirag_wrapper import HiRAGWrapper

    HIRAG_AVAILABLE = True
except ImportError:
    HIRAG_AVAILABLE = False
    HiRAGWrapper = None

# Import Hybrid Search wrapper
try:
    from lib.hybrid_search import HybridSearchWrapper

    HYBRID_SEARCH_AVAILABLE = True
except ImportError:
    HYBRID_SEARCH_AVAILABLE = False
    HybridSearchWrapper = None

# Global instances
doc_store: DocumentStore = None
doc_service: DocumentService = None
search_service: SearchService = None
global_search_service: GlobalSearchService = None
lightrag_wrapper = None
hirag_wrapper = None
hybrid_search_wrapper = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup."""
    global \
        doc_store, \
        doc_service, \
        search_service, \
        global_search_service, \
        lightrag_wrapper, \
        hirag_wrapper, \
        hybrid_search_wrapper

    settings.storage_path.mkdir(parents=True, exist_ok=True)

    doc_store = DocumentStore()

    # 初始化 LightRAG wrapper（如果可用）
    if LIGHTRAG_AVAILABLE:
        try:
            lightrag_wrapper = LightRAGWrapper()
            await lightrag_wrapper.initialize()
            print("[Startup] LightRAG initialized successfully")
        except Exception as e:
            print(f"[Startup] LightRAG initialization failed: {e}")
            lightrag_wrapper = None
    else:
        print("[Startup] LightRAG not available")

    # 初始化 HiRAG wrapper（如果可用）
    if HIRAG_AVAILABLE:
        try:
            hirag_wrapper = HiRAGWrapper()
            await hirag_wrapper.initialize()
            print("[Startup] HiRAG initialized successfully")
        except Exception as e:
            print(f"[Startup] HiRAG initialization failed: {e}")
            hirag_wrapper = None
    else:
        print("[Startup] HiRAG not available")

    # 初始化 Hybrid Search wrapper（如果可用）
    if HYBRID_SEARCH_AVAILABLE:
        try:
            hybrid_search_wrapper = HybridSearchWrapper()
            await hybrid_search_wrapper.initialize()
            print("[Startup] Hybrid Search initialized successfully")
        except Exception as e:
            print(f"[Startup] Hybrid Search initialization failed: {e}")
            hybrid_search_wrapper = None
    else:
        print("[Startup] Hybrid Search not available")

    # 创建 DocumentService，传入 wrapper
    doc_service = DocumentService(
        store=doc_store,
        lightrag_wrapper=lightrag_wrapper,
        hirag_wrapper=hirag_wrapper,
        hybrid_search_wrapper=hybrid_search_wrapper,
    )

    # search_service 和 global_search_service 初始化
    llm = LLMClient(settings.openai_api_key, settings.openai_model, settings.openai_base_url)
    search_service = SearchService(None, llm)  # vlm 参数设为 None
    global_search_service = GlobalSearchService(
        doc_store=doc_store,
        doc_service=doc_service,
        search_service=search_service,
        llm=llm,
        lightrag_wrapper=lightrag_wrapper,
        hirag_wrapper=hirag_wrapper,
        hybrid_search_wrapper=hybrid_search_wrapper,
    )

    yield

    # Cleanup
    if lightrag_wrapper:
        await lightrag_wrapper.close()
    if hirag_wrapper:
        await hirag_wrapper.close()
    if hybrid_search_wrapper:
        await hybrid_search_wrapper.close()


app = FastAPI(
    title="PageIndex API Service",
    description="Format-Adaptive PageIndex RAG API",
    version="1.0.0",
    lifespan=lifespan,
)


def get_format_from_filename(filename: str) -> str:
    """Extract format from filename."""
    ext = Path(filename).suffix.lower()
    format_map = {".pdf": "pdf", ".md": "md", ".markdown": "md", ".txt": "txt", ".docx": "docx"}
    return format_map.get(ext)


# File size limits (bytes)
MAX_FILE_SIZES = {
    "pdf": 100 * 1024 * 1024,    # 100MB
    "docx": 50 * 1024 * 1024,    # 50MB
    "md": 20 * 1024 * 1024,      # 20MB
    "txt": 20 * 1024 * 1024,     # 20MB
}


@app.post("/api/v1/documents/upload", status_code=202)
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Upload a document for processing."""
    file_format = get_format_from_filename(file.filename)
    if not file_format:
        raise HTTPException(400, f"Unsupported file format: {file.filename}")

    # Check file size limit
    max_size = MAX_FILE_SIZES.get(file_format, 20 * 1024 * 1024)
    content = await file.read()
    file_size = len(content)

    if file_size > max_size:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "File too large",
                "file_format": file_format,
                "max_size_mb": max_size // (1024 * 1024),
                "actual_size_mb": round(file_size / (1024 * 1024), 2),
            }
        )

    # Calculate content hash for deduplication
    content_hash = calculate_content_hash(content)

    # Check for duplicate content
    existing_doc = await doc_store.find_by_hash(content_hash)
    if existing_doc:
        return {
            "document_id": existing_doc.id,
            "status": existing_doc.status.value,
            "message": "Document already exists (content hash match)",
            "is_duplicate": True,
            "original_document_id": existing_doc.id,
        }

    # Create new document record with hash
    doc = await doc_store.create(
        filename=file.filename,
        format=file_format,
        content_hash=content_hash,
        file_size=file_size,
    )

    # Save uploaded file temporarily
    temp_path = settings.storage_path / f"temp_{doc.id}_{file.filename}"
    with open(temp_path, "wb") as buffer:
        buffer.write(content)

    # Process in background
    background_tasks.add_task(
        doc_service.process_document,
        doc.id,
        str(temp_path),
        file_format,
        content_hash,
        file_size,
    )

    return {
        "document_id": doc.id,
        "status": doc.status.value,
        "message": "Document uploaded and processing started",
        "is_duplicate": False,
        "original_document_id": None,
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
        "error_message": doc.error_message,
        "content_hash": doc.content_hash,
        "available_indexes": doc.available_indexes,
        "failed_indexes": doc.failed_indexes,
        "file_size": doc.file_size,
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
        top_k=request.top_k,
    )

    return result


@app.delete("/api/v1/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document and its index from all backends."""
    doc = await doc_store.get(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    available = doc.available_indexes or []

    # Delete from store (SQLite)
    await doc_store.delete(doc_id)

    # Delete file storage
    storage_dir = settings.storage_path / doc_id
    if storage_dir.exists():
        shutil.rmtree(storage_dir)

    # Delete from backend indexes that were built for this document
    if "lightrag" in available and lightrag_wrapper:
        try:
            await lightrag_wrapper.delete_document(doc_id)
        except Exception as e:
            print(f"[Delete] LightRAG cleanup failed for {doc_id}: {e}")

    if "hirag" in available and hirag_wrapper:
        try:
            await hirag_wrapper.delete_document(doc_id)
        except Exception as e:
            print(f"[Delete] HiRAG cleanup failed for {doc_id}: {e}")

    if "hybrid_search" in available and hybrid_search_wrapper:
        try:
            await hybrid_search_wrapper.delete_document(doc_id)
        except Exception as e:
            print(f"[Delete] HybridSearch cleanup failed for {doc_id}: {e}")

    return {"message": "Document deleted successfully"}


@app.post("/api/v1/search", response_model=GlobalSearchResponse)
async def global_search(request: GlobalSearchRequest):
    """全局多文档搜索 - 自动选择相关文档并综合答案.

    这个端点会：
    1. 从所有文档中选择最相关的文档
    2. 并行检索每个文档的相关内容
    3. 用 LLM 综合生成最终答案

    适用场景：用户不知道答案在哪个文档中

    策略 (strategy):
    - "auto": 自动选择（默认）
    - "pageindex": 仅使用 PageIndex（深度分析）
    - "lightrag": 仅使用 LightRAG（快速检索）
    - "hybrid": LightRAG + PageIndex 混合策略
    - "hybrid_search": BM25 + Vector 语义混合检索
    """
    # 获取策略参数（如果请求模型支持）
    strategy = request.strategy

    result = await global_search_service.search(
        query=request.query,
        top_k_documents=request.top_k_documents,
        top_k_results_per_doc=request.top_k_results_per_doc,
        strategy=strategy,
    )

    return GlobalSearchResponse(**result.to_dict())


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "pageindex-api"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
