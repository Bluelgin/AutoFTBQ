#!/usr/bin/env python3
"""
MC百科 Wiki 数据爬虫 + 缓存
通过访问 mcmod.cn 获取 Mod 的玩法资料
"""

import os, json, time, requests, re
from datetime import datetime, timedelta

# ═══════════════════════════════════════════════════
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_wiki_cache")
CACHE_DAYS = 7
REQUEST_TIMEOUT = 8
REQUEST_INTERVAL = 2.0
SESSION = None

def _get_session():
    global SESSION
    if SESSION is None:
        SESSION = requests.Session()
        SESSION.headers.update({
            "User-Agent": "AutoFTBQ/1.2 (Minecraft Quest Generator; contact: github.com/Bluelgin/AutoFTBQ)"
        })
    return SESSION

# ═══════════════════════════════════════════════════
def _cache_path(mod_id):
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{mod_id}.json")

def _load_cache(mod_id):
    path = _cache_path(mod_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        age = datetime.now() - datetime.fromisoformat(data.get("cached_at", "2000-01-01T00:00:00"))
        if age < timedelta(days=CACHE_DAYS):
            return data
    except Exception:
        pass
    return None

def _save_cache(mod_id, data):
    data["cached_at"] = datetime.now().isoformat()
    path = _cache_path(mod_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ═══════════════════════════════════════════════════
def fetch_mod_wiki(mod_id):
    """
    获取 Mod 在 MC百科上的简要资料。
    返回: {"name": ..., "items_summary": ..., "guide_text": ...} 或 None
    """
    cached = _load_cache(mod_id)
    if cached:
        print(f"[WIKI] Cache hit for {mod_id}")
        return cached.get("data")

    result = _scrape_mod(mod_id)
    if result:
        _save_cache(mod_id, {"data": result})
    return result

def _scrape_mod(mod_id):
    """从 MC百科爬取 Mod 资料。任何错误都返回 None。"""
    try:
        session = _get_session()
        search_url = f"https://api.mcmod.cn/v1/class/search?keyword={mod_id}"
        resp = session.get(search_url, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200 or not resp.text.strip():
            return _scrape_web(session, mod_id)

        data = resp.json()
        results = data.get("data", [])
        if not results:
            return _scrape_web(session, mod_id)

        class_id = results[0].get("classid")
        time.sleep(REQUEST_INTERVAL)

        detail_url = f"https://api.mcmod.cn/v1/class/detail?classid={class_id}"
        resp2 = session.get(detail_url, timeout=REQUEST_TIMEOUT)
        if resp2.status_code != 200:
            return _scrape_web(session, mod_id)

        detail = resp2.json().get("data", {})
        name = detail.get("name", "")
        brief = detail.get("brief", "") or ""

        items_text = ""
        if detail.get("items"):
            items_text = f"已知物品: {detail['items'][:300]}"

        guide_text = ""
        if detail.get("guide"):
            guide_text = str(detail.get("guide", ""))[:2000]

        if brief[:500]:
            guide_text = brief[:500] + "\n" + guide_text

        return {
            "name": name or "",
            "items_summary": items_text,
            "guide_text": guide_text[:3000],
        }
    except Exception:
        return None

def _scrape_web(session, mod_id):
    """回退方案：直接爬取网页"""
    try:
        url = f"https://www.mcmod.cn/class/{mod_id}.html"
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return None

        html = resp.text
        name_match = re.search(r"<title>(.+?)</title>", html)
        name = name_match.group(1).replace(" - MC百科", "").strip() if name_match else ""

        brief = ""
        brief_match = re.search(r'<meta name="description" content="(.+?)"', html)
        if brief_match:
            brief = re.sub(r'&[a-z]+;', '', brief_match.group(1))[:500]

        guide_text = ""
        guide_match = re.search(r'class="common-text[^"]*".*?>(.{10,}?)</div>', html, re.DOTALL)
        if guide_match:
            guide_text = re.sub(r'<[^>]+>', '', guide_match.group(1)).strip()[:2000]

        return {
            "name": name,
            "items_summary": "",
            "guide_text": (brief + "\n" + guide_text) if guide_text else brief,
        }
    except Exception:
        return None

# ═══════════════════════════════════════════════════
def build_wiki_prompt_injections(all_mods, scanned_items=None):
    """
    构造注入 Prompt 的 Wiki 数据文本。
    all_mods: [{"mod_id": ...}, ...]
    返回: str - 可直接插入 Prompt 的文本
    """
    lines = []
    for m in all_mods:
        mod_id = m.get("mod_id", "")
        if not mod_id:
            continue
        try:
            wiki = fetch_mod_wiki(mod_id)
            if not wiki or (not wiki.get("guide_text") and not wiki.get("items_summary")):
                continue
            name = wiki.get("name") or m.get("mod_name", "")
            lines.append(f"\n📖 {name} ({mod_id}) — MC百科资料:")
            if wiki.get("items_summary"):
                lines.append(f"  物品: {wiki['items_summary']}")
            if wiki.get("guide_text"):
                guide = wiki["guide_text"][:1500]
                lines.append(f"  玩法: {guide}")
        except Exception:
            pass

    if not lines:
        return ""

    lines.insert(0, "=== MC百科 Mod 资料（供参考，帮助设计更准确的任务流程）===")
    return "\n".join(lines)