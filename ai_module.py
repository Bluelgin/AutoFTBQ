#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AutoFTBQ AI模块 — FTB Quests SNBT生成 v4"""

import os, re, json, uuid
import requests

try:
    from . import mod_scanner as _ms
except ImportError:
    import mod_scanner as _ms

try:
    from . import ollama_adapter as _oa
except ImportError:
    import ollama_adapter as _oa

try:
    from . import modrinth_client as _mrc
except ImportError:
    import modrinth_client as _mrc

try:
    from .ai_clients import (
        API_TIMEOUT,
        DEEPSEEK_API_URL,
        DEEPSEEK_MODEL,
        DeepSeekClient,
        GenericOpenAIClient,
        create_chat_client,
    )
    from .ai_providers import (
        CUSTOM_PROVIDER,
        PROVIDER_PRESETS,
        derive_models_url,
        fetch_provider_models,
        normalize_provider,
    )
    from .quest_schema import QuestValidationError, extract_quest_batch, normalize_quest_book
    from .quest_writer import write_quest_book
except ImportError:
    from ai_clients import (
        API_TIMEOUT,
        DEEPSEEK_API_URL,
        DEEPSEEK_MODEL,
        DeepSeekClient,
        GenericOpenAIClient,
        create_chat_client,
    )
    from ai_providers import (
        CUSTOM_PROVIDER,
        PROVIDER_PRESETS,
        derive_models_url,
        fetch_provider_models,
        normalize_provider,
    )
    from quest_schema import QuestValidationError, extract_quest_batch, normalize_quest_book
    from quest_writer import write_quest_book

OUTPUT_DIR_NAME = "questbook_output"

# ════════════════════════════════════════════════════════
class _D(float):
    def __repr__(self): return f"{super().__repr__()}d"
class _L(int):
    def __repr__(self): return f"{super().__repr__()}L"
class _B(int):
    def __repr__(self): return f"{super().__repr__()}b"
class _F(float):
    def __repr__(self): return f"{super().__repr__()}f"

def _snbt_value(val, indent=4, level=0):
    if val is None: return "null"
    if isinstance(val, bool): return "true" if val else "false"
    if isinstance(val, (_D,_L,_B,_F)): return repr(val)
    if isinstance(val, float):
        s = str(val)
        if '.' not in s: s += '.0'
        return s + 'd'
    if isinstance(val, int): return str(val)
    if isinstance(val, str): return '"'+val.replace("\\","\\\\").replace('"','\\"')+'"'
    if isinstance(val, list): return _snbt_list(val, indent, level)
    if isinstance(val, dict): return _snbt_dict(val, indent, level)
    return str(val)

def _snbt_list(lst, indent=4, level=0):
    if not lst: return "[]"
    pad = " "*indent*level; inner = " "*indent*(level+1)
    items = [f"{inner}{_snbt_value(v, indent, level+1)}" for v in lst]
    return "[\n"+"\n".join(items)+"\n"+pad+"]"

def _snbt_dict(dct, indent=4, level=0):
    if not dct: return "{}"
    pad = " "*indent*level; inner = " "*indent*(level+1)
    lines = [f"{inner}{k}: {_snbt_value(v, indent, level+1)}" for k,v in dct.items()]
    return "{\n"+"\n".join(lines)+"\n"+pad+"}"

def to_snbt(obj):
    if isinstance(obj, dict): return _snbt_dict(obj)
    if isinstance(obj, list): return _snbt_list(obj)
    return _snbt_value(obj)

# ════════════════════════════════════════════════════════
# MOD_DB: key → {name, modid, category, parent?}
# parent=None 表示核心 Mod；parent="xxx" 表示是 xxx 的附属 Mod
MOD_DB = {
    "minecraft": {"name":"Minecraft","modid":"minecraft","category":"vanilla"},
    "tconstruct": {"name":"Tinkers Construct","modid":"tconstruct","category":"tech"},
    "botania": {"name":"Botania","modid":"botania","category":"magic"},
    "thaumcraft": {"name":"Thaumcraft","modid":"thaumcraft","category":"magic"},
    "twilightforest": {"name":"Twilight Forest","modid":"twilightforest","category":"world"},
    "twilight": {"name":"Twilight Forest","modid":"twilightforest","category":"world"},
    "betweenlands": {"name":"The Betweenlands","modid":"thebetweenlands","category":"world"},
    "abyssalcraft": {"name":"AbyssalCraft","modid":"abyssalcraft","category":"world"},
    "iceandfire": {"name":"Ice and Fire","modid":"iceandfire","category":"world"},
    "lycanitesmobs": {"name":"Lycanites Mobs","modid":"lycanitesmobs","category":"mob"},
    "mowziesmobs": {"name":"Mowzies Mobs","modid":"mowziesmobs","category":"mob"},
    "aether": {"name":"The Aether","modid":"aether","category":"world"},
    "galacticraft": {"name":"Galacticraft","modid":"galacticraft","category":"tech"},
    "mekanism": {"name":"Mekanism","modid":"mekanism","category":"tech"},
    "draconicevolution": {"name":"Draconic Evolution","modid":"draconicevolution","category":"tech"},
    "astralsorcery": {"name":"Astral Sorcery","modid":"astralsorcery","category":"magic"},
    "bloodmagic": {"name":"Blood Magic","modid":"bloodmagic","category":"magic"},
    "bewitchment": {"name":"Bewitchment","modid":"bewitchment","category":"magic"},
    "arsnouveau": {"name":"Ars Nouveau","modid":"arsnouveau","category":"magic"},
    "ars": {"name":"Ars Nouveau","modid":"arsnouveau","category":"magic"},
    "roots": {"name":"Roots","modid":"roots","category":"magic"},
    "embers": {"name":"Embers","modid":"embers","category":"tech"},
    "naturesaura": {"name":"Natures Aura","modid":"naturesaura","category":"magic"},
    "psi": {"name":"Psi","modid":"psi","category":"magic"},
    "apotheosis": {"name":"Apotheosis","modid":"apotheosis","category":"magic"},
    "create": {"name":"Create","modid":"create","category":"tech"},
    "immersiveengineering": {"name":"Immersive Engineering","modid":"immersiveengineering","category":"tech"},
    "immersive": {"name":"Immersive Engineering","modid":"immersiveengineering","category":"tech"},
    "thermalexpansion": {"name":"Thermal Expansion","modid":"thermalexpansion","category":"tech"},
    "thermal": {"name":"Thermal Series","modid":"thermal","category":"tech"},
    "enderio": {"name":"Ender IO","modid":"enderio","category":"tech"},
    "rftools": {"name":"RFTools","modid":"rftools","category":"tech"},
    "mysticalagriculture": {"name":"Mystical Agriculture","modid":"mysticalagriculture","category":"magic"},
    "mysticalag": {"name":"Mystical Agriculture","modid":"mysticalagriculture","category":"magic"},
    "jei": {"name":"Just Enough Items","modid":"jei","category":"utility"},
    "nei": {"name":"Not Enough Items","modid":"nei","category":"utility"},
    "journeymap": {"name":"JourneyMap","modid":"journeymap","category":"utility"},
    "xaerominimap": {"name":"Xaeros Minimap","modid":"xaerominimap","category":"utility"},
    "xaero": {"name":"Xaeros Minimap","modid":"xaerominimap","category":"utility"},
    "waystones": {"name":"Waystones","modid":"waystones","category":"utility"},
    "ironchest": {"name":"Iron Chests","modid":"ironchest","category":"utility"},
    "ironchests": {"name":"Iron Chests","modid":"ironchest","category":"utility"},
    "storagedrawers": {"name":"Storage Drawers","modid":"storagedrawers","category":"utility"},
    "sophisticatedbackpacks": {"name":"Sophisticated Backpacks","modid":"sophisticatedbackpacks","category":"utility"},
    "refinedstorage": {"name":"Refined Storage","modid":"refinedstorage","category":"utility"},
    "appliedenergistics": {"name":"Applied Energistics 2","modid":"appliedenergistics2","category":"tech"},
    "appliedenergistics2": {"name":"Applied Energistics 2","modid":"appliedenergistics2","category":"utility"},
    "ae2": {"name":"Applied Energistics 2","modid":"appliedenergistics2","category":"utility"},
    "cyclic": {"name":"Cyclic","modid":"cyclic","category":"utility"},
    "quark": {"name":"Quark","modid":"quark","category":"utility"},
    "randomthings": {"name":"Random Things","modid":"randomthings","category":"utility"},
    "openblocks": {"name":"OpenBlocks","modid":"openblocks","category":"utility"},
    "farmersdelight": {"name":"Farmers Delight","modid":"farmersdelight","category":"food"},
    "harvestcraft": {"name":"Pams HarvestCraft","modid":"harvestcraft","category":"food"},
    "pamsharvestcraft": {"name":"Pams HarvestCraft","modid":"harvestcraft","category":"food"},
    "chisel": {"name":"Chisel","modid":"chisel","category":"decor"},
    "chiselsandbits": {"name":"Chisels & Bits","modid":"chiselsandbits","category":"decor"},
    "biomesoplenty": {"name":"Biomes O Plenty","modid":"biomesoplenty","category":"world"},
    "bop": {"name":"Biomes O Plenty","modid":"biomesoplenty","category":"world"},
    "industrialcraft": {"name":"IndustrialCraft 2","modid":"ic2","category":"tech"},
    "ic2": {"name":"IndustrialCraft 2","modid":"ic2","category":"tech"},
    "buildcraft": {"name":"BuildCraft","modid":"buildcraft","category":"tech"},
    "forestry": {"name":"Forestry","modid":"forestry","category":"tech"},
    "railcraft": {"name":"Railcraft","modid":"railcraft","category":"tech"},
    "stevescarts": {"name":"Steves Carts","modid":"stevescarts","category":"tech"},
    "actuallyadditions": {"name":"Actually Additions","modid":"actuallyadditions","category":"tech"},
    "extrautils": {"name":"Extra Utilities 2","modid":"extrautils2","category":"tech"},
    "extrautilities": {"name":"Extra Utilities 2","modid":"extrautils2","category":"tech"},
    "bigreactors": {"name":"Big Reactors","modid":"bigreactors","category":"tech"},
    "extreme": {"name":"Extreme Reactors","modid":"bigreactors","category":"tech"},
    "nuclearcraft": {"name":"NuclearCraft","modid":"nuclearcraft","category":"tech"},
    "rftoolsdimensions": {"name":"RFTools Dimensions","modid":"rftoolsdim","category":"tech"},
    "environmentaltech": {"name":"Environmental Tech","modid":"environmentaltech","category":"tech"},
    "solarflux": {"name":"Solar Flux Reborn","modid":"solarflux","category":"tech"},
    "fluxnetworks": {"name":"Flux Networks","modid":"fluxnetworks","category":"tech"},
    "projecte": {"name":"ProjectE","modid":"projecte","category":"tech"},
    "equivalentexchange": {"name":"ProjectE","modid":"projecte","category":"tech"},
    "electroblob": {"name":"Electroblobs Wizardry","modid":"ebwizardry","category":"magic"},
    "ebwizardry": {"name":"Electroblobs Wizardry","modid":"ebwizardry","category":"magic"},
    "mahoutsukai": {"name":"Mahou Tsukai","modid":"mahoutsukai","category":"magic"},
    "manametal": {"name":"ManaMetal","modid":"manametal","category":"magic"},
    "witchery": {"name":"Witchery","modid":"witchery","category":"magic"},
    "gravestone": {"name":"GraveStone Mod","modid":"gravestone","category":"utility"},
    "tombstone": {"name":"Corail Tombstone","modid":"tombstone","category":"utility"},
    "corail": {"name":"Corail Tombstone","modid":"tombstone","category":"utility"},
    # === 1.3.0 新增 ===
    "appliedenergistics2": {"name":"Applied Energistics 2","modid":"appliedenergistics2","category":"tech"},
    "extendedcrafting": {"name":"Extended Crafting","modid":"extendedcrafting","category":"tech"},
    "enderstorage": {"name":"Ender Storage","modid":"enderstorage","category":"tech"},
    "powah": {"name":"Powah!","modid":"powah","category":"tech"},
    "scannable": {"name":"Scannable","modid":"scannable","category":"tech"},
    "simplyjetpacks": {"name":"Simply Jetpacks","modid":"simplyjetpacks","category":"tech"},
    "xnet": {"name":"XNet","modid":"xnet","category":"tech"},
    "mobgrindingutils": {"name":"Mob Grinding Utils","modid":"mobgrindingutils","category":"tech"},
    "mininggadgets": {"name":"Mining Gadgets","modid":"mininggadgets","category":"tech"},
    "laserio": {"name":"LaserIO","modid":"laserio","category":"tech"},
    "occultism": {"name":"Occultism","modid":"occultism","category":"magic"},
    "ironspells": {"name":"Iron Spells n Spellbooks","modid":"irons_spellbooks","category":"magic"},
    "eidolon": {"name":"Eidolon","modid":"eidolon","category":"magic"},
    "elementalcraft": {"name":"ElementalCraft","modid":"elementalcraft","category":"magic"},
    "hexerei": {"name":"Hexerei","modid":"hexerei","category":"magic"},
    "malum": {"name":"Malum","modid":"malum","category":"magic"},
    "reliquary": {"name":"Reliquary","modid":"xreliquary","category":"magic"},
    "blue_skies": {"name":"Blue Skies","modid":"blue_skies","category":"world"},
    "undergarden": {"name":"The Undergarden","modid":"undergarden","category":"world"},
    "betterend": {"name":"BetterEnd","modid":"betterend","category":"world"},
    "betternether": {"name":"Better Nether","modid":"betternether","category":"world"},
    "deeperdarker": {"name":"Deeper and Darker","modid":"deeperdarker","category":"world"},
    "alexmobs": {"name":"Alexs Mobs","modid":"alexsmobs","category":"mob"},
    "aquaculture": {"name":"Aquaculture 2","modid":"aquaculture","category":"food"},
    "cookingforblockheads": {"name":"Cooking for Blockheads","modid":"cookingforblockheads","category":"food"},
    "croptopia": {"name":"Croptopia","modid":"croptopia","category":"food"},
    "supplementaries": {"name":"Supplementaries","modid":"supplementaries","category":"decor"},
    "backpacked": {"name":"Backpacked","modid":"backpacked","category":"utility"},
    "functionalstorage": {"name":"Functional Storage","modid":"functionalstorage","category":"utility"},
    "pneumaticcraft": {"name":"PneumaticCraft","modid":"pneumaticcraft","category":"tech"},
    "advancedperipherals": {"name":"Advanced Peripherals","modid":"advancedperipherals","category":"tech"},
    "computercraft": {"name":"ComputerCraft","modid":"computercraft","category":"tech"},
    "silentgear": {"name":"Silent Gear","modid":"silentgear","category":"tech"},
    "spartanweaponry": {"name":"Spartan Weaponry","modid":"spartanweaponry","category":"tech"},
    "securitycraft": {"name":"Security Craft","modid":"securitycraft","category":"tech"},
    "compactmachines": {"name":"Compact Machines","modid":"compactmachines","category":"tech"},
    "easyvillagers": {"name":"Easy Villagers","modid":"easyvillagers","category":"utility"},
    "torchmaster": {"name":"Torchmaster","modid":"torchmaster","category":"utility"},
    "crafttweaker": {"name":"CraftTweaker","modid":"crafttweaker","category":"utility"},
    "kubejs": {"name":"KubeJS","modid":"kubejs","category":"utility"},
    "patchouli": {"name":"Patchouli","modid":"patchouli","category":"utility"},
    "jade": {"name":"Jade","modid":"jade","category":"utility"},
    "curios": {"name":"Curios API","modid":"curios","category":"utility"},
    "ftbchunks": {"name":"FTB Chunks","modid":"ftbchunks","category":"utility"},
    "ftbquests": {"name":"FTB Quests","modid":"ftbquests","category":"utility"},
}

# 附属 Mod 关系数据库：addon_modid → parent_modid
# 这些 Mod 本身没有独立玩法，必须依附父 Mod 存在
ADDON_PARENTS = {
    # Mekanism 附属
    "mekanismgenerators": "mekanism",
    "mekanismtools": "mekanism",
    "mekanismadditions": "mekanism",
    # Create 附属
    "createstuffadditions": "create",
    "createcafe": "create",
    "createdeco": "create",
    "createbigcannons": "create",
    # Tinkers 附属
    "tinkerstoolleveling": "tconstruct",
    "constructsarmory": "tconstruct",
    "tinkersplanner": "tconstruct",
    # IC2 附属
    "advancedmachines": "ic2",
    "compactsolars": "ic2",
    "gravisuite": "ic2",
    "ic2nuclearcrafting": "ic2",
    # Thaumcraft 附属
    "thaumictinkerer": "thaumcraft",
    "forbiddenmagic": "thaumcraft",
    "thaumicenergistics": "thaumcraft",
    "thaumicbases": "thaumcraft",
    "thaumicrestoration": "thaumcraft",
    "thaumicaugmentation": "thaumcraft",
    "thaumicwonders": "thaumcraft",
    # Thermal 附属
    "thermaldynamics": "thermal",
    "thermalinnovation": "thermal",
    "thermalintegration": "thermal",
    "thermallogistics": "thermal",
    # Immersive Engineering 附属
    "immersivepetroleum": "immersiveengineering",
    "immersivetech": "immersiveengineering",
    # Botania 附属
    "extrabotany": "botania",
    "mythicbotany": "botania",
    # BloodMagic 附属
    "bloodarsenal": "bloodmagic",
    "sanguisscientia": "bloodmagic",
    # AE2 附属
    "ae2wtlib": "appliedenergistics2",
    "appliedmekanistics": "appliedenergistics2",
    "ae2things": "appliedenergistics2",
    # BuildCraft 附属
    "buildcraft robotics": "buildcraft",
    "buildcraftcompat": "buildcraft",
    # Forestry 附属
    "gendustry": "forestry",
    "binnie": "forestry",
    "magicbees": "forestry",
    "extrabees": "forestry",
    # Ars Nouveau 附属
    "toomanyglyphs": "arsnouveau",
    "arscreo": "arsnouveau",
    "arsnouveauperipherals": "arsnouveau",
    # Create 附属（更多）
    "vintageimprovements": "create",
    "createaddition": "create",
    "createenchantmentindustry": "create",
    "creategarnished": "create",
    "createnuclear": "create",
    "createoreexcavation": "create",
    "createsteamnrails": "create",
    # Refined Storage 附属
    "refinedstorageaddons": "refinedstorage",
    "rebornstorage": "refinedstorage",
    "rsinfinitybooster": "refinedstorage",
    # RFTools 附属
    "rftoolsbase": "rftools",
    "rftoolsbuilder": "rftools",
    "rftoolscontrol": "rftools",
    "rftoolspower": "rftools",
    "rftoolsstorage": "rftools",
    "rftoolsutility": "rftools",
    # Actually Additions 附属
    "actuallybaubles": "actuallyadditions",
    # Psi 附属
    "rpsideas": "psi",
    "psionicupgrades": "psi",
    "psipherals": "psi",
    # AstralSocery 附属
    "astralsorceryperipherals": "astralsorcery",
    # Galacticraft 附属
    "extraplanets": "galacticraft",
    "galacticraftplanets": "galacticraft",
    "zollern": "galacticraft",
    "moreplanets": "galacticraft",
    # Twilight Forest 附属
    "twilightforesttweaks": "twilightforest",
    # Betweenlands 附属
    "betweenlandsaddons": "thebetweenlands",
    # Aether 附属
    "aetherii": "aether",
    "deepaether": "aether",
    "aetherredux": "aether",
    "aetherlostcontent": "aether",
    # Ice and Fire 附属
    "spartanfire": "iceandfire",
    "iafgraves": "iceandfire",
    # Embers 附属
    "soot": "embers",
    "aetherworks": "embers",
    # Roots 附属
    "rootclassic": "roots",
    # Quark 附属
    "quarkoddities": "quark",
    # IronChests 附属
    "ironbackpacks": "ironchest",
    # Sophisticated 系列
    "sophisticatedcore": "sophisticatedbackpacks",
    "sophisticatedstorage": "sophisticatedbackpacks",
    # 兼容层（没有独立玩法，不生成章节）
    "tinkersmekanism": "tconstruct",
    "thaumcraftmekanism": "thaumcraft",
    "thaumicjei": "thaumcraft",
    "thaumcraftinventoryscanning": "thaumcraft",
    "tinker_io": "tconstruct",
    "tinkerores": "tconstruct",
}

CAT_LABEL = {"vanilla":"原版","tech":"科技","magic":"魔法","world":"维度/Boss","mob":"生物","utility":"辅助","food":"食物","decor":"装饰","unknown":"未知"}

def _resolve_mod_category(mod_id):
    """两级管道：MOD_DB → Modrinth API（带缓存）"""
    if not mod_id:
        return None
    for info in MOD_DB.values():
        if info["modid"] == mod_id:
            return info["category"]
    try:
        import modrinth_client as _mrc2
        cat = _mrc2.fetch_modrinth_category(mod_id)
        if cat:
            return cat
    except Exception:
        pass
    return None

# 章节分组 — 关键词检测
WEAPON_KEYWORDS = [
    "sword", "blade", "katana", "saber", "rapier", "greatsword", "cutlass",
    "dagger", "scythe", "axe_", "battleaxe", "bow", "crossbow", "longbow",
    "staff", "wand", "gun", "rifle", "pistol", "cannon", "shotgun",
    "hammer", "mace", "warhammer", "spear", "halberd", "glaive", "pike",
    "trident", "shuriken", "bomb", "grenade",
    "cleaver", "broadsword", "flail",
]

ARMOR_KEYWORDS = [
    "helmet", "hood", "crown", "cap", "head_", "_hat",
    "chestplate", "chest_", "body_", "cuirass", "tunic",
    "leggings", "leggin", "legs_", "_legs", "pants_", "_pants", "greaves",
    "boots", "shoes_", "feet_", "_feet", "sabaton",
    "armor_", "_armor", "robe_", "_robe",
]

def _is_weapon(item_id):
    if not item_id or ":" not in item_id:
        return False
    name = item_id.split(":", 1)[1].lower()
    if "pickaxe" in name or "shovel" in name or "hoe" in name:
        return False
    for kw in WEAPON_KEYWORDS:
        if kw.startswith("_"):
            if name.endswith(kw): return True
        elif kw.endswith("_"):
            if name.startswith(kw.rstrip("_")): return True
        else:
            if kw in name: return True
    return False

def _is_armor(item_id):
    if not item_id or ":" not in item_id:
        return False
    name = item_id.split(":", 1)[1].lower()
    for kw in ARMOR_KEYWORDS:
        if kw.startswith("_"):
            if name.endswith(kw): return True
        elif kw.endswith("_"):
            if name.startswith(kw.rstrip("_")): return True
        else:
            if kw in name: return True
    return False

def _get_quest_primary_item(quest):
    if not isinstance(quest, dict):
        return ""
    for task in quest.get("tasks", []):
        if not isinstance(task, dict):
            continue
        ttype = str(task.get("type", "")).lower()
        if "item" in ttype:
            target = task.get("target") or task.get("item", "")
            if target and ":" in target:
                return target
    return ""

def _recipe_chain_depth(item_id, visited=None, max_depth=12):
    if visited is None:
        visited = set()
    if not item_id or item_id in visited or max_depth <= 0:
        return 0
    visited.add(item_id)
    inputs = _ms._recipe_inputs_cache.get(item_id, [])
    if not inputs:
        return 0
    max_inp = 0
    for inp in inputs[:3]:
        d = _recipe_chain_depth(inp, visited, max_depth - 1)
        if d > max_inp:
            max_inp = d
    return max_inp + 1

def _build_milestone_list(all_mods):
    """从配方缓存提取合成链深度≥3的关键物品作为里程碑"""
    milestones = {}
    cache = _ms._recipe_inputs_cache
    for item_id in cache:
        if ":" not in item_id:
            continue
        mod_id = item_id.split(":", 1)[0]
        depth = _recipe_chain_depth(item_id)
        if depth >= 3:
            milestones.setdefault(mod_id, []).append((item_id, depth))
    for m in all_mods:
        mid = m.get("mod_id", "")
        if mid not in milestones:
            items = [(iid, _recipe_chain_depth(iid)) for iid in cache if iid.startswith(mid + ":")]
            if items:
                items.sort(key=lambda x: -x[1])
                if items[0][1] >= 2:
                    milestones[mid] = [items[0]]
    result = {}
    for mod_id, items in milestones.items():
        items.sort(key=lambda x: -x[1])
        result[mod_id] = [it for it, d in items[:3]]
    return result

def _milestone_to_prompt(milestones, lang="zh"):
    """将里程碑字典转为 Prompt 中的'必须覆盖'段落"""
    if not milestones:
        return ""
    lines = []
    if lang == "zh":
        lines.append("【必须覆盖的关键物品 - 每个至少1个任务】")
        for mod_id, items in milestones.items():
            names = ", ".join(items[:3])
            lines.append(f"  {mod_id}: {names}")
        lines.append("以上每个物品都必须在任务书中出现。\n")
    else:
        lines.append("[Must Cover Items - at least 1 quest each]")
        for mod_id, items in milestones.items():
            names = ", ".join(items[:3])
            lines.append(f"  {mod_id}: {names}")
        lines.append("Every item above must appear in the quest book.\n")
    return "\n".join(lines)

# 章节分组配置
CHAPTER_GROUPS = {
    "collections": {"title": "[武器-装备-饰品]", "icon": "minecraft:diamond_sword"},
    "tech":    {"title": "[科技机械]",   "icon": "minecraft:redstone_block"},
    "magic":   {"title": "[魔法研究]",   "icon": "minecraft:enchanting_table"},
    "world":   {"title": "[维度探险]",   "icon": "minecraft:grass_block"},
    "vanilla": {"title": "[主世界发展]", "icon": "minecraft:crafting_table"},
    "misc":    {"title": "[装饰工具]", "icon": "minecraft:chest"},
}

def _parse_mod(filename, filepath=None):
    base = filename
    for ext in (".jar",".zip",".JAR",".ZIP"):
        if base.endswith(ext): base = base[:-len(ext)]; break
    base_ns = base.lower().replace("-","").replace("_","").replace(" ","")
    for key, info in MOD_DB.items():
        if key in base_ns:
            size = os.path.getsize(filepath) if filepath else 0
            mod_id = info["modid"]
            # 检查是否是附属Mod
            parent = ADDON_PARENTS.get(mod_id)
            return {"filename":filename,"mod_name":info["name"],"mod_id":mod_id,
                    "category":info["category"],"size":size,"parent":parent}
    cleaned = re.sub(r'[-_]\d+[.]\d+[.]\d+.*$','',base)
    cleaned = re.sub(r'[-_](mc|MC|forge|fabric|release|beta|alpha|r\d+|universal|sources|deobf).*$','',cleaned,flags=re.IGNORECASE)
    cleaned = re.sub(r'[-_]\d+$','',cleaned).strip("-_ ")
    if not cleaned or len(cleaned)<2: cleaned = base
    mod_id = re.sub(r'[^a-z0-9_]','',cleaned.lower().replace(" ","_")) or re.sub(r'[^a-zA-Z0-9]','',base)[:20].lower()
    mod_name = re.sub(r'\s+',' ',re.sub(r'[-_]',' ',cleaned)).strip().title()
    size = os.path.getsize(filepath) if filepath else 0
    # 也检查未识别Mod是否在ADDON_PARENTS中
    parent = ADDON_PARENTS.get(mod_id)
    return {"filename":filename,"mod_name":mod_name,"mod_id":mod_id,
            "category":"unknown","size":size,"parent":parent}

def scan_mod_folder(folder_path):
    mods = []
    try:
        mods_dir, _, _ = _ms.resolve_pack_paths(folder_path)
        for f in sorted(os.listdir(mods_dir)):
            if f.lower().endswith((".jar",".zip")):
                fp = os.path.join(mods_dir, f)
                info = _parse_mod(f, fp)
                if info: mods.append(info)
    except Exception as e: print(f"[ERROR] {e}")
    mods.sort(key=lambda m: -m["size"])
    return mods

def classify_mods(mods):
    progression, utility, addon, unknown = [], [], [], []
    for m in mods:
        if m.get("parent"):
            addon.append(m)                     # 已识别的附属Mod
        elif m.get("category","unknown") in ("tech","magic","world","mob"):
            progression.append(m)               # 核心玩法Mod
        elif m.get("category","unknown") in ("utility","food","decor"):
            utility.append(m)                   # 辅助Mod
        else:
            unknown.append(m)
    return progression, utility, addon, unknown

# ════════════════════════════════════════════════════════
class QuestBookGenerator:
    def __init__(self, api_key=None, selected_mods=None, mod_folder=None,
                 progress_callback=None, lang="zh", engine="deepseek",
                 ollama_model=None, provider=None, api_url=None, api_model=None, max_output_tokens=None):
        # 根据引擎创建客户端
        self.engine = engine
        self.client = create_chat_client(
            engine=engine,
            api_key=api_key,
            ollama_model=ollama_model,
            provider=provider,
            api_url=api_url,
            api_model=api_model,
        )
        self.all_mods = selected_mods or []
        self.mod_folder = mod_folder
        self.cb = progress_callback
        self.lang = lang
        self.prog_mods, self.util_mods, self.addon_mods, self.unk = classify_mods(selected_mods or [])
        self._all_items = None  # 扫描结果缓存
        self.use_wiki = False
        self.max_output_tokens = max_output_tokens

    def _progress(self, msg, pct=None):
        if self.cb: self.cb(msg, pct)
        print(f"[PROGRESS] {msg}")

    def _scan_items(self):
        """扫描mod JAR文件提取真实物品ID"""
        if self._all_items is not None:
            return self._all_items
        if not self.mod_folder or not os.path.isdir(self.mod_folder):
            self._all_items = {}
            return self._all_items
        try:
            self._all_items = _ms.scan_folder_items(self.mod_folder, self.all_mods)
            total_items = sum(len(v) for v in self._all_items.values())
            print(f"[ITEM_SCAN] Scanned {len(self._all_items)} namespaces, {total_items} items total")
        except Exception as e:
            print(f"[ITEM_SCAN] Error: {e}")
            self._all_items = {}
        return self._all_items

    def generate(self, output_dir=None):
        self._progress("分析选中的Mod列表...", 5)
        scanned_items = self._scan_items()
        # 自动检测依赖库/无内容 Mod
        _ms.detect_library_mods(self.prog_mods, scanned_items)
        _ms.detect_library_mods(self.util_mods, scanned_items)
        _ms.detect_library_mods(self.addon_mods, scanned_items)
        _ms.detect_library_mods(self.unk, scanned_items)
        self.all_mods = [m for m in self.all_mods if not m.get("is_library")]
        self.prog_mods = [m for m in self.prog_mods if not m.get("is_library")]
        self.util_mods = [m for m in self.util_mods if not m.get("is_library")]
        self.addon_mods = [m for m in self.addon_mods if not m.get("is_library")]
        self.unk = [m for m in self.unk if not m.get("is_library")]

        # 统一单次调用（所有 Mod 完整 Prompt）
        mod_list = self._build_mod_list()
        all_ns = self._build_all_ns()
        item_catalog = _ms.build_item_catalog_for_prompt(scanned_items, self.all_mods)
        # 构造合成链提示
        recipe_hints = _ms.build_recipe_chain_hints(self.all_mods, max_chains_per_mod=5)
        if recipe_hints:
            item_catalog = recipe_hints + "\n\n" + item_catalog
        # 注入 Wiki 数据
        wiki_text = ""
        if getattr(self, "use_wiki", False):
            try:
                from . import mcwiki_crawler as _wiki
            except ImportError:
                import mcwiki_crawler as _wiki
            wiki_text = _wiki.build_wiki_prompt_injections(self.all_mods, scanned_items)
            if wiki_text:
                self._progress("已获取 MC百科 Wiki 数据", 12)

        # 远程拉取 playstyle 玩法说明（GitHub raw + 本地缓存7天）
        playstyle_lines = []
        for m in self.all_mods:
            mod_id = m.get("mod_id", "")
            if not mod_id:
                continue
            safe_name = mod_id.replace("/", "_").replace("\\", "_")
            try:
                url = f"https://raw.githubusercontent.com/Bluelgin/AutoFTBQ/main/playstyle_data/{safe_name}.md"
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    content = r.text.strip()
                    if content:
                        playstyle_lines.append(f"\n[{mod_id} 玩法简介]:\n{content[:2000]}\n")
            except Exception:
                pass

        if playstyle_lines:
            if wiki_text:
                wiki_text += "\n"
            wiki_text += "=== 玩法说明（人工提炼）===" + "\n".join(playstyle_lines)
        self._progress("生成丰富的任务书JSON (含支线/主线)...", 15)
        quest_json_text = self._generate_questbook(mod_list, all_ns, item_catalog, wiki_text)
        self._progress("解析并校验物品ID...", 80)
        saved_dir = self._save_snbt_files(quest_json_text, scanned_items, output_dir)
        self._progress("完成!", 100)
        return saved_dir

    def _build_mod_list(self):
        # 库 Mod 列表（告知 AI 不要生成）
        lib_names = [m for m in self.all_mods if m.get("is_library")]
        lib_warning = ""
        if lib_names:
            lib_warning = f"\n⚠️ 以下Mod为依赖库/前置，没有独立玩法，不需要生成任务: {', '.join(m['mod_name'] + '(' + m['mod_id'] + ')' for m in lib_names)}"
        lines = ["=== 核心Mod (有玩法/进度) ==="]
        for i,m in enumerate(self.prog_mods,1):
            cat_cn = CAT_LABEL.get(m.get("category","unknown"), m.get("category","unknown"))
            # 收集该Mod的附属
            addon_names = []
            for am in self.addon_mods:
                if am.get("parent") == m.get("mod_id"):
                    addon_names.append(f"{am['mod_name']}({am['mod_id']})")
            addon_str = f"  ← 附属: {', '.join(addon_names)}" if addon_names else ""
            lines.append(f"{i}. {m['mod_name']} (modid:{m['mod_id']}, 类别:{cat_cn}){addon_str}")
        if self.addon_mods:
            lines.append(f"\n  注意：以上附属Mod不需要单独开设章节，将它们的物品融入父Mod的任务中。")
        if self.util_mods:
            lines.append("\n=== 辅助Mod (工具/存储/食物) ===")
            for i,m in enumerate(self.util_mods,1):
                lines.append(f"{i}. {m['mod_name']} (modid:{m['mod_id']})")
        if self.unk:
            lines.append("\n=== 未分类Mod ===")
            for i,m in enumerate(self.unk,1):
                lines.append(f"{i}. {m['mod_name']} (modid:{m['mod_id']})")
        if lib_warning:
            lines.append(lib_warning)
        return "\n".join(lines)

    def _build_all_ns(self):
        ns = {"minecraft"}
        for m in self.all_mods: ns.add(m['mod_id'])
        ns.update((self._all_items or {}).keys())
        return ", ".join(sorted(ns))

    def _calc_max_tokens(self, is_continuation=False):
        """根据Mod数量动态计算max_tokens，6档精细化"""
        # 如果用户自定义了max_output_tokens，直接使用
        if getattr(self, "max_output_tokens", None) is not None:
            return int(self.max_output_tokens)
        mod_count = len(self.prog_mods) + len(self.unk)
        if mod_count <= 5:
            base = 16384
        elif mod_count <= 10:
            base = 32768
        elif mod_count <= 20:
            base = 49152
        elif mod_count <= 30:
            base = 65536
        elif mod_count <= 50:
            base = 98304
        else:
            base = 131072
        if self.engine == "ollama":
            base = min(base, 49152 if is_continuation else 40960)
        # 根据 density 调整 max_tokens
        density_mult = {
            "light": 0.7,
            "medium": 1.0,
            "rich": 1.5,
            "max": 2.0,
        }.get(getattr(self, "density", "medium"), 1.0)
        if density_mult != 1.0:
            base = int(base * density_mult)
        return base

    def _get_quest_config(self):
        """根据 Mod 数量动态返回 (quest_range_str, max_continue)"""
        mod_count = len(self.prog_mods) + len(self.unk)
        # 根据 density 调整任务数量级别
        density_mult = {
            "light": 0.5,
            "medium": 1.0,
            "rich": 1.5,
            "max": 2.5,
        }.get(getattr(self, "density", "medium"), 1.0)
        if mod_count <= 5:
            quest_range, mc = "50-80", 3
        elif mod_count <= 10:
            quest_range, mc = "80-150", 3
        elif mod_count <= 20:
            quest_range, mc = "150-250", 5
        elif mod_count <= 30:
            quest_range, mc = "250-350", 5
        elif mod_count <= 50:
            quest_range, mc = "350-500", 7
        else:
            quest_range, mc = "500-800", 10
        if self.engine == "ollama":
            mc = min(mc, 2)
        # 根据 density 佘数调整任务数量范围
        if density_mult != 1.0:
            lo, hi = quest_range.split("-")
            lo = int(int(lo) * density_mult)
            hi = int(int(hi) * density_mult)
            quest_range = f"{lo}-{hi}"
            # 密度越高越需要续写
            mc = int(mc * max(density_mult, 1.0))
        return quest_range, mc

    def _build_sp(self, quest_range="70-120"):
        """构建系统提示词（不含物品ID，可被缓存命中）"""
        if self.lang == "zh":
            return (
                "你是Minecraft整合包「任务指南」设计师。为FTB Quests设计一份非常丰富的任务书JSON。\n\n"
                "【核心定位】：这是一份「教程指南」，帮助玩家体验每个Mod的全部玩法内容。\n"
                "不是编故事，而是有目的性地引导玩家一步步上手。\n\n"
                "【结构要求】：\n"
                "1. 原版MC部分覆盖完整流程，4-6章，每章10-15个任务（共约40-60个）。\n"
                "   包含：开局→石器→铁器→钻石→附魔→下界→酿造→末地。\n"
                "   章节按进度顺序排列，第一章必须是开局。\n"
                "2. 每个核心Mod独立设1章，每章8-15个任务。\n"
                "   覆盖Mod从入门到精通的所有内容。\n"
                "   Mod章节按「先科技后魔法」的顺序排列。\n"
                "   不得省略任何已列出的核心Mod —— 每个Mod都必须有至少1章。\n"
                "3. 辅助Mod在奖励中引用其物品，不做单独大量章节。\n"
                "4. chapters数组中的章节顺序 = 游戏内任务书的显示顺序，必须按游戏进程排列。\n"
                "5. 总任务数灵活调整，确保每个Mod都被覆盖到，不要因为总任务数上限而砍Mod。\n\n"
                "【支线与主线设计（极其重要）】：\n"
                "- 主线：必须有dependencies链，玩家按顺序完成。覆盖Mod最核心的玩法流程。\n"
                "- 支线：必须大量设计！每个核心Mod至少5-8条支线任务，每条挂接不同主线节点。\n"
                "- 支线覆盖以下维度（每个维度至少1条）：\n"
                "  ① 材料收集（如：收集XX矿石、种植XX作物）\n"
                "  ② 工具升级（如：制作更强的镐/剑/装备）\n"
                "  ③ 自动化（如：搭建自动农场、自动采矿机）\n"
                "  ④ 能源系统（如：搭建发电机、储能设备）\n"
                "  ⑤ 探索/战斗（如：击败特定怪物、探索特定结构）\n"
                "  ⑥ 装饰/建筑（如：制作装饰方块、建造特定结构）\n"
                "  ⑦ 食物/酿造（如：制作高级食物、酿造药水）\n"
                "  ⑧ 跨Mod联动（如：用ModA的能源驱动ModB的机器）\n"
                "- 支线任务是主线的补充，引导玩家体验Mod的全部内容。\n\n"
                "【坐标布局（非常重要）】：\n"
                "- 主线任务：x从0开始，依次递增2.0（如 0, 2, 4, 6, 8...），y统一为0。\n"
                "- 支线任务：x与所挂接的主线任务相同，y偏移±2.0（上方或下方）。\n"
                "- 每条支线的y值错开（如第一条支线 y=-2.0，第二条 y=2.0，第三条 y=-4.0）。\n"
                "- 每个任务必须提供x和y坐标。\n\n"
                "【任务设计规范】：\n"
                "- 每个任务: title, subtitle(玩法提示), tasks(目标), rewards(奖励)\n"
                "- 任务类型: item(收集/合成), advancement(进度), kill, dimension, checkmark(仅信息类)\n"
                "- 物品ID只能用minecraft:或上述已安装Mod的命名空间\n"
                "- 奖励按阶段合理分配\n"
                "- ⚠️ 不需要写 icon 字段，程序会自动赋值图标\n\n"
                f"【总任务数要求】：共 {quest_range} 个任务（含主线+支线）。Mod越多任务数越接近上限。\n\n"
                "JSON示例(含大量支线):\n"
                '{"title":"整合包指南","chapters":[\n'
                '{"id":"ch_wood","title":"原版·木石时代","quests":[\n'
                '{"id":"q_log","title":"主线·获得原木","subtitle":"空手撸树获得原木","tasks":[{"type":"item","target":"minecraft:oak_log","count":16}],"rewards":[{"type":"item","target":"minecraft:apple","count":4}],"shape":"square","x":0.0,"y":0.0},\n'
                '{"id":"q_table","title":"主线·制作工作台","subtitle":"用4个木板合成工作台","dependencies":["q_log"],"tasks":[{"type":"item","target":"minecraft:crafting_table","count":1}],"rewards":[{"type":"xp","count":10}],"shape":"square","x":2.0,"y":0.0},\n'
                '{"id":"q_pickaxe","title":"主线·石器工具","subtitle":"制作石镐开始挖矿","dependencies":["q_table"],"tasks":[{"type":"item","target":"minecraft:stone_pickaxe","count":1}],"rewards":[{"type":"xp","count":20}],"shape":"square","x":4.0,"y":0.0},\n'
                '{"id":"q_furnace","title":"主线·制作熔炉","subtitle":"8个圆石合成熔炉开始烧矿","dependencies":["q_pickaxe"],"tasks":[{"type":"item","target":"minecraft:furnace","count":1}],"rewards":[{"type":"xp","count":15}],"shape":"square","x":6.0,"y":0.0},\n'
                '{"id":"q_branch_food","title":"支线·解决食物","subtitle":"击杀动物获取食物","dependencies":["q_table"],"tasks":[{"type":"item","target":"minecraft:cooked_beef","count":8}],"rewards":[{"type":"item","target":"minecraft:bread","count":4}],"shape":"diamond","x":2.0,"y":-2.0},\n'
                '{"id":"q_branch_cave","title":"支线·探索洞穴","subtitle":"寻找天然洞穴获取资源","dependencies":["q_pickaxe"],"tasks":[{"type":"item","target":"minecraft:torch","count":32}],"rewards":[{"type":"item","target":"minecraft:iron_ingot","count":3}],"shape":"diamond","x":4.0,"y":-2.0},\n'
                '{"id":"q_branch_shelter","title":"支线·建造小屋","subtitle":"搭建基础庇护所","dependencies":["q_log"],"tasks":[{"type":"item","target":"minecraft:oak_planks","count":64}],"rewards":[{"type":"xp","count":10}],"shape":"circle","x":0.0,"y":2.0}\n'
                ']}\n]}\n\n'
                "要求: 总任务数按Mod数量灵活调整。所有title/subtitle用中文。每个主线任务至少有2-3条支线挂接。不需要写icon字段。只输出JSON。"
            )
        else:
            return (
                f"You are a Minecraft modpack guide designer for FTB Quests. "
                f"Design a VERY RICH questbook JSON. Total: {quest_range} quests.\n\n"
                "POSITIONING: Tutorial guide that helps players experience ALL content of each mod.\n\n"
                "STRUCTURE:\n"
                "1. Vanilla: 4-6 chapters, 10-15 quests each. Wood→Stone→Iron→Diamond→Enchant→Nether→Brew→End.\n"
                "2. Each core mod: 1-2 chapters, 10-15 quests each. Cover from beginner to master.\n"
                "3. Utility mods referenced in rewards only.\n"
                f"4. Total: {quest_range} quests.\n\n"
                "MAIN & BRANCH LINES:\n"
                "- Main: chained via dependencies.\n"
                "- Branches: no dependencies (or depend on 1 main node), players can do anytime.\n"
                "- Each chapter: 2-3 branch quests minimum.\n\n"
                "TASK RULES: item/advancement/kill/dimension/checkmark. Item IDs: minecraft: or listed namespaces.\n"
                "Layout: x spaced 2.0 horizontal. Reward balanced by stage.\n\n"
                f"Output ONLY valid JSON, {quest_range} quests total."
            )

    def _build_up(self, mod_list, all_ns, wiki_text="", item_catalog="", milestone_text=""):
        """构建用户提示词，item_catalog为空时生成不带物品ID的短版（用于缓存预热）"""
        if self.lang == "zh":
            wiki_block = f"{wiki_text}\n\n" if wiki_text else ""
            return (
                f"{mod_list}\n\n"
                f"{wiki_block}"
                f"=== 可用物品命名空间 ===\n{all_ns}\n\n"
                f"{item_catalog}\n\n"
                "请设计一份非常丰富的任务指南JSON。注意：\n"
                "- 覆盖每个Mod的完整玩法，从入门到精通\n"
                "- 必须包含支线任务（无dependencies的独立任务）\n"
                "- 严格使用上面列出的物品ID，不要编造不存在的ID\n"
                "- 确保每个核心Mod都至少有一章\n"
                "- 告诉玩家每一步做什么、用什么做、做完得到什么\n\n"
                f"{milestone_text}"
            )
        else:
            return (
                f"{mod_list}\n\n=== Allowed namespaces ===\n{all_ns}\n\n"
                f"{item_catalog}\n\n"
                "Design a very rich questbook JSON with branches and main lines. "
                "Use ONLY the item IDs listed above.\n\n"
                f"{milestone_text}"
            )

    def _build_generation_plan(self):
        """Build deterministic chapter quotas so density is controlled by code."""
        configs = {
            "light":  {"vanilla": 24, "core": 6,  "utility": 2, "batch": 6},
            "medium": {"vanilla": 40, "core": 10, "utility": 3, "batch": 8},
            "rich":   {"vanilla": 60, "core": 16, "utility": 5, "batch": 8},
            "max":    {"vanilla": 80, "core": 24, "utility": 8, "batch": 10},
        }
        cfg = configs.get(getattr(self, "density", "medium"), configs["medium"])
        vanilla_topics = [
            ("vanilla_start", "原版·生存起步", "原木、工作台、石器、食物与庇护所"),
            ("vanilla_iron", "原版·矿业与铁器", "矿洞探索、熔炼、铁器、红石基础"),
            ("vanilla_magic", "原版·钻石与附魔", "钻石装备、附魔、村民与高级生存"),
            ("vanilla_nether", "原版·下界与酿造", "下界探索、烈焰棒、药水与远古残骸"),
            ("vanilla_end", "原版·末地与终局", "末地传送门、末影龙、鞘翅与终局建设"),
        ]
        density = getattr(self, "density", "medium")
        topic_count = 4 if density in ("light", "medium") else 5
        topics = vanilla_topics[:topic_count]
        base, extra = divmod(cfg["vanilla"], len(topics))
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

        core_mods = self.prog_mods + self.unk
        for mod in core_mods:
            mod_id = mod.get("mod_id", "unknown")
            plan.append({
                "id": f"mod_{mod_id}",
                "title": mod.get("mod_name", mod_id),
                "focus": f"完整覆盖 {mod.get('mod_name', mod_id)} 从入门到精通的玩法与配方链",
                "target": cfg["core"],
                "mods": [mod],
                "namespaces": [mod_id],
            })

        utility_mods = list(self.util_mods)
        for group_index in range(0, len(utility_mods), 5):
            group = utility_mods[group_index:group_index + 5]
            if not group:
                continue
            names = "、".join(m.get("mod_name", m.get("mod_id", "")) for m in group)
            plan.append({
                "id": f"utility_{group_index // 5 + 1}",
                "title": "实用工具与生活" if group_index == 0 else f"实用工具与生活 {group_index // 5 + 1}",
                "focus": f"介绍并实际使用这些辅助模组：{names}",
                "target": max(4, cfg["utility"] * len(group)),
                "mods": group,
                "namespaces": [m.get("mod_id", "") for m in group if m.get("mod_id")],
            })

        known_ns = {m.get("mod_id", "") for m in self.all_mods}
        custom_ns = sorted(ns for ns in getattr(_ms, "_kubejs_namespaces", set()) if ns not in known_ns)
        if custom_ns:
            plan.append({
                "id": "kubejs_custom",
                "title": "整合包自定义内容",
                "focus": "覆盖 KubeJS 自定义物品、魔改配方和关键生产链",
                "target": cfg["core"],
                "mods": [{"mod_id": ns, "mod_name": f"KubeJS {ns}"} for ns in custom_ns],
                "namespaces": custom_ns,
            })

        for chapter in plan:
            chapter["batch_size"] = cfg["batch"]
        return plan

    def _chapter_catalog(self, chapter):
        selected = chapter.get("mods", [])
        if not selected and chapter.get("namespaces") == ["minecraft"]:
            selected = []
        catalog = _ms.build_item_catalog_for_prompt(self._all_items or {}, selected)
        return catalog

    def _parse_generated_quests(self, text):
        """Parse a short staged response and return only quest dictionaries."""
        candidate = self._extract_json(text)
        data = None
        for _ in range(3):
            try:
                data = json.loads(candidate)
                break
            except json.JSONDecodeError:
                candidate = self._repair_json(candidate)
        return extract_quest_batch(data)

    def _build_stage_prompt(self, chapter, count, existing_titles, catalog, wiki_text=""):
        title_list = ", ".join(existing_titles[-30:]) if existing_titles else "无"
        wiki_block = wiki_text[:2500] if wiki_text else ""
        if self.lang == "zh":
            return (
                f"为 FTB Quests 的章节《{chapter['title']}》生成一批任务。\n"
                f"章节重点：{chapter['focus']}\n"
                f"EXACT_QUEST_COUNT={count}，必须恰好返回 {count} 个任务，不多不少。\n"
                "返回结构只能是 {\"quests\":[...]}，不要章节外壳、Markdown或解释。\n"
                "每个任务必须包含 title、subtitle、tasks、rewards；任务ID、dependencies、x、y由程序生成，不要输出。\n"
                "tasks 类型允许 item、advancement、kill、dimension、checkmark；统一用 target 表示目标，item 必须使用目录中的真实ID，并提供count。\n"
                "约70%为顺序推进的核心任务，约30%标题以“支线·”开头，内容不得重复。\n"
                f"已有任务标题（禁止重复）：{title_list}\n\n"
                f"{wiki_block}\n\n{catalog}"
            )
        return (
            f"Generate one batch for the FTB Quests chapter '{chapter['title']}'.\n"
            f"Focus: {chapter['focus']}\n"
            f"EXACT_QUEST_COUNT={count}. Return exactly {count} quests.\n"
            "Output only {\"quests\":[...]}. No chapter wrapper, markdown, IDs, dependencies, x or y.\n"
            "Each quest needs title, subtitle, tasks and rewards. Use only real item IDs from the catalog.\n"
            "Use target for task targets and include count for item tasks.\n"
            "About 70% main progression and 30% titles prefixed with 'Branch ·'. No duplicates.\n"
            f"Existing titles: {title_list}\n\n{wiki_block}\n\n{catalog}"
        )

    def _deduplicate_stage_quests(self, quests, existing_titles=None):
        seen_titles = {str(t).strip().lower() for t in (existing_titles or []) if str(t).strip()}
        seen_targets = set()
        unique = []
        for quest in quests:
            title = str(quest.get("title", "")).strip()
            if not title or title.lower() in seen_titles:
                continue
            primary = _get_quest_primary_item(quest)
            key = (title.lower(), primary)
            if key in seen_targets:
                continue
            seen_titles.add(title.lower())
            seen_targets.add(key)
            unique.append(quest)
        return unique

    def _fallback_stage_quests(self, chapter, count, existing_quests):
        """Fill rare model shortfalls with real scanned items, never duplicated text."""
        existing_titles = {str(q.get("title", "")).lower() for q in existing_quests}
        existing_items = {_get_quest_primary_item(q) for q in existing_quests}
        candidates = []
        for namespace in chapter.get("namespaces", []):
            candidates.extend(sorted((self._all_items or {}).get(namespace, {}).items()))
        if "minecraft" in chapter.get("namespaces", []):
            candidates.extend([
                ("minecraft:crafting_table", "工作台"), ("minecraft:furnace", "熔炉"),
                ("minecraft:iron_ingot", "铁锭"), ("minecraft:diamond", "钻石"),
                ("minecraft:enchanting_table", "附魔台"), ("minecraft:blaze_rod", "烈焰棒"),
                ("minecraft:ender_eye", "末影之眼"), ("minecraft:dragon_breath", "龙息"),
            ])
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

    def _normalize_chapter_quests(self, chapter_id, quests):
        """Programmatically own IDs, dependencies and layout after all batches merge."""
        normalized = []
        main_ids = []
        branches = []
        for index, original in enumerate(quests):
            quest = dict(original)
            quest_id = f"{chapter_id}_q_{index + 1:03d}"
            quest["id"] = quest_id
            title = str(quest.get("title", ""))
            shape = str(quest.get("shape", "")).lower()
            is_branch = ("支线" in title or "branch" in title.lower() or shape in ("diamond", "circle", "hexagon"))
            quest.pop("dependencies", None)
            if is_branch:
                branches.append((quest, len(normalized)))
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
        for branch_index, (quest, _) in enumerate(branches):
            anchor_index = min(branch_index, len(main_ids) - 1)
            quest["dependencies"] = [main_ids[anchor_index]]
            quest["x"] = float(anchor_index * 2)
            level = branch_index // max(1, len(main_ids)) + 1
            quest["y"] = float((-1 if branch_index % 2 == 0 else 1) * 2 * level)
            quest["shape"] = "diamond"
        return normalized

    def _generate_questbook_staged(self, wiki_text=""):
        plan = self._build_generation_plan()
        total_target = sum(chapter["target"] for chapter in plan)
        print(f"[STAGED] density={getattr(self, 'density', 'medium')}, chapters={len(plan)}, target={total_target}")
        self._progress(f"已规划 {len(plan)} 个章节，共 {total_target} 个任务", 14)
        completed = 0
        chapters = []
        system_prompt = (
            "You generate concise valid JSON for FTB Quests. Follow EXACT_QUEST_COUNT. "
            "Never invent item IDs and never include markdown."
        )
        for chapter_index, chapter in enumerate(plan):
            catalog = self._chapter_catalog(chapter)
            quests = []
            while len(quests) < chapter["target"]:
                requested = min(chapter["batch_size"], chapter["target"] - len(quests))
                remaining = requested
                attempts = 0
                while remaining > 0 and attempts < 3:
                    existing_titles = [q.get("title", "") for q in quests]
                    prompt = self._build_stage_prompt(chapter, remaining, existing_titles, catalog, wiki_text)
                    max_tokens = max(3072, min(12288, remaining * 1100))
                    max_tokens = min(max_tokens, self._calc_max_tokens())
                    content, truncated = self.client.chat(
                        [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
                        temperature=0.45, max_tokens=max_tokens,
                    )
                    parsed = [] if truncated else self._parse_generated_quests(content)
                    parsed = self._deduplicate_stage_quests(parsed, existing_titles)
                    accepted = parsed[:remaining]
                    quests.extend(accepted)
                    remaining -= len(accepted)
                    attempts += 1
                if remaining > 0:
                    quests.extend(self._fallback_stage_quests(chapter, remaining, quests))
                completed += requested
                pct = 15 + int(60 * completed / max(1, total_target))
                self._progress(f"分阶段生成：{chapter['title']} {len(quests)}/{chapter['target']}", pct)
            normalized = self._normalize_chapter_quests(chapter["id"], quests[:chapter["target"]])
            chapters.append({"id": chapter["id"], "title": chapter["title"], "quests": normalized})
        result = {"title": "整合包任务指南", "chapters": chapters}
        return json.dumps(result, ensure_ascii=False)

    def _generate_questbook(self, mod_list, all_ns, item_catalog="", wiki_text=""):
        """Generate only in deterministic batches so density remains enforceable."""
        return self._generate_questbook_staged(wiki_text)

    def _generate_questbook_legacy(self, mod_list, all_ns, item_catalog="", wiki_text=""):
        """Original whole-book generation pipeline retained as a compatibility fallback."""
        quest_range, max_continue = self._get_quest_config()
        # 构建里程碑列表
        milestones = _build_milestone_list(self.all_mods)
        milestone_text = _milestone_to_prompt(milestones, self.lang)
        sp = self._build_sp(quest_range)
        max_tok = self._calc_max_tokens()

        # ── 第1级：Cache Warmup（仅API引擎，发送不含物品ID的短版提示词）──
        if self.engine in ("deepseek", "generic"):
            warmup_up = self._build_up(mod_list, all_ns, wiki_text, item_catalog="", milestone_text="")
            warmup_messages = [
                {"role": "system", "content": sp},
                {"role": "user", "content": warmup_up + "\n\n请返回 {}，不需要生成任何实际内容。"}
            ]
            try:
                warmup_model = DEEPSEEK_MODEL if self.engine == "deepseek" else self.client.model
                warmup_url = DEEPSEEK_API_URL if self.engine == "deepseek" else self.client.api_url
                warmup_payload = {
                    "model": warmup_model, "messages": warmup_messages,
                    "temperature": 0.1, "max_tokens": 16, "stream": False
                }
                requests.post(warmup_url, json=warmup_payload,
                              headers=self.client.headers, timeout=10)
            except Exception:
                pass  # 预热失败不阻塞主流程

        # ── 第2级：完整生成 + 第3级：Auto-Continue ──
        full_up = self._build_up(mod_list, all_ns, wiki_text, item_catalog, milestone_text)
        conversation = [{"role": "system", "content": sp},
                        {"role": "user", "content": full_up}]
        full_content = ""

        consecutive_empty = 0
        for _round in range(max_continue + 1):
            content, truncated = self.client.chat(
                conversation, max_tokens=max_tok, temperature=0.5
            )
            # 检测连续多次空响应 → 提前退出
            if len(content.strip()) < 500:
                consecutive_empty += 1
                if consecutive_empty >= 3:
                    print(f"[CONTINUE] Breaking after {consecutive_empty} consecutive small responses ({len(content.strip())} chars)")
                    break
            else:
                consecutive_empty = 0
            if _round > 0:
                # Fix: truncated JSON may lack comma between concatenated parts
                if full_content and full_content[-1] not in (",", "{", "[") and content and content[0] not in (",", "]", "}"):
                    full_content += ","
            full_content += content

            # ── 检查是否需要续写 ──
            if not truncated:
                # API的 finish_reason="stop" → AI已写完，信任它
                # 拼接瑕疵由 _save_snbt_files 的 repair 循环兜底
                break
            else:
                if _round >= max_continue:
                    break

            # 添加续写请求到对话历史
            conversation.append({"role": "assistant", "content": content})
            if self.lang == "zh":
                continuation_prompt = (
                    "继续输出JSON。直接从上次中断处继续，不要重复，不要解释，不要markdown.\n\n"
                    "[格式保持要点]\n"
                    "- 结构: {\"title\":\"...\",\"chapters\":[{\"id\":\"...\",\"title\":\"...\",\"quests\":[...]}]}\n"
                    "- 每个quest: id,title,tasks,rewards,dependencies(主线用),x,y\n"
                    "- tasks中: type为item→需target+count, kill→需entity, advancement→需advancement\n"
                    "- 坐标: 主线x=0,2,4... y=0；支线挂接主线节点，y偏移±2.0\n"
                    "- 物品ID只能用已给出的命名空间(minecraft: 或已列出的modid)\n"
                    "- 禁止出现任何markdown包裹、解释文字、重复已有章节/任务\n\n"
                    "直接输出JSON，不要前缀。"
                )
            else:
                continuation_prompt = (
                    "Continue JSON. Start where you left off. No repeats, no explanation, no markdown.\n\n"
                    "[Format Reminders]\n"
                    "- Structure: {\"title\":\"...\",\"chapters\":[{\"id\":\"...\",\"title\":\"...\",\"quests\":[...]}]}\n"
                    "- Each quest: id, title, tasks, rewards, dependencies(main line), x, y\n"
                    "- Tasks: type=item needs target+count, kill needs entity, advancement needs advancement\n"
                    "- Coordinates: main line x=0,2,4... y=0; branch same x, y offset ±2.0\n"
                    "- Item IDs: only use allowed namespaces (minecraft: or listed modids)\n"
                    "- No markdown, no explanation text, no repeated chapters/quests\n\n"
                    "Output JSON directly, no prefix."
                )
            conversation.append({"role": "user", "content": continuation_prompt})

        return full_content

    def _save_snbt_files(self, quest_json_text, scanned_items=None, output_dir=None):
        SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
        if output_dir and os.path.isdir(os.path.dirname(output_dir)):
            base_dir = output_dir
        else:
            base_dir = os.path.join(SCRIPT_DIR, OUTPUT_DIR_NAME)
        os.makedirs(base_dir, exist_ok=True)
        chapters_dir = os.path.join(base_dir, "chapters")
        os.makedirs(chapters_dir, exist_ok=True)
        rt_dir = os.path.join(base_dir, "reward_tables")
        os.makedirs(rt_dir, exist_ok=True)
        with open(os.path.join(base_dir,"ai_raw_output.txt"),"w",encoding="utf-8") as f:f.write(quest_json_text)
        json_text = self._merge_json_parts(quest_json_text)
        ai_data = None
        for attempt in range(3):
            try:
                ai_data = json.loads(json_text)
                ai_data, schema_issues = normalize_quest_book(ai_data)
                for issue in schema_issues:
                    print(f"[SCHEMA] {issue}")
                ai_data, _ = self._deduplicate_quests(ai_data)
                break
            except json.JSONDecodeError:
                json_text = self._repair_json(json_text)
            except QuestValidationError:
                raise
        # AI二次审查：当常规修复无法解决时，用AI修复JSON结构错误
        if ai_data is None and self.client is not None:
            try:
                print("[AI_REPAIR] Attempting AI repair for broken JSON...")
                ai_data = self._ai_repair_json(json_text)
                if ai_data is not None:
                    ai_data, schema_issues = normalize_quest_book(ai_data)
                    for issue in schema_issues:
                        print(f"[SCHEMA] {issue}")
                    ai_data, _ = self._deduplicate_quests(ai_data)
                    print("[AI_REPAIR] AI repair succeeded!")
            except Exception as e:
                print(f"[AI_REPAIR] Error: {e}")
                ai_data = None

        if ai_data is None:
            with open(os.path.join(base_dir,"parse_error.txt"),"w",encoding="utf-8") as f:
                f.write(f"=== AI原始返回内容 ===\n{quest_json_text}\n\n=== 提取后的JSON ===\n{json_text}")
            raise Exception(f"AI返回了无效JSON（已写入 parse_error.txt 的前 {min(len(quest_json_text), 200)} 字符）。请将AI返回的完整内容复制到导入模式中重试。")

        # 自动修正物品ID
        if scanned_items:
            ai_data, fix_count, unfixable = _ms.auto_fix_item_ids(ai_data, scanned_items)
            # 写入校验报告
            report_lines = [
                "=== 物品ID自动修正报告 ===",
                f"成功修正: {fix_count} 个物品ID",
                f"无法修正: {len(unfixable)} 个物品ID",
            ]
            if unfixable:
                report_lines.append("\n--- 无法修正的物品ID ---")
                for item in unfixable:
                    report_lines.append(f"  {item['id']} — {item['location']}")
                    report_lines.append(f"    原因: {item['reason']}")
                report_lines.append("\n  建议: 手动在SNBT文件中替换为正确的物品ID")
            else:
                report_lines.append("\n所有物品ID均已通过自动修正 ✓" if fix_count else "\n所有物品ID均已通过校验 ✓")
            report_path = os.path.join(base_dir, "id_validation_report.txt")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write("\n".join(report_lines))
            print(f"[VALIDATION] {fix_count} fixed, {len(unfixable)} unfixable — report saved")

        # 给所有章节分配分组标签
        self._annotate_chapter_groups(ai_data)

        return self._write_snbt_files(base_dir, ai_data)

    def _reorganize_chapters(self, quest_json_text):
        """提取并整理 JSON"""
        json_text = self._extract_json(quest_json_text)
        try:
            ai_data = json.loads(json_text)
        except json.JSONDecodeError:
            return quest_json_text
        return json.dumps(ai_data, ensure_ascii=False)

    def _annotate_chapter_groups(self, ai_data):
        """给每个章节分配 _group 字段（用于FTB Quests分组折叠）"""
        for ch in ai_data.get("chapters", []):
            if "_group" in ch:
                continue
            quests_in_ch = ch.get("quests", [])
            namespace_counts = {}
            for q in quests_in_ch:
                item = _get_quest_primary_item(q)
                if item and ":" in item:
                    ns = item.split(":", 1)[0]
                    namespace_counts[ns] = namespace_counts.get(ns, 0) + 1
            mod_id = max(namespace_counts, key=namespace_counts.get) if namespace_counts else "unknown"
            cat = _resolve_mod_category(mod_id) or "unknown"
            if cat in ("tech", "magic", "world"):
                group_key = cat
            elif cat in ("decor", "food", "utility"):
                group_key = "misc"
            else:
                group_key = "vanilla"
            ch["_group"] = group_key

    def _write_snbt_files(self, base_dir, ai_data):
        """Validate and delegate SNBT output while preserving the legacy method."""
        ai_data, schema_issues = normalize_quest_book(ai_data)
        for issue in schema_issues:
            print(f"[SCHEMA] {issue}")
        return write_quest_book(
            base_dir,
            ai_data,
            uid=_uid,
            normalize_item=_fx,
            item_count=_item_ref_count,
            to_snbt=to_snbt,
            double_value=_D,
            long_value=_L,
            group_config=CHAPTER_GROUPS,
        )

    def _deduplicate_quests(self, ai_data):
        """Remove duplicate quests within each chapter (by title and by ID)"""
        removed = 0
        for ch in ai_data.get("chapters", []):
            quests = ch.get("quests", [])
            seen_titles = set()
            seen_ids = set()
            unique = []
            for q in quests:
                qid = q.get("id", "")
                title = q.get("title", "")
                is_dup = False
                if title and title in seen_titles:
                    print(f"[DEDUP] Removing duplicate quest (same title): {title}")
                    is_dup = True
                elif qid and qid in seen_ids:
                    print(f"[DEDUP] Removing duplicate quest (same id): {qid} ({title})")
                    is_dup = True
                if is_dup:
                    removed += 1
                else:
                    if title:
                        seen_titles.add(title)
                    if qid:
                        seen_ids.add(qid)
                    unique.append(q)
            ch["quests"] = unique
        print(f"[DEDUP] Removed {removed} duplicate quests")
        return ai_data, removed



    def _ai_repair_json(self, broken_text):
        """使用AI修复正则无法处理的JSON结构错误（如字符串内嵌括号）"""
        if not self.client:
            return None
        # 截断过长的文本，避免超出上下文窗口
        MAX_INPUT = 80000
        input_text = broken_text[:MAX_INPUT] if len(broken_text) > MAX_INPUT else broken_text
        if self.lang == "zh":
            sys_prompt = "你是一个JSON修复专家。只修复语法错误，不改变任何数据内容。"
            user_prompt = (
                "修复下面FTB任务书JSON的语法错误。规则：\n"
                "1. 只修复JSON语法错误（字符串未闭合、括号不匹配、逗号缺失/多余、换行符）\n"
                "2. 不要删除、添加或修改任何章节、任务、物品ID、标题等数据\n"
                "3. 保持所有文本原样\n"
                "4. 只输出修复后的JSON，不要任何解释\n\n"
                f"JSON：\n{input_text}"
            )
        else:
            sys_prompt = "You are a JSON repair expert. Fix syntax errors only, do not change any data."
            user_prompt = (
                "Fix the JSON syntax errors below. Rules:\n"
                "1. Only fix JSON syntax errors (unclosed strings, mismatched brackets, missing/extra commas)\n"
                "2. Do not delete, add or modify any chapters, quests, item IDs, titles, etc.\n"
                "3. Keep all text content as-is\n"
                "4. Output ONLY the fixed JSON, no explanation\n\n"
                f"JSON:\n{input_text}"
            )
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ]
        max_out = min(int(len(input_text) * 1.3), 131072)
        try:
            result_text, _ = self.client.chat(messages, temperature=0.1, max_tokens=max_out)
            fixed = self._extract_json(result_text)
            return json.loads(fixed)
        except Exception as e:
            print(f"[AI_REPAIR] Failed: {e}")
            return None

    def _merge_json_parts(self, raw_text):
        """提取JSON文本（不重构章节，保留AI原始结构，由 _save_snbt_files 的 repair 循环兜底）"""
        return self._extract_json(raw_text)

    def _repair_json(self, text):
        """修复AI返回JSON的常见语法错误（缺失逗号、尾随逗号、缺括号）"""
        text = re.sub(r',\s*}', '}', text)
        text = re.sub(r',\s*]', ']', text)
        text = re.sub(r'}\s*{', '},{', text)
        text = re.sub(r']\s*{', '],{', text)
        text = re.sub(r'}\s*\[', '},[', text)
        text = re.sub(r']\s*\[', '],[', text)
        d = sum(1 for c in text if c == '{') - sum(1 for c in text if c == '}')
        a = sum(1 for c in text if c == '[') - sum(1 for c in text if c == ']')
        if d > 0: text += '}' * d
        if a > 0: text += ']' * a
        # 4. fix invalid JSON escape sequences (e.g. \x, \a, truncated \u)
        text = re.sub(r'\\(?=u(?:[0-9a-fA-F]{0,3}(?:[^0-9a-fA-F"\\\\]|$)))', r'\\\\', text)
        text = re.sub(r'\\([^"\\\\/bfnrtu])', r'\\\\\1', text)
        return text


    def _extract_json(self, text):
        if not text: return "{}"
        m = re.search(r'```(?:json)?\s*\n(.*?)```', text, re.DOTALL)
        if m: return m.group(1).strip()
        s, e = text.find("{"), text.rfind("}")
        if s < 0 or e <= s: return text
        raw = text[s:e+1]
        # 智能修复截断的JSON：去掉截断中残破的最后一段
        # 找最后一个合法的 }, 或 ], 或 " 结尾
        last_good = -1
        for p in [raw.rfind('\n    }\n'), raw.rfind('\n  }\n'), raw.rfind('\n  ]\n'),
                   raw.rfind('\n    ]\n'), raw.rfind('}\n'), raw.rfind(']\n')]:
            if p > last_good:
                last_good = p
        if last_good > len(raw) * 0.5:  # 过半完整即尝试修复
            raw = raw[:last_good+1]  # 保留那个 }
            # 补上缺失的闭合
            d = sum(1 for c in raw if c == '{') - sum(1 for c in raw if c == '}')
            a = sum(1 for c in raw if c == '[') - sum(1 for c in raw if c == ']')
            raw += ']'*a + '}'*d
            return raw
        return raw

def _build_quest_links(qents):
    """
    根据dependencies自动生成quest_links实现FTB Quests视觉连线。
    对每对有依赖关系的任务创建一个双向link。
    返回: [{"id":..., "source_id":..., "target_id":..., "type":"normal"}, ...]
    """
    links = []
    link_ids_seen = set()
    for q in qents:
        qid = q["id"]
        deps = q.get("dependencies", [])
        for dep_id in deps:
            # 创建唯一的link_id
            pair = tuple(sorted([qid, dep_id]))
            if pair in link_ids_seen:
                continue
            link_ids_seen.add(pair)
            link_id = "link_" + uuid.uuid4().hex[:6].upper()
            links.append({
                "id": link_id,
                "source_id": dep_id,   # 依赖的任务是源（先完成）
                "target_id": qid,       # 当前任务是目标
                "type": "normal"
            })
    return links

def _fx(raw):
    if isinstance(raw, dict):
        raw = raw.get("id") or raw.get("item") or raw.get("target") or ""
        if isinstance(raw, dict):
            return _fx(raw)
    if not isinstance(raw, (str, int)) or not str(raw).strip():
        return ""
    raw = str(raw).strip()
    item_id = raw if ":" in raw else f"minecraft:{raw}"
    if not re.fullmatch(r"[a-z0-9_.-]+:[a-z0-9_./-]+", item_id):
        return ""
    return item_id


def _item_ref_count(container, raw):
    count = container.get("count", 1) if isinstance(container, dict) else 1
    if isinstance(raw, dict):
        count = raw.get("count", raw.get("Count", count))
    try:
        return max(1, int(count))
    except (TypeError, ValueError):
        return 1
def _uid(): return uuid.uuid4().hex[:16]

def generate_quest_book(api_key=None, selected_mods=None, mod_folder=None,
                         progress_callback=None, lang="zh", engine="deepseek",
                         ollama_model=None, output_dir=None, use_wiki=False,
                         provider=None, api_url=None, api_model=None,
                         density="medium", max_output_tokens=None):
    if progress_callback: progress_callback("分析选中的Mod...",3)
    if not selected_mods: raise Exception("未选中任何Mod。")
    gen = QuestBookGenerator(
        api_key=api_key, selected_mods=selected_mods, mod_folder=mod_folder,
        progress_callback=progress_callback, lang=lang, engine=engine,
        ollama_model=ollama_model, provider=provider,
        api_url=api_url, api_model=api_model,
        max_output_tokens=max_output_tokens
    )
    gen.use_wiki = use_wiki
    gen.density = density
    return gen.generate(output_dir=output_dir)


def build_full_prompt(selected_mods, mod_folder=None, lang="zh"):
    """构建完整的提示词，供用户复制到网页AI使用"""
    gen = QuestBookGenerator(
        api_key="", selected_mods=selected_mods, mod_folder=mod_folder,
        lang=lang, engine="dummy"
    )
    gen.client = None  # 不需要API调用
    scanned = gen._scan_items()
    mod_list = gen._build_mod_list()
    all_ns = gen._build_all_ns()
    item_cat = _ms.build_item_catalog_for_prompt(scanned, gen.all_mods)

    # 动态任务数
    mod_count = len(gen.prog_mods) + len(gen.unk)
    if mod_count <= 5:
        quest_range = "50-80"
    elif mod_count <= 10:
        quest_range = "80-150"
    elif mod_count <= 20:
        quest_range = "150-250"
    elif mod_count <= 30:
        quest_range = "250-350"
    elif mod_count <= 50:
        quest_range = "350-500"
    else:
        quest_range = "500-800"

    if lang == "zh":
        sp = (
            "你是Minecraft整合包「任务指南」设计师。为FTB Quests设计一份非常丰富的任务书JSON。\n\n"
            "【核心定位】：这是一份「教程指南」，帮助玩家体验每个Mod的全部玩法内容。\n"
            "【结构要求】：\n"
            "1. 原版MC: 4-6章，每章10-15个任务。开局→石器→铁器→钻石→附魔→下界→酿造→末地。\n"
            "2. 每个核心Mod: 1-2章，每章10-15个任务。从入门到精通。\n"
            "3. 辅助Mod在奖励中引用其物品。\n4. 总任务数: " + quest_range + "（含主线+支线）。\n\n"
            "【支线与主线】：主线用dependencies链串联所有任务。支线必须挂接主线节点（用dependencies引用主线ID），不能完全独立。每章2-3条支线。\n\n"
            "【坐标布局（非常重要）】：\n"
            "- 主线x: 0→2→4→6→8...，y统一为0\n"
            "- 支线x与挂接主线相同，y偏移±2.0\n"
            "- 每个任务必须提供x和y坐标\n\n"
            "【任务规范】：\n"
            "- 任务类型: item(收集/合成), advancement(进度), kill, dimension, checkmark(信息)\n"
            "- 严格使用下面的物品ID，不要编造不存在的ID\n\n"
            "JSON示例(5个任务含1支线):\n"
            '{"title":"整合包指南","chapters":[\n'
            '{"id":"ch1","title":"原版·开局","icon":"minecraft:wooden_pickaxe","quests":[\n'
            '{"id":"q1","title":"获得原木","subtitle":"空手撸树","icon":"minecraft:oak_log","tasks":[{"type":"item","target":"minecraft:oak_log","count":16}],"rewards":[{"type":"item","target":"minecraft:apple","count":4}],"shape":"square","x":0.0,"y":0.0},\n'
            '{"id":"q2","title":"制作工作台","subtitle":"4个木板合成","dependencies":["q1"],"icon":"minecraft:crafting_table","tasks":[{"type":"item","target":"minecraft:crafting_table","count":1}],"rewards":[{"type":"xp","count":10}],"shape":"square","x":2.0,"y":0.0},\n'
            '{"id":"q3","title":"石器工具","subtitle":"圆石→石镐","dependencies":["q2"],"icon":"minecraft:stone_pickaxe","tasks":[{"type":"item","target":"minecraft:stone_pickaxe","count":1}],"rewards":[{"type":"xp","count":20}],"shape":"square","x":4.0,"y":0.0},\n'
            '{"id":"q4","title":"制作熔炉","subtitle":"8圆石合成","dependencies":["q3"],"icon":"minecraft:furnace","tasks":[{"type":"item","target":"minecraft:furnace","count":1}],"rewards":[{"type":"xp","count":15}],"shape":"square","x":6.0,"y":0.0},\n'
            '{"id":"q5","title":"支线·解决食物","subtitle":"击杀动物获取食物","dependencies":["q2"],"icon":"minecraft:cooked_beef","tasks":[{"type":"item","target":"minecraft:cooked_beef","count":8}],"rewards":[{"type":"xp","count":15}],"shape":"diamond","x":2.0,"y":-2.0}\n]}\n]}\n\n'
            "要求: " + quest_range + "总任务。所有title/subtitle用中文。每个任务必须有dependencies（除第一个外）。只输出JSON，json前后不要多余内容。"
        )
    else:
        sp = (
            "You are a Minecraft modpack quest guide designer for FTB Quests. "
            "Design a VERY RICH questbook JSON.\n\n"
            "STRUCTURE: 1. Vanilla: 4-6 ch, 10-15 quests each. "
            "2. Each core mod: 1-2 ch, 10-15 quests each. "
            f"3. Total: {quest_range} quests. "
            "TASK TYPES: item/advancement/kill/dimension/checkmark. "
            "Layout: x spaced 2.0. Use ONLY the item IDs listed below.\n\n"
            "Output ONLY valid JSON."
        )
    # 构建里程碑列表
    milestones = _build_milestone_list(gen.all_mods if hasattr(gen, 'all_mods') else [])
    milestone_text = _milestone_to_prompt(milestones, lang)

    up = (
        f"{mod_list}\n\n"
        f"=== 可用命名空间 ===\n{all_ns}\n\n"
        f"{item_cat}\n\n"
        "请严格使用上面列出的物品ID。只输出JSON。\n\n"
        f"{milestone_text}"
    ) if lang == "zh" else (
        f"{mod_list}\n\n=== Namespaces ===\n{all_ns}\n\n"
        f"{item_cat}\n\n"
        "Use ONLY the IDs above. Output ONLY JSON.\n\n"
        f"{milestone_text}"
    )
    return sp + "\n\n" + up


def import_json_to_snbt(json_text, selected_mods=None, mod_folder=None,
                         progress_callback=None, output_dir=None):
    """
    导入外部JSON文本并生成SNBT文件。
    适用于用户从网页AI复制JSON的场景。
    """
    if progress_callback: progress_callback("解析JSON...", 5)
    if not json_text or not json_text.strip():
        raise Exception("JSON内容为空")

    # 创建临时生成器用于SNBT输出
    gen = QuestBookGenerator(
        api_key="", selected_mods=selected_mods or [],
        mod_folder=mod_folder, lang="zh", engine="dummy"
    )
    gen.client = None

    # 扫描物品（如果可以）
    scanned_items = gen._scan_items() if mod_folder and os.path.isdir(mod_folder) else {}

    if progress_callback: progress_callback("转换SNBT并校验...", 60)
    saved_dir = gen._save_snbt_files(json_text, scanned_items, output_dir)
    if progress_callback: progress_callback("完成!", 100)
    return saved_dir
