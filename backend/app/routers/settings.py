"""系统设置：全局参数 + 密钥托管。"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import GatewaySettings, Provider, utcnow
from ..schemas import AppError, CredentialUpdate, SettingsUpdate, ok
from ..services.auth_service import mask_key

router = APIRouter(prefix="/settings", tags=["settings"])
Db = Annotated[Session, Depends(get_db)]


def _get_settings(db: Session) -> GatewaySettings:
    s = db.query(GatewaySettings).filter(GatewaySettings.id == 1).first()
    if s is None:
        s = GatewaySettings(id=1)
        db.add(s)
        db.commit()
    return s


def _settings_dict(s: GatewaySettings) -> dict:
    return {
        "default_timeout_s": s.default_timeout_s,
        "first_token_timeout_s": s.first_token_timeout_s,
        "billing_cycle": s.billing_cycle,
        "tls_enabled": bool(s.tls_enabled),
        "prompt_injection_guard": bool(s.prompt_injection_guard),
        "audit_log_enabled": bool(s.audit_log_enabled),
        "exchange_rate_usd_cny": s.exchange_rate_usd_cny,
    }


@router.get("")
def get_settings(db: Db):
    return ok(_settings_dict(_get_settings(db)))


@router.put("")
def update_settings(db: Db, body: SettingsUpdate):
    s = _get_settings(db)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    s.updated_at = utcnow()
    db.commit()
    db.refresh(s)
    return ok(_settings_dict(s))


@router.get("/credentials")
def list_credentials(db: Db):
    providers = db.query(Provider).order_by(Provider.id.asc()).all()
    items = [
        {
            "provider_id": p.id,
            "provider_name": p.name,
            "api_key_masked": p.api_key_masked,
        }
        for p in providers
    ]
    return ok({"items": items, "total": len(items)})


@router.put("/credentials/{provider_id}")
def update_credential(db: Db, provider_id: int, body: CredentialUpdate):
    p = db.query(Provider).filter(Provider.id == provider_id).first()
    if p is None:
        raise AppError(1006, "供应商不存在", 404)
    p.api_key_encrypted = body.api_key
    p.api_key_masked = mask_key(body.api_key)
    p.updated_at = utcnow()
    db.commit()
    db.refresh(p)
    return ok({"provider_id": p.id, "provider_name": p.name, "api_key_masked": p.api_key_masked})
