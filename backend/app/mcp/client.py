from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings, get_settings

ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


class MCPServerConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = True
    required_env: list[str] = Field(default_factory=list, alias="requiredEnv")

    def to_langchain_config(self, env_values: dict[str, str]) -> dict[str, Any] | None:
        if any(not env_values.get(key) for key in self.required_env):
            return None
        return _expand_env_vars(
            self.model_dump(
                by_alias=True,
                exclude={"enabled", "required_env"},
                exclude_none=True,
            ),
            env_values,
        )


class MCPConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    servers: dict[str, MCPServerConfig] = Field(default_factory=dict)

    @classmethod
    def from_json(cls, value: Any) -> MCPConfig:
        if not isinstance(value, dict):
            return cls()
        if "servers" in value:
            return cls.model_validate(value)
        return cls(
            servers={
                key: MCPServerConfig.model_validate(item)
                for key, item in value.items()
            }
        )

    def enabled_servers(self, env_values: dict[str, str]) -> dict[str, dict[str, Any]]:
        servers = {}
        for name, server in self.servers.items():
            if not server.enabled:
                continue
            server_config = server.to_langchain_config(env_values)
            if server_config:
                servers[name] = server_config
        return servers


def _settings_env_values(settings: Settings) -> dict[str, str]:
    values = dict(os.environ)
    for field_name, field_info in type(settings).model_fields.items():
        alias = field_info.alias
        if not alias:
            continue
        value = getattr(settings, field_name, "")
        if value is not None:
            values.setdefault(alias, str(value))
    return values


def _expand_env_vars(value: Any, env_values: dict[str, str]) -> Any:
    if isinstance(value, str):
        return ENV_PATTERN.sub(lambda match: env_values.get(match.group(1), ""), value)
    if isinstance(value, list):
        return [_expand_env_vars(item, env_values) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env_vars(item, env_values) for key, item in value.items()}
    return value


def _read_mcp_config(path: Path) -> MCPConfig:
    if not path.exists():
        return MCPConfig()

    raw_text = path.read_text(encoding="utf-8").strip()
    if not raw_text:
        return MCPConfig()

    try:
        raw_config = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"MCP 配置文件格式错误: {path} ({exc})") from exc

    return MCPConfig.from_json(raw_config)


async def load_mcp_tools() -> list[Any]:
    settings = get_settings()
    config = _read_mcp_config(settings.mcp_config_file)
    servers = config.enabled_servers(_settings_env_values(settings))
    if not servers:
        return []

    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except Exception as exc:
        raise RuntimeError(
            "请先安装 langchain-mcp-adapters 后再启用 MCP 工具；"
            f"当前 Python: {sys.executable}；原始错误: {exc}"
        ) from exc

    client = MultiServerMCPClient(servers)
    return list(await client.get_tools())
