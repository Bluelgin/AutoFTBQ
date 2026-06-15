#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ollama本地模型适配器 — 自动检测 + HTTP调用"""

import json
import requests

OLLAMA_BASE = "http://localhost:11434"
DETECT_TIMEOUT = 2

# 推荐的模型列表（按优先级）
RECOMMENDED_MODELS = [
    "qwen2.5-coder:7b",   # 中文代码能力最强
    "qwen2.5:7b",         # 中文通用
    "deepseek-coder:6.7b",# 代码生成
    "llama3.1:8b",        # 英文通用
    "qwen2.5-coder:3b",   # 轻量（最低配置）
    "qwen2.5:3b",         # 轻量中文
    "deepseek-r1:7b",     # 推理能力强
]


def check_ollama_available():
    """检测Ollama是否运行，返回 (available, models_list)"""
    try:
        resp = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=DETECT_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
            return True, models
        return False, []
    except (requests.ConnectionError, requests.Timeout,
            requests.RequestException, json.JSONDecodeError):
        return False, []


def find_best_model(available_models):
    """从可用模型中找到最佳推荐模型"""
    for rec in RECOMMENDED_MODELS:
        # 精确匹配或带latest标签
        if rec in available_models:
            return rec
        # 模糊匹配（如 qwen2.5-coder:7b-instruct）
        base = rec.split(":")[0]
        for am in available_models:
            am_base = am.split(":")[0]
            if am_base == base:
                return am
    # 没找到推荐模型，返回第一个
    return available_models[0] if available_models else None


def get_recommended_models_text():
    """获取推荐模型列表文本"""
    return "\n".join(f"  ollama pull {m}" for m in RECOMMENDED_MODELS[:4])


class OllamaClient:
    """Ollama HTTP客户端 — 与DeepSeekClient接口一致"""

    def __init__(self, model="qwen2.5-coder:7b"):
        self.model = model
        self.base_url = OLLAMA_BASE

    def chat(self, messages, temperature=0.5, max_tokens=8192):
        """
        发送聊天请求到Ollama
        返回生成的文本内容
        """
        system_prompt = ""
        user_prompt = ""
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            elif msg["role"] == "user":
                user_prompt = msg["content"]

        payload = {
            "model": self.model,
            "prompt": user_prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }

        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=600  # 本地模型可能较慢，给10分钟
            )
            if resp.status_code == 200:
                return resp.json().get("response", "")
            elif resp.status_code == 404:
                raise Exception(
                    f"模型 {self.model} 不存在。请运行: ollama pull {self.model}"
                )
            else:
                raise Exception(f"Ollama错误 {resp.status_code}: {resp.text[:200]}")
        except requests.ConnectionError:
            raise Exception(
                "无法连接到Ollama (localhost:11434)。请先启动Ollama。\n"
                "下载安装: https://ollama.com/download"
            )
        except requests.Timeout:
            raise Exception("Ollama请求超时，模型可能太大或内存不足")