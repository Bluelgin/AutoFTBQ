"""Deterministic quest quotas, fallback tasks, and chapter layout."""

from __future__ import annotations

from typing import Any


DENSITY_CONFIGS = {
    "light": {"vanilla": 24, "core": 6, "utility": 2, "batch": 6},
    "medium": {"vanilla": 40, "core": 10, "utility": 3, "batch": 8},
    "rich": {"vanilla": 60, "core": 16, "utility": 5, "batch": 8},
    "max": {"vanilla": 80, "core": 24, "utility": 8, "batch": 10},
}

VANILLA_TOPICS = [
    ("vanilla_start", "原版·生存起步", "原木、工作台、石器、食物与庇护所"),
    ("vanilla_iron", "原版·矿业与铁器", "矿洞探索、熔炼、铁器、红石基础"),
    ("vanilla_magic", "原版·钻石与附魔", "钻石装备、附魔、村民与高级生存"),
    ("vanilla_nether", "原版·下界与酿造", "下界探索、烈焰棒、药水与远古残骸"),
    ("vanilla_end", "原版·末地与终局", "末地传送门、末影龙、鞘翅与终局建设"),
]

VANILLA_FALLBACK_ITEMS = [
    ("minecraft:crafting_table", "工作台"),
    ("minecraft:furnace", "熔炉"),
    ("minecraft:iron_ingot", "铁锭"),
    ("minecraft:diamond", "钻石"),
    ("minecraft:enchanting_table", "附魔台"),
    ("minecraft:blaze_rod", "烈焰棒"),
    ("minecraft:ender_eye", "末影之眼"),
    ("minecraft:dragon_breath", "龙息"),
]


def get_quest_primary_item(quest: Any) -> str:
    if not isinstance(quest, dict):
        return ""
    tasks = quest.get("tasks", [])
    if not isinstance(tasks, list):
        return ""
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_type = str(task.get("type", "")).lower()
        if "item" not in task_type:
            continue
        target = task.get("target") or task.get("item", "")
        if isinstance(target, str) and ":" in target:
            return target
    return ""


def build_generation_plan(
    density: str,
    progression_mods: list[dict],
    utility_mods: list[dict],
    unknown_mods: list[dict],
    all_mods: list[dict],
    kubejs_namespaces: set[str] | None = None,
) -> list[dict]:
    """Build chapter-level integer quotas owned by the application."""
    config = DENSITY_CONFIGS.get(density, DENSITY_CONFIGS["medium"])
    topic_count = 4 if density in ("light", "medium") else 5
    topics = VANILLA_TOPICS[:topic_count]
    base, extra = divmod(config["vanilla"], len(topics))
    plan = []

    for index, (chapter_id, title, focus) in enumerate(topics):
        plan.append({
            "id": chapter_id,
            "title": title,
            "focus": focus,
            "target": base + (1 if index < extra else 0),
            "mods": [],
            "namespaces": ["minecraft"],
        })

    for mod in progression_mods + unknown_mods:
        mod_id = mod.get("mod_id", "unknown")
        mod_name = mod.get("mod_name", mod_id)
        plan.append({
            "id": f"mod_{mod_id}",
            "title": mod_name,
            "focus": f"完整覆盖 {mod_name} 从入门到精通的玩法与配方链",
            "target": config["core"],
            "mods": [mod],
            "namespaces": [mod_id],
        })

    for group_index in range(0, len(utility_mods), 5):
        group = utility_mods[group_index:group_index + 5]
        if not group:
            continue
        names = "、".join(mod.get("mod_name", mod.get("mod_id", "")) for mod in group)
        plan.append({
            "id": f"utility_{group_index // 5 + 1}",
            "title": "实用工具与生活" if group_index == 0 else f"实用工具与生活 {group_index // 5 + 1}",
            "focus": f"介绍并实际使用这些辅助模组：{names}",
            "target": max(4, config["utility"] * len(group)),
            "mods": group,
            "namespaces": [mod.get("mod_id", "") for mod in group if mod.get("mod_id")],
        })

    known_namespaces = {mod.get("mod_id", "") for mod in all_mods}
    custom_namespaces = sorted(
        namespace
        for namespace in (kubejs_namespaces or set())
        if namespace not in known_namespaces
    )
    if custom_namespaces:
        plan.append({
            "id": "kubejs_custom",
            "title": "整合包自定义内容",
            "focus": "覆盖 KubeJS 自定义物品、魔改配方和关键生产链",
            "target": config["core"],
            "mods": [
                {"mod_id": namespace, "mod_name": f"KubeJS {namespace}"}
                for namespace in custom_namespaces
            ],
            "namespaces": custom_namespaces,
        })

    for chapter in plan:
        chapter["batch_size"] = config["batch"]
    return plan


def deduplicate_stage_quests(quests: list[dict], existing_titles=None) -> list[dict]:
    seen_titles = {
        str(title).strip().lower()
        for title in (existing_titles or [])
        if str(title).strip()
    }
    seen_targets = set()
    unique = []
    for quest in quests:
        if not isinstance(quest, dict):
            continue
        title = str(quest.get("title", "")).strip()
        if not title or title.lower() in seen_titles:
            continue
        primary_item = get_quest_primary_item(quest)
        key = (title.lower(), primary_item)
        if key in seen_targets:
            continue
        seen_titles.add(title.lower())
        seen_targets.add(key)
        unique.append(quest)
    return unique


def build_fallback_quests(
    chapter: dict,
    count: int,
    existing_quests: list[dict],
    all_items: dict,
) -> list[dict]:
    """Fill model shortfalls from scanned IDs, then deterministic checkmarks."""
    existing_titles = {
        str(quest.get("title", "")).lower()
        for quest in existing_quests
        if isinstance(quest, dict)
    }
    existing_items = {get_quest_primary_item(quest) for quest in existing_quests}
    candidates = []
    namespaces = chapter.get("namespaces", [])
    for namespace in namespaces:
        namespace_items = all_items.get(namespace, {})
        if isinstance(namespace_items, dict):
            candidates.extend(sorted(namespace_items.items()))
    if "minecraft" in namespaces:
        candidates.extend(VANILLA_FALLBACK_ITEMS)

    result = []
    for item_id, display_name in candidates:
        if len(result) >= count:
            break
        if item_id in existing_items:
            continue
        title = f"实践·获取{display_name}"
        if title.lower() in existing_titles:
            continue
        result.append({
            "title": title,
            "subtitle": f"获取并了解 {display_name} 的用途",
            "tasks": [{"type": "item", "target": item_id, "count": 1}],
            "rewards": [{"type": "xp", "count": 10}],
        })
        existing_items.add(item_id)
        existing_titles.add(title.lower())

    while len(result) < count:
        number = len(existing_quests) + len(result) + 1
        result.append({
            "title": f"实践·{chapter['title']}阶段总结 {number}",
            "subtitle": "确认已经理解并完成本阶段的关键玩法",
            "tasks": [{"type": "checkmark"}],
            "rewards": [{"type": "xp", "count": 10}],
        })
    return result


def normalize_chapter_quests(chapter_id: str, quests: list[dict]) -> list[dict]:
    """Own IDs, dependencies, and coordinates after model batches merge."""
    normalized = []
    main_ids = []
    branches = []
    for original in quests:
        if not isinstance(original, dict):
            continue
        quest = dict(original)
        quest_id = f"{chapter_id}_q_{len(normalized) + 1:03d}"
        quest["id"] = quest_id
        title = str(quest.get("title", ""))
        shape = str(quest.get("shape", "")).lower()
        is_branch = (
            "支线" in title
            or "branch" in title.lower()
            or shape in ("diamond", "circle", "hexagon")
        )
        quest.pop("dependencies", None)
        if is_branch:
            branches.append(quest)
        else:
            if main_ids:
                quest["dependencies"] = [main_ids[-1]]
            quest["x"] = float(len(main_ids) * 2)
            quest["y"] = 0.0
            quest["shape"] = "square"
            main_ids.append(quest_id)
        normalized.append(quest)

    if not main_ids:
        for index, quest in enumerate(normalized):
            quest["x"] = float(index * 2)
            quest["y"] = 0.0
            quest["shape"] = "square"
            if index:
                quest["dependencies"] = [normalized[index - 1]["id"]]
        return normalized

    for branch_index, quest in enumerate(branches):
        anchor_index = min(branch_index, len(main_ids) - 1)
        quest["dependencies"] = [main_ids[anchor_index]]
        quest["x"] = float(anchor_index * 2)
        level = branch_index // max(1, len(main_ids)) + 1
        quest["y"] = float((-1 if branch_index % 2 == 0 else 1) * 2 * level)
        quest["shape"] = "diamond"
    return normalized
