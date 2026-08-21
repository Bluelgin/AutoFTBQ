"""Deterministic quest quotas, fallback tasks, and chapter layout."""

from __future__ import annotations

import math
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
    """Build theme-driven chapters in fixed order, skipping empty themes."""
    try:
        from quest_themes import build_theme_plan
    except ImportError:
        from .quest_themes import build_theme_plan
    return build_theme_plan(
        density,
        progression_mods,
        utility_mods,
        unknown_mods,
        all_mods,
        kubejs_namespaces,
    )



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
    """Fill model shortfalls only from unique scanned IDs with real evidence."""
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
            "description": [
                f"找到或制作 {display_name}，并确认它在当前玩法阶段中的用途。",
                "这个目标来自整合包实际扫描到的物品，而不是临时填充内容。",
            ],
            "tasks": [{"type": "item", "target": item_id, "count": 1}],
            "rewards": [{"type": "xp", "count": 10}],
        })
        existing_items.add(item_id)
        existing_titles.add(title.lower())

    return result


def _task_types(quest: dict) -> set[str]:
    result = set()
    for task in quest.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_type = str(task.get("type", "")).lower().split(":", 1)[-1]
        if task_type:
            result.add(task_type)
    return result


def _primary_namespace(quest: dict) -> str:
    for task in quest.get("tasks", []):
        if not isinstance(task, dict):
            continue
        target = (
            task.get("target")
            or task.get("item")
            or task.get("entity")
            or task.get("advancement")
            or ""
        )
        if isinstance(target, dict):
            target = target.get("id", "")
        if isinstance(target, str) and ":" in target:
            return target.split(":", 1)[0].lower()
    return ""


def _is_summary_quest(quest: dict) -> bool:
    title = str(quest.get("title", "")).lower()
    keywords = (
        "总结", "里程碑", "完成本章", "最终", "终章",
        "summary", "milestone", "chapter complete", "finale",
    )
    return bool(_task_types(quest) <= {"checkmark"}) and any(
        keyword in title for keyword in keywords
    )


def _is_info_quest(quest: dict) -> bool:
    task_types = _task_types(quest)
    if task_types and not task_types <= {"checkmark"}:
        return False
    title = str(quest.get("title", "")).lower()
    shape = str(quest.get("shape", "")).lower()
    info_keywords = (
        "说明", "提示", "指南", "须知", "介绍", "关于", "欢迎",
        "guide", "info", "note", "tips", "read me", "welcome",
    )
    return shape == "gear" or any(keyword in title for keyword in info_keywords)


def _is_boss_quest(chapter_id: str, quest: dict) -> bool:
    title = str(quest.get("title", "")).lower()
    if any(keyword in title for keyword in ("boss", "首领", "领主", "最终战")):
        return True
    return chapter_id.startswith("theme_boss") and "kill" in _task_types(quest)


def _split_layout_groups(quests: list[dict]) -> list[list[dict]]:
    """Keep related namespaces together without creating oversized clusters."""
    groups: list[list[dict]] = []
    current: list[dict] = []
    group_namespace = ""
    for quest in quests:
        namespace = _primary_namespace(quest)
        namespace_changed = (
            len(current) >= 4
            and namespace
            and group_namespace
            and namespace != group_namespace
        )
        if current and (len(current) >= 6 or namespace_changed):
            groups.append(current)
            current = []
            group_namespace = ""
        current.append(quest)
        if namespace and namespace != "minecraft" and not group_namespace:
            group_namespace = namespace
        elif namespace and not group_namespace:
            group_namespace = namespace
    if current:
        groups.append(current)
    return groups


def _split_snowflake_arms(quests: list[dict]) -> list[list[dict]]:
    """Build up to six balanced arms while keeping namespace order intact."""
    namespace_buckets: dict[str, list[dict]] = {}
    for quest in quests:
        namespace = _primary_namespace(quest) or "__general__"
        namespace_buckets.setdefault(namespace, []).append(quest)
    arms = list(namespace_buckets.values())

    while len(arms) > 6:
        smallest_index = min(range(len(arms)), key=lambda index: len(arms[index]))
        smallest = arms.pop(smallest_index)
        target_index = min(range(len(arms)), key=lambda index: len(arms[index]))
        arms[target_index].extend(smallest)

    desired = min(6, max(3, math.ceil(len(quests) / 18))) if quests else 0
    while len(arms) < desired:
        largest_index = max(range(len(arms)), key=lambda index: len(arms[index]))
        largest = arms[largest_index]
        if len(largest) < 4:
            break
        midpoint = math.ceil(len(largest) / 2)
        arms[largest_index:largest_index + 1] = [largest[:midpoint], largest[midpoint:]]
    return arms


def normalize_chapter_quests(chapter_id: str, quests: list[dict]) -> list[dict]:
    """Build a compact semantic graph after independently generated batches merge."""
    normalized: list[dict] = []
    for original in quests:
        if not isinstance(original, dict):
            continue
        quest = dict(original)
        for key in [key for key in quest if key.startswith("_layout_")]:
            quest.pop(key, None)
        quest_id = f"{chapter_id}_q_{len(normalized) + 1:03d}"
        quest["id"] = quest_id
        quest["dependencies"] = []
        quest["x"] = 0.0
        quest["y"] = 0.0
        normalized.append(quest)

    if not normalized:
        return normalized

    summary_candidates = [quest for quest in normalized if _is_summary_quest(quest)]
    milestone = summary_candidates[-1] if summary_candidates else None
    info_quests = [
        quest for quest in normalized
        if _is_info_quest(quest) and quest is not milestone
    ]
    content_quests = [
        quest for quest in normalized
        if quest not in info_quests and quest is not milestone
    ]

    # A fallback-only chapter still needs a connected progression.
    if not content_quests:
        content_quests = list(normalized)
        info_quests = []
        milestone = None

    try:
        from quest_layout import layout_style_for_chapter
    except ImportError:
        from .quest_layout import layout_style_for_chapter
    style = layout_style_for_chapter(chapter_id, len(normalized))

    if style == "snowflake":
        hub = content_quests[0]
        hub["dependencies"] = []
        hub["_layout_group"] = -1
        hub["_layout_arm"] = -1
        hub["_layout_order"] = 0
        hub["_layout_role"] = "hub"
        hub["shape"] = "hexagon"

        arms = _split_snowflake_arms(content_quests[1:])
        arm_endpoints: list[str] = []
        for arm_index, arm in enumerate(arms):
            previous_main = hub["id"]
            for arm_order, quest in enumerate(arm):
                step, position = divmod(arm_order, 3)
                if position == 0:
                    role = "main"
                    dependencies = [previous_main]
                    previous_main = quest["id"]
                    side = 0
                else:
                    role = "branch"
                    dependencies = [previous_main]
                    side = -1 if position == 1 else 1
                quest["dependencies"] = dependencies
                quest["_layout_group"] = arm_index
                quest["_layout_arm"] = arm_index
                quest["_layout_order"] = arm_order
                quest["_layout_step"] = step
                quest["_layout_side"] = side
                quest["_layout_role"] = role
                quest["shape"] = "square" if role == "main" else "diamond"
            arm_endpoints.append(previous_main)

        for index, quest in enumerate(info_quests):
            quest["dependencies"] = []
            quest["_layout_role"] = "info"
            quest["_layout_order"] = index
            quest["shape"] = "gear"

        if milestone is not None:
            target_arm = max(range(len(arms)), key=lambda index: len(arms[index])) if arms else 0
            endpoint = arm_endpoints[target_arm] if arm_endpoints else hub["id"]
            milestone["dependencies"] = [endpoint]
            milestone["_layout_group"] = target_arm
            milestone["_layout_arm"] = target_arm
            milestone["_layout_step"] = math.ceil(len(arms[target_arm]) / 3) if arms else 1
            milestone["_layout_side"] = 0
            milestone["_layout_role"] = "milestone"
            milestone["_layout_order"] = len(normalized)
            milestone["shape"] = "hexagon"
        return normalized

    groups = _split_layout_groups(content_quests)
    group_exits: list[str] = []
    group_roots: list[str] = []

    for group_index, group in enumerate(groups):
        if group_index == 0:
            parent_id = None
        elif style == "tree":
            parent_id = group_exits[(group_index - 1) // 2]
        else:
            columns = 4
            parent_id = (
                group_roots[-1]
                if group_index % columns == 0
                else group_exits[-1]
            )

        main_candidates: list[str] = []
        for local_index, quest in enumerate(group):
            explicit_branch = (
                "支线" in str(quest.get("title", ""))
                or "branch" in str(quest.get("title", "")).lower()
                or str(quest.get("shape", "")).lower() in ("diamond", "circle")
            )
            role = "main" if local_index in (0, 1, 3) and not explicit_branch else "branch"
            if _is_boss_quest(chapter_id, quest):
                role = "boss"

            if local_index == 0:
                dependencies = [parent_id] if parent_id else []
            elif local_index in (1, 2):
                dependencies = [group[0]["id"]]
            elif local_index == 3:
                dependencies = [group[1]["id"]]
            elif local_index == 4:
                dependencies = [group[1]["id"]]
            else:
                dependencies = [group[min(3, local_index - 1)]["id"]]

            quest["dependencies"] = dependencies
            quest["_layout_group"] = group_index
            quest["_layout_order"] = local_index
            quest["_layout_role"] = role
            quest["shape"] = {
                "main": "square",
                "branch": "diamond" if local_index % 2 == 0 else "circle",
                "boss": "hexagon",
            }[role]
            if role in ("main", "boss"):
                main_candidates.append(quest["id"])
        if style == "tree":
            # The final node is the visual tip of a Boss branch; continuing
            # from an earlier side node can cut straight across the cluster.
            group_exits.append(group[-1]["id"])
        else:
            group_exits.append(main_candidates[-1] if main_candidates else group[-1]["id"])
        group_roots.append(group[0]["id"])

    for index, quest in enumerate(info_quests):
        quest["dependencies"] = []
        quest["_layout_role"] = "info"
        quest["_layout_order"] = index
        quest["shape"] = "gear"

    if milestone is not None:
        milestone["dependencies"] = [group_exits[-1]] if group_exits else []
        milestone["_layout_role"] = "milestone"
        milestone["_layout_order"] = len(normalized)
        milestone["shape"] = "hexagon"

    return normalized
