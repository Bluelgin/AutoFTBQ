"""AI client adapters with one shared chat contract."""

from __future__ import annotations

import time
from typing import Protocol

import requests

try:
    from . import ollama_adapter
    from .ai_providers import PROVIDER_PRESETS, normalize_provider
except ImportError:
    import ollama_adapter
    from ai_providers import PROVIDER_PRESETS, normalize_provider


DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
API_TIMEOUT = 300
MAX_RETRIES = 3
RETRY_DELAY = 3


class ChatClient(Protocol):
    def chat(self, messages, temperature=0.7, max_tokens=8192):
        """Return ``(content, was_truncated)``."""


def _response_content(payload):
    """Read an OpenAI-compatible text response with useful shape errors."""
    if not isinstance(payload, dict):
        raise ValueError("API 返回值不是 JSON 对象")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("API 返回值缺少 choices[0]")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ValueError("API 返回值缺少 choices[0].message")
    content = message.get("content", "")
    if isinstance(content, list):
        content = "".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("text")
        )
    if not isinstance(content, str):
        raise ValueError("API 返回的 message.content 不是文本")
    return content, choices[0].get("finish_reason", "stop") == "length"


class GenericOpenAIClient:
    """Minimal OpenAI Chat Completions compatible client."""

    def __init__(self, api_key, api_url, model, timeout=API_TIMEOUT):
        if not api_url:
            raise ValueError("未配置 API URL")
        if not model:
            raise ValueError("未配置模型 ID")
        self.api_url = api_url
        self.model = model
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Bearer {str(api_key).strip()}",
            "Content-Type": "application/json",
            "User-Agent": "AutoFTBQ",
        }

    def chat(self, messages, temperature=0.7, max_tokens=8192):
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(
                    self.api_url,
                    json=payload,
                    headers=self.headers,
                    timeout=self.timeout,
                )
                if response.status_code == 200:
                    return _response_content(response.json())
                if response.status_code == 401:
                    raise RuntimeError("API Key 无效，请检查后重试")
                if response.status_code == 402:
                    raise RuntimeError("账户额度不足，请检查 API 余额")
                if response.status_code in (400, 403, 404, 422):
                    raise RuntimeError(f"API 请求无效（HTTP {response.status_code}）：{response.text[:200]}")
                if response.status_code not in (429, 500, 502, 503, 504):
                    raise RuntimeError(f"API 请求失败（HTTP {response.status_code}）：{response.text[:200]}")
                if attempt < MAX_RETRIES - 1:
                    retry_after = response.headers.get("Retry-After", "")
                    delay = float(retry_after) if retry_after.replace(".", "", 1).isdigit() else RETRY_DELAY * (attempt + 1)
                    time.sleep(min(delay, 30))
                    continue
                raise RuntimeError(f"API 服务暂时不可用（HTTP {response.status_code}）")
            except requests.exceptions.Timeout:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise RuntimeError("API 请求超时")
            except requests.exceptions.ConnectionError:
                raise RuntimeError("无法连接 API 服务器")
            except requests.RequestException as exc:
                raise RuntimeError(f"API 网络请求失败：{exc}") from exc
        raise RuntimeError("API 请求失败（重试次数耗尽）")


class DeepSeekClient(GenericOpenAIClient):
    def __init__(self, api_key):
        super().__init__(api_key, DEEPSEEK_API_URL, DEEPSEEK_MODEL)


def create_chat_client(engine, api_key=None, ollama_model=None, provider=None, api_url=None, api_model=None):
    """Create a client while keeping legacy engine names compatible."""
    if engine == "ollama":
        return ollama_adapter.OllamaClient(model=ollama_model or "qwen2.5-coder:7b")
    if engine == "dummy":
        return None
    if engine == "deepseek" and not provider and not api_url and not api_model:
        return DeepSeekClient(api_key or "")

    normalized = normalize_provider(provider)
    preset = PROVIDER_PRESETS.get(normalized, {})
    final_url = api_url or preset.get("chat_url") or DEEPSEEK_API_URL
    final_model = api_model or preset.get("model")
    return GenericOpenAIClient(api_key or "", final_url, final_model)
