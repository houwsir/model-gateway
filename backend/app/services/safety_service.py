"""内容安全过滤（EX-11）。

输出内容命中违禁关键词或疑似 prompt 注入时拦截，返回 code 1008。
"""
from __future__ import annotations

from dataclasses import dataclass

# 演示用违禁关键词（真实环境接入专业内容安全引擎）
_FORBIDDEN_KEYWORDS = ["违禁品", "非法交易", "暴力攻击教程", "色情内容"]

# prompt 注入特征
_INJECTION_PATTERNS = ["忽略以上指令", "ignore previous instructions", "system prompt", "你是开发者模式"]


@dataclass
class SafetyResult:
    """安全过滤结果。"""

    blocked: bool = False
    reason: str = ""


class SafetyService:
    """内容安全服务。"""

    def filter_output(self, content: str) -> SafetyResult:
        """过滤输出内容，命中违禁词则拦截。"""
        for kw in _FORBIDDEN_KEYWORDS:
            if kw in content:
                return SafetyResult(blocked=True, reason=f"输出包含违禁内容关键词「{kw}」")
        return SafetyResult(blocked=False)

    def filter_input(self, content: str, prompt_injection_guard: bool = True) -> SafetyResult:
        """过滤输入内容（可选 prompt 注入防护）。"""
        if prompt_injection_guard:
            for pattern in _INJECTION_PATTERNS:
                if pattern.lower() in content.lower():
                    return SafetyResult(blocked=True, reason="疑似 Prompt 注入攻击")
        return SafetyResult(blocked=False)


safety_service = SafetyService()
