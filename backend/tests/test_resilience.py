"""容灾熔断状态机单元测试。"""
from __future__ import annotations

from app.services.resilience_service import ResilienceService


def test_circuit_opens_after_failures():
    svc = ResilienceService()
    model_id = 999
    threshold = 0.5
    cooldown = 30

    # 连续 5 次失败，失败率 100% >= 50% → 触发 open
    transition = None
    for _ in range(5):
        transition = svc.record(model_id, False, threshold, cooldown)
    assert transition == "opened"
    assert svc.state_of(model_id) == "open"
    # open 期间拒绝请求
    assert svc.is_allowed(model_id, threshold, cooldown) is False


def test_half_open_recovers_on_success():
    svc = ResilienceService()
    model_id = 998
    threshold = 0.5
    cooldown = 0  # 冷却立即到期

    for _ in range(5):
        svc.record(model_id, False, threshold, cooldown)
    assert svc.state_of(model_id) == "open"

    # 冷却到期后放行试探（half_open）
    assert svc.is_allowed(model_id, threshold, cooldown, half_open_enabled=True) is True
    # 试探成功 → 恢复 closed
    transition = svc.record(model_id, True, threshold, cooldown, half_open_enabled=True)
    assert transition == "recovered"
    assert svc.state_of(model_id) == "closed"


def test_half_open_failure_reopens():
    svc = ResilienceService()
    model_id = 997
    threshold = 0.5
    cooldown = 0

    for _ in range(5):
        svc.record(model_id, False, threshold, cooldown)
    assert svc.is_allowed(model_id, threshold, cooldown, half_open_enabled=True) is True
    transition = svc.record(model_id, False, threshold, cooldown, half_open_enabled=True)
    assert transition == "opened"
    assert svc.state_of(model_id) == "open"


def test_success_keeps_closed():
    svc = ResilienceService()
    model_id = 996
    for _ in range(10):
        transition = svc.record(model_id, True, 0.5, 30)
    assert transition is None
    assert svc.state_of(model_id) == "closed"
