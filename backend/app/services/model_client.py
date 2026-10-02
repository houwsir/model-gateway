"""可插拔模型客户端：``ModelClient`` 抽象 + 工厂（按 ``provider.provider_type`` 实例化）。

- ``mock`` → ``MockModelClient``（本地进程内生成，demo 默认）；
- ``openai``/``zhipu`` → ``OpenAICompatibleClient``（OpenAI 兼容协议）；
- ``anthropic`` → ``AnthropicClient``（Messages API）。
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

import httpx

from ..models import Provider
from ..schemas import AppError
from . import mock_backend


class ModelClient(ABC):
    """模型客户端抽象接口。"""

    def __init__(self, provider: Provider, model_name: str):
        self.provider = provider
        self.model_name = model_name

    @abstractmethod
    async def complete(self, payload: dict) -> dict:
        """非流式调用，返回 {content, prompt_tokens, completion_tokens, finish_reason}。"""

    @abstractmethod
    async def stream(self, payload: dict) -> AsyncIterator[str]:
        """流式调用，逐段产出内容文本。"""

    @abstractmethod
    async def ping(self) -> bool:
        """健康探测。"""


class MockModelClient(ModelClient):
    """本地 mock 客户端。"""

    async def complete(self, payload: dict) -> dict:
        if mock_backend.should_fail():
            raise AppError(1010, f"mock 上游 {self.model_name} 注入失败", 502)
        messages = payload.get("messages", [])
        content = mock_backend.generate_response(messages, self.model_name, payload.get("max_tokens", 512))
        prompt_tokens = sum(mock_backend.estimate_tokens(m.get("content", "")) for m in messages)
        return {
            "content": content,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": mock_backend.estimate_tokens(content),
            "finish_reason": "stop",
        }

    async def stream(self, payload: dict) -> AsyncIterator[str]:
        if mock_backend.should_fail():
            raise AppError(1010, f"mock 上游 {self.model_name} 注入失败", 502)
        messages = payload.get("messages", [])
        content = mock_backend.generate_response(messages, self.model_name, payload.get("max_tokens", 512))
        for chunk in mock_backend.chunk_content(content):
            yield chunk

    async def ping(self) -> bool:
        return self.provider.status != "offline"


class OpenAICompatibleClient(ModelClient):
    """OpenAI 兼容协议客户端（openai / zhipu 等）。"""

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.provider.api_key_encrypted or ''}", "Content-Type": "application/json"}

    def _require_config(self) -> str:
        base_url = (self.provider.base_url or "").rstrip("/")
        if not base_url:
            raise AppError(1010, f"供应商 {self.provider.name} 缺少 base_url", 502)
        return base_url

    async def complete(self, payload: dict) -> dict:
        base_url = self._require_config()
        body = {
            "model": self.model_name,
            "messages": payload.get("messages", []),
            "max_tokens": payload.get("max_tokens", 512),
            "temperature": payload.get("temperature", 0.7),
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(f"{base_url}/chat/completions", json=body, headers=self._headers())
        except httpx.TimeoutException:
            raise AppError(1009, "上游超时", 504)
        except httpx.HTTPError:
            raise AppError(1010, "上游网络错误", 502)

        if resp.status_code == 429:
            raise AppError(1010, "上游限流 429", 502)
        if resp.status_code >= 400:
            raise AppError(1010, f"上游错误 {resp.status_code}", 502)

        data = resp.json()
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = data.get("usage", {})
        return {
            "content": message.get("content", ""),
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "finish_reason": choice.get("finish_reason", "stop"),
        }

    async def stream(self, payload: dict) -> AsyncIterator[str]:
        base_url = self._require_config()
        body = {
            "model": self.model_name,
            "messages": payload.get("messages", []),
            "max_tokens": payload.get("max_tokens", 512),
            "temperature": payload.get("temperature", 0.7),
            "stream": True,
        }
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", f"{base_url}/chat/completions", json=body, headers=self._headers()) as resp:
                    if resp.status_code == 429:
                        raise AppError(1010, "上游限流 429", 502)
                    if resp.status_code >= 400:
                        raise AppError(1010, f"上游错误 {resp.status_code}", 502)
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            obj = json.loads(data)
                        except ValueError:
                            continue
                        delta = obj.get("choices", [{}])[0].get("delta", {}).get("content")
                        if delta:
                            yield delta
        except httpx.TimeoutException:
            raise AppError(1009, "上游超时", 504)
        except httpx.HTTPError:
            raise AppError(1010, "上游网络错误", 502)

    async def ping(self) -> bool:
        try:
            base_url = self._require_config()
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(base_url)
                return resp.status_code < 500
        except Exception:  # noqa: BLE001
            return False


class AnthropicClient(ModelClient):
    """Anthropic Messages API 客户端。"""

    def _require_config(self) -> str:
        base_url = (self.provider.base_url or "https://api.anthropic.com").rstrip("/")
        return base_url

    async def complete(self, payload: dict) -> dict:
        base_url = self._require_config()
        body = {
            "model": self.model_name,
            "max_tokens": payload.get("max_tokens", 512),
            "messages": [m for m in payload.get("messages", []) if m.get("role") in ("user", "assistant")],
        }
        headers = {
            "x-api-key": self.provider.api_key_encrypted or "",
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(f"{base_url}/v1/messages", json=body, headers=headers)
        except httpx.TimeoutException:
            raise AppError(1009, "上游超时", 504)
        except httpx.HTTPError:
            raise AppError(1010, "上游网络错误", 502)

        if resp.status_code == 429:
            raise AppError(1010, "上游限流 429", 502)
        if resp.status_code >= 400:
            raise AppError(1010, f"上游错误 {resp.status_code}", 502)

        data = resp.json()
        content = "".join(b.get("text", "") for b in data.get("content", []))
        usage = data.get("usage", {})
        return {
            "content": content,
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "finish_reason": data.get("stop_reason", "stop"),
        }

    async def stream(self, payload: dict) -> AsyncIterator[str]:
        # Anthropic 流式协议为事件流，逐段产出 text_delta 文本
        base_url = self._require_config()
        body = {
            "model": self.model_name,
            "max_tokens": payload.get("max_tokens", 512),
            "messages": [m for m in payload.get("messages", []) if m.get("role") in ("user", "assistant")],
            "stream": True,
        }
        headers = {
            "x-api-key": self.provider.api_key_encrypted or "",
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", f"{base_url}/v1/messages", json=body, headers=headers) as resp:
                    if resp.status_code >= 400:
                        raise AppError(1010, f"上游错误 {resp.status_code}", 502)
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        try:
                            obj = json.loads(data)
                        except ValueError:
                            continue
                        if obj.get("type") == "content_block_delta":
                            text = obj.get("delta", {}).get("text", "")
                            if text:
                                yield text
        except httpx.TimeoutException:
            raise AppError(1009, "上游超时", 504)
        except httpx.HTTPError:
            raise AppError(1010, "上游网络错误", 502)

    async def ping(self) -> bool:
        return True


def get_model_client(provider: Provider, model_name: str) -> ModelClient:
    """工厂：按 ``provider.provider_type`` 实例化客户端。"""
    ptype = (provider.provider_type or "mock").lower()
    if ptype == "mock":
        return MockModelClient(provider, model_name)
    if ptype in ("openai", "zhipu"):
        return OpenAICompatibleClient(provider, model_name)
    if ptype == "anthropic":
        return AnthropicClient(provider, model_name)
    return MockModelClient(provider, model_name)
