# tests/test_lightrag_integration.py
"""LightRAG 集成测试.

测试与 FastAPI 服务的集成.
"""

# 确保可以导入 lib 目录下的模块
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from httpx import AsyncClient

from main import app

try:
    from lib.lightrag import LightRAGWrapper

    LIGHTRAG_AVAILABLE = True
except ImportError:
    LIGHTRAG_AVAILABLE = False
    LightRAGWrapper = None


pytestmark = [
    pytest.mark.skipif(not LIGHTRAG_AVAILABLE, reason="lightrag-hku not installed"),
    pytest.mark.asyncio(loop_scope="function"),
]


@pytest.fixture(scope="function")
async def async_client():
    """Async HTTP client fixture."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.mark.integration
async def test_health_check(async_client):
    """测试健康检查端点."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.integration
async def test_global_search_with_lightrag(async_client):
    """测试使用 LightRAG 策略的全局搜索."""
    # 注意：这需要先上传文档并等待处理完成
    # 这是一个集成测试，需要完整的服务运行

    # 使用 LightRAG 策略搜索
    response = await async_client.post(
        "/api/v1/search",
        json={
            "query": "Test query about technology",
            "strategy": "lightrag",
            "top_k_documents": 3,
            "top_k_results_per_doc": 2,
        },
    )

    # 如果没有文档，应该返回 200 但提示没有相关文档
    assert response.status_code == 200
    data = response.json()
    assert "final_answer" in data


@pytest.mark.integration
async def test_global_search_strategies(async_client):
    """测试不同的搜索策略."""
    strategies = ["auto", "pageindex", "lightrag", "hybrid"]

    for strategy in strategies:
        response = await async_client.post(
            "/api/v1/search", json={"query": "Test query", "strategy": strategy}
        )

        # 所有策略都应该返回 200（即使没有文档）
        assert response.status_code == 200, f"Strategy {strategy} failed"
        data = response.json()
        assert "final_answer" in data


async def test_lightrag_wrapper_initialization():
    """测试 LightRAG wrapper 初始化."""
    if not LIGHTRAG_AVAILABLE:
        pytest.skip("lightrag-hku not installed")

    wrapper = LightRAGWrapper()
    await wrapper.initialize()

    # 验证初始化成功
    assert wrapper._rag is not None
    assert wrapper.working_dir.exists()

    await wrapper.close()


async def test_document_processing_with_lightrag():
    """测试文档处理流程集成 LightRAG."""
    # 这需要 DocumentService 和完整的集成环境
    # 简化测试：验证 DocumentService 可以接受 LightRAG wrapper

    from models.document_store import DocumentStore
    from services.document_service import DocumentService

    if not LIGHTRAG_AVAILABLE:
        pytest.skip("lightrag-hku not installed")

    # 创建临时存储
    import shutil
    import tempfile

    temp_dir = tempfile.mkdtemp()

    try:
        store = DocumentStore()
        lightrag_wrapper = LightRAGWrapper()
        await lightrag_wrapper.initialize()

        # 创建带有 LightRAG wrapper 的 DocumentService
        doc_service = DocumentService(store=store, lightrag_wrapper=lightrag_wrapper)

        assert doc_service.lightrag is not None

        await lightrag_wrapper.close()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
