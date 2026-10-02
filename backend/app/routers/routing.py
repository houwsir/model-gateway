"""智能路由策略/规则 CRUD + 路由预览。"""
from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ModelInstance, RoutePolicy, RouteRule, utcnow
from ..schemas import AppError, RoutePolicyBody, RouteRuleBody, RouteRuleUpdate, RoutingPreviewRequest, ok
from ..services.router_service import router_service

router = APIRouter(prefix="/routing", tags=["routing"])
Db = Annotated[Session, Depends(get_db)]

_TAG_LABELS = {"default": "默认策略", "realtime": "实时交互", "quality": "客服核心链路"}
_HIT_RATES = {"default": 94, "realtime": 91, "quality": 97}


def _policy_item(db: Session, p: RoutePolicy) -> dict:
    candidate_count = db.query(ModelInstance).count()
    return {
        "id": p.id,
        "name": p.name,
        "scenario_tag": p.scenario_tag,
        "tag_label": _TAG_LABELS.get(p.scenario_tag, p.scenario_tag),
        "weight_cost": p.weight_cost,
        "weight_latency": p.weight_latency,
        "weight_quality": p.weight_quality,
        "exploration_rate": p.exploration_rate,
        "candidate_count": candidate_count,
        "hit_rate": _HIT_RATES.get(p.scenario_tag, 90),
        "is_default": bool(p.is_default),
        "status": p.status,
    }


def _rule_item(r: RouteRule) -> dict:
    try:
        condition = json.loads(r.condition_json)
    except (TypeError, ValueError):
        condition = {}
    return {
        "id": r.id,
        "name": r.name,
        "rule_type": r.rule_type,
        "condition": condition,
        "action": r.action,
        "priority": r.priority,
        "enabled": bool(r.enabled),
    }


@router.get("/policies")
def list_policies(db: Db):
    policies = db.query(RoutePolicy).order_by(RoutePolicy.id.asc()).all()
    items = [_policy_item(db, p) for p in policies]
    return ok({"items": items, "total": len(items)})


@router.post("/policies")
def create_policy(db: Db, body: RoutePolicyBody):
    if abs(body.weight_cost + body.weight_latency + body.weight_quality - 1.0) > 0.01:
        raise AppError(1001, "三权重之和必须等于 1（允许 ±0.01）", 400)
    if db.query(RoutePolicy).filter(RoutePolicy.scenario_tag == body.scenario_tag).first():
        raise AppError(1001, f"scenario_tag「{body.scenario_tag}」已存在", 400)
    p = RoutePolicy(
        name=body.name,
        scenario_tag=body.scenario_tag,
        weight_cost=body.weight_cost,
        weight_latency=body.weight_latency,
        weight_quality=body.weight_quality,
        exploration_rate=body.exploration_rate,
        is_default=body.is_default,
        status=body.status,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    router_service.reload(db)
    return ok(_policy_item(db, p))


@router.put("/policies/{policy_id}")
def update_policy(db: Db, policy_id: int, body: RoutePolicyBody):
    p = db.query(RoutePolicy).filter(RoutePolicy.id == policy_id).first()
    if p is None:
        raise AppError(1006, "路由策略不存在", 404)
    if abs(body.weight_cost + body.weight_latency + body.weight_quality - 1.0) > 0.01:
        raise AppError(1001, "三权重之和必须等于 1（允许 ±0.01）", 400)
    p.name = body.name
    p.scenario_tag = body.scenario_tag
    p.weight_cost = body.weight_cost
    p.weight_latency = body.weight_latency
    p.weight_quality = body.weight_quality
    p.exploration_rate = body.exploration_rate
    p.is_default = body.is_default
    p.status = body.status
    p.updated_at = utcnow()
    db.commit()
    db.refresh(p)
    router_service.reload(db)
    return ok(_policy_item(db, p))


@router.delete("/policies/{policy_id}")
def delete_policy(db: Db, policy_id: int):
    p = db.query(RoutePolicy).filter(RoutePolicy.id == policy_id).first()
    if p is None:
        raise AppError(1006, "路由策略不存在", 404)
    db.delete(p)
    db.commit()
    router_service.reload(db)
    return ok(None)


@router.get("/rules")
def list_rules(db: Db, policy_id: int | None = None):
    rules = db.query(RouteRule).order_by(RouteRule.priority.asc()).all()
    items = [_rule_item(r) for r in rules]
    return ok({"items": items, "total": len(items)})


@router.post("/rules")
def create_rule(db: Db, body: RouteRuleBody):
    r = RouteRule(
        name=body.name,
        rule_type=body.rule_type,
        condition_json=json.dumps(body.condition, ensure_ascii=False),
        action=body.action,
        priority=body.priority,
        enabled=body.enabled,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    router_service.reload(db)
    return ok(_rule_item(r))


@router.put("/rules/{rule_id}")
def update_rule(db: Db, rule_id: int, body: RouteRuleUpdate):
    r = db.query(RouteRule).filter(RouteRule.id == rule_id).first()
    if r is None:
        raise AppError(1006, "路由规则不存在", 404)
    data = body.model_dump(exclude_unset=True)
    if "condition" in data:
        r.condition_json = json.dumps(data.pop("condition"), ensure_ascii=False)
    for k, v in data.items():
        setattr(r, k, v)
    r.updated_at = utcnow()
    db.commit()
    db.refresh(r)
    router_service.reload(db)
    return ok(_rule_item(r))


@router.delete("/rules/{rule_id}")
def delete_rule(db: Db, rule_id: int):
    r = db.query(RouteRule).filter(RouteRule.id == rule_id).first()
    if r is None:
        raise AppError(1006, "路由规则不存在", 404)
    db.delete(r)
    db.commit()
    router_service.reload(db)
    return ok(None)


@router.post("/preview")
def preview(db: Db, body: RoutingPreviewRequest):
    decision = router_service.route(
        db, body.scenario_tag, body.capabilities, body.messages, body.model, max_tokens=512
    )
    return ok(
        {
            "selected_model": decision.selected.name if decision.selected else None,
            "candidates": decision.candidates,
            "filtered_out": decision.filtered_out,
        }
    )
