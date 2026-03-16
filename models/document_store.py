"""文档元数据存储.

使用 SQLite 持久化文档元数据，解决服务重启丢失数据的问题。
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import sessionmaker

from models.database import DocumentRecord, init_db
from models.schemas import Document, DocumentStatus


class DocumentStore:
    """文档元数据存储（SQLite 持久化）."""

    def __init__(self, db_url: str = "sqlite:///./data/documents.db"):
        """初始化文档存储.

        Args:
            db_url: 数据库连接 URL
        """
        self.engine = init_db(db_url)
        self.SessionLocal = sessionmaker(bind=self.engine)

    async def create(
        self,
        filename: str,
        format: str,
        content_hash: str | None = None,
        file_size: int | None = None,
    ) -> Document:
        """创建新文档记录.

        Args:
            filename: 文件名
            format: 文件格式（pdf, md, txt）
            content_hash: 内容哈希（可选）
            file_size: 文件大小（可选）

        Returns:
            创建的文档对象
        """
        session = self.SessionLocal()
        try:
            record = DocumentRecord(
                id=str(uuid.uuid4()),
                filename=filename,
                format=format,
                status=DocumentStatus.PENDING,
                content_hash=content_hash,
                file_size=file_size,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return self._to_document(record)
        finally:
            session.close()

    async def get(self, doc_id: str) -> Document | None:
        """获取文档记录.

        Args:
            doc_id: 文档 ID

        Returns:
            文档对象，如果不存在返回 None
        """
        session = self.SessionLocal()
        try:
            record = session.query(DocumentRecord).filter_by(id=doc_id).first()
            return self._to_document(record) if record else None
        finally:
            session.close()

    async def find_by_hash(self, content_hash: str) -> Document | None:
        """通过内容哈希查找文档.

        Args:
            content_hash: SHA-256 内容哈希

        Returns:
            文档对象，如果不存在返回 None
        """
        session = self.SessionLocal()
        try:
            record = session.query(DocumentRecord).filter_by(content_hash=content_hash).first()
            return self._to_document(record) if record else None
        finally:
            session.close()

    async def update_status(
        self,
        doc_id: str,
        status: DocumentStatus,
        error_message: str | None = None,
    ) -> Document | None:
        """更新文档状态.

        Args:
            doc_id: 文档 ID
            status: 新状态
            error_message: 错误信息（如果状态为 FAILED）

        Returns:
            更新后的文档对象，如果不存在返回 None
        """
        session = self.SessionLocal()
        try:
            record = session.query(DocumentRecord).filter_by(id=doc_id).first()
            if record:
                record.status = status
                if error_message:
                    record.error_message = error_message
                if status == DocumentStatus.COMPLETED:
                    record.completed_at = datetime.now(UTC)
                session.commit()
                session.refresh(record)
                return self._to_document(record)
            return None
        finally:
            session.close()

    async def update_indexes(
        self,
        doc_id: str,
        available_indexes: list[str],
        failed_indexes: dict[str, str],
    ) -> Document | None:
        """更新文档索引状态.

        Args:
            doc_id: 文档 ID
            available_indexes: 可用索引列表
            failed_indexes: 失败索引字典 {name: error}

        Returns:
            更新后的文档对象，如果不存在返回 None
        """
        session = self.SessionLocal()
        try:
            record = session.query(DocumentRecord).filter_by(id=doc_id).first()
            if record:
                record.set_available_indexes(available_indexes)
                record.set_failed_indexes(failed_indexes)
                session.commit()
                session.refresh(record)
                return self._to_document(record)
            return None
        finally:
            session.close()

    async def delete(self, doc_id: str) -> bool:
        """删除文档记录.

        Args:
            doc_id: 文档 ID

        Returns:
            是否成功删除
        """
        session = self.SessionLocal()
        try:
            record = session.query(DocumentRecord).filter_by(id=doc_id).first()
            if record:
                session.delete(record)
                session.commit()
                return True
            return False
        finally:
            session.close()

    async def list_completed_documents(self) -> list[Document]:
        """获取所有已完成的文档.

        Returns:
            已完成文档列表
        """
        session = self.SessionLocal()
        try:
            records = session.query(DocumentRecord).filter_by(status=DocumentStatus.COMPLETED).all()
            return [self._to_document(r) for r in records]
        finally:
            session.close()

    def _to_document(self, record: DocumentRecord) -> Document:
        """转换数据库记录为 Pydantic 模型.

        Args:
            record: 数据库记录

        Returns:
            Pydantic Document 对象
        """
        return Document(
            id=record.id,
            filename=record.filename,
            format=record.format,
            status=record.status,
            created_at=record.created_at,
            completed_at=record.completed_at,
            error_message=record.error_message,
            content_hash=record.content_hash,
            available_indexes=record.get_available_indexes(),
            failed_indexes=record.get_failed_indexes(),
            file_size=record.file_size,
        )
