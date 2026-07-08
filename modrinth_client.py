#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Modrinth API 客户端 — Mod 分类查询 + 缓存"""

import os, json, time, requests
from datetime import datetime, timedelta

MODRINTH_API_BASE = "https://api.modrinth.com/v2"
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_modrinth_cache")
CACHE_DAYS = 30  # Mod 分类数据稳定，缓存久一些
REQUEST_TIMEOUT = 5
REQUEST_INTERVAL = 0.5  # Modrinth 限流宽松

# Modrinth 分类映射到内部 category
MODRINTH_MAP = {
    "technology":  "tech",
    "tech":        "tech",
    "magic":       "magic",
    "adventure":   "world",
    "worldgen":    "world",
    "food":        "food",
    "feasts":      "food",
    "farming":     "food",
    "decoration":  "decor",
    "decorative":  "decor",
    "building":    "decor",
    "storage":     "utility",
    "utility":     "utility",
    "equipment":   "tech",
    "tools":       "tech",
    "armor":       "tech",
    "weapons":     "tech",
    "combat":      "mob",
    "mobs":        "mob",
    "creatures":   "mob",
    "transport":   "tech",
    "transportation": "tech",
    "automation":  "tech",
    "energy":      "tech",
    "processing":  "tech",
    "redstone":    "tech",
}

SESSION = None

def _get_session():
    global SESSION
    if SESSION is None:
        SESSION = requests.Session()
        SESSION.headers.update({
            "User-Agent": "AutoFTBQ/1.3 (GitHub: Bluelgin/AutoFTBQ)"
        })
    return SESSION


def _cache_path(mod_id):
    os.makedirs(CACHE_DIR, exist_ok=True)
    safe_name = mod_id.replace("/", "_").replace("\\", "_")
    return os.path.join(CACHE_DIR, f"{safe_name}.json")


def _load_cache(mod_id):
    path = _cache_path(mod_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        age = datetime.now() - datetime.fromisoformat(data.get("cached_at", "2000-01-01T00:00:00"))
        if age < timedelta(days=CACHE_DAYS):
            return data.get("category")
    except Exception:
        pass
    return None


def _save_cache(mod_id, category):
    path = _cache_path(mod_id)
    data = {"mod_id": mod_id, "category": category, "cached_at": datetime.now().isoformat()}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _map_categories(modrinth_categories):
    """将 Modrinth 的多个 tag 映射为最匹配的单个内部 category"""
    scores = {}
    for ct in modrinth_categories:
        ct_lower = ct.lower()
        mapped = MODRINTH_MAP.get(ct_lower)
        if mapped:
            scores[mapped] = scores.get(mapped, 0) + 1
    if not scores:
        return None
    # 返回出现最多的 category
    return max(scores, key=scores.get)


def fetch_modrinth_category(mod_id):
    """
    从 Modrinth API 查询 Mod 分类。
    返回: category 字符串 (tech/magic/decor/...) 或 None
    """
    # Step 1: 检查本地缓存
    cached = _load_cache(mod_id)
    if cached is not None:
        return cached if cached != "__not_found__" else None

    # Step 2: 搜索 Modrinth
    try:
        session = _get_session()
        # 尝试精确 slug 查询
        resp = session.get(
            f"{MODRINTH_API_BASE}/project/{mod_id}",
            timeout=REQUEST_TIMEOUT
        )
        if resp.status_code == 200:
            data = resp.json()
            cats = _map_categories(data.get("categories", []))
            if cats:
                _save_cache(mod_id, cats)
                return cats

        # 尝试搜索
        time.sleep(REQUEST_INTERVAL)
        resp = session.get(
            f"{MODRINTH_API_BASE}/search",
            params={"query": mod_id, "facets": '[["project_type:mod"]]', "limit": 1},
            timeout=REQUEST_TIMEOUT
        )
        if resp.status_code == 200:
            hits = resp.json().get("hits", [])
            if hits:
                cats = _map_categories(hits[0].get("categories", []))
                if cats:
                    _save_cache(mod_id, cats)
                    return cats

        # 未找到
        _save_cache(mod_id, "__not_found__")
        return None

    except Exception:
        return None
