"""容灾策略 CRUD。"""
from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Provider, ResiliencePolicy, utcnow
from ..schemas import AppError, ResiliencePolicyBody, ResiliencePolicyUpdate, ok

router = APIRouter(prefix="/resilience", tags=["resilience"])
Db = Annotated[Session, Depends(get_db)]


def _item(db: Session, r: ResiliencePolicy) -> dict:
    provider = db.query(Provider).filter(Provider.id == r.provider_id).first()
    try:
        chain = json.loads(r.backup_chain_json)
    except (TypeError, ValueError):
        chain = []
    return {
        "id": r.id,
        "provider_id": r.provider_id,
        "provider_name": provider.name if provider else "",
        "backup_chain": chain,
        "retry_count": r.retry_count,
        "status": r.status,
        "switch_count": r.switch_count,
        "failure_rate_threshold": r.failure_rate_threshold,
        "cooldown_seconds": r.cooldown_seconds,
        "half_open_enabled": bool(r.half_open_enabled),
        "failover_mode": r.failover_mode,
        "backup_selection": r.backup_selection,
        "degrade_mode": r.degrade_mode,
    }


@router.get("/policies")
def list_policies(db: Db):
    policies = db.query(ResiliencePolicy).order_by(ResiliencePolicy.id.asc()).all()
    items = [_item(db, r) for r in policies]
    return ok({"items": items, "total": len(items)})


@router.post("/policies")
def create_policy(db: Db, body: ResiliencePolicyBody):
    if db.query(Provider).filter(Provider.id == body.provider_id).first() is None:
        raise AppError(1006, "供应商不存在", 404)
    if db.query(ResiliencePolicy).filter(ResiliencePolicy.provider_id == body.provider_id).first():
        raise AppError(1001, "该供应商已存在容灾策略", 400)
    r = ResiliencePolicy(
        provider_id=body.provider_id,
        failure_rate_threshold=body.failure_rate_threshold,
        cooldown_seconds=body.cooldown_seconds,
        half_open_enabled=body.half_open_enabled,
        failover_mode=body.failover_mode,
        backup_selection=body.backup_selection,
        degrade_mode=body.degrade_mode,
        backup_chain_json=json.dumps(body.backup_chain, ensure_ascii=False),
        retry_count=body.retry_count,
        status="normal",
        switch_count=0,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return ok(_item(db, r))


@router.put("/policies/{policy_id}")
def update_policy(db: Db, policy_id: int, body: ResiliencePolicyUpdate):
    r = db.query(ResiliencePolicy).filter(ResiliencePolicy.id == policy_id).first()
    if r is None:
        raise AppError(1006, "容灾策略不存在", 404)
    data = body.model_dump(exclude_unset=True)
    if "backup_chain" in data:
        r.backup_chain_json = json.dumps(data.pop("backup_chain"), ensure_ascii=False)
    for k, v in data.items():
        setattr(r, k, v)
    r.updated_at = utcnow()
    db.commit()
    db.refresh(r)
    return ok(_item(db, r))
