#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AutoFTBQ AI模块 — FTB Quests SNBT生成 v4"""

import os, re, json, uuid, time
import requests

try:
    from . import mod_scanner as _ms
except ImportError:
    import mod_scanner as _ms

try:
    from . import ollama_adapter as _oa
except ImportError:
    import ollama_adapter as _oa

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
MAX_RETRIES = 3; RETRY_DELAY = 3; API_TIMEOUT = 300
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
MOD_DB = {
    "minecraft":("Minecraft","minecraft","vanilla"),
    "tconstruct":("Tinkers Construct","tconstruct","tech"),
    "botania":("Botania","botania","magic"),
    "thaumcraft":("Thaumcraft","thaumcraft","magic"),
    "twilightforest":("Twilight Forest","twilightforest","world"),
    "twilight":("Twilight Forest","twilightforest","world"),
    "betweenlands":("The Betweenlands","thebetweenlands","world"),
    "abyssalcraft":("AbyssalCraft","abyssalcraft","world"),
    "iceandfire":("Ice and Fire","iceandfire","world"),
    "lycanitesmobs":("Lycanites Mobs","lycanitesmobs","mob"),
    "mowziesmobs":("Mowzies Mobs","mowziesmobs","mob"),
    "aether":("The Aether","aether","world"),
    "galacticraft":("Galacticraft","galacticraft","tech"),
    "mekanism":("Mekanism","mekanism","tech"),
    "draconicevolution":("Draconic Evolution","draconicevolution","tech"),
    "astralsorcery":("Astral Sorcery","astralsorcery","magic"),
    "bloodmagic":("Blood Magic","bloodmagic","magic"),
    "bewitchment":("Bewitchment","bewitchment","magic"),
    "arsnouveau":("Ars Nouveau","arsnouveau","magic"),
    "ars":("Ars Nouveau","arsnouveau","magic"),
    "roots":("Roots","roots","magic"),
    "embers":("Embers","embers","tech"),
    "naturesaura":("Natures Aura","naturesaura","magic"),
    "psi":("Psi","psi","magic"),
    "apotheosis":("Apotheosis","apotheosis","magic"),
    "create":("Create","create","tech"),
    "immersiveengineering":("Immersive Engineering","immersiveengineering","tech"),
    "immersive":("Immersive Engineering","immersiveengineering","tech"),
    "thermalexpansion":("Thermal Expansion","thermalexpansion","tech"),
    "thermal":("Thermal Series","thermal","tech"),
    "enderio":("Ender IO","enderio","tech"),
    "rftools":("RFTools","rftools","tech"),
    "mysticalagriculture":("Mystical Agriculture","mysticalagriculture","magic"),
    "mysticalag":("Mystical Agriculture","mysticalagriculture","magic"),
    "jei":("Just Enough Items","jei","utility"),
    "nei":("Not Enough Items","nei","utility"),
    "journeymap":("JourneyMap","journeymap","utility"),
    "xaerominimap":("Xaeros Minimap","xaerominimap","utility"),
    "xaero":("Xaeros Minimap","xaerominimap","utility"),
    "waystones":("Waystones","waystones","utility"),
    "ironchest":("Iron Chests","ironchest","utility"),
    "ironchests":("Iron Chests","ironchest","utility"),
    "storagedrawers":("Storage Drawers","storagedrawers","utility"),
    "sophisticatedbackpacks":("Sophisticated Backpacks","sophisticatedbackpacks","utility"),
    "refinedstorage":("Refined Storage","refinedstorage","utility"),
    "appliedenergistics":("Applied Energistics 2","appliedenergistics2","utility"),
    "appliedenergistics2":("Applied Energistics 2","appliedenergistics2","utility"),
    "ae2":("Applied Energistics 2","appliedenergistics2","utility"),
    "cyclic":("Cyclic","cyclic","utility"),
    "quark":("Quark","quark","utility"),
    "randomthings":("Random Things","randomthings","utility"),
    "openblocks":("OpenBlocks","openblocks","utility"),
    "farmersdelight":("Farmers Delight","farmersdelight","food"),
    "harvestcraft":("Pams HarvestCraft","harvestcraft","food"),
    "pamsharvestcraft":("Pams HarvestCraft","harvestcraft","food"),
    "chisel":("Chisel","chisel","decor"),
    "chiselsandbits":("Chisels & Bits","chiselsandbits","decor"),
    "biomesoplenty":("Biomes O Plenty","biomesoplenty","world"),
    "bop":("Biomes O Plenty","biomesoplenty","world"),
    "industrialcraft":("IndustrialCraft 2","ic2","tech"),
    "ic2":("IndustrialCraft 2","ic2","tech"),
    "buildcraft":("BuildCraft","buildcraft","tech"),
    "forestry":("Forestry","forestry","tech"),
    "railcraft":("Railcraft","railcraft","tech"),
    "stevescarts":("Steves Carts","stevescarts","tech"),
    "actuallyadditions":("Actually Additions","actuallyadditions","tech"),
    "extrautils":("Extra Utilities 2","extrautils2","tech"),
    "extrautilities":("Extra Utilities 2","extrautils2","tech"),
    "bigreactors":("Big Reactors","bigreactors","tech"),
    "extreme":("Extreme Reactors","bigreactors","tech"),
    "nuclearcraft":("NuclearCraft","nuclearcraft","tech"),
    "rftoolsdimensions":("RFTools Dimensions","rftoolsdim","tech"),
    "environmentaltech":("Environmental Tech","environmentaltech","tech"),
    "solarflux":("Solar Flux Reborn","solarflux","tech"),
    "fluxnetworks":("Flux Networks","fluxnetworks","tech"),
    "projecte":("ProjectE","projecte","tech"),
    "equivalentexchange":("ProjectE","projecte","tech"),
    "electroblob":("Electroblobs Wizardry","ebwizardry","magic"),
    "ebwizardry":("Electroblobs Wizardry","ebwizardry","magic"),
    "mahoutsukai":("Mahou Tsukai","mahoutsukai","magic"),
    "manametal":("ManaMetal","manametal","magic"),
    "witchery":("Witchery","witchery","magic"),
    "gravestone":("GraveStone Mod","gravestone","utility"),
    "tombstone":("Corail Tombstone","tombstone","utility"),
    "corail":("Corail Tombstone","tombstone","utility"),
}

CAT_LABEL = {"vanilla":"原版","tech":"科技","magic":"魔法","world":"维度/Boss","mob":"生物","utility":"辅助","food":"食物","decor":"装饰","unknown":"未知"}

def _parse_mod(filename, filepath=None):
    base = filename
    for ext in (".jar",".zip",".JAR",".ZIP"):
        if base.endswith(ext): base = base[:-len(ext)]; break
    base_ns = base.lower().replace("-","").replace("_","").replace(" ","")
    for key,(name,mid,cat) in MOD_DB.items():
        if key in base_ns:
            size = os.path.getsize(filepath) if filepath else 0
            return {"filename":filename,"mod_name":name,"mod_id":mid,"category":cat,"size":size}
    cleaned = re.sub(r'[-_]\d+[.]\d+[.]\d+.*$','',base)
    cleaned = re.sub(r'[-_](mc|MC|forge|fabric|release|beta|alpha|r\d+|universal|sources|deobf).*$','',cleaned,flags=re.IGNORECASE)
    cleaned = re.sub(r'[-_]\d+$','',cleaned).strip("-_ ")
    if not cleaned or len(cleaned)<2: cleaned = base
    mod_id = re.sub(r'[^a-z0-9_]','',cleaned.lower().replace(" ","_")) or re.sub(r'[^a-zA-Z0-9]','',base)[:20].lower()
    mod_name = re.sub(r'\s+',' ',re.sub(r'[-_]',' ',cleaned)).strip().title()
    size = os.path.getsize(filepath) if filepath else 0
    return {"filename":filename,"mod_name":mod_name,"mod_id":mod_id,"category":"unknown","size":size}

def scan_mod_folder(folder_path):
    mods = []
    try:
        for f in sorted(os.listdir(folder_path)):
            if f.lower().endswith((".jar",".zip")):
                fp = os.path.join(folder_path, f)
                info = _parse_mod(f, fp)
                if info: mods.append(info)
    except Exception as e: print(f"[ERROR] {e}")
    mods.sort(key=lambda m: -m["size"])
    return mods

def classify_mods(mods):
    progression, utility, unknown = [], [], []
    for m in mods:
        cat = m.get("category","unknown")
        if cat in ("tech","magic","world","mob"): progression.append(m)
        elif cat in ("utility","food","decor"): utility.append(m)
        else: unknown.append(m)
    return progression, utility, unknown

# ════════════════════════════════════════════════════════
class DeepSeekClient:
    def __init__(self, api_key):
        self.headers = {"Authorization":f"Bearer {api_key.strip()}","Content-Type":"application/json"}
    def chat(self, messages, temperature=0.7, max_tokens=8192):
        payload = {"model":DEEPSEEK_MODEL,"messages":messages,"temperature":temperature,"max_tokens":max_tokens,"stream":False}
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.post(DEEPSEEK_API_URL,json=payload,headers=self.headers,timeout=API_TIMEOUT)
                if resp.status_code==200: return resp.json()["choices"][0]["message"]["content"]
                elif resp.status_code==401: raise Exception("API Key无效，请检查后重试")
                elif resp.status_code==429: time.sleep(RETRY_DELAY*(attempt+1)*2)
                elif resp.status_code>=500: time.sleep(RETRY_DELAY*(attempt+1))
                else: raise Exception(f"API错误 {resp.status_code}: {resp.text[:200]}")
            except requests.exceptions.Timeout:
                if attempt==MAX_RETRIES-1: raise Exception("请求超时，请检查网络后重试")
            except requests.exceptions.ConnectionError: raise Exception("网络错误，无法连接到DeepSeek API")
            except Exception as e:
                if "API Key" in str(e) or "网络" in str(e): raise
                if attempt==MAX_RETRIES-1: raise
                time.sleep(RETRY_DELAY)
        raise Exception("已达最大重试次数")

# ════════════════════════════════════════════════════════
class QuestBookGenerator:
    def __init__(self, api_key=None, selected_mods=None, mod_folder=None,
                 progress_callback=None, lang="zh", engine="deepseek",
                 ollama_model=None):
        # 根据引擎创建客户端
        self.engine = engine
        if engine == "ollama":
            model = ollama_model or "qwen2.5-coder:7b"
            self.client = _oa.OllamaClient(model=model)
        else:
            self.client = DeepSeekClient(api_key or "")
        self.all_mods = selected_mods or []
        self.mod_folder = mod_folder
        self.cb = progress_callback
        self.lang = lang
        self.prog_mods, self.util_mods, self.unk = classify_mods(selected_mods or [])
        self._all_items = None  # 扫描结果缓存

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

    def generate(self):
        self._progress("分析选中的Mod列表...",5)
        mod_list = self._build_mod_list()
        all_ns = self._build_all_ns()

        # 扫描真实物品ID并构建目录
        self._progress("扫描Mod中的物品ID...",10)
        scanned_items = self._scan_items()
        item_catalog = _ms.build_item_catalog_for_prompt(scanned_items, self.all_mods)

        self._progress("生成丰富的任务书JSON (含支线/主线)...",15)
        quest_json_text = self._generate_questbook(mod_list, all_ns, item_catalog)

        self._progress("解析并校验物品ID...",80)
        output_dir = self._save_snbt_files(quest_json_text, scanned_items)
        self._progress("完成!",100)
        return output_dir

    def _build_mod_list(self):
        lines = ["=== 核心Mod (有玩法/进度) ==="]
        for i,m in enumerate(self.prog_mods,1):
            cat_cn = CAT_LABEL.get(m.get("category","unknown"), m.get("category","unknown"))
            lines.append(f"{i}. {m['mod_name']} (modid:{m['mod_id']}, 类别:{cat_cn})")
        if self.util_mods:
            lines.append("\n=== 辅助Mod (工具/存储/食物) ===")
            for i,m in enumerate(self.util_mods,1):
                lines.append(f"{i}. {m['mod_name']} (modid:{m['mod_id']})")
        if self.unk:
            lines.append("\n=== 未分类Mod ===")
            for i,m in enumerate(self.unk,1):
                lines.append(f"{i}. {m['mod_name']} (modid:{m['mod_id']})")
        return "\n".join(lines)

    def _build_all_ns(self):
        ns = {"minecraft"}
        for m in self.all_mods: ns.add(m['mod_id'])
        return ", ".join(sorted(ns)[:50])

    def _generate_questbook(self, mod_list, all_ns, item_catalog=""):
        if self.lang == "zh":
            sp = (
                "你是Minecraft整合包「任务指南」设计师。为FTB Quests设计一份非常丰富的任务书JSON。\n\n"
                "【核心定位】：这是一份「教程指南」，帮助玩家体验每个Mod的全部玩法内容。\n"
                "不是编故事，而是有目的性地引导玩家一步步上手。\n\n"
                "【结构要求】：\n"
                "1. 原版MC部分覆盖完整流程，4-6章，每章10-15个任务。\n"
                "   包含：开局→石器→铁器→钻石→附魔→下界→酿造→末地。\n"
                "2. 每个核心Mod独立设1-2章（内容多的Mod放2章），每章10-15个任务。\n"
                "   覆盖Mod从入门到精通的所有内容。\n"
                "3. 辅助Mod在奖励中引用其物品，不做单独大量章节。\n"
                "4. 总任务数目标：70-120个任务。\n\n"
                "【支线与主线设计】：\n"
                "- 主线：必须有dependencies链，玩家按顺序完成。\n"
                "- 支线：不使用dependencies（或依赖主线中的某个节点），玩家可以随时做。\n"
                "- 每个章节至少有2-3条支线任务。\n"
                "- 支线任务是主线的补充（如：主线让你做基础机器，支线让你升级机器）。\n\n"
                "【任务设计规范】：\n"
                "- 每个任务: title, subtitle(玩法提示), tasks(目标), rewards(奖励)\n"
                "- 任务类型: item(收集/合成), advancement(进度), kill, dimension, checkmark(仅信息类)\n"
                "- 布局: x间隔2.0水平展开，相关任务同y，分支任务偏离y\n"
                "- 物品ID只能用minecraft:或上述已安装Mod的命名空间\n"
                "- 奖励按阶段合理分配\n\n"
                "JSON示例(含主线+支线):\n"
                '{"title":"整合包指南","chapters":[\n'
                '{"id":"ch_wood","title":"原版·木石时代","icon":"minecraft:wooden_pickaxe","quests":[\n'
                '{"id":"q_log","title":"获得原木","subtitle":"空手撸树获得原木","icon":"minecraft:oak_log","tasks":[{"type":"item","target":"minecraft:oak_log","count":16}],"rewards":[{"type":"item","target":"minecraft:apple","count":4}],"shape":"square","x":0,"y":0},\n'
                '{"id":"q_table","title":"制作工作台","subtitle":"用4个木板合成","dependencies":["q_log"],"icon":"minecraft:crafting_table","tasks":[{"type":"item","target":"minecraft:crafting_table","count":1}],"rewards":[{"type":"xp","count":10}],"shape":"square","x":2.0,"y":0},\n'
                '{"id":"q_stone","title":"石器工具","subtitle":"圆石→石镐/石斧/石锹","dependencies":["q_table"],"icon":"minecraft:stone_pickaxe","tasks":[{"type":"item","target":"minecraft:stone_pickaxe","count":1}],"rewards":[{"type":"xp","count":20}],"shape":"square","x":4.0,"y":0},\n'
                '{"id":"q_branch_food","title":"支线·解决食物","subtitle":"击杀动物获取食物","icon":"minecraft:cooked_beef","tasks":[{"type":"item","target":"minecraft:cooked_beef","count":8}],"rewards":[{"type":"xp","count":15}],"shape":"diamond","x":2.0,"y":-2.0}\n'
                ']}\n]}\n\n'
                "要求: 70-120总任务。所有title/subtitle用中文。只输出JSON。"
            )
            up = (
                f"{mod_list}\n\n"
                f"=== 可用物品命名空间 ===\n{all_ns}\n\n"
                f"{item_catalog}\n\n"
                "请设计一份非常丰富的任务指南JSON。注意：\n"
                "- 覆盖每个Mod的完整玩法，从入门到精通\n"
                "- 必须包含支线任务（无dependencies的独立任务）\n"
                "- 总任务数70-120\n"
                "- 严格使用上面列出的物品ID，不要编造不存在的ID\n"
                "- 告诉玩家每一步做什么、用什么做、做完得到什么"
            )
        else:
            sp = (
                "You are a Minecraft modpack guide designer for FTB Quests. "
                "Design a VERY RICH questbook JSON.\n\n"
                "POSITIONING: Tutorial guide that helps players experience ALL content of each mod.\n\n"
                "STRUCTURE:\n"
                "1. Vanilla: 4-6 chapters, 10-15 quests each. Wood→Stone→Iron→Diamond→Enchant→Nether→Brew→End.\n"
                "2. Each core mod: 1-2 chapters, 10-15 quests each. Cover from beginner to master.\n"
                "3. Utility mods referenced in rewards only.\n"
                "4. Total: 70-120 quests.\n\n"
                "MAIN & BRANCH LINES:\n"
                "- Main: chained via dependencies.\n"
                "- Branches: no dependencies (or depend on 1 main node), players can do anytime.\n"
                "- Each chapter: 2-3 branch quests minimum.\n\n"
                "TASK RULES: item/advancement/kill/dimension/checkmark. Item IDs: minecraft: or listed namespaces.\n"
                "Layout: x spaced 2.0 horizontal. Reward balanced by stage.\n\n"
                "Output ONLY valid JSON, 70-120 quests total."
            )
            up = (
                f"{mod_list}\n\n=== Allowed namespaces ===\n{all_ns}\n\n"
                f"{item_catalog}\n\n"
                "Design a very rich questbook JSON with branches and main lines. "
                "Use ONLY the item IDs listed above."
            )
        max_tok = 40960 if self.engine == "ollama" else 32768
        return self.client.chat([{"role":"system","content":sp},{"role":"user","content":up}], max_tokens=max_tok, temperature=0.5)

    def _save_snbt_files(self, quest_json_text, scanned_items=None):
        SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.join(SCRIPT_DIR, OUTPUT_DIR_NAME)
        os.makedirs(base_dir, exist_ok=True)
        chapters_dir = os.path.join(base_dir, "chapters")
        os.makedirs(chapters_dir, exist_ok=True)
        rt_dir = os.path.join(base_dir, "reward_tables")
        os.makedirs(rt_dir, exist_ok=True)
        with open(os.path.join(base_dir,"ai_raw_output.txt"),"w",encoding="utf-8") as f:f.write(quest_json_text)
        json_text = self._extract_json(quest_json_text)
        ai_data = None
        for attempt in range(4):
            try:
                ai_data = json.loads(json_text); break
            except json.JSONDecodeError:
                if attempt==0: json_text = re.sub(r',\s*}','}',re.sub(r',\s*]',']',json_text))
                elif attempt==1:
                    d = sum(1 for c in json_text if c=='{') - sum(1 for c in json_text if c=='}')
                    if d>0: json_text += '\n'+'}'*d
                elif attempt==2:
                    idx = json_text.rfind('\n    }\n')
                    if idx>0: json_text = json_text[:idx]+'\n  ]\n}'
        if ai_data is None:
            with open(os.path.join(base_dir,"parse_error.txt"),"w",encoding="utf-8") as f:f.write("=== Raw ===\n"+json_text)
            raise Exception("AI返回无效JSON。请检查 parse_error.txt")

        # 校验物品ID
        if scanned_items:
            valid_count, invalid_list = _ms.validate_item_ids(ai_data, scanned_items)
            # 写入校验报告
            report_lines = [
                "=== 物品ID校验报告 ===",
                f"有效物品ID: {valid_count}",
                f"无效/未验证物品ID: {len(invalid_list)}",
            ]
            if invalid_list:
                report_lines.append("\n--- 无效物品ID详情 ---")
                for item in invalid_list:
                    report_lines.append(f"  {item['id']} — {item['location']}")
                    report_lines.append(f"    建议: {item['suggestion']}")
            else:
                report_lines.append("\n所有物品ID均已通过校验 ✓")
            report_path = os.path.join(base_dir, "id_validation_report.txt")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write("\n".join(report_lines))
            print(f"[VALIDATION] {valid_count} valid, {len(invalid_list)} invalid — report saved")

        return self._write_snbt_files(base_dir, ai_data)

    def _write_snbt_files(self, base_dir, ai_data):
        chapters_dir = os.path.join(base_dir, "chapters")
        chapters_data = ai_data.get("chapters",[])
        title = ai_data.get("title","Quest Book")
        chapter_groups = []
        qid2uid = {}
        for ch in chapters_data:
            for q in ch.get("quests",[]):
                r = q.get("id",_uid())
                if r not in qid2uid: qid2uid[r] = _uid().upper()
        for chi, ch in enumerate(chapters_data):
            chu = _uid().upper()
            cht = ch.get("title",f"Chapter {chi+1}")
            chi_icon = ch.get("icon","minecraft:book")
            qents = []
            for qi, q in enumerate(ch.get("quests",[])):
                rid = q.get("id",f"q_{chi}_{qi}")
                qu = qid2uid.get(rid)
                if not qu: continue
                qt = q.get("title",f"Quest {qi+1}")
                qs = q.get("subtitle","")
                qi_icon = q.get("icon","minecraft:book")
                qde = q.get("description",[])
                if isinstance(qde,str): qde = [qde]
                tasks = []
                for t in q.get("tasks",[]):
                    tid = _uid().upper(); tt = t.get("type","checkmark")
                    tg = t.get("target",""); cnt = int(t.get("count",1))
                    to = {"id":tid,"type":tt}
                    if tt == "item":
                        to["item"] = {"id":_fx(tg),"Count":_B(1),"tag":{}}
                        to["count"] = _L(cnt) if cnt>10 else cnt
                        to["consume_items"] = False
                    elif tt == "advancement":
                        to["advancement"] = tg or "minecraft:story/root"
                        to["criterion"] = ""
                    elif tt == "kill":
                        to["entity"] = tg or "minecraft:zombie"
                        to["value"] = _L(cnt) if cnt>10 else cnt
                    elif tt == "dimension": to["dimension"] = tg or "minecraft:overworld"
                    elif tt == "checkmark": to["value"] = 1
                    tasks.append(to)
                if not tasks: tasks.append({"id":_uid().upper(),"type":"checkmark","value":1})
                rewards = []
                for r in q.get("rewards",[]):
                    ri = _uid().upper(); rt = r.get("type","item")
                    rg = r.get("target",""); cnt = int(r.get("count",1))
                    ro = {"id":ri,"type":rt}
                    if rt == "item":
                        ro["item"] = {"id":_fx(rg),"Count":_B(1),"tag":{}}
                        ro["count"] = cnt
                    elif rt == "command": ro["command"] = rg or "/say Hello"
                    elif rt == "xp": ro["xp_amount"] = cnt
                    elif rt == "xp_levels": ro["xp_levels"] = cnt
                    rewards.append(ro)
                deps = q.get("dependencies",[])
                if isinstance(deps,str): deps = [deps]
                du = [qid2uid[d] for d in deps if d in qid2uid]
                sh = q.get("shape","square")
                if sh not in ("square","diamond","hexagon","gear"): sh = "square"
                xv = _D(round(qi*2.0, 1))
                yv = _D(round((qi%3)*1.5 - 1.5, 1))
                qo = {"id":qu,"title":qt,"icon":qi_icon,"x":xv,"y":yv,"shape":sh,"dependencies":du,"tasks":tasks,"rewards":rewards}
                if qs: qo["subtitle"] = qs
                if qde: qo["description"] = qde
                qents.append(qo)
            cho = {
                "default_hide_dependency_lines":False,"default_quest_shape":"","filename":chu,
                "group":chu,"icon":chi_icon,"id":chu,"images":[],"order_index":chi,
                "quest_links":[],"quests":qents,"title":cht,
            }
            with open(os.path.join(chapters_dir,f"{chu}.snbt"),"w",encoding="utf-8") as f:f.write(to_snbt(cho))
            chapter_groups.append({"id":chu,"title":cht})
        with open(os.path.join(base_dir,"chapter_groups.snbt"),"w",encoding="utf-8") as f:f.write(to_snbt({"chapter_groups":chapter_groups}))
        ds = {
            "default_autoclaim_rewards":"disabled","default_consume_items":False,
            "default_quest_disable_jei":False,"default_quest_shape":"circle",
            "default_reward_team":False,"detection_delay":20,"disable_gui":False,
            "drop_loot_crates":False,"emergency_items_cooldown":300,"grid_scale":0.5,
            "icon":"minecraft:book","lock_message":"",
            "loot_crate_no_drop":{"boss":0,"monster":600,"passive":4000},
            "pause_game":False,"progression_mode":"linear","title":title,"version":13,
        }
        with open(os.path.join(base_dir,"data.snbt"),"w",encoding="utf-8") as f:f.write(to_snbt(ds))
        return base_dir

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
        if last_good > len(raw) * 0.7:  # 只在大部完整时才截断修复
            raw = raw[:last_good+1]  # 保留那个 }
            # 补上缺失的闭合
            d = sum(1 for c in raw if c == '{') - sum(1 for c in raw if c == '}')
            a = sum(1 for c in raw if c == '[') - sum(1 for c in raw if c == ']')
            raw += ']'*a + '}'*d
            return raw
        return raw

def _fx(raw):
    if not raw: return "minecraft:stone"
    raw = str(raw).strip()
    return raw if ":" in raw else f"minecraft:{raw}"
def _uid(): return uuid.uuid4().hex[:16]

def generate_quest_book(api_key=None, selected_mods=None, mod_folder=None,
                         progress_callback=None, lang="zh", engine="deepseek",
                         ollama_model=None):
    if progress_callback: progress_callback("分析选中的Mod...",3)
    if not selected_mods: raise Exception("未选中任何Mod。")
    return QuestBookGenerator(
        api_key=api_key, selected_mods=selected_mods, mod_folder=mod_folder,
        progress_callback=progress_callback, lang=lang, engine=engine,
        ollama_model=ollama_model
    ).generate()
