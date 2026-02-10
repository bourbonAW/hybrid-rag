from models.schemas import Document, DocumentStatus, TreeNode, SearchResult
from datetime import datetime


def test_document_creation():
    doc = Document(
        id="test-123",
        filename="test.pdf",
        format="pdf",
        status=DocumentStatus.PENDING
    )
    assert doc.id == "test-123"
    assert doc.format == "pdf"
    assert doc.status == DocumentStatus.PENDING


def test_tree_node_creation():
    node = TreeNode(
        id="0001",
        level=1,
        title="Introduction",
        content="This is the intro",
        page_start=1,
        page_end=2
    )
    assert node.id == "0001"
    assert node.children == []
