from __future__ import annotations

import re


def normalize_custom_model_name(value: str) -> str:
    name = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,80}", name):
        return ""
    return name


def to_openai_compat_endpoint(url: str) -> str:
    trimmed = str(url or "").strip().rstrip("/")
    if not trimmed:
        return ""
    if trimmed.endswith("/chat/completions"):
        return trimmed
    return f"{trimmed}/chat/completions"


def to_openai_client_base_url(endpoint: str) -> str:
    trimmed = str(endpoint or "").strip().rstrip("/")
    if not trimmed:
        return ""
    return re.sub(r"/chat/completions$", "", trimmed, flags=re.I)


class ModelRegistry:
    all_models: list[str] = []
    default_model: str = ""

    def resolve_selection(self, model_name: str = "") -> None:
        return None


model_registry = ModelRegistry()
