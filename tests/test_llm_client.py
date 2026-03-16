from unittest.mock import AsyncMock, patch

import pytest
from services.llm_client import LLMClient


@pytest.mark.asyncio
async def test_build_tree_from_markdown():
    with patch("services.llm_client.AsyncOpenAI") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock(message=AsyncMock(content='{"nodes": []}'))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        client = LLMClient(api_key="test-key")
        md_content = "# Title\n\n## Section 1\nContent"
        result = await client.build_tree_from_markdown(md_content)

        assert "nodes" in result


@pytest.mark.asyncio
async def test_search_tree_text():
    with patch("services.llm_client.AsyncOpenAI") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock(message=AsyncMock(content='{"node_list": ["0001"]}'))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        client = LLMClient(api_key="test-key")
        tree = {"nodes": [{"id": "0001", "title": "Test"}]}
        result = await client.search_tree(tree, "test query")

        assert "node_list" in result
