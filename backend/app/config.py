"""全局配置（pydantic-settings）。

配置优先级：环境变量 > .env 文件 > 默认值。
数据库路径默认解析到 ``backend/data/gateway.db``，保证从任意工作目录启动均可用。
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ 目录（config.py 位于 backend/app/ 下）
BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
DEFAULT_DB_PATH = DATA_DIR / "gateway.db"


class Settings(BaseSettings):
    """应用运行配置。"""

    database_url: str = f"sqlite:///{DEFAULT_DB_PATH}"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # 上游调用超时（EX-03 分级超时）
    default_timeout_s: int = 30
    first_token_timeout_s: int = 5

    # 后台健康检查间隔
    health_check_interval_s: int = 5

    # 幂等记录 TTL（秒，默认 10 分钟）
    idempotency_ttl_seconds: int = 600

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        """返回拆分后的 CORS 来源列表。"""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
