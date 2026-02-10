import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.global_search_service import GlobalSearchService, GlobalSearchResult
from models.schemas import DocumentStatus


@pytest.fixture
def mock_services():
    doc_store = MagicMock()
    doc_service = MagicMock()
    search_service = MagicMock()
    llm = MagicMock()

    # Mock document store with completed documents
    doc1 = MagicMock(
        id="doc-1",
        filename="financial_report.pdf",
        format="pdf",
        status=DocumentStatus.COMPLETED
    )
    doc2 = MagicMock(
        id="doc-2",
        filename="technical_manual.pdf",
        format="pdf",
        status=DocumentStatus.COMPLETED
    )

    # Mock the async list_completed_documents method
    doc_store.list_completed_documents = AsyncMock(return_value=[doc1, doc2])

    # Mock tree structure
    doc_service.get_tree.return_value = {
        "nodes": [
            {
                "id": "0001",
                "title": "Introduction",
                "content": "This is a test document",
                "page_start": 1,
                "page_end": 1
            }
        ]
    }

    return doc_store, doc_service, search_service, llm


@pytest.mark.asyncio
async def test_global_search_no_documents(mock_services):
    """测试没有文档时的情况"""
    doc_store, doc_service, search_service, llm = mock_services
    doc_store.list_completed_documents = AsyncMock(return_value=[])

    service = GlobalSearchService(doc_store, doc_service, search_service, llm)
    result = await service.search("test query")

    assert isinstance(result, GlobalSearchResult)
    assert "未找到相关文档" in result.final_answer
    assert result.total_documents_searched == 0


@pytest.mark.asyncio
async def test_global_search_document_selection(mock_services):
    """测试文档选择阶段"""
    doc_store, doc_service, search_service, llm = mock_services

    # Mock LLM document selection response
    llm.client.chat.completions.create = AsyncMock(return_value=MagicMock(
        choices=[MagicMock(
            message=MagicMock(
                content='{"thinking": "Analysis", "selected_documents": [{"doc_id": "doc-1", "relevance_score": 0.9, "reasoning": "Most relevant"}]}'
            )
        )]
    ))

    # Mock search service response
    search_service.search = AsyncMock(return_value=MagicMock(
        results=[
            MagicMock(
                node_id="0001",
                title="Test Section",
                content="Test content",
                page_refs=[1],
                reasoning_path=["reasoning"]
            )
        ]
    ))

    service = GlobalSearchService(doc_store, doc_service, search_service, llm)
    result = await service.search("test query", top_k_documents=1)

    assert result.total_documents_searched == 1
    assert len(result.sources) > 0


@pytest.mark.asyncio
async def test_global_search_answer_synthesis(mock_services):
    """测试答案聚合阶段"""
    doc_store, doc_service, search_service, llm = mock_services

    call_count = [0]

    async def mock_create(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call: document selection
            return MagicMock(
                choices=[MagicMock(
                    message=MagicMock(
                        content='{"thinking": "test", "selected_documents": [{"doc_id": "doc-1", "relevance_score": 0.9, "reasoning": "relevant"}]}'
                    )
                )]
            )
        else:
            # Second call: answer synthesis
            return MagicMock(
                choices=[MagicMock(
                    message=MagicMock(
                        content="This is the synthesized answer from multiple documents."
                    )
                )]
            )

    llm.client.chat.completions.create = AsyncMock(side_effect=mock_create)

    search_service.search = AsyncMock(return_value=MagicMock(
        results=[
            MagicMock(
                node_id="0001",
                title="Section",
                content="Content",
                page_refs=[1],
                reasoning_path=["reasoning"]
            )
        ]
    ))

    service = GlobalSearchService(doc_store, doc_service, search_service, llm)
    result = await service.search("test query")

    assert "synthesized answer" in result.final_answer.lower()
    assert result.sources is not None


@pytest.mark.asyncio
async def test_global_search_api_endpoint():
    """测试 API 端点集成"""
    from fastapi.testclient import TestClient
    import main

    # Mock all services
    mock_doc_store = MagicMock()
    mock_doc_store.list_completed_documents = AsyncMock(return_value=[
        MagicMock(
            id="doc-1",
            filename="test.pdf",
            format="pdf",
            status=DocumentStatus.COMPLETED
        )
    ])

    mock_global_search = MagicMock()
    mock_global_search.search = AsyncMock(return_value=MagicMock(
        to_dict=lambda: {
            "query": "test query",
            "final_answer": "Test answer",
            "sources": [],
            "document_selection_reasoning": "Test reasoning",
            "total_documents_searched": 1,
            "processing_time_ms": 100.0
        }
    ))

    main.doc_store = mock_doc_store
    main.global_search_service = mock_global_search

    from main import app
    client = TestClient(app)

    response = client.post(
        "/api/v1/search",
        json={"query": "test query", "top_k_documents": 3}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "test query"
    assert "final_answer" in data
    assert "sources" in data
