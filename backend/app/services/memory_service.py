"""持久记忆：会话上下文（热内存 dict + 冷 SQLite）+ TTL + 用户删除。

EX-08：上下文过长时截断最旧消息；记忆写回失败降级为告警，不阻断主链路。
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..models import ChatSession, MemoryMessage, MemoryPolicy, utcnow


class MemoryService:
    """会话记忆服务（进程内单例）。"""

    def __init__(self) -> None:
        self._hot_cache: dict[str, list[dict]] = {}
        self._lock = threading.Lock()

    def _load_policy(self, db: Session) -> MemoryPolicy:
        policy = db.query(MemoryPolicy).filter(MemoryPolicy.id == 1).first()
        if policy is None:
            policy = MemoryPolicy(id=1, hot_storage="memory", cold_storage="sqlite+vector")
            db.add(policy)
            db.commit()
        return policy

    def get_context(self, db: Session, session_id: str, max_tokens: int | None = None) -> list[dict]:
        """获取会话上下文（热 + 冷合并，按需截断）。"""
        with self._lock:
            hot = list(self._hot_cache.get(session_id, []))
        if hot:
            return self._truncate(hot, max_tokens)

        session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        if session is None:
            return []
        memories = (
            db.query(MemoryMessage)
            .filter(MemoryMessage.session_id == session.id)
            .order_by(MemoryMessage.id.asc())
            .all()
        )
        context = [{"role": m.role, "content": m.content} for m in memories]
        return self._truncate(context, max_tokens)

    @staticmethod
    def _truncate(context: list[dict], max_tokens: int | None) -> list[dict]:
        if max_tokens is None:
            return context
        total = 0
        kept: list[dict] = []
        for msg in reversed(context):
            tokens = max(1, len(msg.get("content", "")) // 4)
            if total + tokens > max_tokens and kept:
                break
            kept.append(msg)
            total += tokens
        kept.reverse()
        return kept

    def save(self, db: Session, session_id: str, tenant_id: int, messages: list[dict]) -> bool:
        """写回一轮对话（user + assistant）到热缓存与冷存储。"""
        session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        if session is None:
            session = ChatSession(
                session_id=session_id,
                tenant_id=tenant_id,
                message_count=0,
                context_tokens=0,
                status="active",
                last_active_at=utcnow(),
                ttl_seconds=86400,
                created_at=utcnow(),
            )
            db.add(session)
            db.flush()

        policy = self._load_policy(db)
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=policy.context_ttl_seconds)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 更新热缓存
        with self._lock:
            self._hot_cache.setdefault(session_id, []).extend(messages)

        # 写冷存储
        try:
            for m in messages:
                db.add(
                    MemoryMessage(
                        session_id=session.id,
                        role=m.get("role", "user"),
                        content=m.get("content", ""),
                        tokens=max(1, len(m.get("content", "")) // 4),
                        storage_tier="hot" if len(self._hot_cache.get(session_id, [])) <= 4 else "cold",
                        created_at=utcnow(),
                        expires_at=expires_at,
                    )
                )
            session.message_count += len(messages)
            session.context_tokens += sum(max(1, len(m.get("content", "")) // 4) for m in messages)
            session.last_active_at = utcnow()
            session.status = "active"
            db.commit()
            return True
        except Exception:  # noqa: BLE001 - 写回失败不阻断主链路（EX-08）
            db.rollback()
            return False

    def delete(self, db: Session, session_id: str) -> bool:
        """用户删除：删除会话及其全部记忆（热 + 冷）。"""
        with self._lock:
            self._hot_cache.pop(session_id, None)
        session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        if session is None:
            return False
        db.query(MemoryMessage).filter(MemoryMessage.session_id == session.id).delete()
        db.delete(session)
        db.commit()
        return True

    def expire_ttl(self, db: Session) -> int:
        """清理过期会话与记忆，返回清理会话数。"""
        policy = self._load_policy(db)
        cutoff = (
            datetime.now(timezone.utc) - timedelta(seconds=policy.context_ttl_seconds)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        expired = db.query(ChatSession).filter(ChatSession.last_active_at < cutoff).all()
        for s in expired:
            db.query(MemoryMessage).filter(MemoryMessage.session_id == s.id).delete()
            s.status = "expired"
            with self._lock:
                self._hot_cache.pop(s.session_id, None)
        db.commit()
        return len(expired)


memory_service = MemoryService()
