"""鉴权与密钥托管。"""
from __future__ import annotations

import hashlib
import secrets

from sqlalchemy.orm import Session

from ..models import ApiKey, Tenant, utcnow
from ..schemas import AppError


def hash_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def mask_key(api_key: str | None, keep: int = 4) -> str:
    """返回掩码后的密钥（仅保留末 ``keep`` 位）。"""
    if not api_key:
        return "sk-••••••••"
    head = api_key[:3]
    return f"{head}{'•' * 8}{api_key[-keep:]}"


class AuthService:
    """API Key 鉴权 + 签发 + 掩码。"""

    def authenticate(self, db: Session, api_key: str) -> Tenant:
        """校验 API Key 并返回租户（复用 deps 的校验逻辑）。"""
        from ..deps import get_current_tenant  # 延迟导入避免循环

        return get_current_tenant(db, api_key)

    def issue_api_key(self, db: Session, tenant_id: int, name: str) -> tuple[ApiKey, str]:
        """签发新 API Key，返回 (记录, 明文 key)。"""
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant is None:
            raise AppError(1006, "租户不存在", 404)

        raw = f"gw_{secrets.token_hex(16)}"  # gw_<32hex>
        record = ApiKey(
            tenant_id=tenant_id,
            name=name or f"{tenant.name}·密钥",
            key_hash=hash_key(raw),
            key_prefix=f"{raw[:8]}****",
            status="active",
            created_at=utcnow(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record, raw

    def mask(self, api_key: str | None) -> str:
        return mask_key(api_key)


auth_service = AuthService()
