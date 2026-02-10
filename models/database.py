"""
数据库模型定义

使用 SQLAlchemy 定义文档元数据表结构。
"""
from sqlalchemy import create_engine, Column, String, DateTime, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
from models.schemas import DocumentStatus

Base = declarative_base()


class DocumentRecord(Base):
    """文档元数据表"""
    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    filename = Column(String, nullable=False)
    format = Column(String, nullable=False)
    status = Column(SQLEnum(DocumentStatus), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime)
    error_message = Column(String)


def init_db(db_url: str = "sqlite:///./data/documents.db"):
    """
    初始化数据库

    Args:
        db_url: 数据库连接 URL

    Returns:
        SQLAlchemy Engine 对象
    """
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)
    return engine
