"""依赖注入：数据库会话 + API Key 鉴权。"""
from __future__ import annotations

import hashlib
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from .db import get_db
from .models import ApiKey, Tenant
from .schemas import AppError

DbSession = Annotated[Session, Depends(get_db)]


def _hash_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def get_current_tenant(
    db: DbSession,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> Tenant:
    """校验 ``X-API-Key`` 并返回对应租户。

    失败抛出 ``AppError(1002, http 401)``。
    """
    if not x_api_key or not x_api_key.strip():
        raise AppError(1002, "缺少 X-API-Key 请求头", 401)

    key = x_api_key.strip()
    key_hash = _hash_key(key)
    api_key = db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
    if api_key is None or api_key.status != "active":
        raise AppError(1002, "API Key 无效或已停用", 401)

    if api_key.expires_at:
        from .models import utcnow

        if api_key.expires_at <= utcnow():
            raise AppError(1002, "API Key 已过期", 401)

    tenant = db.query(Tenant).filter(Tenant.id == api_key.tenant_id).first()
    if tenant is None or tenant.status != "active":
        raise AppError(1002, "租户不存在或已停用", 401)

    # 更新最近使用时间
    from .models import utcnow

    api_key.last_used_at = utcnow()
    db.commit()
    return tenant
