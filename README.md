# 模型网关（Model Gateway）

模型网关是「业务应用」与「后端大模型供应商」之间的统一接入与调度层。业务方持 API Key 调用网关统一入口，网关负责：智能路由、负载均衡、容灾切换、持久记忆、流量控制、鉴权、日志监控、内容安全过滤。

> 技术栈：后端 **FastAPI + SQLAlchemy 2.0 + SQLite**；前端 **React 18 + TypeScript + Vite + Tailwind CSS**。

---

## 目录结构

```
model-gateway/
├── docs/                 # 架构设计文档（唯一编码依据）
├── backend/              # Python FastAPI 后端
│   ├── app/
│   │   ├── main.py       # 入口：建表+seed、CORS、路由、异常处理
│   │   ├── models.py     # 19 张 ORM 表
│   │   ├── schemas.py    # Pydantic 请求/响应 + 统一响应包
│   │   ├── seed.py       # 幂等种子数据
│   │   ├── routers/      # 10 个路由模块（55+ 端点）
│   │   ├── services/     # 调度/韧性/流量/记忆/安全/观测服务
│   │   └── utils/        # 令牌桶/滑动窗口/幂等
│   ├── tests/            # pytest 测试（25 例全绿）
│   └── requirements.txt
└── frontend/             # React 18 + Vite + Tailwind 前端（9 页面）
```

---

## 一键启动

### 后端（端口 8000）

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

启动后：
- 首次启动自动建表 + 写入种子数据（`backend/data/gateway.db`，幂等）。
- Swagger：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/api/v1/health> → `{"code":0,"data":{"status":"up","version":"v2.4"}}`

### 前端（端口 5173）

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 <http://localhost:5173>（Vite 已将 `/api` 代理到后端 8000）。

### 生产构建

```bash
cd frontend && npm run build   # tsc 类型检查 + vite 打包
```

---

## 种子 API Key（供测试业务转发接口）

| 租户 | API Key |
|------|---------|
| 客服中心 | `gw_a1b2c3d4e5f60718293a4b5c6d7e8f90` |
| 营销部 | `gw_f9e8d7c6b5a493827161504132231405` |
| 研发平台 | `gw_0123456789abcdef0123456789abcdef` |
| 数据团队 | `gw_abcdef0123456789abcdef0123456789` |

业务调用示例（非流式）：

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: gw_a1b2c3d4e5f60718293a4b5c6d7e8f90" \
  -d '{"messages":[{"role":"user","content":"你好"}],"scenario_tag":"default"}'
```

流式（SSE）：

```bash
curl -N -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: gw_a1b2c3d4e5f60718293a4b5c6d7e8f90" \
  -d '{"messages":[{"role":"user","content":"你好"}],"stream":true}'
```

---

## 种子数据概览（启动即有，与前端 9 页一致）

4 供应商（OpenAI/Anthropic/自建集群/智谱，均 `mock`）、5 模型实例、4 物理节点、3 路由策略、4 路由规则、1 均衡组、4 容灾策略、4 会话、4 告警、3 告警规则、4 限流规则、4 优先级队列、4 租户、1 记忆策略、1 全局参数、近 24h 采样请求日志。

> 供应商 `provider_type` 全部为 `mock`，demo 不依赖真实 API Key；真实接入只需把 `provider_type` 改为 `openai/anthropic/zhipu` 并提供 `base_url` + `api_key`。

---

## 关键设计实现

- **可插拔上游**：`ModelClient` 抽象 + 工厂按 `provider_type` 实例化（`mock`/`openai`/`anthropic`/`zhipu`）。
- **两段式路由**：规则过滤（能力/成本/配额/延迟）→ 加权打分（成本/延迟/质量，按场景标签）→ 探索率 5%。
- **容灾状态机**：closed → open（错误率超阈值）→ half_open（冷却到期放行试探）→ closed；后台每 5s 健康检查。
- **持久记忆**：热内存 dict + 冷 SQLite 两层，TTL + 用户删除 + 上下文截断。
- **统一响应**：`{code, message, data}`；时间 ISO 8601 UTC；成本 USD 4 位小数；字段 snake_case。
- **鉴权**：仅 `/chat/completions` 校验 `X-API-Key`；控制台接口 demo 阶段开放。
- **幂等**：`X-Request-Id` 命中直接返回首次缓存，不重复计费。
- **SSE**：`start` / `delta` / `done` / `[DONE]`，生成器 `finally` 补记中断状态。

### 错误码

| HTTP | code | 含义 |
|------|------|------|
| 400 | 1001 | 参数错误 |
| 401 | 1002 | 未授权 |
| 403 | 1003 | 配额耗尽 |
| 429 | 1004 | 触发限流 |
| 503 | 1005 | 无可用模型 |
| 404 | 1006 | 资源不存在 |
| 400 | 1008 | 内容不合规 |
| 504 | 1009 | 上游超时 |
| 502 | 1010 | 上游错误 |
| 500 | 5000 | 服务器内部错误 |

---

## 运行测试

```bash
cd backend
.venv/bin/python -m pytest tests/ -q
```

覆盖核心模块：路由、限流、鉴权、记忆、容灾，共 25 例。
