from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.schemas import DocumentStatus
from services.document_service import DocumentService


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.update_status = AsyncMock()
    store.update_indexes = AsyncMock()
    return store


@pytest.fixture
def mock_pageindex():
    wrapper = MagicMock()
    wrapper.build_tree_from_pdf = AsyncMock(
        return_value={"nodes": [{"id": "0001", "title": "Test", "content": "c",
                                  "page_start": 1, "page_end": 1, "level": 0, "children": []}]}
    )
    wrapper.build_tree_from_markdown = AsyncMock(
        return_value={"nodes": [{"id": "0001", "title": "Test", "content": "c",
                                  "page_start": 1, "page_end": 1, "level": 0, "children": []}]}
    )
    return wrapper


@pytest.mark.asyncio
async def test_process_pdf_success(mock_store, mock_pageindex, tmp_path):
    """PageIndex succeeds → doc marked COMPLETED with pageindex in available_indexes."""
    import fitz
    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((100, 100), "Test Document")
    doc.save(str(pdf_path))
    doc.close()

    service = DocumentService(store=mock_store, pageindex_wrapper=mock_pageindex)

    with patch("services.document_service.settings") as mock_settings:
        mock_settings.storage_path = tmp_path
        success, available, failed = await service.process_document("test-id", str(pdf_path), "pdf")

    assert success is True
    assert "pageindex" in available
    mock_store.update_status.assert_called_with("test-id", DocumentStatus.COMPLETED)


@pytest.mark.asyncio
async def test_process_md_success(mock_store, mock_pageindex, tmp_path):
    """Markdown processing succeeds."""
    md_path = tmp_path / "test.md"
    md_path.write_text("# Hello\n\nWorld content.")

    service = DocumentService(store=mock_store, pageindex_wrapper=mock_pageindex)

    with patch("services.document_service.settings") as mock_settings:
        mock_settings.storage_path = tmp_path
        success, available, failed = await service.process_document("test-id", str(md_path), "md")

    assert success is True
    assert "pageindex" in available


@pytest.mark.asyncio
async def test_process_all_indexes_fail_marks_failed(mock_store, tmp_path):
    """All indexes fail → doc marked FAILED."""
    bad_pageindex = MagicMock()
    bad_pageindex.build_tree_from_pdf = AsyncMock(side_effect=RuntimeError("API error"))

    import fitz
    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf_path))
    doc.close()

    service = DocumentService(store=mock_store, pageindex_wrapper=bad_pageindex)

    with patch("services.document_service.settings") as mock_settings:
        mock_settings.storage_path = tmp_path
        success, available, failed = await service.process_document("test-id", str(pdf_path), "pdf")

    assert success is False
    assert "pageindex" in failed
    mock_store.update_status.assert_called_with("test-id", DocumentStatus.FAILED, "All indexes failed")
