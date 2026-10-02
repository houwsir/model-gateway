"""告警中心：列表/确认/恢复/已读 + 告警规则。"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Alert, AlertRule, utcnow
from ..schemas import AlertRuleBody, AppError, ok

router = APIRouter(prefix="/alerts", tags=["alerts"])
Db = Annotated[Session, Depends(get_db)]


def _item(a: Alert) -> dict:
    return {
        "id": a.id,
        "severity": a.severity,
        "title": a.title,
        "description": a.description,
        "source": a.source,
        "status": a.status,
        "created_at": a.created_at,
    }


@router.get("")
def list_alerts(
    db: Db,
    status: str = Query(default=""),
    severity: str = Query(default=""),
    limit: int = Query(default=100),
):
    q = db.query(Alert)
    if status:
        q = q.filter(Alert.status == status)
    if severity:
        q = q.filter(Alert.severity == severity)
    q = q.order_by(Alert.created_at.desc()).limit(limit)
    alerts = q.all()
    return ok({"items": [_item(a) for a in alerts], "total": len(alerts)})


@router.post("/{alert_id}/ack")
def ack_alert(db: Db, alert_id: int):
    a = db.query(Alert).filter(Alert.id == alert_id).first()
    if a is None:
        raise AppError(1006, "告警不存在", 404)
    a.status = "acknowledged"
    db.commit()
    db.refresh(a)
    return ok(_item(a))


@router.post("/{alert_id}/resolve")
def resolve_alert(db: Db, alert_id: int):
    a = db.query(Alert).filter(Alert.id == alert_id).first()
    if a is None:
        raise AppError(1006, "告警不存在", 404)
    a.status = "recovered"
    a.resolved_at = utcnow()
    db.commit()
    db.refresh(a)
    return ok(_item(a))


@router.post("/read-all")
def read_all(db: Db):
    db.query(Alert).filter(Alert.status == "open").update({"status": "acknowledged"})
    db.commit()
    return ok(None)


@router.get("/rules")
def list_rules(db: Db):
    rules = db.query(AlertRule).order_by(AlertRule.id.asc()).all()
    items = [
        {
            "id": r.id,
            "name": r.name,
            "metric": r.metric,
            "threshold": r.threshold,
            "severity": r.severity,
            "enabled": bool(r.enabled),
        }
        for r in rules
    ]
    return ok({"items": items, "total": len(items)})


@router.post("/rules")
def create_rule(db: Db, body: AlertRuleBody):
    r = AlertRule(
        name=body.name,
        metric=body.metric,
        threshold=body.threshold,
        severity=body.severity,
        enabled=True,
        created_at=utcnow(),
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return ok(
        {
            "id": r.id,
            "name": r.name,
            "metric": r.metric,
            "threshold": r.threshold,
            "severity": r.severity,
            "enabled": bool(r.enabled),
        }
    )
