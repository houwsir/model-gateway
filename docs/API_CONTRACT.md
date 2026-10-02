# 模型网关 REST API 契约

> 版本 v1.0 · 后端 Base URL：`http://localhost:8000` · 统一前缀 `/api/v1`
> 前端调用经 Vite 代理 `/api` → `http://localhost:8000`（见 TASK_BREAKDOWN 的 vite.config）

---

## 1. 通用约定

### 1.1 统一响应包

所有接口返回 JSON：

```json
{ "code": 0, "message": "ok", "data": { } }
```

- `code = 0` 表示成功；非 0 为业务错误码（见第 3 节）。
- `data` 为负载：列表接口统一返回 `{ "items": [...], "total": n }`；单对象/聚合返回对象；无数据返回 `null`。

### 1.2 鉴权

| 接口类别 | 鉴权方式 |
|----------|----------|
| 业务转发 `POST /api/v1/chat/completions` | 必须携带 `X-API-Key: gw_<32hex>`；同时可选 `X-Request-Id`（幂等去重） |
| 控制台/管理接口（其余全部） | **demo 阶段不鉴权**（README 注明；真实环境加 `X-Admin-Key`） |

### 1.3 时间与金额

- 时间：ISO 8601 UTC 字符串（`2026-10-02T14:32:08Z`）。
- 金额：`cost` 统一 USD 4 位小数；单价按 `currency`（`USD`/`CNY`）存原生币种。

---

## 2. 接口清单

### 2.1 业务转发（核心入口）

#### POST /api/v1/chat/completions

网关统一推理入口：鉴权 → 限流/配额/优先级 → 智能路由 → 负载均衡 → 容灾（熔断/重试/切换/降级）→ 模型调用 → 安全过滤 → 记忆写回 → 日志指标。

**Headers**
- `X-API-Key`（必填）
- `X-Request-Id`（可选，幂等键，重复则返回首次缓存响应，不重复计费）

**Request Body**
```json
{
  "model": "gpt-4o-mini",              // 可选；不填则完全由路由决策
  "messages": [ {"role": "user", "content": "你好"} ],   // 必填，非空
  "stream": false,                     // true 时返回 SSE
  "session_id": "sess_9f2a1c",        // 可选；持久记忆，跨请求复用上下文
  "priority": "P1",                   // P0/P1/P2/P3，默认取租户默认
  "scenario_tag": "default",          // 路由场景标签 default/realtime/quality
  "capabilities": ["text"],           // 能力需求，如 ["text","multimodal"]
  "temperature": 0.7,
  "max_tokens": 512
}
```

**Response（非流式）— HTTP 200**
```json
{
  "code": 0, "message": "ok",
  "data": {
    "request_id": "req_1a2b3c4d",
    "model": "gpt-4o-mini",
    "provider": "openai",
    "instance": "inst-openai-01",
    "route_policy": "通用对话·默认",
    "content": "你好，有什么可以帮你？",
    "usage": { "prompt_tokens": 12, "completion_tokens": 18, "total_tokens": 30 },
    "cost": 0.0003,
    "latency_ms": 42,
    "finish_reason": "stop",
    "memory_saved": true
  }
}
```

**Response（流式）— `text/event-stream`，事件序列：**

```
data: {"type":"start","request_id":"req_1a2b3c4d","model":"gpt-4o-mini","provider":"openai","instance":"inst-openai-01"}

data: {"type":"delta","content":"你好"}

data: {"type":"delta","content":"，有什么可以帮你？"}

data: {"type":"done","usage":{"prompt_tokens":12,"completion_tokens":18,"total_tokens":30},"cost":0.0003,"latency_ms":42,"finish_reason":"stop"}

data: [DONE]
```

> 流式中断（EX-09）：生成器 `finally` 补记 `RequestLog(status='interrupted')` 并可能告警。

**错误响应**（均含 envelope，HTTP 状态见第 3 节）：鉴权失败 `1002`、限流 `1004`、配额耗尽 `1003`、全部不可用 `1005`、内容不合规 `1008`。

---

### 2.2 监控大盘（overview）

#### GET /api/v1/overview/summary
4 指标卡数据。
```json
{
  "code":0,"message":"ok",
  "data":{
    "today_requests": 1284392, "requests_delta_pct": 12.4,
    "latency_p50_ms": 342, "latency_delta_pct": -5.8,
    "availability": 99.98,
    "today_cost_usd": 1171.11, "cost_budget_pct": 68
  }
}
```

#### GET /api/v1/overview/traffic-trend?window=24h
```json
{ "code":0,"message":"ok","data":{
  "points":[ {"t":"2026-10-02T00:00:00Z","total":120,"success":118,"failed":2} ]
}}
```

#### GET /api/v1/overview/model-health
```json
{ "code":0,"message":"ok","data":{ "items":[
  {"model":"gpt-4o-mini","provider":"OpenAI","status":"healthy","latency_ms":212,"load":64}
]}}
```

#### GET /api/v1/overview/recent-alerts?limit=3
返回 `data.items`（结构同 alerts 列表项）。

#### GET /api/v1/overview/cost-distribution
```json
{ "code":0,"message":"ok","data":{ "items":[
  {"provider":"OpenAI","cost_usd":533.61,"ratio":45}
]}}
```

---

### 2.3 智能路由（routing）

#### GET /api/v1/routing/policies
```json
{ "code":0,"message":"ok","data":{ "items":[
  {"id":1,"name":"通用对话·默认","scenario_tag":"default","tag_label":"默认策略",
   "weight_cost":0.4,"weight_latency":0.35,"weight_quality":0.25,
   "exploration_rate":0.05,"candidate_count":6,"hit_rate":94,"is_default":true,"status":"enabled"}
]}}
```

#### POST /api/v1/routing/policies
Body：`{ "name", "scenario_tag", "weight_cost", "weight_latency", "weight_quality", "exploration_rate", "is_default" }`
校验：三权重之和 = 1（允许 ±0.01）。返回新建对象。

#### PUT /api/v1/routing/policies/{id}
Body 同上（可部分更新，PATCH 语义但用 PUT）。返回更新对象。

#### DELETE /api/v1/routing/policies/{id}
返回 `data: null`。

#### GET /api/v1/routing/rules?policy_id=
```json
{ "code":0,"message":"ok","data":{ "items":[
  {"id":1,"name":"能力过滤","rule_type":"capability",
   "condition":{"field":"input_has_image","operator":"eq","value":true},
   "action":"route_to_multimodal","priority":1,"enabled":true}
]}}
```

#### POST /api/v1/routing/rules
Body：`{ "name", "rule_type", "condition", "action", "priority" }`。

#### PUT /api/v1/routing/rules/{id}
可更新 `enabled`（开关）、condition、action、priority。

#### DELETE /api/v1/routing/rules/{id}

#### POST /api/v1/routing/preview  （可选，演示路由决策）
Body：`{ "scenario_tag":"default", "capabilities":["text"], "messages":[{"role":"user","content":"x"}] }`
返回：`data = { "selected_model":"gpt-4o-mini", "candidates":[{"model":"...","score":0.82}], "filtered_out":["glm-4"] }`

---

### 2.4 供应商管理（providers）

#### GET /api/v1/providers
```json
{ "code":0,"message":"ok","data":{ "items":[
  {"id":1,"name":"OpenAI","provider_type":"openai","status":"online",
   "today_requests":512000,"success_rate":99.7,"quota_used_pct":28,
   "model_summary":"gpt-4o · gpt-4o-mini","api_key_masked":"sk-••••3f2a"}
]}}
```

#### POST /api/v1/providers
Body：`{ "name", "provider_type", "base_url", "api_key" }`（api_key 后端加密存、只返回掩码）。

#### PUT /api/v1/providers/{id}
更新 name/base_url/api_key/status。

#### DELETE /api/v1/providers/{id}

#### GET /api/v1/model-instances?provider_id=
```json
{ "code":0,"message":"ok","data":{ "items":[
  {"id":1,"provider_id":1,"provider_name":"OpenAI","name":"gpt-4o-mini",
   "capabilities":["text","multimodal"],"input_price":0.15,"output_price":0.60,"currency":"USD",
   "max_context_tokens":128000,"tier":"high","status":"healthy",
   "latency_p50_ms":212,"latency_p95_ms":380,"load":64,"quality_score":0.82}
]}}
```

#### POST /api/v1/model-instances
Body：`{ "provider_id", "name", "capabilities", "input_price", "output_price", "currency", "max_context_tokens", "tier", "quality_score" }`。

#### PUT /api/v1/model-instances/{id}
#### DELETE /api/v1/model-instances/{id}

---

### 2.5 负载均衡（balancing）

#### GET /api/v1/balancing/groups
```json
{ "code":0,"message":"ok","data":{ "items":[
  {"id":1,"name":"默认均衡组","strategy":"weighted_least_conn","provider_strategy":"quota_success_cost"}
]}}
```

#### GET /api/v1/balancing/groups/{id}
返回组详情 + 实例权重 + 供应商分流比例：
```json
{ "code":0,"message":"ok","data":{
  "id":1,"name":"默认均衡组","strategy":"weighted_least_conn","provider_strategy":"quota_success_cost",
  "instance_weights":[ {"node":"inst-qwen-01","model":"qwen2.5-72b","weight":40} ],
  "provider_ratios":[ {"provider":"OpenAI","ratio":45},{"provider":"Anthropic","ratio":27},{"provider":"自建集群","ratio":28} ]
}}
```

#### PUT /api/v1/balancing/groups/{id}
Body：`{ "strategy", "provider_strategy", "instance_weights":[{"node_id":1,"weight":40}] }`。

#### GET /api/v1/balancing/nodes
```json
{ "code":0,"message":"ok","data":{ "items":[
  {"id":1,"name":"inst-qwen-01","model":"qwen2.5-72b","provider":"自建集群",
   "current_connections":142,"load":88,"status":"healthy"}
]}}
```

#### POST /api/v1/balancing/nodes/{id}/drain
摘流：`status` → `draining`（不再接收新流量）。返回更新对象。

#### POST /api/v1/balancing/nodes/{id}/recover
恢复：`status` → `healthy`。返回更新对象。

---

### 2.6 流量控制（traffic）

#### GET /api/v1/traffic/summary
```json
{ "code":0,"message":"ok","data":{
  "today_requests_used":1920000,"today_requests_quota":3000000,"today_used_pct":64,
  "month_tokens_used":428000000,"month_tokens_quota":1200000000,"month_used_pct":36,
  "current_qps_limit":500,"current_qps_used_pct":72,"rate_limit_hits_today":3
}}
```

#### GET /api/v1/traffic/rate-limits
```json
{ "code":0,"message":"ok","data":{ "items":[
  {"id":1,"name":"全局 QPS","dimension":"global","threshold":500,"window_seconds":1,
   "algorithm":"token_bucket","action":"reject_429","enabled":true}
]}}
```

#### POST /api/v1/traffic/rate-limits
Body：`{ "name", "dimension", "threshold", "window_seconds", "algorithm", "action" }`。

#### PUT /api/v1/traffic/rate-limits/{id}
可更新 `enabled` 等。

#### DELETE /api/v1/traffic/rate-limits/{id}

#### GET /api/v1/traffic/priority-queues
```json
{ "code":0,"message":"ok","data":{ "items":[
  {"id":1,"priority":"P0","scenario":"实时对话","queue_length":0,"wait_ms":0}
]}}
```

#### GET /api/v1/traffic/tenant-quotas
```json
{ "code":0,"message":"ok","data":{ "items":[
  {"tenant_id":1,"name":"客服中心","used_pct":68,"quota_monthly":1200000,"status":"normal"}
]}}
```

#### PUT /api/v1/traffic/tenant-quotas/{tenant_id}
Body：`{ "quota_monthly": 1200000, "token_quota_monthly": 500000000 }`。

---

### 2.7 持久记忆（memory）

#### GET /api/v1/memory/summary
```json
{ "code":0,"message":"ok","data":{
  "active_sessions":48210,"active_delta_pct":8.2,
  "storage_gb":86,"storage_delta_gb":12,
  "context_hit_rate":96.3
}}
```

#### GET /api/v1/memory/policy
```json
{ "code":0,"message":"ok","data":{
  "hot_storage":"memory","cold_storage":"sqlite+vector","context_ttl_seconds":86400,
  "rag_enabled":true,"user_delete_enabled":true,"pii_mask_enabled":true,
  "auto_expire_enabled":true,"audit_enabled":true
}}
```

#### PUT /api/v1/memory/policy
Body 同上（部分更新）。返回更新对象。

#### GET /api/v1/memory/sessions?search=
```json
{ "code":0,"message":"ok","data":{ "items":[
  {"session_id":"sess_9f2a1c","tenant_name":"客服中心","message_count":24,
   "context_tokens":8400,"last_active_at":"2026-10-02T14:31:08Z","status":"active"}
]}}
```

#### GET /api/v1/memory/sessions/{session_id}/messages
```json
{ "code":0,"message":"ok","data":{ "items":[
  {"id":1,"role":"user","content":"...","tokens":12,"storage_tier":"hot","created_at":"..."}
]}}
```

#### DELETE /api/v1/memory/sessions/{session_id}
用户删除：删除会话及其全部记忆（热 + 冷）。返回 `data: null`。

---

### 2.8 容灾策略（resilience）

#### GET /api/v1/resilience/policies
```json
{ "code":0,"message":"ok","data":{ "items":[
  {"id":1,"provider_id":1,"provider_name":"OpenAI","backup_chain":["Anthropic","自建集群"],
   "retry_count":2,"status":"normal","switch_count":3,
   "failure_rate_threshold":0.5,"cooldown_seconds":30,"half_open_enabled":true,
   "failover_mode":"auto_switch","backup_selection":"same_capability_lowest_cost",
   "degrade_mode":"downgrade_model"}
]}}
```

#### PUT /api/v1/resilience/policies/{id}
Body：`{ "failure_rate_threshold", "cooldown_seconds", "half_open_enabled", "failover_mode", "backup_selection", "degrade_mode", "backup_chain", "retry_count" }`。

#### POST /api/v1/resilience/policies
Body：`{ "provider_id", ...同上 }`。

---

### 2.9 告警中心（alerts）

#### GET /api/v1/alerts?status=open&severity=&limit=
```json
{ "code":0,"message":"ok","data":{ "items":[
  {"id":1,"severity":"critical","title":"GLM-4 供应商熔断",
   "description":"连续失败率超过 50%，已自动切换至备用模型 Qwen2.5-72B",
   "source":"circuit_breaker","status":"open","created_at":"2026-10-02T14:32:08Z"}
], "total": 3 }}
```

#### POST /api/v1/alerts/{id}/ack
确认：`status` → `acknowledged`。

#### POST /api/v1/alerts/{id}/resolve
恢复：`status` → `recovered`，记 `resolved_at`。

#### POST /api/v1/alerts/read-all
批量：所有 `open` → `acknowledged`。

#### GET /api/v1/alerts/rules
#### POST /api/v1/alerts/rules
Body：`{ "name", "metric", "threshold", "severity" }`。

---

### 2.10 系统设置（settings）

#### GET /api/v1/settings
```json
{ "code":0,"message":"ok","data":{
  "default_timeout_s":30,"first_token_timeout_s":5,"billing_cycle":"daily",
  "tls_enabled":true,"prompt_injection_guard":true,"audit_log_enabled":true,
  "exchange_rate_usd_cny":7.2
}}
```

#### PUT /api/v1/settings
Body 同上（部分更新）。

#### GET /api/v1/settings/credentials
```json
{ "code":0,"message":"ok","data":{ "items":[
  {"provider_id":1,"provider_name":"OpenAI","api_key_masked":"sk-••••••••3f2a"}
]}}
```

#### PUT /api/v1/settings/credentials/{provider_id}
Body：`{ "api_key": "sk-..." }`。返回更新后的掩码。

---

### 2.11 系统元信息

#### GET /api/v1/health
```json
{ "code":0,"message":"ok","data":{ "status":"up", "version":"v2.4" } }
```

---

## 3. 错误码表

| HTTP | code | 含义 | 触发场景 |
|------|------|------|----------|
| 400 | 1001 | 参数错误 | 请求体校验失败、权重和≠1、messages 为空 |
| 401 | 1002 | 未授权 | API Key 缺失/无效/停用 |
| 403 | 1003 | 配额耗尽 | 租户周期配额用尽（EX-05） |
| 429 | 1004 | 触发限流 | 令牌桶/滑动窗口超限（EX-06） |
| 503 | 1005 | 无可用模型 | 全部候选/备用不可用（EX-04） |
| 404 | 1006 | 资源不存在 | 模型/供应商/会话等不存在 |
| 409 | 1007 | 重复请求 | 幂等键冲突（EX-07，实际返回首次缓存响应而非报错） |
| 400 | 1008 | 内容不合规 | 输出被安全过滤拦截（EX-11） |
| 504 | 1009 | 上游超时 | 分级超时重试后仍失败（EX-03） |
| 502 | 1010 | 上游错误 | 供应商非 429/超时类错误 |
| 500 | 5000 | 服务器内部错误 | 未捕获异常 |

> 说明：`1007` 在幂等命中时**不报错**，而是直接返回首次缓存结果（HTTP 200）；本行仅定义语义，供日志标识。控制台管理接口 CRUD 失败时统一返回 `1001`/`1006`/`5000`。

---

## 4. 前端页面 → API 依赖映射

| 页面 | 数据获取/操作依赖的 API |
|------|--------------------------|
| 1 监控大盘 Overview | `GET /overview/summary`、`GET /overview/traffic-trend`、`GET /overview/model-health`、`GET /overview/recent-alerts`、`GET /overview/cost-distribution`；「新建请求」→ `POST /chat/completions` |
| 2 智能路由 Routing | `GET /routing/policies`、`GET /routing/rules`；新建/编辑/删除策略与规则（POST/PUT/DELETE）；开关切换 `PUT /routing/rules/{id}` |
| 3 供应商管理 Providers | `GET /providers`、`GET /model-instances`；接入供应商 `POST /providers`；模型配置 `PUT /model-instances/{id}` |
| 4 负载均衡 Balancing | `GET /balancing/groups`、`GET /balancing/groups/{id}`、`GET /balancing/nodes`；策略更新 `PUT /balancing/groups/{id}`；摘流/恢复 `POST /balancing/nodes/{id}/drain`、`/recover` |
| 5 流量控制 Traffic | `GET /traffic/summary`、`GET /traffic/rate-limits`、`GET /traffic/priority-queues`、`GET /traffic/tenant-quotas`；规则增删改、租户配额 `PUT /traffic/tenant-quotas/{tenant_id}` |
| 6 持久记忆 Memory | `GET /memory/summary`、`GET /memory/policy`、`PUT /memory/policy`、`GET /memory/sessions`、`GET /memory/sessions/{id}/messages`、`DELETE /memory/sessions/{id}` |
| 7 容灾策略 Resilience | `GET /resilience/policies`、`PUT /resilience/policies/{id}`、`POST /resilience/policies` |
| 8 告警中心 Alerts | `GET /alerts`（按 status/severity 过滤）、`POST /alerts/{id}/ack`、`/resolve`、`/read-all`、`GET /alerts/rules` |
| 9 系统设置 Settings | `GET /settings`、`PUT /settings`、`GET /settings/credentials`、`PUT /settings/credentials/{provider_id}` |

> 契约原则：**前端每调用一个接口，后端必有对应实现；后端每个接口，前端至少被一个页面使用**（除 `/health` 供部署探活、`/routing/preview` 供演示）。
