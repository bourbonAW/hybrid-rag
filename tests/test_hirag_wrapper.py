# tests/test_hirag_wrapper.py
"""HiRAGWrapper 单元测试.

注意：由于 HiRAG 内部使用了复杂的初始化和 event loop，
在同一个测试进程中多次初始化可能会导致问题。
实际运行时的服务不会出现此问题。
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


async def test_initialize():
    """测试初始化."""
    wrapper = HiRAGWrapper()
    assert wrapper._rag is None

    await wrapper.initialize()
    assert wrapper._rag is not None
    assert wrapper.working_dir.exists()

    await wrapper.close()


async def test_error_handling():
    """测试错误处理."""
    # 测试未初始化时的搜索（应该抛出异常）
    uninitialized_wrapper = HiRAGWrapper()

    with pytest.raises(RuntimeError, match="not initialized"):
        await uninitialized_wrapper.search("test query")

    with pytest.raises(RuntimeError, match="not initialized"):
        await uninitialized_wrapper.index_document("test", "content")

    # 清理
    await uninitialized_wrapper.close()


def test_config_loading():
    """测试配置加载."""
    wrapper = HiRAGWrapper()

    # 验证配置已加载
    assert "llm" in wrapper.config
    assert "embedding" in wrapper.config
    assert "storage" in wrapper.config
    assert "retrieval" in wrapper.config

    # 验证工作目录
    assert wrapper.working_dir.exists()
