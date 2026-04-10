from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from models.schemas import DocumentStatus


@pytest.fixture
def client():
    # Import main to get the app
    import main

    # Create mock instances
    mock_store_instance = MagicMock()
    mock_store_instance.create = AsyncMock(
        return_value=MagicMock(
            id="test-id", filename="test.pdf", format="pdf", status=DocumentStatus.PENDING
        )
    )
    mock_store_instance.find_by_hash = AsyncMock(return_value=None)
    mock_store_instance.get = AsyncMock(
        return_value=MagicMock(
            id="test-id",
            filename="test.pdf",
            format="pdf",
            status=DocumentStatus.COMPLETED,
            created_at=MagicMock(isoformat=lambda: "2025-01-01T00:00:00"),
            completed_at=MagicMock(isoformat=lambda: "2025-01-01T00:01:00"),
            error_message=None,
        )
    )

    # Replace global variables in main module
    main.doc_store = mock_store_instance
    main.doc_service = MagicMock()
    main.search_service = MagicMock()

    from main import app

    return TestClient(app)


def test_upload_document(client):
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
    )
    assert response.status_code == 202
    assert "document_id" in response.json()


def test_get_document_status(client):
    response = client.get("/api/v1/documents/test-id/status")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
