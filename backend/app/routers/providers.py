"""供应商管理 + 模型实例 CRUD。"""
from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import InstanceNode, ModelInstance, Provider, RequestLog, ResiliencePolicy, utcnow
from ..schemas import AppError, ModelInstanceBody, ModelInstanceUpdate, ProviderBody, ProviderUpdate, ok
from ..services.auth_service import mask_key

router = APIRouter(tags=["providers"])
Db = Annotated[Session, Depends(get_db)]


def _provider_item(db: Session, p: Provider) -> dict:
    today = utcnow()[:10]  # YYYY-MM-DD
    today_requests = (
        db.query(RequestLog)
        .filter(RequestLog.provider_id == p.id, RequestLog.created_at >= f"{today}T00:00:00Z")
        .count()
    )
    models = db.query(ModelInstance).filter(ModelInstance.provider_id == p.id).all()
    model_summary = " · ".join(m.name for m in models) if models else ""
    quota_used_pct = round(p.quota_used / p.quota_total * 100) if p.quota_total > 0 else 0
    return {
        "id": p.id,
        "name": p.name,
        "provider_type": p.provider_type,
        "status": p.status,
        "today_requests": today_requests,
        "success_rate": p.success_rate,
        "quota_used_pct": quota_used_pct,
        "model_summary": model_summary,
        "api_key_masked": p.api_key_masked,
    }


@router.get("/providers")
def list_providers(db: Db):
    providers = db.query(Provider).order_by(Provider.id.asc()).all()
    items = [_provider_item(db, p) for p in providers]
    return ok({"items": items, "total": len(items)})


@router.post("/providers")
def create_provider(db: Db, body: ProviderBody):
    if db.query(Provider).filter(Provider.name == body.name).first():
        raise AppError(1001, "供应商名称已存在", 400)
    p = Provider(
        name=body.name,
        provider_type=body.provider_type,
        base_url=body.base_url,
        api_key_encrypted=body.api_key,
        api_key_masked=mask_key(body.api_key),
        status="online",
        quota_total=1000000000,
        quota_used=0,
        success_rate=100.0,
        cost_weight=1.0,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return ok(_provider_item(db, p))


@router.put("/providers/{provider_id}")
def update_provider(db: Db, provider_id: int, body: ProviderUpdate):
    p = db.query(Provider).filter(Provider.id == provider_id).first()
    if p is None:
        raise AppError(1006, "供应商不存在", 404)
    data = body.model_dump(exclude_unset=True)
    if "api_key" in data:
        raw = data.pop("api_key")
        p.api_key_encrypted = raw
        p.api_key_masked = mask_key(raw)
    for k, v in data.items():
        setattr(p, k, v)
    p.updated_at = utcnow()
    db.commit()
    db.refresh(p)
    return ok(_provider_item(db, p))


@router.delete("/providers/{provider_id}")
def delete_provider(db: Db, provider_id: int):
    p = db.query(Provider).filter(Provider.id == provider_id).first()
    if p is None:
        raise AppError(1006, "供应商不存在", 404)
    instances = db.query(ModelInstance).filter(ModelInstance.provider_id == provider_id).all()
    for inst in instances:
        db.query(InstanceNode).filter(InstanceNode.model_instance_id == inst.id).delete()
    db.query(ModelInstance).filter(ModelInstance.provider_id == provider_id).delete()
    db.query(ResiliencePolicy).filter(ResiliencePolicy.provider_id == provider_id).delete()
    db.delete(p)
    db.commit()
    return ok(None)


def _instance_item(db: Session, mi: ModelInstance) -> dict:
    provider = db.query(Provider).filter(Provider.id == mi.provider_id).first()
    try:
        capabilities = json.loads(mi.capabilities_json)
    except (TypeError, ValueError):
        capabilities = []
    return {
        "id": mi.id,
        "provider_id": mi.provider_id,
        "provider_name": provider.name if provider else "",
        "name": mi.name,
        "capabilities": capabilities,
        "input_price": mi.input_price,
        "output_price": mi.output_price,
        "currency": mi.currency,
        "max_context_tokens": mi.max_context_tokens,
        "tier": mi.tier,
        "status": mi.status,
        "latency_p50_ms": int(mi.latency_p50_ms),
        "latency_p95_ms": int(mi.latency_p95_ms),
        "load": mi.load,
        "quality_score": mi.quality_score,
    }


@router.get("/model-instances")
def list_model_instances(db: Db, provider_id: int | None = Query(default=None)):
    q = db.query(ModelInstance)
    if provider_id is not None:
        q = q.filter(ModelInstance.provider_id == provider_id)
    instances = q.order_by(ModelInstance.id.asc()).all()
    items = [_instance_item(db, mi) for mi in instances]
    return ok({"items": items, "total": len(items)})


@router.post("/model-instances")
def create_model_instance(db: Db, body: ModelInstanceBody):
    if db.query(Provider).filter(Provider.id == body.provider_id).first() is None:
        raise AppError(1006, "供应商不存在", 404)
    mi = ModelInstance(
        provider_id=body.provider_id,
        name=body.name,
        capabilities_json=json.dumps(body.capabilities, ensure_ascii=False),
        input_price=body.input_price,
        output_price=body.output_price,
        currency=body.currency,
        max_context_tokens=body.max_context_tokens,
        tier=body.tier,
        quality_score=body.quality_score,
        status="healthy",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(mi)
    db.commit()
    db.refresh(mi)
    return ok(_instance_item(db, mi))


@router.put("/model-instances/{instance_id}")
def update_model_instance(db: Db, instance_id: int, body: ModelInstanceUpdate):
    mi = db.query(ModelInstance).filter(ModelInstance.id == instance_id).first()
    if mi is None:
        raise AppError(1006, "模型实例不存在", 404)
    data = body.model_dump(exclude_unset=True)
    if "capabilities" in data:
        mi.capabilities_json = json.dumps(data.pop("capabilities"), ensure_ascii=False)
    for k, v in data.items():
        setattr(mi, k, v)
    mi.updated_at = utcnow()
    db.commit()
    db.refresh(mi)
    return ok(_instance_item(db, mi))


@router.delete("/model-instances/{instance_id}")
def delete_model_instance(db: Db, instance_id: int):
    mi = db.query(ModelInstance).filter(ModelInstance.id == instance_id).first()
    if mi is None:
        raise AppError(1006, "模型实例不存在", 404)
    db.query(InstanceNode).filter(InstanceNode.model_instance_id == instance_id).delete()
    db.delete(mi)
    db.commit()
    return ok(None)
