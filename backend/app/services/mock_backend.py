"""本地 mock 模型端点（demo 可跑，不依赖真实 API Key）。

提供确定性的「生成」逻辑与故障注入能力：
- ``generate_response`` 基于最后一条用户消息返回演示文案；
- ``inject_failures`` 注入 N 次失败（用于演示/测试熔断与故障切换）。
"""
from __future__ import annotations

import threading

_failure_budget = 0
_lock = threading.Lock()

# 各模型风格化前缀，便于在响应中体现路由命中的模型
_MODEL_FLAVOR = {
    "gpt-4o-mini": "OpenAI · GPT-4o-mini",
    "claude-3.5-sonnet": "Anthropic · Claude 3.5 Sonnet",
    "qwen2.5-72b": "通义 · Qwen2.5-72B",
    "llama-3.1-70b": "Meta · Llama 3.1-70B",
    "glm-4": "智谱 · GLM-4",
}


def inject_failures(n: int) -> None:
    """注入接下来 n 次模型调用失败。"""
    global _failure_budget
    with _lock:
        _failure_budget = max(0, _failure_budget + n)


def reset_failures() -> None:
    """清除注入的失败。"""
    global _failure_budget
    with _lock:
        _failure_budget = 0


def should_fail() -> bool:
    global _failure_budget
    with _lock:
        if _failure_budget > 0:
            _failure_budget -= 1
            return True
        return False


def last_user_message(messages: list) -> str:
    """提取最后一条 user 消息内容。"""
    for m in reversed(messages):
        role = getattr(m, "role", m.get("role") if isinstance(m, dict) else None)
        content = getattr(m, "content", m.get("content") if isinstance(m, dict) else "")
        if role == "user" and content:
            return content
    return "你好"


def generate_response(messages: list, model: str, max_tokens: int = 512) -> str:
    """生成演示回复。"""
    flavor = _MODEL_FLAVOR.get(model, model)
    question = last_user_message(messages)
    if not question.strip():
        question = "你好"
    return (
        f"你好，我是 {flavor} 的 mock 回复。已收到你的问题：「{question[:40]}」。"
        "本响应由模型网关本地 mock 端点生成，用于演示路由转发与 SSE 流式链路，无需真实 API Key。"
    )


def estimate_tokens(text: str) -> int:
    """粗略 token 估算（约 4 字符/token）。"""
    return max(1, len(text) // 4)


def chunk_content(content: str, chunk_size: int = 6) -> list[str]:
    """将内容切分为 SSE delta 分片。"""
    return [content[i : i + chunk_size] for i in range(0, len(content), chunk_size)]
