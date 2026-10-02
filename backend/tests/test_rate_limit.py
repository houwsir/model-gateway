"""流量控制单元测试：限流（令牌桶）+ 配额。"""
from __future__ import annotations

import pytest

from app.models import RateLimitRule, Tenant, utcnow
from app.schemas import AppError
from app.services.traffic_service import TrafficService


def _make_rule(dimension: str, threshold: int, algorithm: str = "token_bucket") -> RateLimitRule:
    return RateLimitRule(
        name="test",
        dimension=dimension,
        threshold=threshold,
        window_seconds=1,
        algorithm=algorithm,
        action="reject_429",
        enabled=True,
        created_at=utcnow(),
        updated_at=utcnow(),
    )


def test_token_bucket_rate_limit_rejects_second_request():
    svc = TrafficService()
    rule = _make_rule("global", 1)
    svc._snapshot = [rule]

    # 第一次通过
    svc.check_rate_limit(None, None)
    # 第二次超限
    with pytest.raises(AppError) as exc:
        svc.check_rate_limit(None, None)
    assert exc.value.code == 1004
    assert exc.value.http_status == 429


def test_sliding_window_rate_limit():
    svc = TrafficService()
    rule = _make_rule("model", 1, algorithm="sliding_window")
    svc._snapshot = [rule]

    svc.check_rate_limit(1, "gpt-4o-mini")
    with pytest.raises(AppError) as exc:
        svc.check_rate_limit(1, "gpt-4o-mini")
    assert exc.value.code == 1004


def test_quota_exhausted_returns_1003():
    svc = TrafficService()
    tenant = Tenant(
        name="配额耗尽租户",
        quota_daily=10,
        quota_used_daily=10,
        quota_monthly=100,
        quota_used_monthly=50,
        token_quota_monthly=1000,
        token_used_monthly=10,
        priority_default="P1",
        status="active",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    with pytest.raises(AppError) as exc:
        svc.check_quota(tenant)
    assert exc.value.code == 1003
    assert exc.value.http_status == 403


def test_quota_ok_when_available():
    svc = TrafficService()
    tenant = Tenant(
        name="正常租户",
        quota_daily=100,
        quota_used_daily=10,
        quota_monthly=1000,
        quota_used_monthly=100,
        token_quota_monthly=10000,
        token_used_monthly=100,
        priority_default="P1",
        status="active",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    svc.check_quota(tenant)  # 不应抛异常


def test_same_dimension_rules_have_independent_buckets():
    svc = TrafficService()
    r1 = _make_rule("global", 1)
    r2 = _make_rule("global", 2)
    r1.id = 1
    r2.id = 2
    svc._snapshot = [r1, r2]

    # 第一条规则阈值 1：第二次请求即超限（若共享桶，会受第二条规则影响而不报错）
    svc.check_rate_limit(None, None)
    with pytest.raises(AppError) as exc:
        svc.check_rate_limit(None, None)
    assert exc.value.code == 1004


def test_tenant_rule_scoped_per_tenant():
    svc = TrafficService()
    rule = _make_rule("tenant", 1)
    rule.id = 10
    svc._snapshot = [rule]

    # 租户 1 首次通过
    svc.check_rate_limit(1, None)
    # 租户 2 首次也应通过（各租户独立限流）
    svc.check_rate_limit(2, None)
    # 租户 1 第二次超限
    with pytest.raises(AppError) as exc:
        svc.check_rate_limit(1, None)
    assert exc.value.code == 1004


