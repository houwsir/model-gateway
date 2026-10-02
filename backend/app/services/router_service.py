"""两段式智能路由：规则过滤 → 加权打分 → 探索（EX-10 本地快照）。

- 硬性规则过滤（能力/成本/配额/延迟），不满足即排除候选；
- 加权打分：按策略权重对成本/延迟/质量归一化后加权求和；
- 探索：以 ``exploration_rate`` 概率随机挑一个非最优候选（避免冷启动局部最优）。
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from ..models import ModelInstance, Provider, RoutePolicy, RouteRule


@dataclass
class RouteDecision:
    """路由决策结果。"""

    selected: ModelInstance | None = None
    provider: Provider | None = None
    policy: RoutePolicy | None = None
    candidates: list[dict] = field(default_factory=list)  # [{model, score}]
    filtered_out: list[str] = field(default_factory=list)
    explored: bool = False


class RouterService:
    """智能路由服务。"""

    EXCHANGE_RATE_CNY_TO_USD = 7.2  # 与 gateway_settings 默认一致

    def __init__(self) -> None:
        self._policy_snapshot: list[RoutePolicy] = []
        self._rule_snapshot: list[RouteRule] = []

    def reload(self, db: Session) -> None:
        """重建策略与规则快照（EX-10）。"""
        self._policy_snapshot = db.query(RoutePolicy).filter(RoutePolicy.status == "enabled").all()
        self._rule_snapshot = (
            db.query(RouteRule).filter(RouteRule.enabled.is_(True)).order_by(RouteRule.priority.asc()).all()
        )

    def _get_policy(self, scenario_tag: str | None) -> RoutePolicy:
        tag = scenario_tag or "default"
        for p in self._policy_snapshot:
            if p.scenario_tag == tag:
                return p
        # 回退默认策略
        for p in self._policy_snapshot:
            if p.is_default:
                return p
        return self._policy_snapshot[0] if self._policy_snapshot else None

    def _usd_price(self, instance: ModelInstance) -> float:
        """将输入单价折算为 USD（CNY 按汇率 7.2）。"""
        if instance.currency == "CNY":
            return instance.input_price / self.EXCHANGE_RATE_CNY_TO_USD
        return instance.input_price

    def _input_has_image(self, messages: list) -> bool:
        for m in messages:
            content = getattr(m, "content", "") or ""
            if "[image]" in content.lower() or "image_url" in content.lower():
                return True
        return False

    def _estimated_cost(self, instance: ModelInstance, messages: list, max_tokens: int) -> float:
        """粗略估算本次请求 USD 成本（仅用于成本规则过滤）。"""
        input_chars = sum(len(getattr(m, "content", "") or "") for m in messages)
        est_prompt_tokens = max(1, input_chars // 4)
        input_usd = est_prompt_tokens / 1_000_000 * self._usd_price(instance)
        output_price_usd = (
            instance.output_price / self.EXCHANGE_RATE_CNY_TO_USD if instance.currency == "CNY" else instance.output_price
        )
        output_usd = (max_tokens or 512) / 1_000_000 * output_price_usd
        return round(input_usd + output_usd, 6)

    def route(
        self,
        db: Session,
        scenario_tag: str | None,
        capabilities: list[str],
        messages: list,
        model: str | None = None,
        max_tokens: int = 512,
    ) -> RouteDecision:
        """执行两段式路由，返回 ``RouteDecision``。

        若显式指定 ``model``，则直接定位该模型（仍做基本可用性校验）。
        """
        if not self._policy_snapshot:
            self.reload(db)

        decision = RouteDecision()

        # 显式指定模型：直接返回
        if model:
            instance = (
                db.query(ModelInstance)
                .join(Provider, ModelInstance.provider_id == Provider.id)
                .filter(ModelInstance.name == model)
                .first()
            )
            if instance is None:
                decision.filtered_out = [model]
                return decision
            provider = db.query(Provider).filter(Provider.id == instance.provider_id).first()
            decision.selected = instance
            decision.provider = provider
            decision.candidates = [{"model": instance.name, "score": 1.0}]
            return decision

        policy = self._get_policy(scenario_tag)
        decision.policy = policy

        candidates = (
            db.query(ModelInstance)
            .join(Provider, ModelInstance.provider_id == Provider.id)
            .filter(Provider.status == "online")
            .filter(ModelInstance.status != "circuit_open", ModelInstance.status != "offline")
            .all()
        )

        quota_map = self._provider_quota_map(db)
        req_caps = set(capabilities or ["text"])
        filtered_out: list[str] = []

        # ---------- 第一段：规则过滤 ----------
        remaining: list[ModelInstance] = []
        for inst in candidates:
            if not req_caps.issubset(set(self._caps(inst))):
                filtered_out.append(inst.name)
                continue
            remaining.append(inst)

        # 应用 route_rules
        for rule in self._rule_snapshot:
            cond = json.loads(rule.condition_json) if isinstance(rule.condition_json, str) else rule.condition_json
            field_name = cond.get("field", "")
            operator = cond.get("operator", "eq")
            value = cond.get("value")

            if rule.rule_type == "capability" and field_name == "input_has_image":
                if self._input_has_image(messages) and operator == "eq" and value is True:
                    remaining = [i for i in remaining if "multimodal" in self._caps(i)]
                    filtered_out.extend(i.name for i in candidates if i not in remaining and i.name not in filtered_out)

            elif rule.rule_type == "cost" and field_name == "estimated_cost":
                remaining = [
                    i for i in remaining if not self._op(self._estimated_cost(i, messages, max_tokens), operator, value)
                ]

            elif rule.rule_type == "quota" and field_name == "provider_quota_remaining":
                remaining = [i for i in remaining if quota_map.get(i.provider_id, 0.0) >= (value or 0)]

            elif rule.rule_type == "latency" and field_name == "p95_latency":
                remaining = [i for i in remaining if not self._op(i.latency_p95_ms, operator, value)]

        filtered_out.extend(i.name for i in candidates if i not in remaining and i.name not in filtered_out)

        if not remaining:
            decision.filtered_out = list(dict.fromkeys(filtered_out))
            return decision

        # ---------- 第二段：加权打分 ----------
        scored = self.score(remaining, policy)
        # 按分数降序
        scored.sort(key=lambda x: x[1], reverse=True)
        decision.candidates = [{"model": name, "score": round(score, 4)} for name, score in scored]

        # 探索机制
        if len(scored) > 1 and policy is not None and random.random() < policy.exploration_rate:
            # 从非最优候选中随机挑一个
            others = scored[1:]
            selected_name, _ = random.choice(others)
            decision.explored = True
        else:
            selected_name = scored[0][0]

        selected = next((i for i in remaining if i.name == selected_name), None)
        decision.selected = selected
        if selected is not None:
            decision.provider = db.query(Provider).filter(Provider.id == selected.provider_id).first()

        return decision

    def score(self, candidates: list[ModelInstance], policy: RoutePolicy | None) -> list[tuple[str, float]]:
        """加权打分，返回 [(模型名, 分数)]。"""
        if not candidates:
            return []

        wc = policy.weight_cost if policy else 0.4
        wl = policy.weight_latency if policy else 0.35
        wq = policy.weight_quality if policy else 0.25

        costs = [self._usd_price(i) for i in candidates]
        latencies = [i.latency_p50_ms for i in candidates]
        qualities = [i.quality_score for i in candidates]

        cost_score = self._normalize_lower_better(costs)
        latency_score = self._normalize_lower_better(latencies)
        quality_score = self._normalize_higher_better(qualities)

        result: list[tuple[str, float]] = []
        for idx, inst in enumerate(candidates):
            score = wc * cost_score[idx] + wl * latency_score[idx] + wq * quality_score[idx]
            result.append((inst.name, score))
        return result

    @staticmethod
    def _normalize_lower_better(values: list[float]) -> list[float]:
        """数值越小得分越高（成本/延迟）。"""
        if not values:
            return []
        lo, hi = min(values), max(values)
        if hi - lo < 1e-9:
            return [1.0 for _ in values]
        return [(hi - v) / (hi - lo) for v in values]

    @staticmethod
    def _normalize_higher_better(values: list[float]) -> list[float]:
        """数值越大得分越高（质量）。"""
        if not values:
            return []
        lo, hi = min(values), max(values)
        if hi - lo < 1e-9:
            return [1.0 for _ in values]
        return [(v - lo) / (hi - lo) for v in values]

    @staticmethod
    def _caps(instance: ModelInstance) -> list[str]:
        try:
            return json.loads(instance.capabilities_json)
        except (TypeError, ValueError):
            return []

    @staticmethod
    def _op(actual: float, operator: str, value: float) -> bool:
        if operator == "gt":
            return actual > value
        if operator == "lt":
            return actual < value
        if operator == "gte":
            return actual >= value
        if operator == "lte":
            return actual <= value
        return actual == value

    def _provider_quota_map(self, db: Session) -> dict[int, float]:
        providers = db.query(Provider).all()
        result: dict[int, float] = {}
        for p in providers:
            if p.quota_total > 0:
                result[p.id] = round((p.quota_total - p.quota_used) / p.quota_total * 100, 2)
            else:
                result[p.id] = 0.0
        return result


router_service = RouterService()
