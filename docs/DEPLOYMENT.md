# 模型网关 · 部署文档

> 本文档说明模型网关的本地部署、生产部署与运维要点，配合 `README.md` 与 `docs/` 下设计文档使用。

## 一、环境要求

| 项 | 要求 |
|----|------|
| Python | 3.10 及以上（开发验证于 3.13） |
| Node.js | 18 及以上 |
| 数据库 | 内置 SQLite（无需额外安装）；生产可切换其他 DB |
| 模型端点 | 可选。demo 模式内置 `mock` 供应商，无需真实 API Key |

## 二、本地部署（开发模式）

### 1. 后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- 首次启动自动建表并写入种子数据（`backend/data/gateway.db`，幂等）。
- Swagger 文档：http://localhost:8000/docs
- 健康检查：`curl http://localhost:8000/api/v1/health`

### 2. 前端

```bash
cd frontend
npm install
npm run dev      # 开发模式，Vite 已代理 /api → 8000
```

浏览器打开 http://localhost:5173。

### 3. 一键验证清单

```bash
# 后端单测
cd backend && .venv/bin/python -m pytest -q        # 期望 25 passed

# 前端构建
cd frontend && npm run build                       # 期望 tsc 无错 + dist 产物

# 接口连通
curl http://localhost:8000/api/v1/health           # 期望 {"code":0,...}
```

## 三、生产部署

### 方式 A：进程 + 反向代理

```bash
# 后端多 worker（无状态数据面可水平扩展）
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# 前端静态托管
cd frontend && npm run build    # 产物 dist/ 交给 Nginx 等静态服务器
```

Nginx 反向代理示例：

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Request-Id $request_id;
}
location / {
    root /path/to/frontend/dist;
    try_files $uri /index.html;
}
```

### 方式 B：Docker（推荐）

见 `deploy/` 目录（如已提供 Dockerfile / docker-compose.yml），核心思路：

- 后端镜像：`python:3.12-slim` 基础镜像，`pip install -r requirements.txt`，`uvicorn` 启动。
- 前端镜像：`node:20-alpine` 构建 + Nginx 托管 `dist/`。
- 数据卷：挂载 `gateway.db` 到持久卷。

## 四、关键配置项（环境变量）

| 变量 | 说明 | 默认 |
|------|------|------|
| `DATABASE_URL` | 数据库连接串 | `sqlite:///./data/gateway.db` |
| `GATEWAY_PORT` | 后端监听端口 | `8000` |
| `ROUTE_EXPLORE_RATE` | 路由探索率 | `0.05` |
| `HEALTH_CHECK_INTERVAL` | 容灾健康检查间隔（秒） | `5` |
| 供应商 `provider_type` | `mock` / `openai` / `anthropic` / `zhipu` | `mock` |

> 真实供应商接入：在「供应商管理」页将 `provider_type` 改为目标类型，并提供 `base_url` + `api_key`（密钥经网关集中托管）。

## 五、运维要点

- **可观测**：`/api/v1/overview/summary` 提供核心指标；请求日志表 `request_logs` 记录全链路。
- **限流/配额**：规则改动后服务层 `reload` 即时重建桶（EX-10 内存快照）。
- **容灾**：熔断状态机 closed→open→half_open→closed，后台健康检查每 5s 探测。
- **数据备份**：定期备份 `gateway.db`；切库时保持表结构（见 `docs/DATA_MODEL.md` 19 张表 DDL）。

## 六、已知边界（demo 阶段）

1. 控制台管理接口 demo 阶段不鉴权，仅 `/chat/completions` 校验 `X-API-Key`。
2. 默认供应商为 `mock`，返回模拟响应；真实推理需配置真实供应商。
3. SQLite 适用于单机 demo；高并发生产建议切换 PostgreSQL 并引入 Redis 作记忆热层。

> 本工程为产品设计参考实现，具体上线请结合公司合规与法务要求确认。
