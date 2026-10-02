"""容灾：健康检查 + 熔断（滑动窗口/半开）+ 故障切换 + 降级 + 退避重试。

状态机：closed → open（错误率超阈值）→ half_open（冷却到期放行试探）→ closed/healthy。
每次状态迁移通过 ObservabilityService 生成告警（EX-01/EX-02/EX-03/EX-04）。
"""
from __future__ import annotations

import asyncio
import time

from sqlalchemy.orm import Session

from ..models import Alert, ModelInstance, Provider, ResiliencePolicy, utcnow
from ..schemas import AppError
from ..utils.sliding_window import FailureWindow


class CircuitState:
    """单个模型的熔断状态。"""

    def __init__(self) -> None:
        self.state: str = "closed"  # closed / open / half_open
        self.failure_window: FailureWindow = FailureWindow(window_seconds=60)
        self.open_until: float = 0.0
        self.probe_in_flight: bool = False


class ResilienceService:
    """容灾服务（进程内单例）。"""

    def __init__(self) -> None:
        self.circuits: dict[int, CircuitState] = {}

    def _get(self, model_id: int) -> CircuitState:
        if model_id not in self.circuits:
            self.circuits[model_id] = CircuitState()
        return self.circuits[model_id]

    def is_allowed(
        self,
        model_id: int,
        threshold: float = 0.5,
        cooldown_seconds: int = 30,
        half_open_enabled: bool = True,
    ) -> bool:
        """是否允许请求通过该模型（熔断检查）。"""
        cs = self._get(model_id)
        now = time.monotonic()
        if cs.state == "open":
            if now < cs.open_until:
                return False
            # 冷却到期
            if half_open_enabled:
                cs.state = "half_open"
                return True
            cs.state = "closed"
            cs.failure_window = FailureWindow(60)
            return True
        if cs.state == "half_open":
            if cs.probe_in_flight:
                return False
            cs.probe_in_flight = True
            return True
        return True

    def record(
        self,
        model_id: int,
        success: bool,
        threshold: float = 0.5,
        cooldown_seconds: int = 30,
        half_open_enabled: bool = True,
    ) -> str | None:
        """记录一次调用结果，返回状态迁移（若有），用于告警。"""
        cs = self._get(model_id)
        previous = cs.state
        now = time.monotonic()

        if cs.state == "half_open":
            cs.probe_in_flight = False
            if success:
                cs.state = "closed"
                cs.failure_window = FailureWindow(60)
                return "recovered" if previous == "half_open" else None
            cs.state = "open"
            cs.open_until = now + cooldown_seconds
            return "opened"
        # closed 状态
        cs.failure_window.record(success)
        failed, total = cs.failure_window.stats()
        if total >= 5 and failed / total >= threshold:
            cs.state = "open"
            cs.open_until = now + cooldown_seconds
            return "opened"
        return None

    def state_of(self, model_id: int) -> str:
        return self._get(model_id).state

    # ------------------------------------------------------------------
    # 健康检查（后台周期任务）
    # ------------------------------------------------------------------
    def check_health(self, db: Session) -> list[dict]:
        """主动探测各模型，更新状态并返回本次告警事件。"""
        events: list[dict] = []
        providers = db.query(Provider).all()
        pstatus = {p.id: p.status for p in providers}
        instances = db.query(ModelInstance).all()
        for inst in instances:
            cs = self._get(inst.id)
            # mock 场景：供应商 offline 视为不可用；circuit_open 的模型跳过探测
            provider_ok = pstatus.get(inst.provider_id, "online") != "offline"
            if cs.state == "open":
                inst.status = "circuit_open"
                continue
            if not provider_ok:
                if inst.status != "offline":
                    inst.status = "offline"
                    events.append(
                        {"severity": "critical", "title": f"{inst.name} 供应商不可用", "source": "circuit_breaker"}
                    )
                continue
            # 半开试探：放行一次 ping 判断恢复
            if cs.state == "half_open":
                # ping 视为成功（mock 无真实后端）
                self.record(inst.id, True, half_open_enabled=True)
                inst.status = "healthy"
                events.append(
                    {"severity": "info", "title": f"{inst.name} 已恢复", "source": "circuit_breaker"}
                )
            else:
                inst.status = "high_load" if inst.load >= 80 else "healthy"

        db.commit()
        return events

    # ------------------------------------------------------------------
    # 退避重试 + 故障切换 + 降级（供 chat 路由编排使用）
    # ------------------------------------------------------------------
    async def call_with_retry(self, call_fn, retry_count: int = 2) -> tuple[bool, dict | Exception]:
        """指数退避重试，返回 (成功, 结果/异常)。"""
        last_err: Exception | None = None
        for attempt in range(retry_count + 1):
            try:
                result = await call_fn()
                return True, result
            except Exception as exc:  # noqa: BLE001 - 网关需捕获一切上游异常
                last_err = exc
                if attempt < retry_count:
                    await asyncio.sleep(min(0.05 * (2**attempt), 0.5))
        return False, last_err if last_err is not None else AppError(1010, "上游错误", 502)


resilience_service = ResilienceService()
