import uuid
from typing import Dict, Optional
from models.schemas import Document, DocumentStatus


class DocumentStore:
    def __init__(self):
        self._documents: Dict[str, Document] = {}

    async def create(self, filename: str, format: str) -> Document:
        doc = Document(
            id=str(uuid.uuid4()),
            filename=filename,
            format=format,
            status=DocumentStatus.PENDING
        )
        self._documents[doc.id] = doc
        return doc

    async def get(self, doc_id: str) -> Optional[Document]:
        return self._documents.get(doc_id)

    async def update_status(
        self,
        doc_id: str,
        status: DocumentStatus,
        error_message: Optional[str] = None
    ) -> Optional[Document]:
        doc = self._documents.get(doc_id)
        if doc:
            doc.status = status
            if error_message:
                doc.error_message = error_message
            if status == DocumentStatus.COMPLETED:
                from datetime import datetime, timezone
                doc.completed_at = datetime.now(timezone.utc)
        return doc

    async def delete(self, doc_id: str) -> bool:
        if doc_id in self._documents:
            del self._documents[doc_id]
            return True
        return False
