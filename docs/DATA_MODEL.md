# 模型网关数据模型与 SQLite 表设计

> 版本 v1.0 · 数据库：SQLite（文件 `backend/data/gateway.db`）
> 实现方式：SQLAlchemy 2.x ORM 映射（`models.py`），下列 DDL 为等价表结构（规范约束以 ORM 为准）
> 通用约定：主键 `id INTEGER PRIMARY KEY AUTOINCREMENT`；时间字段 `TEXT`（ISO 8601 UTC）；JSON 字段 `TEXT`（存序列化 JSON 字符串）

---

## 1. 实体关系总览

```
tenants 1─* api_keys
tenants 1─* sessions
sessions 1─* memories
providers 1─* model_instances
model_instances 1─* instance_nodes
providers 1─* resilience_policies
route_policies 1─* route_rules（规则全局生效，policy_id 可空）
request_logs *─1 tenants / providers / model_instances / route_policies
```

19 张表：tenants、api_keys、providers、model_instances、instance_nodes、route_policies、route_rules、balancing_groups、resilience_policies、sessions、memories、memory_policies、rate_limit_rules、priority_queues、request_logs、alerts、alert_rules、gateway_settings、idempotency_records。

---

## 2. 表结构（DDL）

### 2.1 tenants 租户
```sql
CREATE TABLE tenants (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,                 -- 租户名（客服中心/营销部/研发平台/数据团队）
  priority_default TEXT NOT NULL DEFAULT 'P1', -- 默认优先级 P0-P3
  quota_daily INTEGER NOT NULL DEFAULT 0,    -- 每日请求配额
  quota_used_daily INTEGER NOT NULL DEFAULT 0,
  quota_monthly INTEGER NOT NULL DEFAULT 0,  -- 每月请求配额
  quota_used_monthly INTEGER NOT NULL DEFAULT 0,
  token_quota_monthly INTEGER NOT NULL DEFAULT 0,   -- 每月 token 配额
  token_used_monthly INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'active',     -- active/disabled
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

### 2.2 api_keys API Key
```sql
CREATE TABLE api_keys (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL REFERENCES tenants(id),
  name TEXT NOT NULL,
  key_hash TEXT NOT NULL UNIQUE,             -- sha256(key)
  key_prefix TEXT NOT NULL,                  -- 展示前缀 gw_abcd****
  status TEXT NOT NULL DEFAULT 'active',     -- active/disabled
  created_at TEXT NOT NULL,
  expires_at TEXT,                           -- 可空=永不过期
  last_used_at TEXT
);
```

### 2.3 providers 供应商
```sql
CREATE TABLE providers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,                 -- OpenAI / Anthropic / 自建集群 / 智谱
  provider_type TEXT NOT NULL,               -- mock/openai/anthropic/zhipu（决定工厂实例化）
  base_url TEXT,                             -- 真实供应商 base_url；mock 可空
  api_key_encrypted TEXT,                    -- 演示用简单掩码存储（真实应 AES 加密）
  api_key_masked TEXT,                       -- 前端展示掩码
  status TEXT NOT NULL DEFAULT 'online',     -- online/offline/degraded
  quota_total INTEGER NOT NULL DEFAULT 0,    -- 供应商配额总量（token）
  quota_used INTEGER NOT NULL DEFAULT 0,
  success_rate REAL NOT NULL DEFAULT 100.0,  -- 百分比 0-100
  cost_weight REAL NOT NULL DEFAULT 1.0,     -- 供应商级分流成本权重
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

### 2.4 model_instances 模型实例（逻辑模型，路由候选）
```sql
CREATE TABLE model_instances (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider_id INTEGER NOT NULL REFERENCES providers(id),
  name TEXT NOT NULL,                        -- gpt-4o-mini / claude-3.5-sonnet / qwen2.5-72b ...
  capabilities_json TEXT NOT NULL DEFAULT '[]', -- ["text","multimodal","long_context"]
  input_price REAL NOT NULL DEFAULT 0,       -- 每 1M tokens 输入单价（原生币种）
  output_price REAL NOT NULL DEFAULT 0,
  currency TEXT NOT NULL DEFAULT 'USD',      -- USD / CNY
  max_context_tokens INTEGER NOT NULL DEFAULT 32768,
  tier TEXT NOT NULL DEFAULT 'mid',          -- high/mid/low/fallback（降级档位）
  status TEXT NOT NULL DEFAULT 'healthy',    -- healthy/high_load/circuit_open/offline
  latency_p50_ms REAL NOT NULL DEFAULT 0,
  latency_p95_ms REAL NOT NULL DEFAULT 0,
  load INTEGER NOT NULL DEFAULT 0,           -- 0-100 负载百分比
  quality_score REAL NOT NULL DEFAULT 0.8,   -- 0-1 质量分（加权打分用）
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

### 2.5 instance_nodes 物理实例节点（实例级 LB 目标）
```sql
CREATE TABLE instance_nodes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  model_instance_id INTEGER NOT NULL REFERENCES model_instances(id),
  name TEXT NOT NULL UNIQUE,                 -- inst-qwen-01 / inst-glm-01 ...
  weight INTEGER NOT NULL DEFAULT 10,        -- LB 权重
  current_connections INTEGER NOT NULL DEFAULT 0, -- 当前连接数（加权最小连接用）
  status TEXT NOT NULL DEFAULT 'healthy',    -- healthy/draining/circuit_open
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

### 2.6 route_policies 路由策略
```sql
CREATE TABLE route_policies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,                        -- 通用对话·默认 / 高优时延 / 高优质量
  scenario_tag TEXT NOT NULL UNIQUE,         -- default/realtime/quality
  weight_cost REAL NOT NULL,                 -- 0-1
  weight_latency REAL NOT NULL,
  weight_quality REAL NOT NULL,              -- 三者之和=1
  exploration_rate REAL NOT NULL DEFAULT 0.05, -- 探索机制概率
  is_default INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'enabled',    -- enabled/disabled
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

### 2.7 route_rules 路由规则（硬性过滤）
```sql
CREATE TABLE route_rules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,                        -- 能力过滤/成本上限/配额保护/延迟上限
  rule_type TEXT NOT NULL,                   -- capability/cost/quota/latency
  condition_json TEXT NOT NULL,              -- {"field":"...","operator":"...","value":...}
  action TEXT NOT NULL,                      -- exclude/route_to_multimodal/downgrade
  priority INTEGER NOT NULL DEFAULT 0,       -- 数字越小越先执行
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

### 2.8 balancing_groups 负载均衡组
```sql
CREATE TABLE balancing_groups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL DEFAULT '默认均衡组',
  strategy TEXT NOT NULL DEFAULT 'weighted_least_conn', -- weighted_least_conn/weighted_round_robin/consistent_hash/random
  provider_strategy TEXT NOT NULL DEFAULT 'quota_success_cost', -- quota_success_cost/fixed_ratio/cost_first
  config_json TEXT NOT NULL DEFAULT '{}',  -- {"fixed_ratios":{...},"hash_key_field":"session_id"}
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

### 2.9 resilience_policies 容灾策略
```sql
CREATE TABLE resilience_policies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider_id INTEGER NOT NULL REFERENCES providers(id),
  failure_rate_threshold REAL NOT NULL DEFAULT 0.5,  -- 滑动窗口失败率阈值
  cooldown_seconds INTEGER NOT NULL DEFAULT 30,      -- 熔断冷却
  half_open_enabled INTEGER NOT NULL DEFAULT 1,      -- 半开试探
  failover_mode TEXT NOT NULL DEFAULT 'auto_switch', -- auto_switch/alert_only
  backup_selection TEXT NOT NULL DEFAULT 'same_capability_lowest_cost', -- 或 fixed_list
  degrade_mode TEXT NOT NULL DEFAULT 'downgrade_model', -- downgrade_model/cache_fallback/error
  backup_chain_json TEXT NOT NULL DEFAULT '[]',      -- ["Anthropic","自建集群"] 备用链路
  retry_count INTEGER NOT NULL DEFAULT 2,            -- 最大重试次数
  status TEXT NOT NULL DEFAULT 'normal',             -- normal/degraded/circuit_open（运行时状态镜像）
  switch_count INTEGER NOT NULL DEFAULT 0,           -- 切换次数
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

### 2.10 sessions 会话（持久记忆主键）
```sql
CREATE TABLE sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL UNIQUE,           -- sess_9f2a1c
  tenant_id INTEGER NOT NULL REFERENCES tenants(id),
  message_count INTEGER NOT NULL DEFAULT 0,
  context_tokens INTEGER NOT NULL DEFAULT 0, -- 累计上下文 token
  status TEXT NOT NULL DEFAULT 'active',     -- active/idle/expired
  last_active_at TEXT NOT NULL,
  ttl_seconds INTEGER NOT NULL DEFAULT 86400,
  created_at TEXT NOT NULL
);
```

### 2.11 memories 记忆消息（冷数据）
```sql
CREATE TABLE memories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES sessions(id),
  role TEXT NOT NULL,                        -- user/assistant/system
  content TEXT NOT NULL,
  tokens INTEGER NOT NULL DEFAULT 0,
  storage_tier TEXT NOT NULL DEFAULT 'cold', -- hot/cold（热数据额外驻内存）
  created_at TEXT NOT NULL,
  expires_at TEXT                            -- TTL 到期
);
```

### 2.12 memory_policies 记忆策略（单行配置）
```sql
CREATE TABLE memory_policies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  hot_storage TEXT NOT NULL DEFAULT 'memory',        -- memory/redis
  cold_storage TEXT NOT NULL DEFAULT 'sqlite+vector',-- sqlite+vector/object_only
  context_ttl_seconds INTEGER NOT NULL DEFAULT 86400,
  rag_enabled INTEGER NOT NULL DEFAULT 1,
  user_delete_enabled INTEGER NOT NULL DEFAULT 1,
  pii_mask_enabled INTEGER NOT NULL DEFAULT 1,
  auto_expire_enabled INTEGER NOT NULL DEFAULT 1,
  audit_enabled INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL
);
```

### 2.13 rate_limit_rules 限流规则
```sql
CREATE TABLE rate_limit_rules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,                        -- 全局 QPS / 单租户 QPS ...
  dimension TEXT NOT NULL,                   -- global/tenant/model/provider
  threshold INTEGER NOT NULL,                -- 阈值（req 数）
  window_seconds INTEGER NOT NULL DEFAULT 1,
  algorithm TEXT NOT NULL DEFAULT 'token_bucket', -- token_bucket/sliding_window
  action TEXT NOT NULL DEFAULT 'reject_429', -- reject_429/queue_then_reject/switch_provider
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

### 2.14 priority_queues 优先级队列
```sql
CREATE TABLE priority_queues (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  priority TEXT NOT NULL UNIQUE,             -- P0/P1/P2/P3
  scenario TEXT NOT NULL,                    -- 实时对话/在线服务/异步任务/批处理
  queue_length INTEGER NOT NULL DEFAULT 0,   -- 运行时状态
  wait_ms INTEGER NOT NULL DEFAULT 0,        -- 运行时状态
  updated_at TEXT NOT NULL
);
```

### 2.15 request_logs 请求日志（指标统计数据源）
```sql
CREATE TABLE request_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id TEXT NOT NULL UNIQUE,           -- req_<uuid8>
  tenant_id INTEGER REFERENCES tenants(id),
  session_id TEXT,                           -- 冗余 session_id 便于检索
  provider_id INTEGER,
  model_instance_id INTEGER,
  instance_node_id INTEGER,
  route_policy_id INTEGER,
  priority TEXT NOT NULL DEFAULT 'P1',
  prompt_tokens INTEGER NOT NULL DEFAULT 0,
  completion_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,
  latency_ms INTEGER NOT NULL DEFAULT 0,
  cost REAL NOT NULL DEFAULT 0,              -- USD 4 位小数
  status TEXT NOT NULL,                      -- success/failed/degraded/rejected/rate_limited/interrupted
  error_code TEXT,                           -- 1003/1004/1005/1008/1009/1010 ...
  error_message TEXT,
  is_stream INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_request_logs_created ON request_logs(created_at);
CREATE INDEX idx_request_logs_tenant ON request_logs(tenant_id);
```

### 2.16 alerts 告警
```sql
CREATE TABLE alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  severity TEXT NOT NULL,                    -- critical/warning/info
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  source TEXT NOT NULL,                      -- circuit_breaker/load/cost/quota/system
  status TEXT NOT NULL DEFAULT 'open',       -- open/acknowledged/recovered
  created_at TEXT NOT NULL,
  resolved_at TEXT
);
```

### 2.17 alert_rules 告警规则
```sql
CREATE TABLE alert_rules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  metric TEXT NOT NULL,                      -- error_rate/load/cost/quota
  threshold REAL NOT NULL,
  severity TEXT NOT NULL DEFAULT 'warning',
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);
```

### 2.18 gateway_settings 全局参数（单行）
```sql
CREATE TABLE gateway_settings (
  id INTEGER PRIMARY KEY CHECK (id = 1),     -- 单行
  default_timeout_s INTEGER NOT NULL DEFAULT 30,
  first_token_timeout_s INTEGER NOT NULL DEFAULT 5,
  billing_cycle TEXT NOT NULL DEFAULT 'daily', -- daily/realtime
  tls_enabled INTEGER NOT NULL DEFAULT 1,
  prompt_injection_guard INTEGER NOT NULL DEFAULT 1,
  audit_log_enabled INTEGER NOT NULL DEFAULT 1,
  exchange_rate_usd_cny REAL NOT NULL DEFAULT 7.2,
  updated_at TEXT NOT NULL
);
```

### 2.19 idempotency_records 幂等去重
```sql
CREATE TABLE idempotency_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT NOT NULL UNIQUE,                  -- X-Request-Id
  response_json TEXT NOT NULL,               -- 首次响应缓存
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL                   -- TTL（默认 10 分钟）
);
```

---

## 3. 种子数据（seed.py，启动幂等写入）

> 目标：demo 启动即有数据，且与前端原型 9 页展示一致。写入前检查 `tenants` 是否已有数据，有则跳过。

### 3.1 tenants（4）
| name | priority_default | quota_daily | quota_monthly | quota_used_monthly | token_quota_monthly | token_used_monthly |
|------|------------------|-------------|---------------|--------------------|---------------------|--------------------|
| 客服中心 | P1 | 50000 | 1200000 | 816000(68%) | 400000000 | 144000000 |
| 营销部 | P2 | 20000 | 600000 | 492000(82%) | 200000000 | 164000000 |
| 研发平台 | P1 | 80000 | 2000000 | 900000(45%) | 600000000 | 270000000 |
| 数据团队 | P3 | 10000 | 300000 | 285000(95%) | 100000000 | 95000000 |

### 3.2 api_keys（4，key 形如 `gw_<32hex>`）
每租户 1 个 key：`客服中心 → gw_a1b2c3d4...`（种子固定 key 需在 README 列出，供测试 `POST /chat/completions`）。

### 3.3 providers（4）
| name | provider_type | status | quota_total | quota_used | success_rate |
|------|---------------|--------|-------------|------------|--------------|
| OpenAI | mock | online | 1000000000 | 280000000(28% 已用) | 99.7 |
| Anthropic | mock | online | 800000000 | 368000000(46%) | 99.9 |
| 自建集群 | mock | online | 500000000 | 440000000(88% 负载) | 98.2 |
| 智谱 | mock | offline | 200000000 | 200000000 | 45.0 |

> `provider_type` 全部用 `mock` 保证 demo 可跑（真实接入把 type 换成 openai/anthropic/zhipu 并提供 base_url + api_key 即可）。

### 3.4 model_instances（5）
| name | provider | capabilities | input_price | output_price | currency | tier | status | p50 | p95 | load | quality |
|------|----------|--------------|-------------|--------------|----------|------|--------|-----|-----|------|---------|
| gpt-4o-mini | OpenAI | ["text","multimodal"] | 0.15 | 0.60 | USD | high | healthy | 212 | 380 | 64 | 0.82 |
| claude-3.5-sonnet | Anthropic | ["text","long_context"] | 3.00 | 15.00 | USD | high | healthy | 388 | 610 | 41 | 0.92 |
| qwen2.5-72b | 自建集群 | ["text"] | 0.50 | 2.00 | CNY | mid | high_load | 505 | 800 | 88 | 0.80 |
| llama-3.1-70b | 自建集群 | ["text"] | 0.40 | 1.60 | CNY | mid | healthy | 301 | 520 | 55 | 0.75 |
| glm-4 | 智谱 | ["text","multimodal"] | 1.00 | 3.00 | CNY | fallback | circuit_open | 0 | 0 | 0 | 0.78 |

### 3.5 instance_nodes（4）
| name | model_instance | weight | current_connections | status |
|------|----------------|--------|---------------------|--------|
| inst-qwen-01 | qwen2.5-72b | 40 | 142 | healthy |
| inst-qwen-02 | qwen2.5-72b | 35 | 96 | healthy |
| inst-llama-01 | llama-3.1-70b | 25 | 88 | healthy |
| inst-glm-01 | glm-4 | 10 | 0 | circuit_open |

### 3.6 route_policies（3）
| name | scenario_tag | weight_cost | weight_latency | weight_quality | is_default |
|------|--------------|-------------|----------------|----------------|------------|
| 通用对话·默认 | default | 0.40 | 0.35 | 0.25 | 1 |
| 高优时延 | realtime | 0.15 | 0.70 | 0.15 | 0 |
| 高优质量 | quality | 0.20 | 0.20 | 0.60 | 0 |

### 3.7 route_rules（4）
| name | rule_type | condition | action | priority | enabled |
|------|-----------|-----------|--------|----------|---------|
| 能力过滤 | capability | input_has_image == true | route_to_multimodal | 1 | 1 |
| 成本上限 | cost | estimated_cost > 0.5 | downgrade | 2 | 1 |
| 配额保护 | quota | provider_quota_remaining < 10% | exclude_provider | 3 | 1 |
| 延迟上限 | latency | p95_latency > 800 | exclude_model | 4 | 0 |

### 3.8 balancing_groups（1）
| name | strategy | provider_strategy | config |
|------|----------|-------------------|--------|
| 默认均衡组 | weighted_least_conn | quota_success_cost | {} |

### 3.9 resilience_policies（4）
| provider | backup_chain | retry_count | status | switch_count |
|----------|--------------|-------------|--------|--------------|
| OpenAI | ["Anthropic","自建集群"] | 2 | normal | 3 |
| Anthropic | ["OpenAI","自建集群"] | 2 | normal | 1 |
| 自建集群 | ["OpenAI"] | 1 | degraded | 7 |
| 智谱 | ["自建集群"] | 2 | circuit_open | 12 |

### 3.10 sessions（4）+ memories（各 2-4 条）
| session_id | tenant | message_count | context_tokens | status |
|------------|--------|---------------|----------------|--------|
| sess_9f2a1c | 客服中心 | 24 | 8400 | active |
| sess_3b7e8d | 营销部 | 41 | 12100 | active |
| sess_7c1a42 | 研发平台 | 8 | 3200 | idle |
| sess_d5e9f0 | 数据团队 | 67 | 18600 | idle |

### 3.11 memory_policies（1 行）
hot=memory, cold=sqlite+vector, ttl=86400, rag/user_delete/pii/auto_expire/audit 全 1。

### 3.12 rate_limit_rules（4）
| name | dimension | threshold | algorithm | action | enabled |
|------|-----------|-----------|-----------|--------|---------|
| 全局 QPS | global | 500 | token_bucket | reject_429 | 1 |
| 单租户 QPS | tenant | 50 | token_bucket | reject_429 | 1 |
| 单模型并发 | model | 200 | sliding_window | queue_then_reject | 1 |
| 供应商保护 | provider | 按额度 | token_bucket | switch_provider | 0 |

### 3.13 priority_queues（4）
P0 实时对话(0/0ms)、P1 在线服务(12/45ms)、P2 异步任务(86/320ms)、P3 批处理(412/2100ms)。

### 3.14 alerts（4，含 3 未处理 + 1 已恢复）
| severity | title | status |
|----------|-------|--------|
| critical | GLM-4 供应商熔断 | open |
| warning | Qwen2.5-72B 负载偏高 | open |
| info | 成本预算使用达 68% | open |
| info | 实例 inst-llama-01 完成扩容 | recovered |

### 3.15 alert_rules（3）
错误率>50%→critical；负载>80%→warning；成本预算>80%→info。

### 3.16 gateway_settings（1 行）
default_timeout_s=30, first_token_timeout_s=5, billing_cycle=daily, tls/prompt_injection/audit=1, exchange_rate=7.2。

### 3.17 request_logs / idempotency_records
种子各写入若干条（近 24h 分钟级流量趋势用 20-30 条采样数据，让 `/overview/traffic-trend` 有曲线可画；request_logs 无需全量，采样即可）。

---

## 4. 内存态运行时结构（非 SQLite）

| 结构 | 用途 | 位置 |
|------|------|------|
| `rate_limit_buckets: dict[key, TokenBucket]` | 令牌桶（按租户/全局/模型） | traffic_service.py |
| `sliding_windows: dict[key, deque]` | 滑动窗口（并发/错误率） | utils/sliding_window.py |
| `circuit_states: dict[model_id, CircuitState]` | 熔断状态机（closed/open/half_open + 时间戳 + 计数） | resilience_service.py |
| `session_hot_cache: dict[session_id, list[msg]]` | 会话上下文热数据 | memory_service.py |
| `policy_snapshot: dict` | 路由策略/规则/限流配置本地快照（EX-10） | router_service/traffic_service |
| `idempotency_cache: dict[key, response]` | 幂等快速命中（DB 落盘兜底） | utils/idempotency.py |

> 这些状态**进程内**维护，启动时从 SQLite 加载快照；写操作（增删改配置）即时失效重建快照，消除「策略下发延迟」（EX-10）。
