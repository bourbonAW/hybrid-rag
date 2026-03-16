"""数据库模型定义.

使用 SQLAlchemy 定义文档元数据表结构。
"""

import json
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String, create_engine
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base

from models.schemas import DocumentStatus

Base = declarative_base()


class JSONEncodedDict:
    """SQLAlchemy 类型装饰器用于 JSON 字段."""

    impl = String

    def process_bind_param(self, value, dialect):
        """Convert Python value to database value.

        Args:
            value: Python value (list or dict)
            dialect: SQL dialect

        Returns:
            JSON string for storage
        """
        if value is not None:
            return json.dumps(value)
        return None

    def process_result_value(self, value, dialect):
        """Convert database value to Python value.

        Args:
            value: JSON string from database
            dialect: SQL dialect

        Returns:
            Python list or dict
        """
        if value is not None:
            return json.loads(value)
        return None


class DocumentRecord(Base):
    """文档元数据表."""

    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    filename = Column(String, nullable=False)
    format = Column(String, nullable=False)
    status = Column(SQLEnum(DocumentStatus), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    completed_at = Column(DateTime)
    error_message = Column(String)

    # New fields for content deduplication and index tracking
    content_hash = Column(String(64), nullable=True, index=True, unique=True)
    available_indexes = Column(String, default="[]")  # JSON encoded list
    failed_indexes = Column(String, default="{}")  # JSON encoded dict
    file_size = Column(Integer, nullable=True)

    def get_available_indexes(self) -> list[str]:
        """Get list of available indexes.

        Returns:
            List of index names that were successfully built.
        """
        if self.available_indexes:
            return json.loads(self.available_indexes)
        return []

    def set_available_indexes(self, indexes: list[str]) -> None:
        """Set available indexes list.

        Args:
            indexes: List of successfully built index names.
        """
        self.available_indexes = json.dumps(indexes)

    def get_failed_indexes(self) -> dict[str, str]:
        """Get dict of failed indexes with error messages.

        Returns:
            Dict mapping index name to error message.
        """
        if self.failed_indexes:
            return json.loads(self.failed_indexes)
        return {}

    def set_failed_indexes(self, indexes: dict[str, str]) -> None:
        """Set failed indexes dict.

        Args:
            indexes: Dict mapping index name to error message.
        """
        self.failed_indexes = json.dumps(indexes)


def init_db(db_url: str = "sqlite:///./data/documents.db"):
    """初始化数据库.

    Args:
        db_url: 数据库连接 URL

    Returns:
        SQLAlchemy Engine 对象
    """
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)
    return engine
