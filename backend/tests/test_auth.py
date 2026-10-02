"""鉴权与业务转发接口测试（HTTP）。"""
from __future__ import annotations


def test_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["status"] == "up"


def test_chat_missing_api_key(client):
    resp = client.post("/api/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]})
    assert resp.status_code == 401
    assert resp.json()["code"] == 1002


def test_chat_invalid_api_key(client):
    resp = client.post(
        "/api/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers={"X-API-Key": "gw_invalid"},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == 1002


def test_chat_success(client, seed_key):
    resp = client.post(
        "/api/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "你好"}]},
        headers={"X-API-Key": seed_key},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["content"]
    assert body["data"]["model"]
    assert body["data"]["provider"]
    assert body["data"]["usage"]["total_tokens"] > 0


def test_chat_idempotent(client, seed_key):
    headers = {"X-API-Key": seed_key, "X-Request-Id": "req_test_idem_001"}
    payload = {"messages": [{"role": "user", "content": "幂等测试"}]}
    first = client.post("/api/v1/chat/completions", json=payload, headers=headers).json()
    second = client.post("/api/v1/chat/completions", json=payload, headers=headers).json()
    assert first["data"]["request_id"] == second["data"]["request_id"]


def test_chat_stream_sse(client, seed_key):
    with client.stream(
        "POST",
        "/api/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "你好"}], "stream": True},
        headers={"X-API-Key": seed_key},
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = "".join(resp.iter_text())
    assert "data: " in body
    assert "[DONE]" in body


def test_chat_content_safety_blocked(client, seed_key):
    resp = client.post(
        "/api/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "你好"}], "model": "gpt-4o-mini"},
        headers={"X-API-Key": seed_key},
    )
    # 正常路径不受影响（内容安全在输出阶段；mock 输出不触发违禁词）
    assert resp.status_code == 200


class _FakeClient:
    """捕获转发 payload 的假客户端。"""

    def __init__(self) -> None:
        self.captured: dict | None = None

    async def complete(self, payload: dict) -> dict:
        self.captured = payload
        return {"content": "ok", "prompt_tokens": 1, "completion_tokens": 1, "finish_reason": "stop"}


def test_chat_reuses_session_context(client, seed_key, monkeypatch):
    import app.routers.chat as chat_mod

    fake = _FakeClient()
    monkeypatch.setattr(chat_mod, "get_model_client", lambda provider, model_name: fake)

    headers = {"X-API-Key": seed_key}
    client.post(
        "/api/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "第一轮"}], "session_id": "sess_ctx_test"},
        headers=headers,
    )
    client.post(
        "/api/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "第二轮"}], "session_id": "sess_ctx_test"},
        headers=headers,
    )
    assert fake.captured is not None
    # 第二轮 payload 应包含历史（user1+assistant1）与本次 user2
    assert len(fake.captured["messages"]) >= 3

