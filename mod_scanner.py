#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mod Item Scanner — 从JAR文件中提取真实物品ID"""

import os
import re
import json
import zipfile
import threading
from collections import defaultdict

# 缓存
_item_cache = {}          # filepath → (mtime, {namespace: {item_id: display_name}})
_adv_cache = {}            # filepath → {namespace: [preferred_icon_item_ids]}
_recipe_inputs_cache = {}  # {output_item: [input_item_list]}
_cache_lock = threading.Lock()

# ════════════════════════════════════════════════════════
# 核心扫描函数
# ════════════════════════════════════════════════════════

def scan_jar_items(filepath, max_items_per_ns=200):
    """
    扫描单个JAR/ZIP文件，提取物品ID。
    返回: {namespace: {item_id: display_name, ...}, ...}
    """
    filepath = os.path.abspath(filepath)
    mtime = os.path.getmtime(filepath) if os.path.exists(filepath) else 0

    with _cache_lock:
        cached = _item_cache.get(filepath)
        if cached and cached[0] == mtime:
            return cached[1]

    result = defaultdict(dict)
    try:
        with zipfile.ZipFile(filepath, 'r') as zf:
            # 获取文件列表
            namelist = zf.namelist()

            # ── 1. 从data目录检测命名空间 ──
            detected_ns = set()
            for name in namelist:
                # data/<namespace>/...
                m = re.match(r'data/([^/]+)/', name)
                if m:
                    detected_ns.add(m.group(1))
                # assets/<namespace>/models/item/...
                m2 = re.match(r'assets/([^/]+)/models/item/(.+)\.json$', name)
                if m2:
                    detected_ns.add(m2.group(1))

            # ── 2. 加载语言文件获取显示名称 ──
            lang_map = {}
            for ns in list(detected_ns):
                for lang_file in [f'assets/{ns}/lang/en_us.json',
                                  f'assets/{ns}/lang/zh_cn.json',
                                  f'assets/{ns}/lang/en.json']:
                    try:
                        with zf.open(lang_file) as lf:
                            translations = json.loads(lf.read().decode('utf-8'))
                            lang_map.update(translations)
                    except (KeyError, json.JSONDecodeError, UnicodeDecodeError):
                        pass

            # ── 3. 提取物品ID — 从models/item/ ──
            for ns in detected_ns:
                prefix = f'assets/{ns}/models/item/'
                count = 0
                for name in namelist:
                    if not name.startswith(prefix) or not name.endswith('.json'):
                        continue
                    if count >= max_items_per_ns:
                        break
                    item_path = name[len(prefix):-len('.json')]  # e.g. "iron_pickaxe"
                    if not item_path or '/' in item_path:
                        # 跳过子目录中的(如armor/等)，后续处理
                        pass
                    item_id = f"{ns}:{item_path}"
                    display_name = lang_map.get(f"item.{ns}.{item_path}", "")
                    if not display_name:
                        display_name = lang_map.get(f"block.{ns}.{item_path}", "")
                    if not display_name:
                        # 尝试从block models中找
                        pass
                    result[ns][item_id] = display_name or _id_to_name(item_path)
                    count += 1

                # ── 4. 提取方块ID — 从models/block/ ──
                prefix_b = f'assets/{ns}/models/block/'
                count_b = 0
                for name in namelist:
                    if not name.startswith(prefix_b) or not name.endswith('.json'):
                        continue
                    if count + count_b >= max_items_per_ns:
                        break
                    block_path = name[len(prefix_b):-len('.json')]
                    if not block_path or '/' in block_path:
                        continue
                    item_id = f"{ns}:{block_path}"
                    if item_id in result[ns]:
                        continue  # 已有
                    display_name = lang_map.get(f"block.{ns}.{block_path}", "")
                    if not display_name:
                        display_name = lang_map.get(f"tile.{ns}.{block_path}.name", "")
                    result[ns][item_id] = display_name or _id_to_name(block_path)
                    count_b += 1

                # ── 5. 从成就/进度中提取图标物品ID ──
                adv_prefix = f'data/{ns}/advancements/'
                adv_icons = set()
                for name in namelist:
                    if not name.startswith(adv_prefix) or not name.endswith('.json'):
                        continue
                    try:
                        adv_data = json.loads(zf.read(name).decode('utf-8'))
                        if not isinstance(adv_data, dict):
                            continue
                        display = adv_data.get("display", {})
                        icon = display.get("icon", {})
                        if isinstance(icon, dict):
                            icon_id = icon.get("item", icon.get("id", ""))
                            if icon_id and ":" in icon_id and icon_id.startswith(ns + ":"):
                                adv_icons.add(icon_id)
                        elif isinstance(icon, str) and ":" in icon and icon.startswith(ns + ":"):
                            adv_icons.add(icon)
                    except Exception:
                        pass
                if adv_icons:
                    with _cache_lock:
                        _adv_cache[filepath] = (mtime, {ns: sorted(adv_icons)})
                    for aid in adv_icons:
                        if aid not in result[ns]:
                            result[ns][aid] = _id_to_name(aid.split(":", 1)[1])

                # ── 6. 从recipes中补充 ──
                recipe_prefix = f'data/{ns}/recipes/'
                seen_recipe_outputs = set()
                for name in namelist:
                    if not name.startswith(recipe_prefix):
                        continue
                    if len(seen_recipe_outputs) >= 50:
                        break
                    try:
                        raw = zf.read(name).decode('utf-8')
                        recipe = json.loads(raw)
                        output = recipe.get("result", "")
                        if isinstance(output, dict):
                            output = output.get("item", output.get("id", ""))
                    except Exception:
                        continue
                    if output and ":" in output:
                        seen_recipe_outputs.add(output)
                for rid in seen_recipe_outputs:
                    if rid not in result[ns]:
                        result[ns][rid] = _id_to_name(rid.split(":", 1)[1])

                # ── 7. 从recipes中提取原料依赖图 ──
                recipe_prefix2 = f'data/{ns}/recipes/'
                for name in namelist:
                    if not name.startswith(recipe_prefix2) or not name.endswith('.json'):
                        continue
                    try:
                        recipe = json.loads(zf.read(name).decode('utf-8'))
                        if not isinstance(recipe, dict):
                            continue
                        output = recipe.get("result", "")
                        if isinstance(output, dict):
                            output = output.get("item", output.get("id", ""))
                        if not output or ":" not in output:
                            continue
                        inputs = []
                        if recipe.get("type") == "minecraft:crafting_shaped":
                            for k, v in recipe.get("key", {}).items():
                                if k == " ":
                                    continue
                                if isinstance(v, dict):
                                    inp_id = v.get("item", v.get("id", ""))
                                    if inp_id and ":" in inp_id and inp_id not in inputs:
                                        inputs.append(inp_id)
                        elif recipe.get("type") in ("minecraft:crafting_shapeless", "minecraft:smelting", "minecraft:blasting", "minecraft:smoking"):
                            for ing in recipe.get("ingredients", []):
                                if isinstance(ing, dict):
                                    inp_id = ing.get("item", ing.get("id", ""))
                                elif isinstance(ing, str):
                                    inp_id = ing
                                else:
                                    continue
                                if inp_id and ":" in inp_id and inp_id not in inputs:
                                    inputs.append(inp_id)
                        if inputs:
                            with _cache_lock:
                                _recipe_inputs_cache[output] = inputs
                    except Exception:
                        pass

    except (zipfile.BadZipFile, IOError) as e:
        print(f"[WARN] Cannot scan {os.path.basename(filepath)}: {e}")

    # 缓存
    final = {ns: dict(items) for ns, items in result.items() if items}
    with _cache_lock:
        _item_cache[filepath] = (mtime, final)
    return final


def scan_folder_items(folder_path, selected_mods=None, progress_cb=None):
    """
    扫描mod文件夹中所有JAR文件，聚合物品ID。
    selected_mods: 可选, [{"filename":..., "mod_id":...}, ...]
    返回: {mod_id: {item_id: display_name, ...}, ...}
    """
    all_items = {}
    jar_files = []
    if selected_mods:
        jar_files = [os.path.join(folder_path, m["filename"]) for m in selected_mods
                     if os.path.isfile(os.path.join(folder_path, m["filename"]))]
    else:
        # 扫描整个文件夹
        for f in sorted(os.listdir(folder_path)):
            if f.lower().endswith((".jar", ".zip")):
                jar_files.append(os.path.join(folder_path, f))

    total = len(jar_files)
    for i, jarpath in enumerate(jar_files):
        if progress_cb:
            progress_cb(i + 1, total, os.path.basename(jarpath))
        items = scan_jar_items(jarpath)
        for ns, idmap in items.items():
            if ns not in all_items:
                all_items[ns] = {}
            all_items[ns].update(idmap)

    return all_items


def build_item_catalog_for_prompt(all_items, selected_mods):
    """
    构建用于AI prompt的物品目录文本。
    selected_mods: [{"mod_id":...}, ...]
    返回: str — 可直接嵌入prompt的物品列表
    """
    # 先确定哪些namespace属于已选mod
    active_ns = set()
    for m in selected_mods:
        active_ns.add(m.get("mod_id", ""))
    active_ns.add("minecraft")

    lines = ["=== 已验证的物品ID (请严格使用以下ID) ==="]
    lines.append("以下为从实际Mod文件中提取的物品ID，任务书中只能使用这些物品ID。\n")

    # minecraft items — 常用原版物品
    mc_items_common = [
        "minecraft:oak_log", "minecraft:spruce_log", "minecraft:birch_log",
        "minecraft:oak_planks", "minecraft:crafting_table", "minecraft:stick",
        "minecraft:wooden_pickaxe", "minecraft:stone_pickaxe", "minecraft:iron_pickaxe",
        "minecraft:diamond_pickaxe", "minecraft:netherite_pickaxe",
        "minecraft:wooden_axe", "minecraft:stone_axe", "minecraft:iron_axe",
        "minecraft:wooden_sword", "minecraft:stone_sword", "minecraft:iron_sword",
        "minecraft:diamond_sword", "minecraft:wooden_shovel", "minecraft:stone_shovel",
        "minecraft:iron_shovel", "minecraft:cobblestone", "minecraft:stone",
        "minecraft:iron_ingot", "minecraft:gold_ingot", "minecraft:diamond",
        "minecraft:netherite_ingot", "minecraft:coal", "minecraft:redstone",
        "minecraft:lapis_lazuli", "minecraft:emerald", "minecraft:flint",
        "minecraft:furnace", "minecraft:blast_furnace", "minecraft:smoker",
        "minecraft:enchanting_table", "minecraft:anvil", "minecraft:brewing_stand",
        "minecraft:obsidian", "minecraft:flint_and_steel", "minecraft:bow",
        "minecraft:arrow", "minecraft:shield", "minecraft:fishing_rod",
        "minecraft:shears", "minecraft:bucket", "minecraft:water_bucket",
        "minecraft:lava_bucket", "minecraft:torch", "minecraft:bedrock",
        "minecraft:apple", "minecraft:golden_apple", "minecraft:enchanted_golden_apple",
        "minecraft:cooked_beef", "minecraft:cooked_porkchop", "minecraft:bread",
        "minecraft:cake", "minecraft:ender_pearl", "minecraft:ender_eye",
        "minecraft:blaze_rod", "minecraft:blaze_powder", "minecraft:nether_wart",
        "minecraft:ghast_tear", "minecraft:magma_cream", "minecraft:spider_eye",
        "minecraft:rotten_flesh", "minecraft:bone", "minecraft:string",
        "minecraft:leather", "minecraft:gunpowder", "minecraft:slime_ball",
        "minecraft:book", "minecraft:bookshelf", "minecraft:paper",
        "minecraft:saddle", "minecraft:name_tag", "minecraft:experience_bottle",
        "minecraft:totem_of_undying", "minecraft:elytra", "minecraft:nether_star",
        "minecraft:dragon_egg", "minecraft:dragon_head", "minecraft:wither_skeleton_skull",
        "minecraft:netherrack", "minecraft:end_stone", "minecraft:prismarine",
        "minecraft:iron_block", "minecraft:gold_block", "minecraft:diamond_block",
        "minecraft:netherite_block", "minecraft:emerald_block",
        "minecraft:iron_helmet", "minecraft:iron_chestplate", "minecraft:iron_leggings",
        "minecraft:iron_boots", "minecraft:diamond_helmet", "minecraft:diamond_chestplate",
        "minecraft:diamond_leggings", "minecraft:diamond_boots",
        "minecraft:netherite_helmet", "minecraft:netherite_chestplate",
        "minecraft:netherite_leggings", "minecraft:netherite_boots",
        "minecraft:chainmail_helmet", "minecraft:chainmail_chestplate",
        "minecraft:potion", "minecraft:splash_potion", "minecraft:lingering_potion",
        "minecraft:glass_bottle", "minecraft:netherite_upgrade_smithing_template",
        "minecraft:cod", "minecraft:salmon", "minecraft:cooked_cod",
        "minecraft:white_bed", "minecraft:red_bed",
        "minecraft:oak_sapling", "minecraft:bone_meal", "minecraft:wheat",
        "minecraft:wheat_seeds", "minecraft:carrot", "minecraft:potato",
        "minecraft:sugar_cane", "minecraft:bamboo", "minecraft:kelp",
        "minecraft:egg", "minecraft:milk_bucket", "minecraft:sugar",
        "minecraft:glowstone_dust", "minecraft:glowstone",
        "minecraft:nether_brick", "minecraft:quartz",
        "minecraft:brick", "minecraft:clay_ball", "minecraft:clay",
        "minecraft:terracotta", "minecraft:glass", "minecraft:iron_bars",
        "minecraft:ladder", "minecraft:chest", "minecraft:barrel",
        "minecraft:hopper", "minecraft:dispenser", "minecraft:dropper",
        "minecraft:observer", "minecraft:piston", "minecraft:sticky_piston",
        "minecraft:repeater", "minecraft:comparator", "minecraft:lever",
        "minecraft:daylight_detector", "minecraft:tnt", "minecraft:rail",
        "minecraft:powered_rail", "minecraft:detector_rail", "minecraft:minecart",
        "minecraft:chest_minecart", "minecraft:furnace_minecart",
        "minecraft:painting", "minecraft:item_frame", "minecraft:armor_stand",
        "minecraft:lead", "minecraft:compass", "minecraft:clock",
        "minecraft:map", "minecraft:filled_map", "minecraft:crossbow",
        "minecraft:trident", "minecraft:turtle_helmet", "minecraft:scute",
        "minecraft:phantom_membrane", "minecraft:heart_of_the_sea",
        "minecraft:nautilus_shell", "minecraft:conduit", "minecraft:shulker_shell",
        "minecraft:shulker_box", "minecraft:end_crystal", "minecraft:fire_charge",
        "minecraft:firework_rocket", "minecraft:beacon", "minecraft:bell",
        "minecraft:honey_bottle", "minecraft:honeycomb",
    ]
    # 从扫描结果中获取minecraft items — 全部列出，不截断
    mc_scanned = all_items.get("minecraft", {})
    mc_combined = set(mc_items_common)
    mc_combined.update(mc_scanned.keys())
    lines.append(f"  minecraft ({len(mc_combined)} items)，列出前60个:")
    mc_sorted = sorted(mc_combined)
    for i in range(0, min(len(mc_sorted), 60), 15):
        chunk = mc_sorted[i:i+15]
        lines.append(f"    {', '.join(chunk)}")
    if len(mc_sorted) > 60:
        lines.append(f"    ... 以及其余 {len(mc_sorted) - 60} 个原版物品（使用标准 Minecraft ID 即可，如 minecraft:diamond_sword）")

    # 各mod的物品 — 每个Mod最多列出50个
    for ns in sorted(active_ns):
        if ns == "minecraft":
            continue
        items = all_items.get(ns, {})
        if items:
            sorted_ids = sorted(items.keys())
            display_count = min(len(sorted_ids), 50)
            lines.append(f"\n  {ns} ({len(items)} items)，列出前{display_count}个:")
            for i in range(0, display_count, 15):
                chunk = sorted_ids[i:i+15]
                lines.append(f"    {', '.join(chunk)}")
            if len(sorted_ids) > 50:
                lines.append(f"    ... 以及其余 {len(sorted_ids) - 50} 个物品，均遵循 {ns}:item_name 格式")
        else:
            lines.append(f"\n  {ns}: (no items scanned from JAR — use commonly known IDs)")

    lines.append("\n【重要】只使用以上列出的物品ID或遵循相同命名规律的ID。不要编造不存在的物品ID。")
    lines.append("如果某个Mod的物品ID没有列出，可以推测使用 'modid:item_name' 格式（全小写，下划线分隔）。")
    return "\n".join(lines)


def _levenshtein(a, b):
    """编辑距离"""
    if len(a) < len(b): a, b = b, a
    if not b: return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j+1]+1, curr[j]+1, prev[j]+(ca!=cb)))
        prev = curr
    return prev[-1]

def _find_best_match(target, all_items, ns):
    """在指定命名空间中找最佳匹配物品ID"""
    target_item = target.split(":", 1)[1] if ":" in target else target
    pool = sorted(all_items.get(ns, {}).keys())
    if not pool: return None

    # Level 1: 前缀/子串匹配
    for pid in pool:
        pid_item = pid.split(":", 1)[1] if ":" in pid else pid
        if target_item.lower() in pid_item.lower() or pid_item.lower() in target_item.lower():
            return pid

    # Level 2: 编辑距离 ≤ 3
    best, best_dist = None, 999
    for pid in pool:
        pid_item = pid.split(":", 1)[1] if ":" in pid else pid
        d = _levenshtein(target_item.lower(), pid_item.lower())
        if d < best_dist:
            best_dist = d
            best = pid
    if best_dist <= 3:
        return best

    return None

def auto_fix_item_ids(quest_data, all_items):
    """
    自动修正AI生成的任务书中的无效物品ID。
    返回: (fixed_data, fix_count, unfixable_list)
      - fixed_data: 修正后的 quest_data（原地修改 + deep copy 保护）
      - fix_count: 成功修正的ID数量
      - unfixable_list: 无法修正的ID列表 [{id, location, reason}]
    """
    import copy
    fixed = copy.deepcopy(quest_data)
    fix_count = 0
    unfixable = []

    for ch in fixed.get("chapters", []):
        # 修正章节图标 — 基于任务目标物品
        ch_ns = None
        for qch in ch.get("quests", []):
            for tch in qch.get("tasks", []):
                tg = tch.get("target", "")
                if tg and ":" in tg:
                    ch_ns = tg.split(":", 1)[0]
                    break
            if ch_ns:
                break
        chi = ch.get("icon", "")
        if chi and ":" in chi:
            ns = chi.split(":", 1)[0]
            if not (ns in all_items and chi in all_items[ns]):
                best = _find_best_match(chi, all_items, ns)
                if best:
                    print(f"[FIX] Chapter '{ch.get('title', '?')}' icon: {chi} → {best}")
                    ch["icon"] = best
                    fix_count += 1
                elif ch_ns and ch_ns in all_items and all_items[ch_ns]:
                    ch["icon"] = sorted(all_items[ch_ns].keys())[0]
                    fix_count += 1
        for q in ch.get("quests", []):
            qtitle = q.get("title", "?")
            # 修正任务图标 — 优先用 task 的目标物品
            qi_icon = q.get("icon", "")
            if qi_icon and ":" in qi_icon:
                ns = qi_icon.split(":", 1)[0]
                if not (ns in all_items and qi_icon in all_items[ns]):
                    best = _find_best_match(qi_icon, all_items, ns)
                    if best:
                        print(f"[FIX] Quest '{qtitle}' icon: {qi_icon} → {best}")
                        q["icon"] = best
                        fix_count += 1
                    else:
                        # 回退: 用第一个 task 的 target
                        for tq in q.get("tasks", []):
                            tg = tq.get("target", "")
                            if tg and ":" in tg and tg.split(":", 1)[0] in all_items and tg in all_items[tg.split(":", 1)[0]]:
                                q["icon"] = tg
                                fix_count += 1
                                break
            # 修正 tasks
            for t in q.get("tasks", []):
                target = t.get("target", "")
                if not target or ":" not in target:
                    continue
                ns = target.split(":", 1)[0]
                if ns in all_items and target in all_items[ns]:
                    continue  # 有效
                best = _find_best_match(target, all_items, ns)
                if best:
                    print(f"[FIX] Task '{qtitle}': {target} → {best}")
                    t["target"] = best
                    fix_count += 1
                elif ns == "minecraft" and ns in all_items:
                    # 尝试修正原版物品ID的拼写错误
                    best = _find_best_match(target, all_items, ns)
                    if best:
                        print(f"[FIX] Task '{qtitle}': {target} → {best}")
                        t["target"] = best
                        fix_count += 1
                    else:
                        unfixable.append({"id": target, "location": f"Task in '{qtitle}'", "reason": "Minecraft ID 无法匹配到任何已知物品"})
                elif ns not in all_items:
                    unfixable.append({"id": target, "location": f"Task in '{qtitle}'", "reason": f"Mod '{ns}' 不在已安装的 Mod 列表中，无法验证此 ID"})
                else:
                    unfixable.append({"id": target, "location": f"Task in '{qtitle}'", "reason": f"在 '{ns}' 中找不到相似物品，ID 可能不存在"})

            # 修正 rewards
            for r in q.get("rewards", []):
                target = r.get("target", "")
                if not target or ":" not in target:
                    continue
                ns = target.split(":", 1)[0]
                if ns in all_items and target in all_items[ns]:
                    continue
                best = _find_best_match(target, all_items, ns)
                if best:
                    print(f"[FIX] Reward in '{qtitle}': {target} → {best}")
                    r["target"] = best
                    fix_count += 1
                elif ns == "minecraft" and ns in all_items:
                    best_mc = _find_best_match(target, all_items, ns)
                    if best_mc:
                        print(f"[FIX] Reward in '{qtitle}': {target} → {best_mc}")
                        r["target"] = best_mc
                        fix_count += 1
                    else:
                        unfixable.append({"id": target, "location": f"Reward in '{qtitle}'", "reason": "Minecraft ID 无法匹配到任何已知物品"})
                elif ns not in all_items:
                    unfixable.append({"id": target, "location": f"Reward in '{qtitle}'", "reason": f"Mod '{ns}' 不在已安装的 Mod 列表中，无法验证此 ID"})
                else:
                    unfixable.append({"id": target, "location": f"Reward in '{qtitle}'", "reason": f"在 '{ns}' 中找不到相似物品，ID 可能不存在"})

    return fixed, fix_count, unfixable


def validate_item_ids(quest_data, all_items):
    """
    [已弃用] 仅保留兼容性，实际使用 auto_fix_item_ids()。
    返回: (valid_count, invalid_list)
    """
    invalid = []
    valid = 0
    for ch in quest_data.get("chapters", []):
        for q in ch.get("quests", []):
            for t in q.get("tasks", []):
                target = t.get("target", "")
                if target and ":" in target:
                    ns = target.split(":", 1)[0]
                    if ns in all_items and target in all_items[ns]:
                        valid += 1
                    else:
                        invalid.append({"id": target, "location": f"Task in '{q.get('title', '?')}'", "suggestion": ""})
                elif target:
                    valid += 1
            for r in q.get("rewards", []):
                target = r.get("target", "")
                if target and ":" in target:
                    ns = target.split(":", 1)[0]
                    if ns in all_items and target in all_items[ns]:
                        valid += 1
                    else:
                        invalid.append({"id": target, "location": f"Reward in '{q.get('title', '?')}'", "suggestion": ""})
                elif target:
                    valid += 1
    return valid, invalid


# ════════════════════════════════════════════════════════
# 辅助函数
# ════════════════════════════════════════════════════════

def _id_to_name(raw_id):
    """从item_id猜测可读名称"""
    name = raw_id.replace("_", " ").strip()
    return name.title()


def detect_library_mods(mods, all_items):
    """
    检测无内容的依赖库/辅助 Mod，标记 is_library=True。
    规则: 扫描到的物品数量 ≤ 5 且不在 MOD_DB 核心分类中的 Mod，自动标记为库。
    """
    for m in mods:
        mod_id = m.get("mod_id", "")
        if m.get("parent"):            # 已识别的附属 Mod → 不需要复标记
            m["is_library"] = True
            continue
        cat = m.get("category", "unknown")
        if cat in ("tech", "magic", "world", "mob", "vanilla"):
            m["is_library"] = False    # 核心 Mod → 坚决不是库
            continue
        items = all_items.get(mod_id, {})
        item_count = len(items)
        m["is_library"] = (item_count <= 5)  # 物品数量太少 → 依赖库
    return mods


def build_recipe_chain_hints(all_mods, max_chains_per_mod=5):
    """
    从配方缓存中提取合成链提示，注入 Prompt。
    为每个 Mod 最多提取 max_chains_per_mod 个里程碑物品的合成链。
    """
    # 里程碑关键词（这些物品通常有合成关系，适合做任务）
    MILESTONE_KEYWORDS = [
        "pickaxe", "sword", "axe", "shovel", "hoe", "helmet", "chestplate",
        "leggings", "boots", "furnace", "generator", "press", "crusher",
        "drill", "saw", "gear", "wheel", "plate", "block", "crystal",
        "star", "core", "controller", "machine", "table", "altar",
    ]
    lines = []

    for m in all_mods:
        mod_id = m.get("mod_id", "")
        if not mod_id:
            continue
        mod_outputs = {k: v for k, v in _recipe_inputs_cache.items()
                       if k.startswith(mod_id + ":")}
        if not mod_outputs:
            continue

        # 筛选里程碑物品（包含关键词的优先）
        milestones = []
        for output in sorted(mod_outputs.keys()):
            item_name = output.split(":", 1)[1]
            for kw in MILESTONE_KEYWORDS:
                if kw in item_name.lower():
                    milestones.append(output)
                    break
        # 不够的用前几个补
        if len(milestones) < max_chains_per_mod:
            for output in sorted(mod_outputs.keys()):
                if output not in milestones:
                    milestones.append(output)
                if len(milestones) >= max_chains_per_mod:
                    break
        milestones = milestones[:max_chains_per_mod]

        for out in milestones:
            inputs = mod_outputs[out]
            inputs_str = " + ".join(inputs[:5])
            lines.append(f"  {out} ← {inputs_str}")
            # BFS 回溯一层
            for inp in inputs[:3]:
                if inp in _recipe_inputs_cache:
                    sub = _recipe_inputs_cache[inp]
                    lines.append(f"    └ {inp} ← {' + '.join(sub[:4])}")
                    break  # 每个输入只回溯一层

        if lines and lines[-1] != f"  {mod_id}:":  # 有数据才加标题
            lines.insert(0, f"")
            lines.insert(0, f"📐 {m.get('mod_name', mod_id)} ({mod_id}) 合成路线参考:")

    if not lines:
        return ""

    lines.insert(0, "=== 合成路线参考（请按这些链设计任务）===")
    return "\n".join(lines)


def clear_cache():
    with _cache_lock:
        _item_cache.clear()
        _adv_cache.clear()


def get_cache_stats():
    with _cache_lock:
        return len(_item_cache)