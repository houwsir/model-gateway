"""19 张 SQLite 表对应的 SQLAlchemy 2.x ORM 模型。

字段严格对齐 ``docs/DATA_MODEL.md`` 第 2 节。
约定：
- 时间字段 TEXT（ISO 8601 UTC），由 ``utcnow()`` 生成；
- JSON 字段 TEXT（存序列化字符串），在服务层/路由层用 ``json.loads`` 解析；
- 布尔字段用 ``Boolean``（SQLite 下映射为 INTEGER 0/1）；
- 为避免与 SQLAlchemy 的 ``Session`` 冲突，会话表模型命名为 ``ChatSession``
  （``__tablename__ = "sessions"``），记忆表模型命名为 ``MemoryMessage``。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Float, Integer, String, Text

from .db import Base


def utcnow() -> str:
    """返回当前 UTC 时间的 ISO 8601 秒级字符串。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Tenant(Base):
    """租户。"""

    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    priority_default = Column(String, nullable=False, default="P1")
    quota_daily = Column(Integer, nullable=False, default=0)
    quota_used_daily = Column(Integer, nullable=False, default=0)
    quota_monthly = Column(Integer, nullable=False, default=0)
    quota_used_monthly = Column(Integer, nullable=False, default=0)
    token_quota_monthly = Column(Integer, nullable=False, default=0)
    token_used_monthly = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="active")
    created_at = Column(String, nullable=False, default=utcnow)
    updated_at = Column(String, nullable=False, default=utcnow)


class ApiKey(Base):
    """租户 API Key。"""

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    key_hash = Column(String, nullable=False, unique=True)
    key_prefix = Column(String, nullable=False)
    status = Column(String, nullable=False, default="active")
    created_at = Column(String, nullable=False, default=utcnow)
    expires_at = Column(String, nullable=True)
    last_used_at = Column(String, nullable=True)


class Provider(Base):
    """供应商。"""

    __tablename__ = "providers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    provider_type = Column(String, nullable=False, default="mock")
    base_url = Column(String, nullable=True)
    api_key_encrypted = Column(String, nullable=True)
    api_key_masked = Column(String, nullable=True)
    status = Column(String, nullable=False, default="online")
    quota_total = Column(Integer, nullable=False, default=0)
    quota_used = Column(Integer, nullable=False, default=0)
    success_rate = Column(Float, nullable=False, default=100.0)
    cost_weight = Column(Float, nullable=False, default=1.0)
    created_at = Column(String, nullable=False, default=utcnow)
    updated_at = Column(String, nullable=False, default=utcnow)


class ModelInstance(Base):
    """模型实例（逻辑模型，路由候选）。"""

    __tablename__ = "model_instances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_id = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    capabilities_json = Column(String, nullable=False, default="[]")
    input_price = Column(Float, nullable=False, default=0.0)
    output_price = Column(Float, nullable=False, default=0.0)
    currency = Column(String, nullable=False, default="USD")
    max_context_tokens = Column(Integer, nullable=False, default=32768)
    tier = Column(String, nullable=False, default="mid")
    status = Column(String, nullable=False, default="healthy")
    latency_p50_ms = Column(Float, nullable=False, default=0.0)
    latency_p95_ms = Column(Float, nullable=False, default=0.0)
    load = Column(Integer, nullable=False, default=0)
    quality_score = Column(Float, nullable=False, default=0.8)
    created_at = Column(String, nullable=False, default=utcnow)
    updated_at = Column(String, nullable=False, default=utcnow)


class InstanceNode(Base):
    """物理实例节点（实例级 LB 目标）。"""

    __tablename__ = "instance_nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_instance_id = Column(Integer, nullable=False)
    name = Column(String, nullable=False, unique=True)
    weight = Column(Integer, nullable=False, default=10)
    current_connections = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="healthy")
    created_at = Column(String, nullable=False, default=utcnow)
    updated_at = Column(String, nullable=False, default=utcnow)


class RoutePolicy(Base):
    """路由策略。"""

    __tablename__ = "route_policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    scenario_tag = Column(String, nullable=False, unique=True)
    weight_cost = Column(Float, nullable=False)
    weight_latency = Column(Float, nullable=False)
    weight_quality = Column(Float, nullable=False)
    exploration_rate = Column(Float, nullable=False, default=0.05)
    is_default = Column(Boolean, nullable=False, default=False)
    status = Column(String, nullable=False, default="enabled")
    created_at = Column(String, nullable=False, default=utcnow)
    updated_at = Column(String, nullable=False, default=utcnow)


class RouteRule(Base):
    """路由规则（硬性过滤）。"""

    __tablename__ = "route_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    rule_type = Column(String, nullable=False)
    condition_json = Column(String, nullable=False)
    action = Column(String, nullable=False)
    priority = Column(Integer, nullable=False, default=0)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(String, nullable=False, default=utcnow)
    updated_at = Column(String, nullable=False, default=utcnow)


class BalancingGroup(Base):
    """负载均衡组。"""

    __tablename__ = "balancing_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, default="默认均衡组")
    strategy = Column(String, nullable=False, default="weighted_least_conn")
    provider_strategy = Column(String, nullable=False, default="quota_success_cost")
    config_json = Column(String, nullable=False, default="{}")
    created_at = Column(String, nullable=False, default=utcnow)
    updated_at = Column(String, nullable=False, default=utcnow)


class ResiliencePolicy(Base):
    """容灾策略。"""

    __tablename__ = "resilience_policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_id = Column(Integer, nullable=False)
    failure_rate_threshold = Column(Float, nullable=False, default=0.5)
    cooldown_seconds = Column(Integer, nullable=False, default=30)
    half_open_enabled = Column(Boolean, nullable=False, default=True)
    failover_mode = Column(String, nullable=False, default="auto_switch")
    backup_selection = Column(String, nullable=False, default="same_capability_lowest_cost")
    degrade_mode = Column(String, nullable=False, default="downgrade_model")
    backup_chain_json = Column(String, nullable=False, default="[]")
    retry_count = Column(Integer, nullable=False, default=2)
    status = Column(String, nullable=False, default="normal")
    switch_count = Column(Integer, nullable=False, default=0)
    created_at = Column(String, nullable=False, default=utcnow)
    updated_at = Column(String, nullable=False, default=utcnow)


class ChatSession(Base):
    """会话（持久记忆主键）。"""

    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False, unique=True)
    tenant_id = Column(Integer, nullable=False)
    message_count = Column(Integer, nullable=False, default=0)
    context_tokens = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="active")
    last_active_at = Column(String, nullable=False, default=utcnow)
    ttl_seconds = Column(Integer, nullable=False, default=86400)
    created_at = Column(String, nullable=False, default=utcnow)


class MemoryMessage(Base):
    """记忆消息（冷数据）。"""

    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, nullable=False)
    role = Column(String, nullable=False)
    content = Column(String, nullable=False)
    tokens = Column(Integer, nullable=False, default=0)
    storage_tier = Column(String, nullable=False, default="cold")
    created_at = Column(String, nullable=False, default=utcnow)
    expires_at = Column(String, nullable=True)


class MemoryPolicy(Base):
    """记忆策略（单行配置）。"""

    __tablename__ = "memory_policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hot_storage = Column(String, nullable=False, default="memory")
    cold_storage = Column(String, nullable=False, default="sqlite+vector")
    context_ttl_seconds = Column(Integer, nullable=False, default=86400)
    rag_enabled = Column(Boolean, nullable=False, default=True)
    user_delete_enabled = Column(Boolean, nullable=False, default=True)
    pii_mask_enabled = Column(Boolean, nullable=False, default=True)
    auto_expire_enabled = Column(Boolean, nullable=False, default=True)
    audit_enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(String, nullable=False, default=utcnow)


class RateLimitRule(Base):
    """限流规则。"""

    __tablename__ = "rate_limit_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    dimension = Column(String, nullable=False)
    threshold = Column(Integer, nullable=False)
    window_seconds = Column(Integer, nullable=False, default=1)
    algorithm = Column(String, nullable=False, default="token_bucket")
    action = Column(String, nullable=False, default="reject_429")
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(String, nullable=False, default=utcnow)
    updated_at = Column(String, nullable=False, default=utcnow)


class PriorityQueue(Base):
    """优先级队列。"""

    __tablename__ = "priority_queues"

    id = Column(Integer, primary_key=True, autoincrement=True)
    priority = Column(String, nullable=False, unique=True)
    scenario = Column(String, nullable=False)
    queue_length = Column(Integer, nullable=False, default=0)
    wait_ms = Column(Integer, nullable=False, default=0)
    updated_at = Column(String, nullable=False, default=utcnow)


class RequestLog(Base):
    """请求日志（指标统计数据源）。"""

    __tablename__ = "request_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String, nullable=False, unique=True)
    tenant_id = Column(Integer, nullable=True)
    session_id = Column(String, nullable=True)
    provider_id = Column(Integer, nullable=True)
    model_instance_id = Column(Integer, nullable=True)
    instance_node_id = Column(Integer, nullable=True)
    route_policy_id = Column(Integer, nullable=True)
    priority = Column(String, nullable=False, default="P1")
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    latency_ms = Column(Integer, nullable=False, default=0)
    cost = Column(Float, nullable=False, default=0.0)
    status = Column(String, nullable=False)
    error_code = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    is_stream = Column(Boolean, nullable=False, default=False)
    created_at = Column(String, nullable=False, default=utcnow, index=True)


class Alert(Base):
    """告警。"""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    severity = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    source = Column(String, nullable=False)
    status = Column(String, nullable=False, default="open")
    created_at = Column(String, nullable=False, default=utcnow)
    resolved_at = Column(String, nullable=True)


class AlertRule(Base):
    """告警规则。"""

    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    metric = Column(String, nullable=False)
    threshold = Column(Float, nullable=False)
    severity = Column(String, nullable=False, default="warning")
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(String, nullable=False, default=utcnow)


class GatewaySettings(Base):
    """全局参数（单行，id 恒为 1）。"""

    __tablename__ = "gateway_settings"

    id = Column(Integer, primary_key=True)
    default_timeout_s = Column(Integer, nullable=False, default=30)
    first_token_timeout_s = Column(Integer, nullable=False, default=5)
    billing_cycle = Column(String, nullable=False, default="daily")
    tls_enabled = Column(Boolean, nullable=False, default=True)
    prompt_injection_guard = Column(Boolean, nullable=False, default=True)
    audit_log_enabled = Column(Boolean, nullable=False, default=True)
    exchange_rate_usd_cny = Column(Float, nullable=False, default=7.2)
    updated_at = Column(String, nullable=False, default=utcnow)


class IdempotencyRecord(Base):
    """幂等去重记录。"""

    __tablename__ = "idempotency_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String, nullable=False, unique=True)
    response_json = Column(Text, nullable=False)
    created_at = Column(String, nullable=False, default=utcnow)
    expires_at = Column(String, nullable=False)
