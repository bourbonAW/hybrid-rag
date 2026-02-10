import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.mark.integration
class TestIntegration:
    """Integration tests for the full flow."""

    @pytest.fixture
    def client(self):
        # Import main module first
        import main

        with patch('services.vlm_client.VLMClient') as mock_vlm, \
             patch('services.llm_client.LLMClient') as mock_llm:

            # Setup VLM mock
            mock_vlm_instance = MagicMock()
            mock_vlm_instance.build_tree_from_images = AsyncMock(return_value={
                "nodes": [
                    {
                        "id": "0001",
                        "level": 0,
                        "title": "Test Document",
                        "content": "Test content",
                        "page_start": 1,
                        "page_end": 1,
                        "children": []
                    }
                ]
            })
            mock_vlm_instance.search_tree = AsyncMock(return_value={
                "thinking": "Found relevant node",
                "node_list": ["0001"]
            })
            mock_vlm_instance.answer_with_images = AsyncMock(return_value="Test answer")
            mock_vlm.return_value = mock_vlm_instance

            # Setup LLM mock
            mock_llm_instance = MagicMock()
            mock_llm.return_value = mock_llm_instance

            # Initialize global services in main module
            from models.document_store import DocumentStore
            from services.document_service import DocumentService
            from services.search_service import SearchService
            from config import settings

            settings.storage_path.mkdir(parents=True, exist_ok=True)
            main.doc_store = DocumentStore()
            main.doc_service = DocumentService(main.doc_store, settings.openai_api_key)
            main.search_service = SearchService(mock_vlm_instance, mock_llm_instance)

            from main import app
            return TestClient(app)

    def test_full_pdf_flow(self, client, tmp_path):
        """Test complete PDF upload -> process -> search flow."""
        import fitz

        # Create test PDF
        pdf_path = tmp_path / "test.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((100, 100), "This is a test document about AI technology.")
        doc.save(str(pdf_path))
        doc.close()

        # Upload
        with open(pdf_path, "rb") as f:
            response = client.post(
                "/api/v1/documents/upload",
                files={"file": ("test.pdf", f, "application/pdf")}
            )
        assert response.status_code == 202
        doc_id = response.json()["document_id"]

        # Check status (will be pending/processing since it's background)
        response = client.get(f"/api/v1/documents/{doc_id}/status")
        assert response.status_code == 200

        print(f"Integration test passed! Document ID: {doc_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
