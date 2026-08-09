"""Theme-driven chapter planning.

Human-made quest books organize chapters by gameplay theme (farming, tech,
magic, pets, exploration...) and blend vanilla content with mod content inside
each chapter, instead of dedicating one chapter per mod. This module defines
the fixed theme templates and assigns every selected mod to a theme.
"""

from __future__ import annotations

from typing import Any


THEME_CONFIGS = {
    "light": {"vanilla": 24, "core": 6, "utility": 2, "batch": 6},
    "medium": {"vanilla": 40, "core": 10, "utility": 3, "batch": 8},
    "rich": {"vanilla": 60, "core": 16, "utility": 5, "batch": 8},
    "max": {"vanilla": 80, "core": 24, "utility": 8, "batch": 10},
}

VANILLA_THEME_IDS = (
    "theme_start",
    "theme_food",
    "theme_mining",
    "theme_tech",
    "theme_magic",
    "theme_world",
    "theme_boss",
)
MAX_MODS_PER_CHAPTER = 5


TOPIC_TEMPLATES = [
    {
        "id": "theme_start",
        "title": "新手开局",
        "focus": (
            "原版生存起步：获取原木、制作工作台与基础工具、建庇护所、解决食物。"
            "融入背包、地图、传送、墓碑、照明等实用工具模组，让玩家熟悉整合包的基础玩法。"
        ),
    },
    {
        "id": "theme_food",
        "title": "农业与美食",
        "focus": (
            "原版种植、畜牧与食物为基础，引入农夫乐事、作物、烹饪类模组："
            "从种田、养牛到搭建厨房、制作料理，覆盖该主题模组的入门到进阶玩法。"
        ),
    },
    {
        "id": "theme_mining",
        "title": "矿业与资源",
        "focus": (
            "原版挖矿、熔炼与基础储物为主线，融入矿石、挖掘、存储类模组："
            "从石镐到铁镐、挖矿致富，再到搭建储物柜、抽屉、AE 存储系统。"
        ),
    },
    {
        "id": "theme_tech",
        "title": "科技与自动化",
        "focus": (
            "原版红石、漏斗、矿车为基础，引入科技类模组："
            "从发电机、机器到自动化产线，覆盖能量、物流与生产链的入门到进阶。"
        ),
    },
    {
        "id": "theme_magic",
        "title": "魔法与附魔",
        "focus": (
            "原版附魔、酿造、经验为基础，引入魔法类模组："
            "从附魔台到魔法祭坛、法术研究，覆盖该主题模组的仪式、法杖与进阶魔法。"
        ),
    },
    {
        "id": "theme_pet",
        "title": "养成与伙伴",
        "focus": (
            "以村民、动物互动为基础，引入女仆、宠物、伙伴类模组："
            "从驯服宠物、招募女仆到培养强化伙伴，覆盖养成玩法的完整流程。"
        ),
    },
    {
        "id": "theme_world",
        "title": "探索与维度",
        "focus": (
            "原版下界、末地为起点，引入维度与生态类模组："
            "从寻找传送门、探索新地形到征服新维度，覆盖探险类模组的地图、结构与资源。"
        ),
    },
    {
        "id": "theme_boss",
        "title": "Boss 挑战",
        "focus": (
            "原版凋灵、末影龙为起点，引入生物与 Boss 类模组："
            "从了解怪物生态到挑战强敌、获取战利品，覆盖击杀与成就类玩法。"
        ),
    },
]


def _keyword_hit(mod_id: str, keywords: tuple[str, ...]) -> bool:
    lowered = mod_id.lower()
    return any(keyword in lowered for keyword in keywords)


def assign_mod_to_theme(mod: dict) -> str:
    """Map one mod to a theme id using category plus keyword overrides."""
    mod_id = str(mod.get("mod_id", "") or "").lower()
    category = str(mod.get("category", "unknown") or "unknown").lower()

    # Niche mods (maids, pets) often arrive as "unknown" category.
    if _keyword_hit(mod_id, ("maid", "pet", "companion", "tame", "alexmobs")):
        return "theme_pet"

    if category == "food":
        return "theme_food"
    if category == "magic":
        return "theme_magic"
    if category == "world":
        return "theme_world"
    if category == "mob":
        if _keyword_hit(mod_id, ("lycan", "mowzie", "boss", "wither")):
            return "theme_boss"
        return "theme_pet"
    if category == "tech":
        return "theme_tech"
    if category == "decor":
        return "theme_start"
    if category == "utility":
        if _keyword_hit(
            mod_id,
            ("storage", "chest", "drawer", "refined", "ae2", "functionalstorage"),
        ):
            return "theme_mining"
        return "theme_start"

    # Unknown category: fall back to keyword guesses.
    if _keyword_hit(
        mod_id,
        (
            "farm", "food", "crop", "cook", "delight", "aquacult", "harvest",
            "cookery", "solcarrot", "culinary",
        ),
    ):
        return "theme_food"
    if _keyword_hit(
        mod_id,
        (
            "storage", "chest", "drawer", "refined", "ae2", "advancedae",
            "extendedae", "aeadditions", "toms_storage",
        ),
    ):
        return "theme_mining"
    if _keyword_hit(
        mod_id,
        (
            "spell", "magic", "goety", "arcane", "tarot", "celestial", "thaum",
            "botani", "witch", "sorcer", "ritual", "enchant", "potion",
        ),
    ):
        return "theme_magic"
    if _keyword_hit(
        mod_id,
        (
            "boss", "dragon", "cataclysm", "lycan", "mowzie", "wither",
            "slashblade", "weapon", "maid_weapon",
        ),
    ):
        return "theme_boss"
    if _keyword_hit(
        mod_id,
        (
            "dimension", "world", "explore", "adventure", "aether", "broom",
            "flight", "relic", "artifact",
        ),
    ):
        return "theme_world"
    if mod_id.startswith("_"):
        return "theme_start"
    if _keyword_hit(
        mod_id,
        ("backpack", "map", "compass", "waystone", "torch", "tool"),
    ):
        return "theme_mining"
    return "theme_world"


def build_theme_plan(
    density: str,
    progression_mods: list[dict],
    utility_mods: list[dict],
    unknown_mods: list[dict],
    all_mods: list[dict],
    kubejs_namespaces: set[str] | None = None,
) -> list[dict]:
    """Build theme-based chapters in fixed order, skipping empty themes."""
    config = THEME_CONFIGS.get(density, THEME_CONFIGS["medium"])
    theme_mods: dict[str, list[tuple[dict, int]]] = {
        template["id"]: [] for template in TOPIC_TEMPLATES
    }

    for mod in progression_mods + unknown_mods:
        if not isinstance(mod, dict):
            continue
        mod_id = mod.get("mod_id", "")
        if mod_id == "minecraft":
            continue
        theme_id = assign_mod_to_theme(mod)
        theme_mods.setdefault(theme_id, []).append((mod, config["core"]))
    for mod in utility_mods:
        if not isinstance(mod, dict):
            continue
        mod_id = mod.get("mod_id", "")
        if not mod_id or mod_id == "minecraft":
            continue
        theme_id = assign_mod_to_theme(mod)
        theme_mods.setdefault(theme_id, []).append((mod, config["utility"]))

    vanilla_base, vanilla_extra = divmod(
        config["vanilla"],
        len(VANILLA_THEME_IDS),
    )
    vanilla_targets = {
        theme_id: vanilla_base + (1 if index < vanilla_extra else 0)
        for index, theme_id in enumerate(VANILLA_THEME_IDS)
    }

    plan = []
    for template in TOPIC_TEMPLATES:
        theme_id = template["id"]
        weighted_mods = theme_mods.get(theme_id, [])
        vanilla_target = vanilla_targets.get(theme_id, 0)
        if not weighted_mods and not vanilla_target:
            continue
        chunks = [
            weighted_mods[index:index + MAX_MODS_PER_CHAPTER]
            for index in range(0, len(weighted_mods), MAX_MODS_PER_CHAPTER)
        ] or [[]]
        for chunk_index, chunk in enumerate(chunks):
            mods = [mod for mod, _weight in chunk]
            target = sum(weight for _mod, weight in chunk)
            if chunk_index == 0:
                target += vanilla_target
            names = "、".join(
                mod.get("mod_name", mod.get("mod_id", "")) for mod in mods
            )
            focus = template["focus"]
            if names:
                focus += f"\n本章核心模组：{names}"
            suffix = "" if chunk_index == 0 else f"_{chunk_index + 1}"
            title_suffix = "" if chunk_index == 0 else f" {chunk_index + 1}"
            plan.append({
                "id": theme_id + suffix,
                "title": template["title"] + title_suffix,
                "focus": focus,
                "target": target,
                "mods": mods,
                "namespaces": ["minecraft"] + [
                    mod.get("mod_id", "") for mod in mods if mod.get("mod_id")
                ],
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
