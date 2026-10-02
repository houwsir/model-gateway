"""负载均衡：实例级（加权最小连接/轮询/一致性哈希/随机）+ 供应商级分流。"""
from __future__ import annotations

import hashlib
import random
import threading

from sqlalchemy.orm import Session

from ..models import InstanceNode, ModelInstance, Provider


class BalancerService:
    """实例级 / 供应商级负载均衡。"""

    def __init__(self) -> None:
        self._rr_counters: dict[int, int] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # 实例级
    # ------------------------------------------------------------------
    def pick_instance(
        self,
        db: Session,
        model_instance: ModelInstance,
        strategy: str = "weighted_least_conn",
        session_id: str | None = None,
    ) -> InstanceNode | None:
        """为逻辑模型选择物理节点。"""
        nodes = (
            db.query(InstanceNode)
            .filter(InstanceNode.model_instance_id == model_instance.id)
            .filter(InstanceNode.status == "healthy")
            .all()
        )
        if not nodes:
            return None

        if strategy == "weighted_round_robin":
            return self._weighted_round_robin(nodes)
        if strategy == "consistent_hash":
            return self._consistent_hash(nodes, session_id or model_instance.name)
        if strategy == "random":
            return random.choice(nodes)
        # 默认 weighted_least_conn
        return self._weighted_least_conn(nodes)

    def _weighted_least_conn(self, nodes: list[InstanceNode]) -> InstanceNode:
        """加权最小连接：优先负载比（连接数/权重）最低的节点。"""
        def key(n: InstanceNode) -> float:
            return n.current_connections / max(1, n.weight)

        return min(nodes, key=key)

    def _weighted_round_robin(self, nodes: list[InstanceNode]) -> InstanceNode:
        """加权轮询（按权重展开的平滑近似）。"""
        with self._lock:
            key = id(nodes[0].model_instance_id)
            counter = self._rr_counters.get(key, 0)
            # 平滑加权轮询：按权重取模
            total_weight = sum(max(1, n.weight) for n in nodes)
            idx = counter % total_weight
            acc = 0
            chosen = nodes[-1]
            for n in nodes:
                acc += max(1, n.weight)
                if idx < acc:
                    chosen = n
                    break
            self._rr_counters[key] = counter + 1
            return chosen

    def _consistent_hash(self, nodes: list[InstanceNode], key: str) -> InstanceNode:
        """一致性哈希：按节点名构造简单哈希环。"""
        def h(s: str) -> int:
            return int(hashlib.md5(s.encode("utf-8")).hexdigest(), 16)

        ring: list[tuple[int, InstanceNode]] = []
        # 每节点 3 个虚拟点
        for n in nodes:
            for i in range(3):
                ring.append((h(f"{n.name}#{i}"), n))
        ring.sort(key=lambda x: x[0])
        target = h(key)
        for point, node in ring:
            if point >= target:
                return node
        return ring[0][1]

    # ------------------------------------------------------------------
    # 供应商级
    # ------------------------------------------------------------------
    def pick_provider(self, db: Session, candidates: list[Provider], strategy: str = "quota_success_cost") -> Provider | None:
        """按分流策略选择供应商。"""
        available = [p for p in candidates if p.status == "online"]
        if not available:
            return None

        if strategy == "fixed_ratio":
            return available[0]
        if strategy == "cost_first":
            return min(available, key=lambda p: p.cost_weight)

        # 默认 quota_success_cost：配额余量 * 成功率 / 成本权重 综合最高
        def score(p: Provider) -> float:
            remaining = max(0.0, p.quota_total - p.quota_used) / max(1, p.quota_total)
            return remaining * (p.success_rate / 100.0) / max(0.01, p.cost_weight)

        return max(available, key=score)

    def provider_ratios(self, db: Session) -> list[dict]:
        """计算当前供应商分流比例（用于 balancing 接口展示）。"""
        providers = db.query(Provider).filter(Provider.status == "online").all()
        if not providers:
            return []

        def score(p: Provider) -> float:
            remaining = max(0.0, p.quota_total - p.quota_used) / max(1, p.quota_total)
            return remaining * (p.success_rate / 100.0) / max(0.01, p.cost_weight)

        scores = [score(p) for p in providers]
        total = sum(scores) or 1.0
        return [
            {"provider": p.name, "ratio": round(s / total * 100)}
            for p, s in sorted(zip(providers, scores), key=lambda x: x[1], reverse=True)
        ]


balancer_service = BalancerService()
