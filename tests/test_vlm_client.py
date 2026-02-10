import pytest
from unittest.mock import AsyncMock, patch, mock_open
from services.vlm_client import VLMClient


@pytest.mark.asyncio
async def test_build_tree_from_images(tmp_path):
    # Create a fake image file
    img_path = tmp_path / "page1.jpg"
    img_path.write_bytes(b"fake image data")

    with patch('services.vlm_client.AsyncOpenAI') as mock_client_class:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock(message=AsyncMock(content='{"nodes": []}'))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        client = VLMClient(api_key="test-key")
        result = await client.build_tree_from_images([str(img_path)], total_pages=1)

        assert "nodes" in result


@pytest.mark.asyncio
async def test_search_tree():
    with patch('services.vlm_client.AsyncOpenAI') as mock_client_class:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock(message=AsyncMock(content='{"node_list": ["0001"]}'))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        client = VLMClient(api_key="test-key")
        tree = {"nodes": [{"id": "0001", "title": "Test"}]}
        result = await client.search_tree(tree, "test query")

        assert "node_list" in result
