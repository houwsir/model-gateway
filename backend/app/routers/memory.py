"""持久记忆：summary/policy/sessions/messages/删除。"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ChatSession, MemoryMessage, MemoryPolicy, Tenant, utcnow
from ..schemas import AppError, MemoryPolicyUpdate, ok
from ..services.memory_service import memory_service

router = APIRouter(prefix="/memory", tags=["memory"])
Db = Annotated[Session, Depends(get_db)]


def _policy_dict(p: MemoryPolicy) -> dict:
    return {
        "hot_storage": p.hot_storage,
        "cold_storage": p.cold_storage,
        "context_ttl_seconds": p.context_ttl_seconds,
        "rag_enabled": bool(p.rag_enabled),
        "user_delete_enabled": bool(p.user_delete_enabled),
        "pii_mask_enabled": bool(p.pii_mask_enabled),
        "auto_expire_enabled": bool(p.auto_expire_enabled),
        "audit_enabled": bool(p.audit_enabled),
    }


@router.get("/summary")
def summary(db: Db):
    active_sessions = db.query(ChatSession).filter(ChatSession.status == "active").count()
    return ok(
        {
            "active_sessions": active_sessions,
            "active_delta_pct": 8.2,
            "storage_gb": 86,
            "storage_delta_gb": 12,
            "context_hit_rate": 96.3,
        }
    )


@router.get("/policy")
def get_policy(db: Db):
    p = memory_service._load_policy(db)
    return ok(_policy_dict(p))


@router.put("/policy")
def update_policy(db: Db, body: MemoryPolicyUpdate):
    p = memory_service._load_policy(db)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    p.updated_at = utcnow()
    db.commit()
    db.refresh(p)
    return ok(_policy_dict(p))


@router.get("/sessions")
def list_sessions(db: Db, search: str = Query(default="")):
    q = db.query(ChatSession)
    if search:
        q = q.filter(ChatSession.session_id.contains(search))
    sessions = q.order_by(ChatSession.last_active_at.desc()).all()
    items = []
    for s in sessions:
        tenant = db.query(Tenant).filter(Tenant.id == s.tenant_id).first()
        items.append(
            {
                "session_id": s.session_id,
                "tenant_name": tenant.name if tenant else "",
                "message_count": s.message_count,
                "context_tokens": s.context_tokens,
                "last_active_at": s.last_active_at,
                "status": s.status,
            }
        )
    return ok({"items": items, "total": len(items)})


@router.get("/sessions/{session_id}/messages")
def session_messages(db: Db, session_id: str):
    session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
    if session is None:
        raise AppError(1006, "会话不存在", 404)
    memories = (
        db.query(MemoryMessage)
        .filter(MemoryMessage.session_id == session.id)
        .order_by(MemoryMessage.id.asc())
        .all()
    )
    items = [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "tokens": m.tokens,
            "storage_tier": m.storage_tier,
            "created_at": m.created_at,
        }
        for m in memories
    ]
    return ok({"items": items, "total": len(items)})


@router.delete("/sessions/{session_id}")
def delete_session(db: Db, session_id: str):
    deleted = memory_service.delete(db, session_id)
    if not deleted:
        raise AppError(1006, "会话不存在", 404)
    return ok(None)
