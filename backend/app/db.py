"""数据库引擎与会话管理。

SQLite 文件路径默认 ``backend/data/gateway.db``，启动时由 main.py 负责建表。
``check_same_thread=False`` 允许 FastAPI 线程池内复用连接。
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import DATA_DIR, settings

# 确保数据目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入：提供数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
