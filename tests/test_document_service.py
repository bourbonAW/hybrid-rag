from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.schemas import DocumentStatus
from services.document_service import DocumentService


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.create = AsyncMock(
        return_value=MagicMock(
            id="test-id", filename="test.pdf", format="pdf", status=DocumentStatus.PENDING
        )
    )
    store.update_status = AsyncMock()
    return store


@pytest.mark.asyncio
async def test_process_pdf(mock_store, tmp_path):
    with (
        patch("services.document_service.extract_pdf_pages") as mock_extract,
        patch("services.document_service.VLMClient") as mock_vlm,
    ):
        mock_extract.return_value = {1: "page1.jpg"}
        mock_vlm.return_value.build_tree_from_images = AsyncMock(
            return_value={"nodes": [{"id": "0001", "title": "Test"}]}
        )

        service = DocumentService(mock_store, "test-key")

        # Create a test PDF
        import fitz

        pdf_path = tmp_path / "test.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((100, 100), "Test")
        doc.save(str(pdf_path))
        doc.close()

        result = await service.process_document("test-id", str(pdf_path), "pdf")

        assert result is True
        mock_store.update_status.assert_called()
