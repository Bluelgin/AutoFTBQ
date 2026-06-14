#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mod Item Scanner — 从JAR文件中提取真实物品ID"""

import os
import re
import json
import zipfile
import threading
from collections import defaultdict

# 缓存 key: (filepath, mtime) → {namespace: {item_id: display_name}}
_item_cache = {}
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

                # ── 5. 从recipes中补充 ──
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
    # 从扫描结果中获取minecraft items
    mc_scanned = all_items.get("minecraft", {})
    mc_combined = set(mc_items_common)
    mc_combined.update(mc_scanned.keys())
    lines.append(f"  minecraft ({len(mc_combined)} items): {', '.join(sorted(mc_combined)[:80])} ...")
    if len(mc_combined) > 80:
        remaining = sorted(mc_combined)[80:]
        lines.append(f"    (more minecraft items): {', '.join(remaining[:60])}")
        if len(remaining) > 60:
            lines.append(f"    ... and {len(remaining)-60} more minecraft items")

    # 各mod的物品
    for ns in sorted(active_ns):
        if ns == "minecraft":
            continue
        items = all_items.get(ns, {})
        if items:
            sample_ids = sorted(items.keys())[:40]
            lines.append(f"\n  {ns} ({len(items)} items):")
            lines.append(f"    {', '.join(sample_ids)}")
            if len(items) > 40:
                lines.append(f"    ... and {len(items)-40} more items in {ns}")
        else:
            lines.append(f"\n  {ns}: (no items scanned from JAR — use commonly known IDs)")

    lines.append("\n【重要】请只使用以上列出的物品ID作为任务target/reward。不要编造不存在的物品ID。")
    lines.append("如果某个Mod的物品ID没有列出，可以推测使用 'modid:item_name' 格式（全小写，下划线分隔）。")
    return "\n".join(lines)


def validate_item_ids(quest_data, all_items):
    """
    校验AI生成的任务书中物品ID是否存在于扫描结果中。
    返回: (valid_count, invalid_list) — invalid_list中每一项为 {id, location, suggestion}
    """
    invalid = []
    valid = 0

    # 检查chapters
    for ch in quest_data.get("chapters", []):
        for q in ch.get("quests", []):
            for t in q.get("tasks", []):
                target = t.get("target", "")
                if target and ":" in target:
                    ns, item = target.split(":", 1)
                    if ns in all_items and target in all_items[ns]:
                        valid += 1
                    elif ns in all_items:
                        # 命名空间存在但物品ID不存在
                        candidates = sorted(all_items[ns].keys())[:10]
                        invalid.append({
                            "id": target,
                            "location": f"Task in quest '{q.get('title', '?')}'",
                            "suggestion": f"Namespace '{ns}' 存在，建议使用: {', '.join(candidates[:5])}"
                        })
                    else:
                        invalid.append({
                            "id": target,
                            "location": f"Task in quest '{q.get('title', '?')}'",
                            "suggestion": f"Namespace '{ns}' 在扫描结果中未找到"
                        })
                elif target:
                    valid += 1  # advancement/dimension等非物品类型的target

            for r in q.get("rewards", []):
                target = r.get("target", "")
                if target and ":" in target:
                    ns, item = target.split(":", 1)
                    if ns in all_items and target in all_items[ns]:
                        valid += 1
                    elif ns in all_items:
                        candidates = sorted(all_items[ns].keys())[:10]
                        invalid.append({
                            "id": target,
                            "location": f"Reward in quest '{q.get('title', '?')}'",
                            "suggestion": f"Namespace '{ns}' 存在，建议使用: {', '.join(candidates[:5])}"
                        })
                    else:
                        invalid.append({
                            "id": target,
                            "location": f"Reward in quest '{q.get('title', '?')}'",
                            "suggestion": f"Namespace '{ns}' 在扫描结果中未找到"
                        })
                elif target:
                    valid += 1  # xp/command等非物品奖励

    return valid, invalid


# ════════════════════════════════════════════════════════
# 辅助函数
# ════════════════════════════════════════════════════════

def _id_to_name(raw_id):
    """从item_id猜测可读名称"""
    name = raw_id.replace("_", " ").strip()
    return name.title()


def clear_cache():
    with _cache_lock:
        _item_cache.clear()


def get_cache_stats():
    with _cache_lock:
        return len(_item_cache)