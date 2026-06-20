from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env.server", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    server_port: int = Field(default=8000, alias="SERVER_PORT")
    cors_origin: str = Field(default="", alias="CORS_ORIGIN")

    auth_username: str = Field(default="admin", alias="AUTH_USERNAME")
    auth_password: str = Field(default="123456", alias="AUTH_PASSWORD")
    auth_secret: str = Field(default="kira_dev_secret", alias="AUTH_SECRET")
    auth_token_ttl_ms: int = Field(default=15 * 60 * 1000, alias="AUTH_TOKEN_TTL_MS")
    refresh_token_ttl_ms: int = Field(
        default=30 * 24 * 60 * 60 * 1000,
        alias="REFRESH_TOKEN_TTL_MS",
    )
    refresh_cookie_name: str = Field(default="refresh_token", alias="REFRESH_COOKIE_NAME")

    mongodb_uri: str = Field(default="mongodb://127.0.0.1:27017", alias="MONGODB_URI")
    mongodb_db_name: str = Field(default="chat_app", alias="MONGODB_DB_NAME")

    upstream_timeout_ms: int = Field(default=120000, alias="UPSTREAM_TIMEOUT_MS")
    upstream_auth_mode: str = Field(default="bearer", alias="UPSTREAM_AUTH_MODE")
    upstream_temperature: float = Field(default=1.0, alias="UPSTREAM_TEMPERATURE")
    upstream_top_p: float = Field(default=1.0, alias="UPSTREAM_TOP_P")
    upstream_system_prompt: str = Field(
        default="你是一个专业、简洁、准确的中文 AI 助手，只说中文。",
        alias="UPSTREAM_SYSTEM_PROMPT",
    )
    upstream_headers_json: str = Field(default="", alias="UPSTREAM_HEADERS_JSON")

    upload_max_size: int = Field(default=10 * 1024 * 1024, alias="UPLOAD_MAX_SIZE")
    avatar_max_size: int = Field(default=10 * 1024 * 1024, alias="AVATAR_MAX_SIZE")
    uploads_dir: str = Field(default="../uploads", alias="UPLOADS_DIR")

    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    mcp_config_path: str = Field(default="app/mcp/config.json", alias="MCP_CONFIG_PATH")
    amap_maps_api_key: str = Field(default="", alias="AMAP_MAPS_API_KEY")
    agent_debug_history: bool = Field(default=False, alias="AGENT_DEBUG_HISTORY")

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origin.split(",") if item.strip()]

    @property
    def upload_path(self) -> Path:
        path = Path(self.uploads_dir)
        if not path.is_absolute():
            path = (BACKEND_DIR / path).resolve()
        return path

    @property
    def mcp_config_file(self) -> Path:
        path = Path(self.mcp_config_path)
        if not path.is_absolute():
            path = (BACKEND_DIR / path).resolve()
        return path

    @property
    def extra_headers(self) -> dict[str, str]:
        if not self.upstream_headers_json:
            return {}
        try:
            parsed = json.loads(self.upstream_headers_json)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return {str(k): str(v) for k, v in parsed.items()}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
