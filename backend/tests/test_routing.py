"""路由服务单元测试：两段式路由 + 探索 + 场景权重差异。"""
from __future__ import annotations

from app.services.router_service import RouterService


def test_route_returns_selected_model(db):
    svc = RouterService()
    svc.reload(db)

    decision = svc.route(db, "default", ["text"], [{"role": "user", "content": "你好"}])
    assert decision.selected is not None
    assert decision.policy is not None
    assert decision.candidates, "候选列表不应为空"
    # 候选按分数降序
    scores = [c["score"] for c in decision.candidates]
    assert scores == sorted(scores, reverse=True)


def test_route_respects_model_override(db):
    svc = RouterService()
    svc.reload(db)

    decision = svc.route(db, "default", ["text"], [{"role": "user", "content": "x"}], model="qwen2.5-72b")
    assert decision.selected is not None
    assert decision.selected.name == "qwen2.5-72b"


def test_route_filters_circuit_open_models(db):
    svc = RouterService()
    svc.reload(db)

    decision = svc.route(db, "default", ["text"], [{"role": "user", "content": "x"}])
    # glm-4 状态 circuit_open，不应出现在候选
    candidate_names = [c["model"] for c in decision.candidates]
    assert "glm-4" not in candidate_names


def test_route_capability_filter_multimodal(db):
    svc = RouterService()
    svc.reload(db)

    decision = svc.route(db, "default", ["multimodal"], [{"role": "user", "content": "x"}])
    candidate_names = [c["model"] for c in decision.candidates]
    # 只有含 multimodal 能力的模型能通过能力过滤
    for name in candidate_names:
        assert name in {"gpt-4o-mini"}  # glm-4 已熔断，仅 gpt-4o-mini 可多模态


def test_scenario_policies_have_different_weights(db):
    svc = RouterService()
    svc.reload(db)

    default = svc._get_policy("default")
    realtime = svc._get_policy("realtime")
    quality = svc._get_policy("quality")
    assert default.weight_latency < realtime.weight_latency
    assert default.weight_quality < quality.weight_quality
