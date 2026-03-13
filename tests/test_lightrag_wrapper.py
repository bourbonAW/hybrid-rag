# tests/test_lightrag_wrapper.py
"""
LightRAGWrapper 单元测试

注意：由于 LightRAG 内部使用了 event loop 绑定的锁机制，
在同一个测试进程中多次初始化可能会导致问题。
实际运行时的服务不会出现此问题。
"""

import pytest
import asyncio
from pathlib import Path

# 确保可以导入 lib 目录下的模块
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from lib.lightrag import LightRAGWrapper
    LIGHTRAG_AVAILABLE = True
except ImportError:
    LIGHTRAG_AVAILABLE = False
    LightRAGWrapper = None


pytestmark = [
    pytest.mark.skipif(not LIGHTRAG_AVAILABLE, reason="lightrag-hku not installed"),
    pytest.mark.asyncio(loop_scope="function")
]


@pytest.fixture(scope="session")
def lightrag_wrapper_session():
    """Session-scoped LightRAG wrapper fixture"""
    if not LIGHTRAG_AVAILABLE:
        pytest.skip("lightrag-hku not installed")
    
    # 使用同步方式创建和初始化
    wrapper = LightRAGWrapper()
    asyncio.run(wrapper.initialize())
    yield wrapper
    asyncio.run(wrapper.close())


async def test_initialize():
    """测试初始化"""
    if not LIGHTRAG_AVAILABLE:
        pytest.skip("lightrag-hku not installed")
    
    wrapper = LightRAGWrapper()
    assert wrapper._rag is None
    
    await wrapper.initialize()
    assert wrapper._rag is not None
    
    await wrapper.close()


async def test_error_handling():
    """测试错误处理"""
    if not LIGHTRAG_AVAILABLE:
        pytest.skip("lightrag-hku not installed")
    
    # 测试未初始化时的搜索（应该抛出异常）
    uninitialized_wrapper = LightRAGWrapper()
    
    with pytest.raises(RuntimeError, match="not initialized"):
        await uninitialized_wrapper.search("test query")
    
    with pytest.raises(RuntimeError, match="not initialized"):
        await uninitialized_wrapper.index_document("test", "content")
    
    # 清理
    await uninitialized_wrapper.close()


async def test_config_loading():
    """测试配置加载"""
    if not LIGHTRAG_AVAILABLE:
        pytest.skip("lightrag-hku not installed")
    
    wrapper = LightRAGWrapper()
    
    # 验证配置已加载
    assert "llm" in wrapper.config
    assert "embedding" in wrapper.config
    assert "storage" in wrapper.config
    assert "retrieval" in wrapper.config
    
    # 验证工作目录
    assert wrapper.working_dir.exists()
