# tests/test_hirag_integration.py
"""HiRAG 集成测试.

测试与 FastAPI 服务的集成.
"""

# 确保可以导入 lib 目录下的模块
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from lib.hirag_wrapper import HiRAGWrapper

    HIRAG_AVAILABLE = True
except ImportError:
    HIRAG_AVAILABLE = False
    HiRAGWrapper = None


pytestmark = [
    pytest.mark.skipif(not HIRAG_AVAILABLE, reason="HiRAG not installed"),
    pytest.mark.asyncio(loop_scope="function"),
]


@pytest.mark.integration
async def test_hirag_wrapper_initialization():
    """测试 HiRAG wrapper 初始化."""
    wrapper = HiRAGWrapper()
    await wrapper.initialize()

    # 验证初始化成功
    assert wrapper._rag is not None
    assert wrapper.working_dir.exists()

    await wrapper.close()


async def test_document_processing_with_hirag():
    """测试文档处理流程集成 HiRAG."""
    from models.document_store import DocumentStore
    from services.document_service import DocumentService

    # 创建临时存储
    store = DocumentStore()

    if not HIRAG_AVAILABLE:
        pytest.skip("HiRAG not installed")

    hirag_wrapper = HiRAGWrapper()
    await hirag_wrapper.initialize()

    # 创建带有 HiRAG wrapper 的 DocumentService
    doc_service = DocumentService(
        store=store,
        hirag_wrapper=hirag_wrapper,
    )

    assert doc_service.hirag is not None

    await hirag_wrapper.close()
