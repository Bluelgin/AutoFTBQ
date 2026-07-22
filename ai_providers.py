"""Provider presets and model-discovery helpers for AutoFTBQ."""

from __future__ import annotations

import time
from urllib.parse import urlsplit, urlunsplit

import requests


CUSTOM_PROVIDER = "第三方自定义"

PROVIDER_PRESETS = {
    "DeepSeek": {
        "chat_url": "https://api.deepseek.com/chat/completions",
        "models_url": "https://api.deepseek.com/models",
        "model": "deepseek-chat",
    },
    "OpenAI": {
        "chat_url": "https://api.openai.com/v1/chat/completions",
        "models_url": "https://api.openai.com/v1/models",
        "model": "gpt-4o",
    },
    "Gemini": {
        "chat_url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "models_url": "https://generativelanguage.googleapis.com/v1beta/openai/models",
        "model": "gemini-2.5-flash",
    },
    "Moonshot": {
        "chat_url": "https://api.moonshot.cn/v1/chat/completions",
        "models_url": "https://api.moonshot.cn/v1/models",
        "model": "moonshot-v1-8k",
    },
    "Zhipu": {
        "chat_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "models_url": "https://open.bigmodel.cn/api/paas/v4/models",
        "model": "glm-4",
    },
    "Qwen": {
        "chat_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "models_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/models",
        "model": "qwen-plus",
    },
    "SiliconFlow": {
        "chat_url": "https://api.siliconflow.cn/v1/chat/completions",
        "models_url": "https://api.siliconflow.cn/v1/models",
        "model": "deepseek-ai/DeepSeek-V3",
    },
    "Volcengine": {
        "chat_url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "models_url": "",
        "model": "",
        "hint": "火山引擎请填写控制台提供的 Model ID 或 Endpoint ID（ep-xxxxx）",
    },
    CUSTOM_PROVIDER: {},
}

_PROVIDER_LEGACY_KEYS = {
    "deepseek": "DeepSeek",
    "custom": CUSTOM_PROVIDER,
}


def normalize_provider(provider):
    """Migrate legacy provider keys while preserving known display names."""
    if not provider:
        return "DeepSeek"
    if provider in PROVIDER_PRESETS:
        return provider
    return _PROVIDER_LEGACY_KEYS.get(str(provider).lower(), "DeepSeek")


def derive_models_url(chat_url):
    """Derive a common OpenAI-compatible models endpoint from a chat URL."""
    if not chat_url:
        return ""
    try:
        parsed = urlsplit(str(chat_url).strip())
    except ValueError:
        return ""
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""

    path = parsed.path.rstrip("/")
    suffix = "/chat/completions"
    if path.endswith(suffix):
        path = path[:-len(suffix)] + "/models"
    elif path.endswith("/v1"):
        path += "/models"
    else:
        return ""
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def fetch_provider_models(api_key, models_url, timeout=15, max_retries=2):
    """Return ``(model_ids, error)`` without making discovery mandatory."""
    if not api_key or not str(api_key).strip():
        return [], "请先填写 API Key，或直接手动输入模型 ID"
    if not models_url:
        return [], "该服务商未提供模型列表接口，请手动输入模型 ID"

    headers = {
        "Authorization": f"Bearer {str(api_key).strip()}",
        "Content-Type": "application/json",
        "User-Agent": "AutoFTBQ",
    }
    last_error = ""
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(models_url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                payload = response.json()
                items = payload.get("data", []) if isinstance(payload, dict) else payload
                if not isinstance(items, list):
                    return [], "模型列表返回格式不受支持，请手动输入模型 ID"
                models = sorted({
                    str(item["id"]).strip()
                    for item in items
                    if isinstance(item, dict) and item.get("id")
                })
                return models, None
            if response.status_code == 401:
                return [], "API Key 无效，请检查后重试"
            if response.status_code == 403:
                return [], "无权读取模型列表，请手动输入模型 ID"
            if response.status_code == 404:
                return [], "该平台不支持模型列表接口，请手动输入模型 ID"
            if response.status_code not in (429, 500, 502, 503, 504):
                return [], f"获取模型失败（HTTP {response.status_code}），请手动输入模型 ID"

            last_error = f"服务暂时不可用（HTTP {response.status_code}）"
            if attempt < max_retries:
                retry_after = response.headers.get("Retry-After", "")
                delay = float(retry_after) if retry_after.replace(".", "", 1).isdigit() else 2 * (attempt + 1)
                time.sleep(min(delay, 10))
        except requests.exceptions.Timeout:
            last_error = "获取模型列表超时"
            if attempt < max_retries:
                time.sleep(2 * (attempt + 1))
        except requests.exceptions.ConnectionError:
            return [], "无法连接模型列表接口，请检查 URL 或手动输入模型 ID"
        except (TypeError, ValueError, requests.exceptions.JSONDecodeError) as exc:
            return [], f"模型列表返回无效：{exc}"
        except requests.RequestException as exc:
            return [], f"获取模型失败：{exc}"

    return [], f"{last_error}，请稍后重试或手动输入模型 ID"
