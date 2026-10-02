"""种子数据（幂等写入）。

启动时若 ``tenants`` 表已有数据则跳过。数据对齐 ``docs/DATA_MODEL.md`` 第 3 节，
保证 demo 启动即有数据且与前端原型 9 页展示一致。
"""
from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .models import (
    Alert,
    AlertRule,
    ApiKey,
    BalancingGroup,
    ChatSession,
    GatewaySettings,
    IdempotencyRecord,
    InstanceNode,
    MemoryMessage,
    MemoryPolicy,
    ModelInstance,
    PriorityQueue,
    Provider,
    RateLimitRule,
    RequestLog,
    ResiliencePolicy,
    RoutePolicy,
    RouteRule,
    Tenant,
    utcnow,
)

# 种子 API Key（README 同步列出，供测试 POST /chat/completions）
SEED_API_KEYS: dict[str, str] = {
    "客服中心": "gw_a1b2c3d4e5f60718293a4b5c6d7e8f90",
    "营销部": "gw_f9e8d7c6b5a493827161504132231405",
    "研发平台": "gw_0123456789abcdef0123456789abcdef",
    "数据团队": "gw_abcdef0123456789abcdef0123456789",
}


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _prefix(key: str) -> str:
    return f"{key[:8]}****"


def _mask_key(key: str | None, keep: int = 4) -> str:
    """简单掩码存储（真实环境应为 AES 加密，demo 用掩码）。"""
    if not key:
        return "sk-••••••••"
    return f"{key[:3]}{'•' * 8}{key[-keep:]}"


def _hours_ago(h: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ")


def seed(db: Session) -> None:
    """幂等写入全部种子数据。"""
    if db.query(Tenant).count() > 0:
        return

    now = utcnow()

    # ------------------------------------------------------------------
    # 3.1 租户（4）
    # ------------------------------------------------------------------
    tenants_data = [
        ("客服中心", "P1", 50000, 1200000, 816000, 400000000, 144000000),
        ("营销部", "P2", 20000, 600000, 492000, 200000000, 164000000),
        ("研发平台", "P1", 80000, 2000000, 900000, 600000000, 270000000),
        ("数据团队", "P3", 10000, 300000, 285000, 100000000, 95000000),
    ]
    tenants: list[Tenant] = []
    for name, pri, qd, qm, qum, tqm, tum in tenants_data:
        t = Tenant(
            name=name,
            priority_default=pri,
            quota_daily=qd,
            quota_monthly=qm,
            quota_used_monthly=qum,
            token_quota_monthly=tqm,
            token_used_monthly=tum,
            status="active",
            created_at=now,
            updated_at=now,
        )
        db.add(t)
        tenants.append(t)
    db.flush()

    # ------------------------------------------------------------------
    # 3.2 api_keys（4）
    # ------------------------------------------------------------------
    for tenant in tenants:
        key = SEED_API_KEYS[tenant.name]
        db.add(
            ApiKey(
                tenant_id=tenant.id,
                name=f"{tenant.name}·默认密钥",
                key_hash=_hash_key(key),
                key_prefix=_prefix(key),
                status="active",
                created_at=now,
                expires_at=None,
            )
        )

    # ------------------------------------------------------------------
    # 3.3 providers（4，全部 mock）
    # ------------------------------------------------------------------
    providers_data = [
        ("OpenAI", "mock", "online", 1000000000, 280000000, 99.7, "sk-proj-demo0000000000003f2a"),
        ("Anthropic", "mock", "online", 800000000, 368000000, 99.9, "sk-ant-demo0000000000009c1b"),
        ("自建集群", "mock", "online", 500000000, 440000000, 98.2, None),
        ("智谱", "mock", "offline", 200000000, 200000000, 45.0, None),
    ]
    providers: list[Provider] = []
    for name, ptype, status, quota_total, quota_used, sr, raw_key in providers_data:
        p = Provider(
            name=name,
            provider_type=ptype,
            base_url=None,
            api_key_encrypted=raw_key,
            api_key_masked=_mask_key(raw_key) if raw_key else "sk-••••••••",
            status=status,
            quota_total=quota_total,
            quota_used=quota_used,
            success_rate=sr,
            cost_weight=1.0,
            created_at=now,
            updated_at=now,
        )
        db.add(p)
        providers.append(p)
    db.flush()

    provider_by_name = {p.name: p for p in providers}

    # ------------------------------------------------------------------
    # 3.4 model_instances（5）
    # ------------------------------------------------------------------
    models_data = [
        ("gpt-4o-mini", "OpenAI", ["text", "multimodal"], 0.15, 0.60, "USD", "high", "healthy", 212, 380, 64, 0.82),
        ("claude-3.5-sonnet", "Anthropic", ["text", "long_context"], 3.00, 15.00, "USD", "high", "healthy", 388, 610, 41, 0.92),
        ("qwen2.5-72b", "自建集群", ["text"], 0.50, 2.00, "CNY", "mid", "high_load", 505, 800, 88, 0.80),
        ("llama-3.1-70b", "自建集群", ["text"], 0.40, 1.60, "CNY", "mid", "healthy", 301, 520, 55, 0.75),
        ("glm-4", "智谱", ["text", "multimodal"], 1.00, 3.00, "CNY", "fallback", "circuit_open", 0, 0, 0, 0.78),
    ]
    instances: list[ModelInstance] = []
    for name, pname, caps, ip, op, cur, tier, status, p50, p95, load, q in models_data:
        mi = ModelInstance(
            provider_id=provider_by_name[pname].id,
            name=name,
            capabilities_json=json.dumps(caps),
            input_price=ip,
            output_price=op,
            currency=cur,
            max_context_tokens=128000,
            tier=tier,
            status=status,
            latency_p50_ms=p50,
            latency_p95_ms=p95,
            load=load,
            quality_score=q,
            created_at=now,
            updated_at=now,
        )
        db.add(mi)
        instances.append(mi)
    db.flush()

    instance_by_name = {mi.name: mi for mi in instances}

    # ------------------------------------------------------------------
    # 3.5 instance_nodes（4）
    # ------------------------------------------------------------------
    nodes_data = [
        ("inst-qwen-01", "qwen2.5-72b", 40, 142, "healthy"),
        ("inst-qwen-02", "qwen2.5-72b", 35, 96, "healthy"),
        ("inst-llama-01", "llama-3.1-70b", 25, 88, "healthy"),
        ("inst-glm-01", "glm-4", 10, 0, "circuit_open"),
    ]
    for name, mname, weight, conn, status in nodes_data:
        db.add(
            InstanceNode(
                model_instance_id=instance_by_name[mname].id,
                name=name,
                weight=weight,
                current_connections=conn,
                status=status,
                created_at=now,
                updated_at=now,
            )
        )

    # ------------------------------------------------------------------
    # 3.6 route_policies（3）
    # ------------------------------------------------------------------
    policies_data = [
        ("通用对话·默认", "default", 0.40, 0.35, 0.25, 1),
        ("高优时延", "realtime", 0.15, 0.70, 0.15, 0),
        ("高优质量", "quality", 0.20, 0.20, 0.60, 0),
    ]
    for name, tag, wc, wl, wq, is_default in policies_data:
        db.add(
            RoutePolicy(
                name=name,
                scenario_tag=tag,
                weight_cost=wc,
                weight_latency=wl,
                weight_quality=wq,
                exploration_rate=0.05,
                is_default=bool(is_default),
                status="enabled",
                created_at=now,
                updated_at=now,
            )
        )

    # ------------------------------------------------------------------
    # 3.7 route_rules（4）
    # ------------------------------------------------------------------
    rules_data = [
        ("能力过滤", "capability", {"field": "input_has_image", "operator": "eq", "value": True}, "route_to_multimodal", 1, True),
        ("成本上限", "cost", {"field": "estimated_cost", "operator": "gt", "value": 0.5}, "downgrade", 2, True),
        ("配额保护", "quota", {"field": "provider_quota_remaining", "operator": "lt", "value": 10}, "exclude_provider", 3, True),
        ("延迟上限", "latency", {"field": "p95_latency", "operator": "gt", "value": 800}, "exclude_model", 4, False),
    ]
    for name, rtype, cond, action, pri, enabled in rules_data:
        db.add(
            RouteRule(
                name=name,
                rule_type=rtype,
                condition_json=json.dumps(cond, ensure_ascii=False),
                action=action,
                priority=pri,
                enabled=enabled,
                created_at=now,
                updated_at=now,
            )
        )

    # ------------------------------------------------------------------
    # 3.8 balancing_groups（1）
    # ------------------------------------------------------------------
    db.add(
        BalancingGroup(
            name="默认均衡组",
            strategy="weighted_least_conn",
            provider_strategy="quota_success_cost",
            config_json="{}",
            created_at=now,
            updated_at=now,
        )
    )

    # ------------------------------------------------------------------
    # 3.9 resilience_policies（4）
    # ------------------------------------------------------------------
    resilience_data = [
        ("OpenAI", ["Anthropic", "自建集群"], 2, "normal", 3),
        ("Anthropic", ["OpenAI", "自建集群"], 2, "normal", 1),
        ("自建集群", ["OpenAI"], 1, "degraded", 7),
        ("智谱", ["自建集群"], 2, "circuit_open", 12),
    ]
    for pname, chain, retry, status, switch in resilience_data:
        db.add(
            ResiliencePolicy(
                provider_id=provider_by_name[pname].id,
                failure_rate_threshold=0.5,
                cooldown_seconds=30,
                half_open_enabled=True,
                failover_mode="auto_switch",
                backup_selection="same_capability_lowest_cost",
                degrade_mode="downgrade_model",
                backup_chain_json=json.dumps(chain, ensure_ascii=False),
                retry_count=retry,
                status=status,
                switch_count=switch,
                created_at=now,
                updated_at=now,
            )
        )

    # ------------------------------------------------------------------
    # 3.10 sessions（4）+ memories
    # ------------------------------------------------------------------
    sessions_data = [
        ("sess_9f2a1c", "客服中心", 24, 8400, "active", 1 / 60),
        ("sess_3b7e8d", "营销部", 41, 12100, "active", 3 / 60),
        ("sess_7c1a42", "研发平台", 8, 3200, "idle", 15 / 60),
        ("sess_d5e9f0", "数据团队", 67, 18600, "idle", 42 / 60),
    ]
    for sid, tname, count, tokens, status, ago_h in sessions_data:
        tenant = next(t for t in tenants if t.name == tname)
        s = ChatSession(
            session_id=sid,
            tenant_id=tenant.id,
            message_count=count,
            context_tokens=tokens,
            status=status,
            last_active_at=_hours_ago(ago_h),
            ttl_seconds=86400,
            created_at=_hours_ago(ago_h * 60),
        )
        db.add(s)
        db.flush()

        for i in range(2):
            db.add(
                MemoryMessage(
                    session_id=s.id,
                    role="user" if i % 2 == 0 else "assistant",
                    content=f"这是 {sid} 的第 {i + 1} 条示例记忆消息（演示数据）。",
                    tokens=random.randint(10, 120),
                    storage_tier="hot" if i == 0 else "cold",
                    created_at=_hours_ago(ago_h + i * 0.01),
                    expires_at=_hours_ago(-24),
                )
            )

    # ------------------------------------------------------------------
    # 3.11 memory_policies（1）
    # ------------------------------------------------------------------
    db.add(
        MemoryPolicy(
            id=1,
            hot_storage="memory",
            cold_storage="sqlite+vector",
            context_ttl_seconds=86400,
            rag_enabled=True,
            user_delete_enabled=True,
            pii_mask_enabled=True,
            auto_expire_enabled=True,
            audit_enabled=True,
            updated_at=now,
        )
    )

    # ------------------------------------------------------------------
    # 3.12 rate_limit_rules（4）
    # ------------------------------------------------------------------
    rl_data = [
        ("全局 QPS", "global", 500, 1, "token_bucket", "reject_429", True),
        ("单租户 QPS", "tenant", 50, 1, "token_bucket", "reject_429", True),
        ("单模型并发", "model", 200, 1, "sliding_window", "queue_then_reject", True),
        ("供应商保护", "provider", 1000, 1, "token_bucket", "switch_provider", False),
    ]
    for name, dim, threshold, win, algo, action, enabled in rl_data:
        db.add(
            RateLimitRule(
                name=name,
                dimension=dim,
                threshold=threshold,
                window_seconds=win,
                algorithm=algo,
                action=action,
                enabled=enabled,
                created_at=now,
                updated_at=now,
            )
        )

    # ------------------------------------------------------------------
    # 3.13 priority_queues（4）
    # ------------------------------------------------------------------
    pq_data = [
        ("P0", "实时对话", 0, 0),
        ("P1", "在线服务", 12, 45),
        ("P2", "异步任务", 86, 320),
        ("P3", "批处理", 412, 2100),
    ]
    for pri, scenario, qlen, wait in pq_data:
        db.add(
            PriorityQueue(
                priority=pri,
                scenario=scenario,
                queue_length=qlen,
                wait_ms=wait,
                updated_at=now,
            )
        )

    # ------------------------------------------------------------------
    # 3.14 alerts（4）
    # ------------------------------------------------------------------
    alerts_data = [
        ("critical", "GLM-4 供应商熔断", "连续失败率超过 50%，已自动切换至备用模型 Qwen2.5-72B", "circuit_breaker", "open"),
        ("warning", "Qwen2.5-72B 负载偏高", "负载 88%，已触发负载均衡分流，建议扩容实例", "load", "open"),
        ("info", "成本预算使用达 68%", "今日成本接近预算阈值，请关注", "cost", "open"),
        ("info", "实例 inst-llama-01 完成扩容", "负载已从 92% 降至 55%，恢复正常", "system", "recovered"),
    ]
    alert_ages_h = [0.02, 0.3, 1.8, 4.0]
    for idx, (sev, title, desc, source, status) in enumerate(alerts_data):
        db.add(
            Alert(
                severity=sev,
                title=title,
                description=desc,
                source=source,
                status=status,
                created_at=_hours_ago(alert_ages_h[idx]),
                resolved_at=now if status == "recovered" else None,
            )
        )

    # ------------------------------------------------------------------
    # 3.15 alert_rules（3）
    # ------------------------------------------------------------------
    alert_rules_data = [
        ("错误率熔断", "error_rate", 50.0, "critical"),
        ("负载告警", "load", 80.0, "warning"),
        ("成本预算", "cost", 80.0, "info"),
    ]
    for name, metric, threshold, sev in alert_rules_data:
        db.add(
            AlertRule(
                name=name,
                metric=metric,
                threshold=threshold,
                severity=sev,
                enabled=True,
                created_at=now,
            )
        )

    # ------------------------------------------------------------------
    # 3.16 gateway_settings（1）
    # ------------------------------------------------------------------
    db.add(
        GatewaySettings(
            id=1,
            default_timeout_s=30,
            first_token_timeout_s=5,
            billing_cycle="daily",
            tls_enabled=True,
            prompt_injection_guard=True,
            audit_log_enabled=True,
            exchange_rate_usd_cny=7.2,
            updated_at=now,
        )
    )

    # ------------------------------------------------------------------
    # 3.17 request_logs（近 24h 采样，供 /overview/traffic-trend 绘图）
    # ------------------------------------------------------------------
    rng = random.Random(20261002)
    log_index = 0
    # 为每个小时生成若干条请求日志，形成 24 个趋势点（绝大多数成功，保持高可用）
    for hour in range(23, -1, -1):
        success_count = rng.randint(8, 12)
        failed_count = 1 if rng.random() < 0.08 else 0
        base_ts = datetime.now(timezone.utc) - timedelta(hours=hour)
        for _ in range(success_count):
            db.add(_build_request_log(base_ts, "success", rng, log_index))
            log_index += 1
        for _ in range(failed_count):
            db.add(_build_request_log(base_ts, "failed", rng, log_index))
            log_index += 1

    # ------------------------------------------------------------------
    # 3.17 idempotency_records（占位示例，不影响业务）
    # ------------------------------------------------------------------
    db.add(
        IdempotencyRecord(
            key="req_demo_idempotent",
            response_json=json.dumps({"code": 0, "message": "ok", "data": {"request_id": "req_demo_idempotent"}}),
            created_at=now,
            expires_at=_hours_ago(-0.1),
        )
    )

    db.commit()


def _build_request_log(base_ts: datetime, status: str, rng: random.Random, index: int) -> RequestLog:
    """构造一条采样请求日志。"""
    ts = (base_ts + timedelta(minutes=rng.randint(0, 59))).strftime("%Y-%m-%dT%H:%M:%SZ")
    prompt_tokens = rng.randint(20, 400)
    completion_tokens = rng.randint(20, 300)
    success = status == "success"
    return RequestLog(
        request_id=f"req_seed{index:06x}",
        tenant_id=1,
        session_id=None,
        provider_id=rng.randint(1, 4),
        model_instance_id=rng.randint(1, 5),
        instance_node_id=None,
        route_policy_id=1,
        priority="P1",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        latency_ms=rng.randint(180, 620) if success else rng.randint(1000, 3000),
        cost=round((prompt_tokens + completion_tokens) * 0.000001, 4),
        status="success" if success else "failed",
        error_code=None if success else "1010",
        error_message=None if success else "mock upstream error",
        is_stream=False,
        created_at=ts,
    )
