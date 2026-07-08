# AutoFTBQ — MC FTB任务书自动生成器

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)
![License](https://img.shields.io/badge/License-GPL--3.0-green.svg)
![Version](https://img.shields.io/badge/Version-1.3.1-orange.svg)
![Downloads](https://img.shields.io/github/downloads/Bluelgin/AutoFTBQ/total?color=blue&label=Downloads)

基于 AI 自动生成 Minecraft [FTB Quests](https://www.curseforge.com/minecraft/mc-mods/ftb-quests-forge) 任务书的桌面工具。

---

## ✨ 功能

- **一键生成**：选择 Mod 文件夹 → 勾选 Mod → AI 自动生成完整任务指南（70-120 个任务）
- **双引擎支持**：DeepSeek API（在线）或 Ollama（本地模型），可自由切换
- **启动弹窗选择模式**：API 自动生成 / 导入 JSON，选中后不可更改，UI 简洁分离
- **两种工作模式**：
  - **🤖 API 自动生成模式** — AI 直接生成 JSON 并转为 SNBT
  - **📄 导入 JSON 模式** — 保存提示词+物品ID文件 → 上传网页 AI → 粘贴 JSON → 转为 SNBT（仅建议 Mod 数量 100 以内的整合包使用）
- **真实物品ID**：自动扫描 .jar/.zip 文件提取真实物品ID，确保图标正确显示
- **主线+支线**：AI 自动设计合理的主线依赖链和支线任务结构
- **智能坐标布局**：主线任务横向排列，支线任务挂接主线并上下偏移
- **ID 校验**：生成后自动校验所有物品ID有效性，出具详细报告
- **全量物品 ID 提示**：prompt 中列出全部物品 ID 不再截断，确保 AI 生成图标正确率
- **自定义输出目录**：两种模式均支持指定输出路径，留空则保存到默认 `questbook_output/` 文件夹，路径会随配置持久化
- **内置 151 个知名 Mod 信息库**：自动识别 Tinkers、Create、Botania、Mekanism 等并分类
- **中英文双语界面**：一键切换

---

## 📦 安装

### 方式一：源码运行（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/Bluelgin/AutoFTBQ.git
cd AutoFTBQ

# 2. 安装依赖（仅需 requests）
pip install requests

# 3. 运行
python main.py
```

---

## 🔧 详细教程

### 教程 A：API 自动生成模式（DeepSeek）

本模式由 AI 直接生成完整的任务书 JSON，然后自动转换为 SNBT。适合有 DeepSeek API Key 的用户。

#### 步骤 1：获取 DeepSeek API Key

1. 打开 [platform.deepseek.com](https://platform.deepseek.com) 并注册/登录
2. 进入「API Keys」页面，点击「创建 API Key」
3. 复制生成的 Key（格式为 `sk-xxxxxxxx`）
4. 注意：DeepSeek API 为付费服务，每次生成约需 ¥1

#### 步骤 2：启动软件并选择模式

双击运行 `main.py` 或 `AutoFTBQ.exe`，在启动弹窗中选择 **「🤖 API 自动生成」**。

#### 步骤 3：填写配置

- **API Key**：粘贴步骤 1 获取的 Key
- **AI 引擎**：默认选择 DeepSeek API。如果电脑上安装了 [Ollama](https://ollama.com)，软件会自动检测并优先切换为本地引擎（免费）
- **Mod 文件夹**：点击「浏览」，选择你的 Minecraft 整合包中的 `mods` 文件夹。例如：
  ```
  D:\Minecraft\.minecraft\versions\MyModpack\mods
  ```
- **输出目录**（可选）：指定任务书输出位置，留空则输出到软件目录下的 `questbook_output/`

#### 步骤 4：选择 Mod

点击 **「选择 Mod」** 按钮，在弹出的窗口中勾选需要生成任务的 Mod。

- 窗口顶部会显示检测到的 Mod 数量和每个 Mod 的类别（科技/魔法/维度/辅助等）
- 建议只勾选有实际玩法内容的核心 Mod（科技类、魔法类、维度类）
- 辅助类 Mod（如 JEI、JourneyMap）会自动在任务的奖励中引用其物品，无需单独勾选
- 可以点击「全选」快速选择所有 Mod

#### 步骤 5：生成任务书

1. 点击 **「生成任务书」** 按钮
2. 在弹出的确认窗口中确认选中的 Mod 数量
3. 等待 2-4 分钟（取决于 Mod 数量和 AI 响应速度）
4. 进度条显示当前状态：
   - 分析 Mod 列表
   - 扫描物品 ID（首次约 10-30 秒，有缓存机制）
   - AI 生成任务书 JSON
   - 转换 SNBT 并校验物品 ID
5. 生成完成后自动弹出输出文件夹

#### 步骤 6：在游戏中使用

将生成的 `questbook_output/` 文件夹中的所有内容复制到：

```
.minecraft\versions\你的整合包\config\ftbquests\quests\
```

重进存档后，打开 FTB Quests 任务书即可看到生成的任务线。

---

### 教程 B：API 自动生成模式（Ollama 本地）

如果你不想付费使用 DeepSeek API，可以使用本地大模型。

#### 准备工作：安装 Ollama

1. 从 [ollama.com](https://ollama.com/download) 下载并安装 Ollama
2. 打开命令行，拉取推荐模型：
   ```bash
   # 推荐（中文代码能力最强）
   ollama pull qwen2.5-coder:7b

   # 备选
   ollama pull deepseek-coder:6.7b
   ollama pull qwen2.5:7b
   ```
3. 确保 Ollama 在后台运行（任务栏应有 Ollama 图标）

#### 使用流程

1. 启动 AutoFTBQ → 选择「API 自动生成」
2. 软件会自动检测到 Ollama 并切换引擎，显示 `✓ 模型: qwen2.5-coder:7b`
3. 无需填写 API Key（Ollama 模式下该输入框会自动隐藏）
4. 后续步骤与教程 A 的步骤 3-6 完全一致

> **注意**：本地模型生成质量可能略低于 DeepSeek，但完全免费。`qwen2.5-coder:7b` 需要约 8GB 显存/内存。

---

### 教程 C：导入模式（无 API Key）

如果你没有 API Key 也没有安装 Ollama，可以使用网页 AI（如 DeepSeek Chat）来生成任务书。

#### 步骤 1：准备提示词文件

1. 启动 AutoFTBQ → 选择「📄 导入 JSON」
2. 选择 Mod 文件夹并勾选 Mod
3. 点击 **「📤 保存提示词文件」**
4. 选择保存位置，软件会生成一个包含完整物品列表和提示词的 `.txt` 文件

#### 步骤 2：使用网页 AI 生成 JSON

1. 打开 [chat.deepseek.com](https://chat.deepseek.com)（或 ChatGPT、通义千问等）
2. 上传刚才保存的 `.txt` 文件（点击输入框旁的 📎 附件图标）
3. 发送消息：「请根据文件中的信息设计任务书 JSON」
4. 等待 AI 返回 JSON 内容
5. **复制全部 JSON**（从 `{` 开始到 `}` 结束）

#### 步骤 3：导入 JSON 生成 SNBT

1. 回到 AutoFTBQ 的导入模式界面
2. 将复制的 JSON **粘贴**到输入框中
3. 点击 **「📄 粘贴并生成 SNBT」**
4. 软件会自动解析 JSON、校验物品 ID、转换为 SNBT 格式
5. 生成完成后自动打开输出文件夹

---

## 📁 输出结构

```
questbook_output/
├── data.snbt                    # 任务书全局配置
│                                #   包含标题、图标、网格比例(0.5d)、进度模式(linear)
│                                #   default_consume_items: false（不消耗物品）
│                                #   default_hide_dependency_lines: false（连线可见）
├── chapter_groups.snbt          # 章节列表（每个章节的 ID 和标题）
├── chapters/                    # 各章节 SNBT 文件
│   ├── XXXXX.snbt               # 每个文件含 quests 列表 + quest_links
│   │                            #   每个 quest 包含: id, title, icon, x/y坐标,
│   │                            #   shape, dependencies, tasks, rewards
│   └── ...
├── reward_tables/               # 奖励表（预留）
├── ai_raw_output.txt            # AI 原始输出（调试用）
└── id_validation_report.txt     # 物品ID校验报告
```

生成的 SNBT 文件放入 FTB Quests 的 `config/ftbquests/quests/` 目录即可在游戏中使用。

---

## 🛠️ 项目结构

| 文件 | 行数 | 说明 |
|------|------|------|
| `main.py` | ~900 | Tkinter GUI 主界面 — 启动模式弹窗、双引擎切换、输出目录、UI 交互、线程管理 |
| `ai_module.py` | ~970 | AI 核心模块 — DeepSeek/Ollama API、三级管道(缓存预热+自动续写)、JSON 合并、SNBT 生成、151 个 Mod 库 |
| `mod_scanner.py` | ~360 | 物品ID扫描器 — JAR/ZIP 解压、模型/配方/语言文件扫描、全量物品目录生成、缓存、ID 校验 |
| `ollama_adapter.py` | ~110 | Ollama 适配器 — 自动检测、模型推荐、HTTP API（带截断检测） |
| `mcwiki_crawler.py` | ~250 | MC百科 Wiki 爬虫 — 并发抓取 Mod 页面，提取物品/方块信息增强数据 |
| `config.example.json` | 4 | 配置模板 — API Key + Mod 文件夹 + 输出目录 |
| `start.bat` | - | Windows 一键启动脚本 |

---

## 📝 技术实现

### AI 任务生成流程

```
选择 Mod → 分类（核心/辅助/未分类）
         → 扫描 JAR 文件提取真实物品ID（带缓存）
         → Cache Warmup（预热DeepSeek前缀缓存）
         → 构建 Prompt（Mod 列表 + 完整物品目录 + 坐标布局规范）
         → 调用 DeepSeek/Ollama API（自动续写截断输出）
         → 智能解析 JSON（多段合并，自动修复截断/缺失括号）
         → 提取 x/y 坐标（优先使用 AI 指定坐标）
         → 转为 FTB Quests 标准 SNBT 格式
         → 校验物品ID → 输出报告
```

### 物品ID扫描原理

```
JAR/ZIP 文件 → 解压读取
  ├── assets/<modid>/models/item/   → 物品模型JSON → 提取物品ID
  ├── assets/<modid>/models/block/  → 方块模型JSON → 提取方块ID
  ├── assets/<modid>/lang/zh_cn.json → 加载中文显示名
  ├── assets/<modid>/lang/en_us.json → 加载英文显示名
  └── data/<modid>/recipes/        → 合成配方 → 补充遗漏的物品ID
```

### SNBT 格式

生成的 SNBT 文件严格遵循 FTB Quests 官方格式：
- 坐标使用 double 类型标注（如 `0.0d`、`-2.5d`）
- task 的 item 使用 flat string `"mod:id"`（简单物品）或 `{Count:1, id:"mod:id", tag:{Damage:0}}`（复杂物品）
- rewards 的 count 字段仅在非 1 时出现
- `quest_links` 留空 — FTB Quests 自动根据 dependencies 绘制连线
- `default_hide_dependency_lines: false` — 依赖线可见

### 坐标布局策略

| 任务类型 | x 坐标 | y 坐标 | 说明 |
|---------|--------|--------|------|
| 主线任务（无坐标） | 0, 2, 4, 6... | 0.0 | 自动横向排列 |
| 有依赖任务（无坐标） | 跟随依赖 + 2.0 | 跟随依赖 | 智能偏移 |
| AI 指定坐标 | 使用 AI 指定的值 | 使用 AI 指定的值 | 尊重 AI 布局 |

### 内置 Mod 数据库覆盖

| 类别 | Mod |
|------|-----|
| 科技 | Create, Mekanism, Thermal, EnderIO, Immersive Engineering, BuildCraft, IC2, AE2, Refined Storage, RFTools, Galacticraft, NuclearCraft, BigReactors, Flux Networks, ProjectE... |
| 魔法 | Botania, Thaumcraft, BloodMagic, ArsNouveau, Psi, AstralSorcery, Bewitchment, Electroblob's Wizardry, MahouTsukai, Roots, Embers, NaturesAura... |
| 维度/Boss | TwilightForest, The Betweenlands, The Aether, Ice&Fire, Biomes O' Plenty... |
| 生物 | LycanitesMobs, MowziesMobs... |
| 辅助 | JEI, JourneyMap, Waystones, IronChests, StorageDrawers, SophisticatedBackpacks, Quark, Cyclic, OpenBlocks, RandomThings... |
| 食物 | FarmersDelight, PamsHarvestCraft... |
| 装饰 | Chisel, Chisels&Bits... |

---

## ⚠️ 注意事项

- **Python 版本**：需要 Python 3.10 或更高版本
- **依赖**：仅需 `requests` 库（`pip install requests`）
- **DeepSeek API** 为付费服务（约 ¥1/次生成），需自行前往 [platform.deepseek.com](https://platform.deepseek.com) 获取 Key
- **Ollama 本地**完全免费，推荐模型 `qwen2.5-coder:7b`（需约 8GB 显存/内存）
- 首次扫描 JAR 文件需要 10-30 秒，后续使用缓存机制秒开
- 生成的 SNBT 需要 FTB Quests mod 加载
- 如果 Mod 不在内置数据库中，软件会自动推测其 modid（基于文件名）

---

## 📄 许可证

GNU General Public License v3.0 — 详见 [LICENSE](LICENSE) 文件。

任何引用、修改、分发本代码的项目也必须以 GPL-3.0 协议开源。

## 👤 作者

**Taki** ([@Bluelgin](https://github.com/Bluelgin))

---

Powered by [DeepSeek AI](https://deepseek.com) / [Ollama](https://ollama.com)
