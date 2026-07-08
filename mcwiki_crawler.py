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
        # Step 1: 搜索 Mod，获取 class_id
        # 新搜索地址
        search_url = f"https://search.mcmod.cn/s?key={mod_id}"
        session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        resp = session.get(search_url, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return None

        html = resp.text
        # 从搜索结果中提取第一个匹配的 class_id
        class_ids = re.findall(r'/class/(\d+)\.html', html)
        if not class_ids:
            # 可能重定向到了详情页
            class_ids = re.findall(r'/class/(\d+)\.html', html)
        if not class_ids:
            return None

        class_id = class_ids[0]  # 第一个结果
        name_match = re.search(r'<a[^>]*href="/class/' + class_id + r'\.html"[^>]*>([^<]+)</a>', html)
        name = re.sub(r'<[^>]+>', '', name_match.group(1)).strip() if name_match else mod_id
        time.sleep(REQUEST_INTERVAL)

        # Step 2: 抓取详情页
        detail_url = f"https://www.mcmod.cn/class/{class_id}.html"
        resp2 = session.get(detail_url, timeout=REQUEST_TIMEOUT)
        if resp2.status_code != 200:
            return None

        detail_html = resp2.text

        # 提取简介（meta description）
        brief = ""
        brief_match = re.search(r'<meta name="description" content="(.+?)"', detail_html)
        if brief_match:
            brief = re.sub(r'&[a-z]+;', '', brief_match.group(1))[:500]

        # 提取玩法说明（common-text 内容区域）
        guide_text = ""
        guide_match = re.search(r'class="common-text[^"]*"[^>]*>', detail_html)
        if guide_match:
            # 找到对应 div 后面的内容
            start = guide_match.end()
            # 收集内容直到遇到下一个同级别标签
            content_parts = []
            depth = 0
            for m in re.finditer(r'<(div|p|ul|ol|li|h[1-6]|br|/?strong|/?b|/?i|/?u|/?a\b|/?span|/?font)[^>]*>|<!--.*?-->|</div>', detail_html[start:], re.DOTALL):
                tag = m.group()
                if tag.startswith('</div') or tag.startswith('<!--'):
                    if tag.startswith('</div'):
                        if depth <= 0:
                            break
                        depth -= 1
                elif tag.startswith('<div'):
                    depth += 1
                content_parts.append(m.group())
            if content_parts:
                guide_text = re.sub(r'<[^>]+>', '', ''.join(content_parts)).strip()[:2000]

        if not guide_text:
            guide_match2 = re.search(r'class="common-text[^"]*"[^>]*>(.{10,}?)</div>', detail_html, re.DOTALL)
            if guide_match2:
                guide_text = re.sub(r'<[^>]+>', '', guide_match2.group(1)).strip()[:2000]

        if not guide_text:
            # 尝试整个内容区域
            for cls in ["block-content", "class-content", "content-box", "article-content", "main-content"]:
                gm = re.search(r'class="' + cls + r'[^"]*"[^>]*>', detail_html)
                if gm:
                    start = gm.end()
                    end = detail_html.find('</div>', start)
                    if end > start:
                        guide_text = re.sub(r'<[^>]+>', '', detail_html[start:end]).strip()[:2000]
                        if guide_text:
                            break

        return {
            "name": name or mod_id,
            "items_summary": "",
            "guide_text": (brief[:300] + "\n" + guide_text) if guide_text else brief[:500],
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

# ═══════════════════════════════════════════════════
# 玩法说明批量爬取 — 原始数据，供用户用 Ollama 自行提炼
PLAYSTYLE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "playstyle_data")

def fetch_mod_guide_raw(mod_id):
    """
    爬取单个 Mod 的玩法简介/机制说明（纯文本，不含格式）。
    返回: str (原始简介文本) 或 None
    """
    wiki = fetch_mod_wiki(mod_id)
    if not wiki:
        return None
    name = wiki.get("name", "") or mod_id
    guide = wiki.get("guide_text", "") or ""
    items = wiki.get("items_summary", "") or ""
    parts = [f"Mod: {name} ({mod_id})"]
    if guide:
        parts.append(f"\n--- 玩法说明 ---\n{guide}")
    if items:
        parts.append(f"\n--- 物品摘要 ---\n{items}")
    return "\n".join(parts)

def batch_crawl_guides(mods_list, progress_callback=None):
    """
    批量爬取 Mod 玩法简介，保存原始文本到 playstyle_raw/。
    mods_list: [{"mod_id": ..., "mod_name": ...}, ...]
    返回: (成功数, 失败数)
    """
    raw_dir = os.path.join(PLAYSTYLE_DIR, "playstyle_raw")
    os.makedirs(raw_dir, exist_ok=True)
    ok, fail = 0, 0
    total = len(mods_list)

    for i, m in enumerate(mods_list):
        mod_id = m.get("mod_id", "")
        if not mod_id:
            fail += 1
            continue

        if progress_callback:
            progress_callback(f"爬取 {mod_id} ({i+1}/{total})...", None)

        try:
            text = fetch_mod_guide_raw(mod_id)
            if text:
                safe_name = mod_id.replace("/", "_").replace("\\", "_")
                path = os.path.join(raw_dir, f"{safe_name}.txt")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                ok += 1
            else:
                fail += 1
        except Exception:
            fail += 1

        time.sleep(REQUEST_INTERVAL)

    return ok, fail