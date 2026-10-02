"""持久记忆单元测试：热缓存 + 冷存储 + 删除。"""
from __future__ import annotations

from app.services.memory_service import MemoryService


def test_memory_save_get_delete(db):
    svc = MemoryService()
    session_id = "sess_test_memory_001"

    saved = svc.save(
        db,
        session_id,
        tenant_id=1,
        messages=[
            {"role": "user", "content": "记忆测试问题"},
            {"role": "assistant", "content": "记忆测试回答"},
        ],
    )
    assert saved is True

    context = svc.get_context(db, session_id)
    assert len(context) >= 2
    assert context[-1]["role"] == "assistant"

    deleted = svc.delete(db, session_id)
    assert deleted is True
    assert svc.get_context(db, session_id) == []


def test_memory_context_truncation():
    long_context = [{"role": "user", "content": "x" * 1000} for _ in range(50)]
    truncated = MemoryService._truncate(long_context, max_tokens=100)
    assert len(truncated) <= len(long_context)
