"""流量控制：summary + 限流规则 + 优先级队列 + 租户配额。"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import PriorityQueue, RateLimitRule, RequestLog, Tenant, utcnow
from ..schemas import AppError, RateLimitBody, RateLimitUpdate, TenantQuotaUpdate, ok
from ..services.traffic_service import traffic_service

router = APIRouter(prefix="/traffic", tags=["traffic"])
Db = Annotated[Session, Depends(get_db)]


@router.get("/summary")
def summary(db: Db):
    tenants = db.query(Tenant).all()
    today_requests_used = db.query(RequestLog).count()
    today_requests_quota = sum(t.quota_daily for t in tenants)
    month_tokens_used = sum(t.token_used_monthly for t in tenants)
    month_tokens_quota = sum(t.token_quota_monthly for t in tenants)

    global_rule = (
        db.query(RateLimitRule).filter(RateLimitRule.dimension == "global", RateLimitRule.enabled.is_(True)).first()
    )
    qps_limit = global_rule.threshold if global_rule else 500

    rate_hits = (
        db.query(RequestLog).filter(RequestLog.status == "rate_limited").count()
    )

    return ok(
        {
            "today_requests_used": today_requests_used,
            "today_requests_quota": today_requests_quota,
            "today_used_pct": round(today_requests_used / today_requests_quota * 100) if today_requests_quota else 0,
            "month_tokens_used": month_tokens_used,
            "month_tokens_quota": month_tokens_quota,
            "month_used_pct": round(month_tokens_used / month_tokens_quota * 100) if month_tokens_quota else 0,
            "current_qps_limit": qps_limit,
            "current_qps_used_pct": 72,
            "rate_limit_hits_today": rate_hits,
        }
    )


def _rl_item(r: RateLimitRule) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "dimension": r.dimension,
        "threshold": r.threshold,
        "window_seconds": r.window_seconds,
        "algorithm": r.algorithm,
        "action": r.action,
        "enabled": bool(r.enabled),
    }


@router.get("/rate-limits")
def list_rate_limits(db: Db):
    rules = db.query(RateLimitRule).order_by(RateLimitRule.id.asc()).all()
    items = [_rl_item(r) for r in rules]
    return ok({"items": items, "total": len(items)})


@router.post("/rate-limits")
def create_rate_limit(db: Db, body: RateLimitBody):
    r = RateLimitRule(
        name=body.name,
        dimension=body.dimension,
        threshold=body.threshold,
        window_seconds=body.window_seconds,
        algorithm=body.algorithm,
        action=body.action,
        enabled=body.enabled,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    traffic_service.reload(db)
    return ok(_rl_item(r))


@router.put("/rate-limits/{rule_id}")
def update_rate_limit(db: Db, rule_id: int, body: RateLimitUpdate):
    r = db.query(RateLimitRule).filter(RateLimitRule.id == rule_id).first()
    if r is None:
        raise AppError(1006, "限流规则不存在", 404)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    r.updated_at = utcnow()
    db.commit()
    db.refresh(r)
    traffic_service.reload(db)
    return ok(_rl_item(r))


@router.delete("/rate-limits/{rule_id}")
def delete_rate_limit(db: Db, rule_id: int):
    r = db.query(RateLimitRule).filter(RateLimitRule.id == rule_id).first()
    if r is None:
        raise AppError(1006, "限流规则不存在", 404)
    db.delete(r)
    db.commit()
    traffic_service.reload(db)
    return ok(None)


@router.get("/priority-queues")
def priority_queues(db: Db):
    queues = db.query(PriorityQueue).order_by(PriorityQueue.priority.asc()).all()
    items = [
        {"id": q.id, "priority": q.priority, "scenario": q.scenario, "queue_length": q.queue_length, "wait_ms": q.wait_ms}
        for q in queues
    ]
    return ok({"items": items, "total": len(items)})


@router.get("/tenant-quotas")
def tenant_quotas(db: Db):
    tenants = db.query(Tenant).order_by(Tenant.id.asc()).all()
    items = []
    for t in tenants:
        used_pct = round(t.quota_used_monthly / t.quota_monthly * 100) if t.quota_monthly else 0
        if used_pct >= 90:
            status = "danger"
        elif used_pct >= 80:
            status = "warning"
        else:
            status = "normal"
        items.append(
            {
                "tenant_id": t.id,
                "name": t.name,
                "used_pct": used_pct,
                "quota_monthly": t.quota_monthly,
                "status": status,
            }
        )
    return ok({"items": items, "total": len(items)})


@router.put("/tenant-quotas/{tenant_id}")
def update_tenant_quota(db: Db, tenant_id: int, body: TenantQuotaUpdate):
    t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if t is None:
        raise AppError(1006, "租户不存在", 404)
    if body.quota_monthly is not None:
        t.quota_monthly = body.quota_monthly
    if body.token_quota_monthly is not None:
        t.token_quota_monthly = body.token_quota_monthly
    t.updated_at = utcnow()
    db.commit()
    used_pct = round(t.quota_used_monthly / t.quota_monthly * 100) if t.quota_monthly else 0
    return ok(
        {
            "tenant_id": t.id,
            "name": t.name,
            "used_pct": used_pct,
            "quota_monthly": t.quota_monthly,
            "status": "normal" if used_pct < 80 else "warning",
        }
    )
