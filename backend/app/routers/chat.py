"""业务转发核心入口：POST /api/v1/chat/completions。

主链路：鉴权 → 限流/配额/优先级 → 智能路由 → 负载均衡 → 容灾 → 模型调用
→ 安全过滤 → 记忆写回 → 日志指标。支持非流式 JSON 与 SSE 流式（EX-09 中断补记）。
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..db import SessionLocal, get_db
from ..deps import get_current_tenant
from ..models import ModelInstance, Provider, ResiliencePolicy, Tenant, utcnow
from ..schemas import AppError, ChatCompletionRequest, ok
from ..services import mock_backend
from ..services.balancer_service import balancer_service
from ..services.memory_service import memory_service
from ..services.model_client import get_model_client
from ..services.observability import observability_service
from ..services.resilience_service import resilience_service
from ..services.router_service import router_service
from ..services.safety_service import safety_service
from ..services.traffic_service import traffic_service
from ..utils.idempotency import lookup_idempotency, save_idempotency

router = APIRouter(prefix="/chat", tags=["chat"])

EXCHANGE_RATE_CNY_TO_USD = 7.2


def _usd_price(instance: ModelInstance, price: float) -> float:
    """将单价折算为 USD。"""
    if instance.currency == "CNY":
        return price / EXCHANGE_RATE_CNY_TO_USD
    return price


def _compute_cost(instance: ModelInstance, prompt_tokens: int, completion_tokens: int) -> float:
    """计算 USD 成本（4 位小数）。"""
    cost = prompt_tokens / 1_000_000 * _usd_price(instance, instance.input_price)
    cost += completion_tokens / 1_000_000 * _usd_price(instance, instance.output_price)
    return round(cost, 4)


def _resilience_policy(db: Session, provider_id: int) -> ResiliencePolicy | None:
    return db.query(ResiliencePolicy).filter(ResiliencePolicy.provider_id == provider_id).first()


def _backup_candidates(
    db: Session,
    policy: ResiliencePolicy | None,
    capabilities: list[str],
    exclude_name: str,
) -> list[tuple[ModelInstance, Provider]]:
    """根据容灾策略的备用链路构造备用候选列表。"""
    if policy is None:
        return []
    chain: list[str] = []
    try:
        chain = json.loads(policy.backup_chain_json)
    except (TypeError, ValueError):
        chain = []
    result: list[tuple[ModelInstance, Provider]] = []
    req_caps = set(capabilities or ["text"])
    for pname in chain:
        provider = db.query(Provider).filter(Provider.name == pname, Provider.status == "online").first()
        if provider is None:
            continue
        instances = (
            db.query(ModelInstance)
            .filter(ModelInstance.provider_id == provider.id)
            .filter(ModelInstance.status != "circuit_open", ModelInstance.status != "offline")
            .all()
        )
        for inst in instances:
            try:
                caps = set(json.loads(inst.capabilities_json))
            except (TypeError, ValueError):
                caps = set()
            if inst.name != exclude_name and req_caps.issubset(caps):
                result.append((inst, provider))
    return result


async def _try_candidates(
    db: Session,
    candidates: list[tuple[ModelInstance, Provider]],
    payload: dict,
) -> tuple[bool, dict | None, ModelInstance | None, Provider | None]:
    """按序尝试候选模型（带熔断检查 + 退避重试），返回第一个成功结果。"""
    for inst, provider in candidates:
        policy = _resilience_policy(db, provider.id)
        threshold = policy.failure_rate_threshold if policy else 0.5
        cooldown = policy.cooldown_seconds if policy else 30
        half_open = policy.half_open_enabled if policy else True

        if not resilience_service.is_allowed(inst.id, threshold, cooldown, half_open):
            continue

        client = get_model_client(provider, inst.name)
        ok_flag, result = await resilience_service.call_with_retry(
            lambda c=client: c.complete(payload),
            retry_count=policy.retry_count if policy else 2,
        )
        resilience_service.record(inst.id, ok_flag, threshold, cooldown, half_open)
        if ok_flag and isinstance(result, dict):
            return True, result, inst, provider
    return False, None, None, None


@router.post("/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    db: Annotated[Session, Depends(get_db)],
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
    x_request_id: Annotated[str | None, Header(alias="X-Request-Id")] = None,
):
    """网关统一推理入口。"""
    request_id = x_request_id or f"req_{uuid.uuid4().hex[:8]}"

    # EX-07 幂等：命中返回首次缓存响应，不重复计费
    if x_request_id:
        cached = lookup_idempotency(db, x_request_id)
        if cached is not None:
            return cached

    # 治理层：限流 / 配额
    traffic_service.check_rate_limit(tenant.id, body.model)
    traffic_service.check_quota(tenant)

    priority = body.priority or tenant.priority_default or "P1"
    traffic_service.enqueue_priority(db, priority)

    # 调度层：智能路由
    decision = router_service.route(
        db, body.scenario_tag, body.capabilities, body.messages, body.model, body.max_tokens
    )
    if decision.selected is None:
        raise AppError(1005, "无可用模型（候选全部被规则过滤或熔断）", 503)

    selected: ModelInstance = decision.selected
    provider: Provider = decision.provider

    # 输入安全（prompt 注入防护）
    for m in body.messages:
        sr_in = safety_service.filter_input(m.content, prompt_injection_guard=True)
        if sr_in.blocked:
            raise AppError(1008, sr_in.reason, 400)

    # 负载均衡：选择物理节点
    node = balancer_service.pick_instance(db, selected, "weighted_least_conn", body.session_id)

    # 持久记忆：跨请求复用上下文（EX-08）。先取历史，再拼接本次消息。
    messages = [m.model_dump() for m in body.messages]
    if body.session_id:
        history = memory_service.get_context(db, body.session_id, max_tokens=8000)
        if history:
            messages = history + messages

    payload = {
        "messages": messages,
        "max_tokens": body.max_tokens,
        "temperature": body.temperature,
    }

    start = time.monotonic()

    if body.stream:
        return _stream_response(
            db, tenant, body, decision, selected, provider, node, payload, priority, request_id, start
        )

    # ---- 非流式 ----
    candidates = [(selected, provider)] + _backup_candidates(
        db, _resilience_policy(db, provider.id), body.capabilities, selected.name
    )
    ok_flag, result, used_model, used_provider = await _try_candidates(db, candidates, payload)

    if not ok_flag or result is None:
        # EX-04 全部高优不可用 → 降级
        policy = _resilience_policy(db, provider.id)
        degrade_mode = policy.degrade_mode if policy else "downgrade_model"
        if degrade_mode == "downgrade_model":
            fallback = (
                db.query(ModelInstance)
                .join(Provider, ModelInstance.provider_id == Provider.id)
                .filter(Provider.status == "online", ModelInstance.status == "healthy")
                .filter(ModelInstance.name != selected.name)
                .order_by(ModelInstance.input_price.asc())
                .first()
            )
            if fallback is not None:
                fb_provider = db.query(Provider).filter(Provider.id == fallback.provider_id).first()
                ok_flag, result, used_model, used_provider = await _try_candidates(
                    db, [(fallback, fb_provider)], payload
                )
        if not ok_flag or result is None:
            raise AppError(1005, "全部可用模型均失败，已尝试降级", 503)

    content = result.get("content", "")
    prompt_tokens = int(result.get("prompt_tokens", 0))
    completion_tokens = int(result.get("completion_tokens", 0))

    # 输出安全过滤（EX-11）
    sr_out = safety_service.filter_output(content)
    if sr_out.blocked:
        observability_service.log_request(
            db,
            request_id=request_id,
            tenant_id=tenant.id,
            session_id=body.session_id,
            provider_id=used_provider.id if used_provider else None,
            model_instance_id=used_model.id if used_model else None,
            instance_node_id=node.id if node else None,
            route_policy_id=decision.policy.id if decision.policy else None,
            priority=priority,
            prompt_tokens=prompt_tokens,
            completion_tokens=0,
            total_tokens=prompt_tokens,
            latency_ms=int((time.monotonic() - start) * 1000),
            cost=0.0,
            status="rejected",
            error_code="1008",
            error_message=sr_out.reason,
            is_stream=False,
        )
        raise AppError(1008, sr_out.reason, 400)

    latency_ms = int((time.monotonic() - start) * 1000)
    cost = _compute_cost(used_model, prompt_tokens, completion_tokens)

    # 记忆写回（EX-08）
    memory_saved = False
    if body.session_id:
        memory_saved = memory_service.save(
            db,
            body.session_id,
            tenant.id,
            [
                {"role": "user", "content": body.messages[-1].content},
                {"role": "assistant", "content": content},
            ],
        )

    # 计量：租户用量累计
    tenant.quota_used_daily += 1
    tenant.quota_used_monthly += 1
    tenant.token_used_monthly += prompt_tokens + completion_tokens
    tenant.updated_at = utcnow()

    observability_service.log_request(
        db,
        request_id=request_id,
        tenant_id=tenant.id,
        session_id=body.session_id,
        provider_id=used_provider.id if used_provider else None,
        model_instance_id=used_model.id if used_model else None,
        instance_node_id=node.id if node else None,
        route_policy_id=decision.policy.id if decision.policy else None,
        priority=priority,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        latency_ms=latency_ms,
        cost=cost,
        status="success",
        is_stream=False,
    )
    db.commit()

    data = {
        "request_id": request_id,
        "model": used_model.name,
        "provider": used_provider.name,
        "instance": node.name if node else "auto",
        "route_policy": decision.policy.name if decision.policy else None,
        "content": content,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
        "cost": cost,
        "latency_ms": latency_ms,
        "finish_reason": result.get("finish_reason", "stop"),
        "memory_saved": memory_saved,
    }
    response = ok(data)
    if x_request_id:
        save_idempotency(db, x_request_id, response)
    return response


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _stream_response(
    request_db: Session,
    tenant: Tenant,
    body: ChatCompletionRequest,
    decision,
    selected: ModelInstance,
    provider: Provider,
    node,
    payload: dict,
    priority: str,
    request_id: str,
    start: float,
) -> StreamingResponse:
    """构造 SSE 流式响应。"""

    async def event_stream():
        db = SessionLocal()
        completed = False
        prompt_tokens = sum(max(1, len(m.get("content", "")) // 4) for m in payload["messages"])
        completion_tokens = 0
        content_parts: list[str] = []
        error_code: str | None = None
        status = "success"
        try:
            yield _sse(
                {
                    "type": "start",
                    "request_id": request_id,
                    "model": selected.name,
                    "provider": provider.name,
                    "instance": node.name if node else "auto",
                }
            )
            client = get_model_client(provider, selected.name)
            async for chunk in client.stream(payload):
                content_parts.append(chunk)
                yield _sse({"type": "delta", "content": chunk})

            content = "".join(content_parts)
            completion_tokens = max(1, len(content) // 4)
            cost = _compute_cost(selected, prompt_tokens, completion_tokens)
            latency_ms = int((time.monotonic() - start) * 1000)
            yield _sse(
                {
                    "type": "done",
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens,
                    },
                    "cost": cost,
                    "latency_ms": latency_ms,
                    "finish_reason": "stop",
                }
            )
            completed = True
            yield "data: [DONE]\n\n"

            # 记忆写回
            if body.session_id:
                memory_service.save(
                    db,
                    body.session_id,
                    tenant.id,
                    [
                        {"role": "user", "content": body.messages[-1].content},
                        {"role": "assistant", "content": content},
                    ],
                )
            # 计量
            t = db.query(Tenant).filter(Tenant.id == tenant.id).first()
            if t:
                t.quota_used_daily += 1
                t.quota_used_monthly += 1
                t.token_used_monthly += prompt_tokens + completion_tokens
                t.updated_at = utcnow()
        except asyncio.CancelledError:
            # EX-09 客户端中断
            status = "interrupted"
            raise
        except Exception as exc:  # noqa: BLE001
            status = "failed"
            error_code = "1010"
            yield _sse({"type": "error", "message": str(exc)})
        finally:
            # EX-09 finally 补记请求状态
            latency_ms = int((time.monotonic() - start) * 1000)
            cost = _compute_cost(selected, prompt_tokens, completion_tokens)
            observability_service.log_request(
                db,
                request_id=request_id,
                tenant_id=tenant.id,
                session_id=body.session_id,
                provider_id=provider.id,
                model_instance_id=selected.id,
                instance_node_id=node.id if node else None,
                route_policy_id=decision.policy.id if decision.policy else None,
                priority=priority,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                latency_ms=latency_ms,
                cost=cost,
                status=status if completed or status == "failed" else "interrupted",
                error_code=error_code,
                is_stream=True,
            )
            db.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
