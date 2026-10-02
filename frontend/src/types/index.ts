// 前端类型定义 —— 与后端 schemas.py / API_CONTRACT.md 字段对齐（snake_case，不做转换）

export interface ApiEnvelope<T> {
  code: number;
  message: string;
  data: T;
}

export interface ListData<T> {
  items: T[];
  total?: number;
}

// ---------- 聊天 ----------
export interface ChatMessage {
  role: string;
  content: string;
}

export interface ChatRequest {
  model?: string;
  messages: ChatMessage[];
  stream?: boolean;
  session_id?: string;
  priority?: string;
  scenario_tag?: string;
  capabilities?: string[];
  temperature?: number;
  max_tokens?: number;
}

export interface Usage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface ChatResponseData {
  request_id: string;
  model: string;
  provider: string;
  instance: string;
  route_policy: string | null;
  content: string;
  usage: Usage;
  cost: number;
  latency_ms: number;
  finish_reason: string;
  memory_saved: boolean;
}

// ---------- 监控大盘 ----------
export interface OverviewSummary {
  today_requests: number;
  requests_delta_pct: number;
  latency_p50_ms: number;
  latency_delta_pct: number;
  availability: number;
  today_cost_usd: number;
  cost_budget_pct: number;
}

export interface TrafficPoint {
  t: string;
  total: number;
  success: number;
  failed: number;
}

export interface ModelHealthItem {
  model: string;
  provider: string;
  status: string;
  latency_ms: number;
  load: number;
}

export interface CostItem {
  provider: string;
  cost_usd: number;
  ratio: number;
}

// ---------- 告警 ----------
export interface AlertItem {
  id: number;
  severity: 'critical' | 'warning' | 'info';
  title: string;
  description: string;
  source: string;
  status: 'open' | 'acknowledged' | 'recovered';
  created_at: string;
}

export interface AlertRuleItem {
  id: number;
  name: string;
  metric: string;
  threshold: number;
  severity: string;
  enabled: boolean;
}

// ---------- 智能路由 ----------
export interface RoutePolicyItem {
  id: number;
  name: string;
  scenario_tag: string;
  tag_label: string;
  weight_cost: number;
  weight_latency: number;
  weight_quality: number;
  exploration_rate: number;
  candidate_count: number;
  hit_rate: number;
  is_default: boolean;
  status: string;
}

export interface RouteRuleItem {
  id: number;
  name: string;
  rule_type: string;
  condition: Record<string, unknown>;
  action: string;
  priority: number;
  enabled: boolean;
}

// ---------- 供应商 ----------
export interface ProviderItem {
  id: number;
  name: string;
  provider_type: string;
  status: string;
  today_requests: number;
  success_rate: number;
  quota_used_pct: number;
  model_summary: string;
  api_key_masked: string;
}

export interface ModelInstanceItem {
  id: number;
  provider_id: number;
  provider_name: string;
  name: string;
  capabilities: string[];
  input_price: number;
  output_price: number;
  currency: string;
  max_context_tokens: number;
  tier: string;
  status: string;
  latency_p50_ms: number;
  latency_p95_ms: number;
  load: number;
  quality_score: number;
}

// ---------- 负载均衡 ----------
export interface BalancingGroupItem {
  id: number;
  name: string;
  strategy: string;
  provider_strategy: string;
}

export interface InstanceWeight {
  node: string;
  model: string;
  weight: number;
  node_id: number;
}

export interface ProviderRatio {
  provider: string;
  ratio: number;
}

export interface BalancingGroupDetail {
  id: number;
  name: string;
  strategy: string;
  provider_strategy: string;
  instance_weights: InstanceWeight[];
  provider_ratios: ProviderRatio[];
}

export interface InstanceNodeItem {
  id: number;
  name: string;
  model: string;
  provider: string;
  current_connections: number;
  load: number;
  status: string;
  weight: number;
}

// ---------- 流量控制 ----------
export interface TrafficSummary {
  today_requests_used: number;
  today_requests_quota: number;
  today_used_pct: number;
  month_tokens_used: number;
  month_tokens_quota: number;
  month_used_pct: number;
  current_qps_limit: number;
  current_qps_used_pct: number;
  rate_limit_hits_today: number;
}

export interface RateLimitItem {
  id: number;
  name: string;
  dimension: string;
  threshold: number;
  window_seconds: number;
  algorithm: string;
  action: string;
  enabled: boolean;
}

export interface PriorityQueueItem {
  id: number;
  priority: string;
  scenario: string;
  queue_length: number;
  wait_ms: number;
}

export interface TenantQuotaItem {
  tenant_id: number;
  name: string;
  used_pct: number;
  quota_monthly: number;
  status: string;
}

// ---------- 记忆 ----------
export interface MemorySummary {
  active_sessions: number;
  active_delta_pct: number;
  storage_gb: number;
  storage_delta_gb: number;
  context_hit_rate: number;
}

export interface MemoryPolicy {
  hot_storage: string;
  cold_storage: string;
  context_ttl_seconds: number;
  rag_enabled: boolean;
  user_delete_enabled: boolean;
  pii_mask_enabled: boolean;
  auto_expire_enabled: boolean;
  audit_enabled: boolean;
}

export interface MemorySession {
  session_id: string;
  tenant_name: string;
  message_count: number;
  context_tokens: number;
  last_active_at: string;
  status: string;
}

export interface MemoryMessageItem {
  id: number;
  role: string;
  content: string;
  tokens: number;
  storage_tier: string;
  created_at: string;
}

// ---------- 容灾 ----------
export interface ResiliencePolicyItem {
  id: number;
  provider_id: number;
  provider_name: string;
  backup_chain: string[];
  retry_count: number;
  status: string;
  switch_count: number;
  failure_rate_threshold: number;
  cooldown_seconds: number;
  half_open_enabled: boolean;
  failover_mode: string;
  backup_selection: string;
  degrade_mode: string;
}

// ---------- 设置 ----------
export interface SettingsData {
  default_timeout_s: number;
  first_token_timeout_s: number;
  billing_cycle: string;
  tls_enabled: boolean;
  prompt_injection_guard: boolean;
  audit_log_enabled: boolean;
  exchange_rate_usd_cny: number;
}

export interface CredentialItem {
  provider_id: number;
  provider_name: string;
  api_key_masked: string;
}
