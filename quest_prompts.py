"""Prompt templates for staged, legacy, and browser-based generation."""

from __future__ import annotations


STAGED_SYSTEM_PROMPT = (
    "You generate concise valid JSON for FTB Quests. Follow EXACT_QUEST_COUNT. "
    "Never invent item IDs and never include markdown."
)


def milestone_to_prompt(milestones, lang="zh"):
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


def build_system_prompt(lang, quest_range="70-120"):
    """构建系统提示词（不含物品ID，可被缓存命中）"""
    if lang == "zh":
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


def build_user_prompt(lang, mod_list, all_ns, wiki_text="", item_catalog="", milestone_text=""):
    """构建用户提示词，item_catalog为空时生成不带物品ID的短版（用于缓存预热）"""
    if lang == "zh":
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


def build_stage_prompt(lang, chapter, count, existing_titles, catalog, wiki_text=""):
    title_list = ", ".join(existing_titles[-30:]) if existing_titles else "无"
    wiki_block = wiki_text[:2500] if wiki_text else ""
    if lang == "zh":
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


def build_web_prompt(lang, quest_range, mod_list, all_ns, item_cat, milestone_text=""):
    """Build the complete prompt copied to a browser-based AI."""
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
