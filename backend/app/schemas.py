"""Pydantic 请求/响应模型 + 统一响应包 + 业务异常。

统一响应格式：``{"code": 0, "message": "ok", "data": <payload>}``。
业务错误通过抛出 ``AppError``，由 main.py 的异常处理器统一转为 envelope。
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class AppError(Exception):
    """业务异常：携带业务错误码与对应 HTTP 状态码。

    错误码语义见 ``docs/API_CONTRACT.md`` 第 3 节：
    1001 参数错误 / 1002 未授权 / 1003 配额耗尽 / 1004 限流 /
    1005 无可用模型 / 1006 资源不存在 / 1008 内容不合规 /
    1009 上游超时 / 1010 上游错误 / 5000 内部错误。
    """

    def __init__(self, code: int, message: str, http_status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def ok(data: Any = None) -> dict[str, Any]:
    """构造成功响应包。"""
    return {"code": 0, "message": "ok", "data": data}


def fail(code: int, message: str, http_status: int = 400) -> AppError:
    """构造业务异常。"""
    return AppError(code, message, http_status)


# ---------------------------------------------------------------------------
# 聊天转发
# ---------------------------------------------------------------------------
class ChatMessage(BaseModel):
    role: str = Field(default="user", description="user/assistant/system")
    content: str = Field(default="", description="消息内容")


class ChatCompletionRequest(BaseModel):
    model: str | None = Field(default=None, description="可选；不填则由路由决策")
    messages: list[ChatMessage] = Field(..., description="必填，非空")
    stream: bool = Field(default=False)
    session_id: str | None = Field(default=None)
    priority: str | None = Field(default=None, description="P0/P1/P2/P3")
    scenario_tag: str | None = Field(default=None, description="default/realtime/quality")
    capabilities: list[str] = Field(default_factory=lambda: ["text"])
    temperature: float = Field(default=0.7)
    max_tokens: int = Field(default=512)

    @field_validator("messages")
    @classmethod
    def messages_not_empty(cls, v: list[ChatMessage]) -> list[ChatMessage]:
        if not v:
            raise ValueError("messages 不能为空")
        return v

    @field_validator("priority")
    @classmethod
    def valid_priority(cls, v: str | None) -> str | None:
        if v is not None and v not in {"P0", "P1", "P2", "P3"}:
            raise ValueError("priority 必须为 P0/P1/P2/P3")
        return v

    @field_validator("scenario_tag")
    @classmethod
    def valid_scenario(cls, v: str | None) -> str | None:
        if v is not None and v not in {"default", "realtime", "quality"}:
            raise ValueError("scenario_tag 必须为 default/realtime/quality")
        return v


# ---------------------------------------------------------------------------
# 路由策略 / 规则
# ---------------------------------------------------------------------------
class RoutePolicyBody(BaseModel):
    name: str
    scenario_tag: str
    weight_cost: float = Field(ge=0, le=1)
    weight_latency: float = Field(ge=0, le=1)
    weight_quality: float = Field(ge=0, le=1)
    exploration_rate: float = Field(default=0.05, ge=0, le=1)
    is_default: bool = Field(default=False)
    status: str = Field(default="enabled")

    @field_validator("weight_cost", "weight_latency", "weight_quality")
    @classmethod
    def weights_sum(cls, v: float, info) -> float:
        return v

    @field_validator("name")
    @classmethod
    def non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name 不能为空")
        return v.strip()


class RouteRuleBody(BaseModel):
    name: str
    rule_type: str
    condition: dict[str, Any]
    action: str
    priority: int = Field(default=0)
    enabled: bool = Field(default=True)


class RouteRuleUpdate(BaseModel):
    name: str | None = None
    rule_type: str | None = None
    condition: dict[str, Any] | None = None
    action: str | None = None
    priority: int | None = None
    enabled: bool | None = None


class RoutingPreviewRequest(BaseModel):
    scenario_tag: str = Field(default="default")
    capabilities: list[str] = Field(default_factory=lambda: ["text"])
    messages: list[ChatMessage] = Field(default_factory=list)
    model: str | None = None


# ---------------------------------------------------------------------------
# 供应商 / 模型实例
# ---------------------------------------------------------------------------
class ProviderBody(BaseModel):
    name: str
    provider_type: str = Field(default="mock")
    base_url: str | None = None
    api_key: str | None = None


class ProviderUpdate(BaseModel):
    name: str | None = None
    provider_type: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    status: str | None = None


class ModelInstanceBody(BaseModel):
    provider_id: int
    name: str
    capabilities: list[str] = Field(default_factory=lambda: ["text"])
    input_price: float = Field(default=0)
    output_price: float = Field(default=0)
    currency: str = Field(default="USD")
    max_context_tokens: int = Field(default=32768)
    tier: str = Field(default="mid")
    quality_score: float = Field(default=0.8)


class ModelInstanceUpdate(BaseModel):
    name: str | None = None
    capabilities: list[str] | None = None
    input_price: float | None = None
    output_price: float | None = None
    currency: str | None = None
    max_context_tokens: int | None = None
    tier: str | None = None
    status: str | None = None
    quality_score: float | None = None


# ---------------------------------------------------------------------------
# 负载均衡
# ---------------------------------------------------------------------------
class InstanceWeightItem(BaseModel):
    node_id: int
    weight: int = Field(ge=0)


class BalancingGroupUpdate(BaseModel):
    strategy: str | None = None
    provider_strategy: str | None = None
    instance_weights: list[InstanceWeightItem] | None = None


# ---------------------------------------------------------------------------
# 流量控制
# ---------------------------------------------------------------------------
class RateLimitBody(BaseModel):
    name: str
    dimension: str
    threshold: int = Field(gt=0)
    window_seconds: int = Field(default=1, gt=0)
    algorithm: str = Field(default="token_bucket")
    action: str = Field(default="reject_429")
    enabled: bool = Field(default=True)


class RateLimitUpdate(BaseModel):
    name: str | None = None
    dimension: str | None = None
    threshold: int | None = None
    window_seconds: int | None = None
    algorithm: str | None = None
    action: str | None = None
    enabled: bool | None = None


class TenantQuotaUpdate(BaseModel):
    quota_monthly: int | None = None
    token_quota_monthly: int | None = None


# ---------------------------------------------------------------------------
# 记忆
# ---------------------------------------------------------------------------
class MemoryPolicyUpdate(BaseModel):
    hot_storage: str | None = None
    cold_storage: str | None = None
    context_ttl_seconds: int | None = None
    rag_enabled: bool | None = None
    user_delete_enabled: bool | None = None
    pii_mask_enabled: bool | None = None
    auto_expire_enabled: bool | None = None
    audit_enabled: bool | None = None


# ---------------------------------------------------------------------------
# 容灾
# ---------------------------------------------------------------------------
class ResiliencePolicyBody(BaseModel):
    provider_id: int
    failure_rate_threshold: float = Field(default=0.5, ge=0, le=1)
    cooldown_seconds: int = Field(default=30, ge=0)
    half_open_enabled: bool = Field(default=True)
    failover_mode: str = Field(default="auto_switch")
    backup_selection: str = Field(default="same_capability_lowest_cost")
    degrade_mode: str = Field(default="downgrade_model")
    backup_chain: list[str] = Field(default_factory=list)
    retry_count: int = Field(default=2, ge=0)


class ResiliencePolicyUpdate(BaseModel):
    failure_rate_threshold: float | None = Field(default=None, ge=0, le=1)
    cooldown_seconds: int | None = Field(default=None, ge=0)
    half_open_enabled: bool | None = None
    failover_mode: str | None = None
    backup_selection: str | None = None
    degrade_mode: str | None = None
    backup_chain: list[str] | None = None
    retry_count: int | None = Field(default=None, ge=0)


# ---------------------------------------------------------------------------
# 告警
# ---------------------------------------------------------------------------
class AlertRuleBody(BaseModel):
    name: str
    metric: str
    threshold: float
    severity: str = Field(default="warning")


# ---------------------------------------------------------------------------
# 设置
# ---------------------------------------------------------------------------
class SettingsUpdate(BaseModel):
    default_timeout_s: int | None = None
    first_token_timeout_s: int | None = None
    billing_cycle: str | None = None
    tls_enabled: bool | None = None
    prompt_injection_guard: bool | None = None
    audit_log_enabled: bool | None = None
    exchange_rate_usd_cny: float | None = None


class CredentialUpdate(BaseModel):
    api_key: str
