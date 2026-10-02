"""pytest 测试配置：使用临时 SQLite 数据库，启动时建表 + 幂等 seed。"""
from __future__ import annotations

import os
import pathlib
import tempfile

# 必须在导入 app 前设置环境变量，使 Settings 单例指向临时数据库
_TEST_DIR = pathlib.Path(tempfile.mkdtemp(prefix="gateway-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DIR / 'test.db'}"
os.environ["HEALTH_CHECK_INTERVAL_S"] = "3600"  # 测试期间暂停后台健康检查

import pytest
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.seed import SEED_API_KEYS, seed


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    """建表 + 幂等 seed（进程内只执行一次）。"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
    yield


@pytest.fixture()
def db() -> Session:
    """提供独立数据库会话。"""
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def seed_key() -> str:
    return SEED_API_KEYS["客服中心"]


from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    """FastAPI 测试客户端（触发 lifespan：seed + 快照加载）。"""
    with TestClient(app) as c:
        yield c
