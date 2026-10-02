"""负载均衡：均衡组 + 节点摘流/恢复。"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import BalancingGroup, InstanceNode, ModelInstance, Provider, utcnow
from ..schemas import AppError, BalancingGroupUpdate, ok
from ..services.balancer_service import balancer_service

router = APIRouter(prefix="/balancing", tags=["balancing"])
Db = Annotated[Session, Depends(get_db)]


@router.get("/groups")
def list_groups(db: Db):
    groups = db.query(BalancingGroup).order_by(BalancingGroup.id.asc()).all()
    items = [
        {"id": g.id, "name": g.name, "strategy": g.strategy, "provider_strategy": g.provider_strategy}
        for g in groups
    ]
    return ok({"items": items, "total": len(items)})


@router.get("/groups/{group_id}")
def get_group(db: Db, group_id: int):
    g = db.query(BalancingGroup).filter(BalancingGroup.id == group_id).first()
    if g is None:
        raise AppError(1006, "均衡组不存在", 404)

    nodes = db.query(InstanceNode).all()
    instance_weights = []
    for n in nodes:
        model = db.query(ModelInstance).filter(ModelInstance.id == n.model_instance_id).first()
        instance_weights.append(
            {"node": n.name, "model": model.name if model else "", "weight": n.weight, "node_id": n.id}
        )

    provider_ratios = balancer_service.provider_ratios(db)

    return ok(
        {
            "id": g.id,
            "name": g.name,
            "strategy": g.strategy,
            "provider_strategy": g.provider_strategy,
            "instance_weights": instance_weights,
            "provider_ratios": provider_ratios,
        }
    )


@router.put("/groups/{group_id}")
def update_group(db: Db, group_id: int, body: BalancingGroupUpdate):
    g = db.query(BalancingGroup).filter(BalancingGroup.id == group_id).first()
    if g is None:
        raise AppError(1006, "均衡组不存在", 404)

    if body.strategy is not None:
        g.strategy = body.strategy
    if body.provider_strategy is not None:
        g.provider_strategy = body.provider_strategy
    if body.instance_weights is not None:
        for item in body.instance_weights:
            node = db.query(InstanceNode).filter(InstanceNode.id == item.node_id).first()
            if node is not None:
                node.weight = item.weight
                node.updated_at = utcnow()
    g.updated_at = utcnow()
    db.commit()
    return get_group(db, group_id)


@router.get("/nodes")
def list_nodes(db: Db):
    nodes = db.query(InstanceNode).order_by(InstanceNode.id.asc()).all()
    items = []
    for n in nodes:
        model = db.query(ModelInstance).filter(ModelInstance.id == n.model_instance_id).first()
        provider = db.query(Provider).filter(Provider.id == model.provider_id).first() if model else None
        load = model.load if model else 0
        items.append(
            {
                "id": n.id,
                "name": n.name,
                "model": model.name if model else "",
                "provider": provider.name if provider else "",
                "current_connections": n.current_connections,
                "load": load,
                "status": n.status,
                "weight": n.weight,
            }
        )
    return ok({"items": items, "total": len(items)})


def _node_item(db: Session, n: InstanceNode) -> dict:
    model = db.query(ModelInstance).filter(ModelInstance.id == n.model_instance_id).first()
    provider = db.query(Provider).filter(Provider.id == model.provider_id).first() if model else None
    return {
        "id": n.id,
        "name": n.name,
        "model": model.name if model else "",
        "provider": provider.name if provider else "",
        "current_connections": n.current_connections,
        "load": model.load if model else 0,
        "status": n.status,
        "weight": n.weight,
    }


@router.post("/nodes/{node_id}/drain")
def drain_node(db: Db, node_id: int):
    n = db.query(InstanceNode).filter(InstanceNode.id == node_id).first()
    if n is None:
        raise AppError(1006, "实例节点不存在", 404)
    n.status = "draining"
    n.updated_at = utcnow()
    db.commit()
    db.refresh(n)
    return ok(_node_item(db, n))


@router.post("/nodes/{node_id}/recover")
def recover_node(db: Db, node_id: int):
    n = db.query(InstanceNode).filter(InstanceNode.id == node_id).first()
    if n is None:
        raise AppError(1006, "实例节点不存在", 404)
    n.status = "healthy"
    n.updated_at = utcnow()
    db.commit()
    db.refresh(n)
    return ok(_node_item(db, n))
