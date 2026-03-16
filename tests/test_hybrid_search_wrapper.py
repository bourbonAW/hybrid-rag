"""HybridSearchWrapper 单元测试."""

import pytest

from lib.hybrid_search import HYBRID_SEARCH_AVAILABLE, HybridSearchWrapper

pytestmark = [
    pytest.mark.skipif(not HYBRID_SEARCH_AVAILABLE, reason="Hybrid Search not installed"),
    pytest.mark.asyncio(loop_scope="function"),
]


@pytest.fixture
async def wrapper(tmp_path):
    """创建测试用的 wrapper 实例."""
    # 创建测试配置
    config_content = """
enabled: true
storage:
  path: "{storage_path}"
  collection_name_template: "doc_{{document_id}}"
chunking:
  chunk_size: 100
  chunk_overlap: 20
  separators: ["\\n\\n", "\\n", ". ", " "]
embedding:
  model: "BAAI/bge-small-en-v1.5"
  dimensions: 384
  batch_size: 32
sparse:
  enabled: true
fusion:
  method: "rrf"
  rrf_k: 60
retrieval:
  top_k_sparse: 5
  top_k_dense: 5
  final_top_k: 3
""".format(storage_path=tmp_path / "hybrid_storage")

    config_path = tmp_path / "test_config.yaml"
    config_path.write_text(config_content)

    w = HybridSearchWrapper(config_path=config_path)
    await w.initialize()
    yield w
    await w.close()


async def test_initialize(wrapper):
    """测试初始化."""
    assert wrapper._client is not None
    assert wrapper._dense_embedder is not None


async def test_chunk_text(wrapper):
    """测试文本分块."""
    # 短文本 - 不分块
    short_text = "This is a short text."
    chunks = wrapper._chunk_text(short_text)
    assert len(chunks) == 1
    assert chunks[0] == short_text

    # 长文本 - 应该分块
    long_text = "This is sentence one. " * 20
    chunks = wrapper._chunk_text(long_text)
    assert len(chunks) > 1
    # 每个块应该不超过 chunk_size
    for chunk in chunks:
        assert len(chunk) <= wrapper.config["chunking"]["chunk_size"]


async def test_index_and_search(wrapper):
    """测试文档索引和搜索."""
    # 索引文档
    doc_text = """
Python is a high-level programming language. It was created by Guido van Rossum.
Python supports multiple programming paradigms including procedural, object-oriented,
and functional programming. Python has a large standard library.
    """.strip()

    result = await wrapper.index_document(
        document_id="test_doc_1",
        text=doc_text,
        metadata={"filename": "test.txt"},
    )

    assert result["status"] == "completed"
    assert result["chunks_count"] > 0
    assert result["document_id"] == "test_doc_1"

    # 语义搜索
    search_result = await wrapper.search(
        query="programming language",
        document_id="test_doc_1",
        top_k=3,
    )

    assert "results" in search_result
    assert search_result["total_results"] > 0
    # 检查结果格式
    first_result = search_result["results"][0]
    assert "text" in first_result
    assert "score" in first_result
    assert "chunk_index" in first_result


async def test_search_not_indexed(wrapper):
    """测试搜索未索引的文档."""
    result = await wrapper.search(
        query="test query",
        document_id="non_existent_doc",
    )

    assert "error" in result
    assert "not indexed" in result["error"]


async def test_delete_document(wrapper):
    """测试删除文档索引."""
    # 先索引文档
    await wrapper.index_document(
        document_id="doc_to_delete",
        text="This document will be deleted.",
    )

    # 删除
    deleted = await wrapper.delete_document("doc_to_delete")
    assert deleted is True

    # 再次删除应该返回 False
    deleted_again = await wrapper.delete_document("doc_to_delete")
    assert deleted_again is False


async def test_keyword_search(wrapper):
    """测试关键词搜索 (BM25)."""
    # 索引包含特定术语的文档
    doc_text = """
The API endpoint for user authentication is POST /api/v1/auth/login.
This endpoint accepts username and password in JSON format.
The response includes a JWT token for subsequent requests.
    """.strip()

    await wrapper.index_document(
        document_id="api_doc",
        text=doc_text,
    )

    # 关键词搜索
    result = await wrapper.search(
        query="API endpoint",
        document_id="api_doc",
        top_k=3,
    )

    assert result["total_results"] > 0
    # 验证返回了相关内容
    texts = [r["text"] for r in result["results"]]
    assert any("API endpoint" in t or "endpoint" in t for t in texts)


async def test_collection_name_formatting(wrapper):
    """测试 collection 名称格式化."""
    # 测试 UUID 格式的 document_id
    doc_id = "550e8400-e29b-41d4-a716-446655440000"
    collection_name = wrapper._get_collection_name(doc_id)
    # 应该将 - 替换为 _
    assert "-" not in collection_name
    assert "_" in collection_name
