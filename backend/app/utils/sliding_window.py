"""限流与滑动窗口数据结构。

- ``TokenBucket``：令牌桶（EX-06 瞬时流量突刺削峰）。
- ``SlidingWindow``：固定窗口内的请求时间戳队列（并发/错误率统计）。
"""
from __future__ import annotations

import threading
import time
from collections import deque


class TokenBucket:
    """令牌桶限流器。

    以 ``capacity`` 为桶容量、``refill_rate`` 为每秒补充令牌数。
    ``consume(n)`` 返回是否允许通过；不通过时不扣减令牌。
    """

    def __init__(self, capacity: int, refill_rate: float):
        self.capacity: int = max(1, int(capacity))
        self.refill_rate: float = max(0.0, float(refill_rate))
        self._tokens: float = float(self.capacity)
        self._last_refill: float = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed > 0:
            self._tokens = min(float(self.capacity), self._tokens + elapsed * self.refill_rate)
            self._last_refill = now

    def consume(self, n: int = 1) -> bool:
        """尝试消费 n 个令牌。"""
        with self._lock:
            self._refill()
            if self._tokens >= n:
                self._tokens -= n
                return True
            return False

    @property
    def available(self) -> float:
        """当前可用令牌数（只读近似值）。"""
        with self._lock:
            self._refill()
            return self._tokens


class SlidingWindow:
    """滑动窗口：保存最近 ``window_seconds`` 内的请求时间戳。"""

    def __init__(self, window_seconds: int = 1):
        self.window_seconds: int = max(1, int(window_seconds))
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    def _prune(self) -> None:
        cutoff = time.monotonic() - self.window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

    def record(self) -> None:
        """记录一次请求。"""
        with self._lock:
            self._prune()
            self._timestamps.append(time.monotonic())

    def count(self) -> int:
        """窗口内请求数。"""
        with self._lock:
            self._prune()
            return len(self._timestamps)


class FailureWindow:
    """错误率滑动窗口：记录窗口内成功/失败次数。"""

    def __init__(self, window_seconds: int = 60):
        self.window_seconds: int = max(1, int(window_seconds))
        self._events: deque[tuple[float, bool]] = deque()  # (timestamp, is_success)
        self._lock = threading.Lock()

    def _prune(self) -> None:
        cutoff = time.monotonic() - self.window_seconds
        while self._events and self._events[0][0] < cutoff:
            self._events.popleft()

    def record(self, success: bool) -> None:
        with self._lock:
            self._prune()
            self._events.append((time.monotonic(), success))

    def stats(self) -> tuple[int, int]:
        """返回 (失败数, 总数)。"""
        with self._lock:
            self._prune()
            total = len(self._events)
            failed = sum(1 for _, ok in self._events if not ok)
            return failed, total
