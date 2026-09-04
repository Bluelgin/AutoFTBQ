#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MOD 信息查询 — 通过 MC百科 / Modrinth 等平台获取并展示 MOD 详情。

查询顺序：MC百科（中文资料最全）→ Modrinth API（下载量/简介）→ 本地资料兜底。
任何来源失败都不会抛异常，保证 UI 始终能展示结果与跳转链接。
"""

import time

try:
    from . import mcwiki_crawler as _wiki
    from . import modrinth_client as _mrc
    from .ai_module import CAT_LABEL as _CAT_LABEL
    from .ai_module import MOD_DB as _MOD_DB
except ImportError:
    import mcwiki_crawler as _wiki
    import modrinth_client as _mrc
    from ai_module import CAT_LABEL as _CAT_LABEL
    from ai_module import MOD_DB as _MOD_DB

REQUEST_TIMEOUT = 8
PLATFORM_LABELS = {
    "mcmod": "MC百科",
    "modrinth": "Modrinth",
    "local": "本地资料",
}


# ═══════════════════════════════════════════════════
# 各平台链接构造
def mcmod_search_url(mod_id):
    return f"https://search.mcmod.cn/s?key={mod_id}"


def mcmod_class_url(class_id):
    if not class_id:
        return ""
    return f"https://www.mcmod.cn/class/{class_id}.html"


def modrinth_search_url(mod_id):
    return f"https://modrinth.com/mods?q={mod_id}"


def modrinth_detail_url(slug):
    if not slug:
        return ""
    return f"https://modrinth.com/mod/{slug}"


def curseforge_search_url(mod_id):
    return f"https://www.curseforge.com/minecraft/search?search={mod_id}"


def build_links(mod_id, mcmod_class_id="", modrinth_slug=""):
    return {
        "mcmod": mcmod_class_url(mcmod_class_id) or mcmod_search_url(mod_id),
        "modrinth": modrinth_detail_url(modrinth_slug) or modrinth_search_url(mod_id),
        "curseforge": curseforge_search_url(mod_id),
        "mcmod_search": mcmod_search_url(mod_id),
    }


# ═══════════════════════════════════════════════════
def _fetch_mcmod_info(mod_id):
    """MC百科：名称 + 玩法简介 + 详情页 class_id。"""
    try:
        wiki = _wiki.fetch_mod_wiki(mod_id)
        if not isinstance(wiki, dict):
            return None
        return {
            "name": wiki.get("name") or mod_id,
            "guide": wiki.get("guide_text") or "",
            "class_id": str(wiki.get("class_id") or ""),
        }
    except Exception:
        return None


def _fetch_modrinth_info(mod_id):
    """Modrinth API：名称 + 简介 + 下载量 + slug。"""
    try:
        session = _mrc._get_session()
        resp = session.get(
            f"{_mrc.MODRINTH_API_BASE}/project/{mod_id}",
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                return {
                    "name": data.get("title") or mod_id,
                    "summary": data.get("description") or "",
                    "categories": data.get("categories") or [],
                    "downloads": int(data.get("downloads") or 0),
                    "slug": data.get("slug") or "",
                }
        time.sleep(0.3)
        resp = session.get(
            f"{_mrc.MODRINTH_API_BASE}/search",
            params={"query": mod_id, "facets": '[["project_type:mod"]]', "limit": 1},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            hits = resp.json().get("hits", [])
            if hits:
                hit = hits[0]
                return {
                    "name": hit.get("title") or mod_id,
                    "summary": hit.get("description") or "",
                    "categories": hit.get("categories") or [],
                    "downloads": int(hit.get("downloads") or 0),
                    "slug": hit.get("slug") or "",
                }
    except Exception:
        return None
    return None


def fetch_mod_info(mod_id, local_name="", local_category=""):
    """综合查询一个 MOD 的信息，任何情况都不抛异常。

    返回 dict：
      mod_id / name / summary / guide / category(内部英文键) / category_label(中文)
      platform / downloads / links({mcmod, modrinth, curseforge, mcmod_search})
    """
    mod_id = str(mod_id or "").strip()
    info = {
        "mod_id": mod_id,
        "name": str(local_name or mod_id),
        "summary": "",
        "guide": "",
        "category": str(local_category or ""),
        "platform": "local",
        "downloads": 0,
        "links": build_links(mod_id),
    }

    # 本地资料兜底：MOD_DB 收录过的补全名称/类别（不覆盖本地扫描名）
    if isinstance(_MOD_DB, dict) and mod_id in _MOD_DB:
        db = _MOD_DB.get(mod_id) or {}
        if isinstance(db, dict):
            if not info["name"] or info["name"] == mod_id:
                info["name"] = db.get("name") or info["name"]
            info["category"] = db.get("category") or info["category"]

    mcmod = _fetch_mcmod_info(mod_id)
    if mcmod:
        info["name"] = mcmod.get("name") or info["name"]
        info["guide"] = mcmod.get("guide") or ""
        info["links"] = build_links(mod_id, mcmod_class_id=mcmod.get("class_id", ""))
        info["platform"] = "mcmod"
        return info

    modrinth = _fetch_modrinth_info(mod_id)
    if modrinth:
        info["name"] = modrinth.get("name") or info["name"]
        info["summary"] = modrinth.get("summary") or ""
        info["downloads"] = int(modrinth.get("downloads") or 0)
        categories = modrinth.get("categories") or []
        if categories:
            mapped = _mrc._map_categories(categories)
            if mapped:
                info["category"] = mapped
        info["links"] = build_links(mod_id, modrinth_slug=modrinth.get("slug", ""))
        info["platform"] = "modrinth"
        return info

    return info


def format_mod_info(info):
    """把 fetch_mod_info 的结果格式化为可读文本（用于信息窗口）。"""
    lines = []
    lines.append(f"【{info.get('name') or '未知'}】")
    lines.append(f"Mod ID: {info.get('mod_id') or '未知'}")
    category = info.get("category") or ""
    if category:
        lines.append(f"分类: {_CAT_LABEL.get(category, category)}")
    platform = PLATFORM_LABELS.get(info.get("platform"), info.get("platform") or "未知")
    lines.append(f"信息来源: {platform}")
    if info.get("downloads"):
        lines.append(f"Modrinth 下载量: {info['downloads']:,}".replace(",", ","))
    links = info.get("links") or {}
    if links.get("mcmod"):
        lines.append(f"MC百科: {links['mcmod']}")
    if links.get("modrinth"):
        lines.append(f"Modrinth: {links['modrinth']}")
    if links.get("curseforge"):
        lines.append(f"CurseForge: {links['curseforge']}")
    lines.append("")
    guide = (info.get("guide") or "").strip()
    summary = (info.get("summary") or "").strip()
    if guide:
        lines.append("── MC百科 玩法简介 ──")
        lines.append(guide[:2000])
    elif summary:
        lines.append("── Modrinth 简介 ──")
        lines.append(summary[:2000])
    else:
        lines.append("（未能从平台获取简介，可点击上方链接到 MC百科 / Modrinth 查看）")
    return "\n".join(lines)
