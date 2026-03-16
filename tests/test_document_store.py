import pytest

from models.document_store import DocumentStore
from models.schemas import DocumentStatus


@pytest.fixture
def store():
    return DocumentStore()


@pytest.mark.asyncio
async def test_create_document(store):
    doc = await store.create(filename="test.pdf", format="pdf")
    assert doc.filename == "test.pdf"
    assert doc.format == "pdf"
    assert doc.status == DocumentStatus.PENDING


@pytest.mark.asyncio
async def test_get_document(store):
    doc = await store.create(filename="test.pdf", format="pdf")
    retrieved = await store.get(doc.id)
    assert retrieved.id == doc.id


@pytest.mark.asyncio
async def test_update_status(store):
    doc = await store.create(filename="test.pdf", format="pdf")
    updated = await store.update_status(doc.id, DocumentStatus.COMPLETED)
    assert updated.status == DocumentStatus.COMPLETED
