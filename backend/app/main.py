"""FastAPI 入口：CORS、中间件、路由注册、启动建表+seed、后台健康检查、异常处理。"""
from __future__ import annotations

import asyncio
import contextlib

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .db import Base, SessionLocal, engine
from .routers import (
    alerts,
    balancing,
    chat,
    memory,
    overview,
    providers,
    resilience,
    routing,
    settings as settings_router,
    traffic,
)
from .schemas import AppError, ok
from .seed import seed
from .services.resilience_service import resilience_service
from .services.router_service import router_service
from .services.traffic_service import traffic_service


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """启动：建表 + 幂等 seed + 加载内存快照；后台启动健康检查。"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db)
        traffic_service.reload(db)
        router_service.reload(db)
    finally:
        db.close()

    health_task = asyncio.create_task(_health_check_loop())
    try:
        yield
    finally:
        health_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await health_task


async def _health_check_loop() -> None:
    """后台周期健康检查（EX-01 熔断状态机）。"""
    while True:
        try:
            await asyncio.sleep(settings.health_check_interval_s)
            db = SessionLocal()
            try:
                events = resilience_service.check_health(db)
                for ev in events:
                    from .services.observability import observability_service

                    observability_service.raise_alert(
                        db,
                        severity=ev["severity"],
                        title=ev["title"],
                        description="健康检查探测触发",
                        source=ev["source"],
                    )
            finally:
                db.close()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - 后台任务不因单次异常退出
            continue


app = FastAPI(title="模型网关", version="v2.4", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.http_status, content={"code": exc.code, "message": exc.message, "data": None})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"code": 1001, "message": "参数错误：请求体校验失败", "data": None})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"code": 5000, "message": "服务器内部错误", "data": None})


@app.get("/api/v1/health")
async def health():
    return ok({"status": "up", "version": "v2.4"})


API_PREFIX = "/api/v1"
app.include_router(chat.router, prefix=API_PREFIX)
app.include_router(overview.router, prefix=API_PREFIX)
app.include_router(routing.router, prefix=API_PREFIX)
app.include_router(providers.router, prefix=API_PREFIX)
app.include_router(balancing.router, prefix=API_PREFIX)
app.include_router(traffic.router, prefix=API_PREFIX)
app.include_router(memory.router, prefix=API_PREFIX)
app.include_router(resilience.router, prefix=API_PREFIX)
app.include_router(alerts.router, prefix=API_PREFIX)
app.include_router(settings_router.router, prefix=API_PREFIX)
