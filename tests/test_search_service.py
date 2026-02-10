import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.search_service import SearchService


@pytest.fixture
def mock_clients():
    vlm = MagicMock()
    llm = MagicMock()
    return vlm, llm


@pytest.mark.asyncio
async def test_search_pdf(mock_clients):
    vlm, llm = mock_clients
    vlm.search_tree = AsyncMock(return_value={
        "thinking": "Found relevant section",
        "node_list": ["0001"]
    })
    vlm.answer_with_images = AsyncMock(return_value="The answer is 42")

    service = SearchService(vlm, llm)

    tree = {
        "nodes": [
            {"id": "0001", "title": "Section 1", "page_start": 1, "page_end": 1}
        ]
    }

    with patch('services.search_service.Path.exists', return_value=True):
        result = await service.search("test query", tree, "pdf", "/storage/test")

    assert result.query == "test query"
    assert len(result.results) > 0


@pytest.mark.asyncio
async def test_search_markdown(mock_clients):
    vlm, llm = mock_clients
    llm.search_tree = AsyncMock(return_value={
        "thinking": "Found relevant section",
        "node_list": ["0001"]
    })
    llm.answer_with_text = AsyncMock(return_value="The answer is 42")

    service = SearchService(vlm, llm)

    tree = {
        "nodes": [
            {"id": "0001", "title": "Section 1", "content": "Test content"}
        ]
    }

    result = await service.search("test query", tree, "md", "/storage/test")

    assert result.query == "test query"
    assert len(result.results) > 0
