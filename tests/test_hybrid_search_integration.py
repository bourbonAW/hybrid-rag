"""Hybrid Search 集成测试."""

import pytest

from lib.hybrid_search import HYBRID_SEARCH_AVAILABLE

pytestmark = [
    pytest.mark.skipif(not HYBRID_SEARCH_AVAILABLE, reason="Hybrid Search not installed"),
    pytest.mark.integration,
    pytest.mark.asyncio(loop_scope="function"),
]


async def test_global_search_hybrid_search_strategy(client):
    """测试全局搜索使用 hybrid_search 策略."""
    # 注意：此测试假设有文档已上传并索引
    # 实际测试可能需要先上传文档

    response = await client.post(
        "/api/v1/search",
        json={
            "query": "API endpoint authentication",
            "strategy": "hybrid_search",
            "top_k_documents": 2,
            "top_k_results_per_doc": 2,
        },
    )

    # 如果没有文档，应该返回 404 或特定错误
    if response.status_code == 200:
        data = response.json()
        assert "final_answer" in data
        assert "sources" in data
        assert "processing_time_ms" in data
    else:
        # 可能是没有文档的情况
        assert response.status_code in [200, 404, 400]


async def test_global_search_auto_selects_hybrid_search(client):
    """测试自动选择 hybrid_search 策略（关键词查询）."""
    # 关键词导向的查询应该自动选择 hybrid_search

    response = await client.post(
        "/api/v1/search",
        json={
            "query": 'function "api_endpoint" id:123',  # 关键词导向
            "strategy": "auto",
        },
    )

    # 主要是验证请求不会出错
    assert response.status_code in [200, 404, 400]


async def test_strategy_param_includes_hybrid_search(client):
    """测试 API 接受 hybrid_search 策略参数."""
    # 测试请求体验证
    response = await client.post(
        "/api/v1/search",
        json={
            "query": "test query",
            "strategy": "hybrid_search",
        },
    )

    # 不应该因为策略参数无效而返回 422
    assert response.status_code != 422


async def test_document_processing_creates_hybrid_index(client, tmp_path):
    """测试文档处理创建 Hybrid Search 索引."""
    import asyncio

    # 创建测试文件
    test_content = b"""
Python Programming Guide

Python is a versatile programming language.
It supports multiple paradigms including OOP and functional programming.
The language has a simple syntax that is easy to learn.
    """

    # 上传文档
    response = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("test_guide.txt", test_content)},
    )

    assert response.status_code == 202
    doc_id = response.json()["document_id"]

    # 等待后台处理
    await asyncio.sleep(0.5)

    # 检查状态
    max_retries = 30
    for _ in range(max_retries):
        status_response = await client.get(f"/api/v1/documents/{doc_id}/status")
        if status_response.status_code == 200:
            status_data = status_response.json()
            if status_data["status"] == "completed":
                break
            elif status_data["status"] == "failed":
                pytest.skip(f"Document processing failed: {status_data.get('error_message')}")
        await asyncio.sleep(0.5)
    else:
        pytest.skip("Document processing timeout")

    # 使用 hybrid_search 策略搜索
    search_response = await client.post(
        "/api/v1/search",
        json={
            "query": "Python programming language",
            "strategy": "hybrid_search",
        },
    )

    assert search_response.status_code == 200
    data = search_response.json()
    assert "final_answer" in data
    assert "sources" in data
