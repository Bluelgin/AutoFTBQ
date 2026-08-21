"""AI client adapters with one shared chat contract."""

from __future__ import annotations

import json
import time
from typing import Protocol

import requests

try:
    from . import ollama_adapter
    from .ai_providers import PROVIDER_PRESETS, normalize_provider, resolve_provider_model
except ImportError:
    import ollama_adapter
    from ai_providers import PROVIDER_PRESETS, normalize_provider, resolve_provider_model


DEEPSEEK_API_URL = PROVIDER_PRESETS["DeepSeek"]["chat_url"]
DEEPSEEK_MODEL = PROVIDER_PRESETS["DeepSeek"]["model"]
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

    def __init__(
        self,
        api_key,
        api_url,
        model,
        timeout=API_TIMEOUT,
        omit_temperature=False,
        request_overrides=None,
    ):
        if not api_url:
            raise ValueError("未配置 API URL")
        if not model:
            raise ValueError("未配置模型 ID")
        self.api_url = api_url
        self.model = model
        self.timeout = timeout
        self.omit_temperature = omit_temperature
        self.request_overrides = dict(request_overrides or {})
        self._tool_support = None
        self.headers = {
            "Authorization": f"Bearer {str(api_key).strip()}",
            "Content-Type": "application/json",
            "User-Agent": "AutoFTBQ",
        }

    def _payload(self, messages, temperature, max_tokens):
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if not self.omit_temperature:
            payload["temperature"] = temperature
        payload.update(self.request_overrides)
        return payload

    def _post(self, payload):
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(
                    self.api_url,
                    json=payload,
                    headers=self.headers,
                    timeout=self.timeout,
                )
                if response.status_code == 200:
                    body = response.json()
                    if not isinstance(body, dict):
                        raise RuntimeError("API 返回值不是 JSON 对象")
                    return body
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

    def chat(self, messages, temperature=0.7, max_tokens=8192):
        return _response_content(self._post(self._payload(messages, temperature, max_tokens)))

    def chat_with_tools(
        self,
        messages,
        tools,
        tool_handler,
        temperature=0.7,
        max_tokens=8192,
        max_rounds=3,
    ):
        """Run a bounded tool loop, falling back once when a provider rejects tools."""
        if self._tool_support is False or not tools:
            return self.chat(messages, temperature, max_tokens)
        conversation = [dict(message) for message in messages]
        for round_index in range(max(1, min(int(max_rounds), 6))):
            payload = self._payload(conversation, temperature, max_tokens)
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
            try:
                body = self._post(payload)
            except RuntimeError as exc:
                unsupported = any(
                    marker in str(exc)
                    for marker in ("HTTP 400", "HTTP 403", "HTTP 404", "HTTP 422")
                )
                if self._tool_support is None and unsupported:
                    self._tool_support = False
                    return self.chat(messages, temperature, max_tokens)
                raise
            choices = body.get("choices")
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                raise ValueError("API 返回值缺少 choices[0]")
            message = choices[0].get("message")
            if not isinstance(message, dict):
                raise ValueError("API 返回值缺少 choices[0].message")
            tool_calls = message.get("tool_calls")
            if not isinstance(tool_calls, list) or not tool_calls:
                self._tool_support = True
                return _response_content(body)
            self._tool_support = True
            bounded_calls = tool_calls[:6]
            bounded_message = dict(message)
            bounded_message.setdefault("role", "assistant")
            bounded_message["tool_calls"] = bounded_calls
            conversation.append(bounded_message)
            for call in bounded_calls:
                function = call.get("function", {}) if isinstance(call, dict) else {}
                name = str(function.get("name", ""))
                try:
                    arguments = json.loads(function.get("arguments", "{}") or "{}")
                except (TypeError, ValueError):
                    arguments = {}
                try:
                    result = tool_handler(name, arguments)
                except Exception as exc:
                    result = json.dumps({"error": str(exc)}, ensure_ascii=False)
                conversation.append({
                    "role": "tool",
                    "tool_call_id": str(call.get("id", f"tool_{round_index}")),
                    "name": name,
                    "content": str(result),
                })
        conversation.append({
            "role": "user",
            "content": (
                "Stop calling tools. Using the tool results already provided, "
                "return the final answer in the exact format requested by the original prompt."
            ),
        })
        payload = self._payload(conversation, temperature, max_tokens)
        return _response_content(self._post(payload))


class DeepSeekClient(GenericOpenAIClient):
    def __init__(self, api_key):
        preset = PROVIDER_PRESETS["DeepSeek"]
        super().__init__(
            api_key,
            DEEPSEEK_API_URL,
            DEEPSEEK_MODEL,
            omit_temperature=preset.get("omit_temperature", False),
            request_overrides=preset.get("request_overrides"),
        )


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
    uses_preset = bool(provider) or not api_url or api_url == preset.get("chat_url")
    final_model = (
        resolve_provider_model(normalized, api_model)
        if uses_preset
        else (api_model or preset.get("model"))
    )
    return GenericOpenAIClient(
        api_key or "",
        final_url,
        final_model,
        omit_temperature=preset.get("omit_temperature", False) if uses_preset else False,
        request_overrides=preset.get("request_overrides") if uses_preset else None,
    )
