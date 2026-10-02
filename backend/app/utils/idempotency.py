"""幂等去重（EX-07）。

业务侧请求携带 ``X-Request-Id``，命中缓存时直接返回首次响应，避免重复计费。
实现：进程内 dict 作为快速命中热缓存 + SQLite ``idempotency_records`` 落盘兜底。
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from ..config import settings


class IdempotencyStore:
    """幂等记录存储。"""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _expiry_iso() -> str:
        return (datetime.now(timezone.utc) + timedelta(seconds=settings.idempotency_ttl_seconds)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    def get(self, key: str) -> str | None:
        """内存命中。"""
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            expires_at, payload = entry
            if expires_at < time.time():
                self._cache.pop(key, None)
                return None
            return payload

    def set(self, key: str, payload: dict[str, Any]) -> None:
        """写入内存缓存。"""
        expires_at = time.time() + settings.idempotency_ttl_seconds
        with self._lock:
            self._cache[key] = (expires_at, json.dumps(payload, ensure_ascii=False))


store = IdempotencyStore()


def lookup_idempotency(db, key: str) -> dict[str, Any] | None:
    """按 X-Request-Id 查找首次响应：先内存后 DB。"""
    from ..models import IdempotencyRecord  # 延迟导入避免循环

    cached = store.get(key)
    if cached is not None:
        return json.loads(cached)

    record = db.query(IdempotencyRecord).filter(IdempotencyRecord.key == key).first()
    if record is None:
        return None
    return json.loads(record.response_json)


def save_idempotency(db, key: str, response: dict[str, Any]) -> None:
    """保存首次响应：先内存后 DB。"""
    from ..models import IdempotencyRecord  # 延迟导入避免循环

    store.set(key, response)
    record = IdempotencyRecord(
        key=key,
        response_json=json.dumps(response, ensure_ascii=False),
        created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        expires_at=store._expiry_iso(),
    )
    db.add(record)
    db.commit()
