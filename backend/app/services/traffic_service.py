"""流量控制：限流（令牌桶/滑动窗口）+ 配额 + 优先级抢占。

EX-10：限流规则读取走内存快照，启动加载，写操作后调用 ``reload`` 即时失效重建。
EX-06：瞬时流量突刺由令牌桶/滑动窗口削峰，超限返回 429 / code 1004。
EX-05：租户周期配额耗尽返回 403 / code 1003。
"""
from __future__ import annotations

import threading

from sqlalchemy.orm import Session

from ..models import PriorityQueue, RateLimitRule, Tenant, utcnow
from ..schemas import AppError
from ..utils.sliding_window import SlidingWindow, TokenBucket


class TrafficService:
    """限流/配额/优先级服务（进程内单例）。"""

    def __init__(self) -> None:
        self._snapshot: list[RateLimitRule] = []
        self._buckets: dict[str, TokenBucket | SlidingWindow] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # 快照（EX-10）
    # ------------------------------------------------------------------
    def reload(self, db: Session) -> None:
        """从 DB 重新加载启用的限流规则快照（EX-10）。"""
        rules = db.query(RateLimitRule).filter(RateLimitRule.enabled.is_(True)).all()
        with self._lock:
            self._snapshot = rules
            # 规则变更后重建桶，使新阈值/新增规则即时生效
            self._buckets.clear()

    @property
    def snapshot(self) -> list[RateLimitRule]:
        with self._lock:
            return list(self._snapshot)

    # ------------------------------------------------------------------
    # 限流
    # ------------------------------------------------------------------
    def _bucket_key(self, rule: RateLimitRule, tenant_id: int | None, model: str | None) -> str:
        """每个规则 + 维度作用域使用独立桶。

        同一规则内按维度（global/tenant/model/provider）再隔离作用域：
        - tenant 规则：不同租户各有限流额度；
        - model/provider 规则：不同模型/供应商各自独立；
        同时保留 ``rule.id``，使同维度多规则阈值互不抢占。
        """
        scope = {
            "tenant": f"tenant:{tenant_id}",
            "model": f"model:{model}",
            "provider": f"provider:{model}",
        }.get(rule.dimension, "global")
        return f"rule:{rule.id}:{scope}"

    def _get_or_create(self, rule: RateLimitRule, key: str) -> TokenBucket | SlidingWindow:
        with self._lock:
            if key not in self._buckets:
                if rule.algorithm == "sliding_window":
                    self._buckets[key] = SlidingWindow(rule.window_seconds)
                else:
                    # 令牌桶：容量 = 阈值，补充速率 = 阈值 / 窗口秒
                    rate = rule.threshold / max(1, rule.window_seconds)
                    self._buckets[key] = TokenBucket(rule.threshold, rate)
            return self._buckets[key]

    def check_rate_limit(self, tenant_id: int | None, model: str | None) -> None:
        """校验所有启用的限流规则，超限抛 1004。"""
        for rule in self.snapshot:
            key = self._bucket_key(rule, tenant_id, model)
            bucket = self._get_or_create(rule, key)
            if isinstance(bucket, SlidingWindow):
                if bucket.count() >= rule.threshold:
                    raise AppError(1004, f"触发限流：{rule.name}", 429)
                bucket.record()
            else:
                if not bucket.consume(1):
                    raise AppError(1004, f"触发限流：{rule.name}", 429)

    # ------------------------------------------------------------------
    # 配额（EX-05）
    # ------------------------------------------------------------------
    def check_quota(self, tenant: Tenant) -> None:
        """校验租户每日/每月配额，耗尽抛 1003。"""
        if tenant.quota_daily > 0 and tenant.quota_used_daily >= tenant.quota_daily:
            raise AppError(1003, "每日请求配额已耗尽", 403)
        if tenant.quota_monthly > 0 and tenant.quota_used_monthly >= tenant.quota_monthly:
            raise AppError(1003, "每月请求配额已耗尽", 403)
        if tenant.token_quota_monthly > 0 and tenant.token_used_monthly >= tenant.token_quota_monthly:
            raise AppError(1003, "每月 Token 配额已耗尽", 403)

    # ------------------------------------------------------------------
    # 优先级抢占
    # ------------------------------------------------------------------
    def enqueue_priority(self, db: Session, priority: str) -> None:
        """将一次请求计入对应优先级队列（仅演示性更新运行时状态）。"""
        row = db.query(PriorityQueue).filter(PriorityQueue.priority == priority).first()
        if row is not None:
            row.queue_length = max(0, row.queue_length + 1)
            row.updated_at = utcnow()
            db.commit()


traffic_service = TrafficService()
