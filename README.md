# AutoFTBQ

一个帮你把 Minecraft 整合包变成 FTB Quests 任务书的小工具。

你只需要选择整合包或 `mods` 文件夹，AutoFTBQ 会扫描 Mod、物品、配方和部分 KubeJS 内容，再交给 AI 规划任务，最后输出可以放进 FTB Quests 的 SNBT 文件。

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)
![License](https://img.shields.io/badge/License-GPL--3.0-green.svg)
![Version](https://img.shields.io/badge/Version-1.3.9-orange.svg)
[![Downloads](https://img.shields.io/github/downloads/Bluelgin/AutoFTBQ/total?color=blue&label=Downloads)](https://github.com/Bluelgin/AutoFTBQ/releases)

## 先说它能做什么

- 根据 Mod 的内容自动规划章节、主线和支线任务。
- 扫描 JAR/ZIP 中的真实物品 ID，减少 AI 生成不存在物品的问题。
- 支持整合包根目录、`mods` 文件夹和 KubeJS 内容扫描。
- 支持 DeepSeek API 和本地 Ollama 两种生成方式。
- 通过分阶段生成控制任务密度，不再把“请生成 40 个任务”完全交给 AI 自己数。
- 自动生成任务 ID、依赖关系、坐标和 FTB Quests 所需的 SNBT 结构。
- 生成后检查物品 ID，并输出检查报告。
- 支持直接生成，也支持导入网页 AI 生成的 JSON。
- 支持中文和英文界面，以及自定义输出目录。

> 目前稳定版支持 DeepSeek、Ollama，以及手动配置的 OpenAI 兼容 API。第三方服务没有统一的模型列表和错误格式，所以自定义 API 需要用户自己填写并确认参数。

## 本次改动

- **自定义 API 完整地址开关**：API URL 可以只填基础地址（如 `https://ark.cn-beijing.volces.com/api/coding/v3`），软件会自动补全为 `/chat/completions`；已包含完整地址时原样使用。模型列表 URL 也能从基础地址自动推导。
- **缓解 Windows 安全中心误报**：打包默认禁用 UPX 压缩并写入正式版本信息；新增 `add_defender_exclusion.bat`，可一键把软件加入 Defender 白名单。
- **生成进度保存**：分阶段生成时每完成一个章节都会写入 `generation_progress.json`；如果 Token/额度不足导致生成中断，已完成的部分任务书会自动保存为可用 SNBT，并在界面提示“部分生成完成”。
- **启动自动检查 Mod 文件夹**：软件会记住上次的 Mod 文件夹并在启动时自动扫描其中的 Mod 文件，无需每次重新浏览选择；文件夹没变时还会自动恢复上次勾选的 Mod。
- **MOD 信息查询窗口**：新增“📖 MOD 信息”按钮，窗口内直接查看每个已选 Mod 的名称、Mod ID、分类，以及来自 MC百科 / Modrinth 的简介和下载量，并可一键跳转 MC百科、Modrinth、CurseForge 页面。

## v1.3.9 更新

- 修复部分启动器版本 JSON 结构不同，导致生成任务刚开始便自动结束的问题。
- 第三方 API 不兼容工具调用时自动退回普通聊天生成，不再直接中断任务。
- 生成进度和结果改由主界面安全接收，失败时会显示原因并保存 `generation_error.log`。

## v1.3.8 更新

- 改用完整分阶段生成：程序负责章节配额、批次续写、全局去重和最终质量检查。
- AI 可按需查询整合包中的真实物品与配方，DeepSeek 工具调用过多时也能正确汇总结果。
- JAR 物品扫描不再限制单命名空间数量，同时保留异常压缩包安全护栏；完整索引不会全部塞进提示词。
- 修复章节分组 ID、SNBT 正文换行、Boss/维度目标误当物品校验等导致章节缺失的问题。
- 自动识别实例版本、加载器和 FTB Quests 版本，并优先输出到当前实例的任务书目录。
- 生成后输出质量报告，检查空章节、重复目标、无效依赖、正文缺失和物品 ID。

## v1.3.7 更新

- 主界面加入纵向滚动，鼠标滚轮、触控板和右侧滚动条均可使用。
- 状态、进度条与生成按钮固定在窗口底部，小屏幕或高 DPI 缩放下也不会消失。
- API 与导入模式同步适配，JSON 编辑框仍保留独立滚动。
- 最小窗口高度降低到 480，改善小尺寸笔记本上的使用体验。

## 人工风格布局与文案润色

AI 初版任务书的结构和文案往往偏"机械感"：任务挤在一两条直线上、描述是一句话流水账。AutoFTBQ 现在内置了人工任务书风格优化：

### 布局重排（自动生效）

生成后程序会先把相关任务整理成 4～6 个任务的小组，再按章节主题选择稳定、易读的布局模板：

- 常规章节使用工整的横向分组，主线严格对齐，多行之间折返衔接
- 魔法与伙伴章节保留独特的六向“雪花”结构，高任务量也不会缩减内容
- Boss 章节使用层级清晰的树状分支
- KubeJS 自定义内容会按任务关系并入对应的横向分组
- 主线、支线、Boss、阶段里程碑和信息卡使用不同形状表达语义
- 只有真正的说明、指南任务会进入独立信息栏，普通勾选任务仍保留在流程中
- 坐标完全由固定网格计算，不再加入随机抖动，并自动控制重叠、长连线和交叉

### 章节组织（按玩法主题融合）

章节不再按 Mod 单独开一章，而是按人工任务书的习惯用玩法主题组织，原版内容与 Mod 内容融合在同一条任务线里：

- 新手开局（原版生存起步 + 背包/地图等实用工具）
- 农业与美食（原版种植 + 食物类 Mod）
- 矿业与资源（原版挖矿 + 存储/矿石类 Mod）
- 科技与自动化（红石 + 科技类 Mod）
- 魔法与附魔（附魔/酿造 + 魔法类 Mod）
- 养成与伙伴（宠物/村民 + 女仆等养成 Mod）
- 探索与维度（下界/末地 + 维度类 Mod）
- Boss 挑战（原版 Boss + 生物/挑战类 Mod）

章节按固定顺序生成；原版核心主题始终保留，仅没有内容的可选扩展主题会跳过。

### AI 文案润色（可选）

软件内置了从 6 个整合包、7000+ 个人工任务整理出的压缩语料。AI 会按任务类型挑选接近的写法示例，逐章润色每个任务的 subtitle（副标题）和 description（描述），让它读起来更像人类作者写的：口语化、副标题点睛、描述给实用干货、适度使用颜色代码。发布版不需要额外准备 `example_all/` 目录。

润色是补丁式的：只允许修改 subtitle 和 description，任务 ID、依赖、坐标、物品 ID 全部锁定，程序侧逐条校验。

软件界面提供了“AI 文案润色”开关，默认关闭。这个功能会产生额外 AI 请求，token 充足、确实想继续打磨文案时再试即可。

也可以对已有的任务书单独运行（需要有效 API Key 或本地 Ollama）：

```bash
# 只重排布局
python polish_quests.py --input quests --output questbook_output

# 重排 + AI 润色（用 config.json 里的 API 配置）
python polish_quests.py --input quests --output questbook_output --polish

# 原地更新，不产生新目录
python polish_quests.py --input quests --in-place --polish
```

润色完成后会生成 `polish_report.txt`，记录每个章节应用了多少条补丁。

## 软件工作流程

下面这张手绘版流程图概括了 AutoFTBQ 从读取整合包到生成任务书的完整流程。线条故意保留了一点歪歪扭扭的感觉，毕竟这是给人看的软件，不是流水线验收报告 hh：

![AutoFTBQ 手绘软件工作流程图](assets/workflow.svg?v=2)

## 下载和安装

### 直接使用 exe

Windows 用户可以直接从 [Releases](https://github.com/Bluelgin/AutoFTBQ/releases) 下载 `AutoFTBQ.exe`，不需要单独安装 Python。

### 从源码运行

需要 Python 3.10 或更高版本：

```bash
git clone https://github.com/Bluelgin/AutoFTBQ.git
cd AutoFTBQ
python -m pip install requests
python main.py
```

Windows 用户也可以运行仓库中的 `start.bat`。

## 两种工作方式

### API 自动生成

适合想让软件自动完成任务规划的人。当前支持：

- DeepSeek API：联网使用，需要 API Key。
- 自定义 API：支持 OpenAI Chat Completions 格式的第三方服务，需要自己填写接口地址和模型名。
- Ollama：模型运行在本地，不需要 API Key，但需要电脑有足够的显存或内存。

软件启动后会检测 Ollama。如果检测到可用模型，通常会优先使用本地引擎；也可以在界面中切回 API 模式。

### 自定义 API 怎么填

如果你使用的是 OpenAI、SiliconFlow、各种中转站，或者本地运行的 OpenAI 兼容服务，可以在 API 模式中选择服务商 `custom`，然后手动填写：

| 输入项 | 填写内容 |
|---|---|
| API Key | 服务商提供的密钥；本地服务如果不校验密钥，也可以填写任意非空内容 |
| 自定义 URL | 接口地址，既可以是完整地址（以 `/chat/completions` 结尾），也可以是基础地址（如只到 `/v1` 或 `/api/coding/v3`） |
| 自动补全 `/chat/completions` | 默认开启：填基础地址时自动补全；填完整地址时原样使用。关闭后地址完全按输入使用 |
| 模型 | 服务商实际提供的模型 ID，必须和接口支持的名称完全一致 |

例如，接口基础地址只到 `/v1` 也可以直接填写：

```text
API URL: https://example.com/v1
模型: your-model-id
```

软件会自动把它补全为 `https://example.com/v1/chat/completions`。火山引擎等平台的 Endpoint 也可以只填控制台地址，例如：

```text
API URL: https://ark.cn-beijing.volces.com/api/coding/v3
模型: ep-xxxxxxxx
```

会自动补全为 `https://ark.cn-beijing.volces.com/api/coding/v3/chat/completions`。

本地代理这样填写：

```text
API URL: http://127.0.0.1:1234/v1/chat/completions
模型: local-model-name
```

这里填写的 URL 不是网页地址。如果关闭了“自动补全”，就需要手动写完整的 `/chat/completions` 接口。

自定义 API 目前不会自动读取模型列表，也不会替你判断服务商是否真的支持 OpenAI 格式。你需要从服务商文档或控制台确认以下内容：

- 请求方式是 `POST`。
- 接口接受 `model`、`messages`、`temperature` 和 `max_tokens` 等字段。
- 返回结果中存在 `choices[0].message.content`。
- API Key 使用 `Authorization: Bearer <API Key>` 传递。

如果生成时报 400、404 或模型不存在，优先检查 URL 是否多写或少写了路径，以及模型 ID 是否填写正确。配置会保存在本地 `config.json` 中，下次启动时会保留。

### 导入 JSON

如果你没有 API Key，也不想安装 Ollama，可以使用网页 AI：

1. 在 AutoFTBQ 中选择导入模式。
2. 选择 Mod 并保存提示词文件。
3. 把提示词文件交给网页 AI，让它生成任务书 JSON。
4. 把完整 JSON 粘贴回 AutoFTBQ。
5. 软件负责校验、转换并输出 SNBT。

这个模式不需要把 API Key 交给软件，适合想自己控制提示词和生成结果的人。

## 从整合包生成任务书

### 1. 选择输入目录

可以选择：

- 整合包根目录，例如 `D:\Modpacks\MyPack`。
- 整合包中的 `mods` 文件夹。
- 只包含 Mod JAR/ZIP 文件的普通文件夹。

如果选择的是整合包根目录，软件会尝试同时查找：

```text
mods/
kubejs/
```

### 2. 选择 Mod

点击“选择 Mod”，勾选真正想生成任务的 Mod。

一般不需要单独勾选 JEI、JourneyMap、依赖库等辅助 Mod。软件会尽量识别依赖和辅助内容，并把合适的物品放进相关任务或奖励中。

勾选结果会保存到 `config.json`。下次启动时软件会自动检查上次的 Mod 文件夹：扫描其中的 Mod 文件并显示数量；如果文件夹没变，还会自动恢复上次勾选的 Mod，直接点“生成”即可。换文件夹后会自动清空旧选择。

### 2.1 查看 MOD 信息（多平台）

选好 Mod 后，点击“📖 MOD 信息”按钮打开信息窗口：

- 左侧列出所有已选 Mod，点击任意一个即可在右侧查看详情。
- 详情包括名称、Mod ID、分类、来源平台，以及来自平台的简介；优先查询 **MC百科**（中文资料最全），查询不到时自动改用 **Modrinth** API（附下载量、支持的游戏版本和加载器），都失败时展示本地已知资料。
- 窗口左下角会显示当前信息来源；点击右下角“🌐 打开 MC百科”可一键跳到该 Mod 的 MC百科详情页（或搜索页）。
- 详情区还会提供以下平台的跳转链接，方便交叉比对：
  - **MC百科**（中文详情/搜索）
  - **Modrinth**（项目页/搜索）
  - **CurseForge**（搜索）
  - **FTB Wiki**、**Modded Minecraft Wiki**（英文百科搜索）
  - **Planet Minecraft**（展示站搜索）
  - **网页搜索**（百度，通用兜底）

> 说明：CurseForge 的官方 API 需要单独申请付费 Key，不适合随软件分发，所以这里以网页搜索链接代替；FTB Wiki / Modded Minecraft Wiki / Planet Minecraft 没有公开的稳定查询接口，同样以搜索链接提供。Modrinth 是完全开放的 API，无需 Key 即可直接查询。

### 3. 选择任务密度

任务密度会影响每个章节的任务配额和 AI 调用次数：

| 密度 | 大致规模 | 适合场景 |
|---|---:|---|
| 精简 | 原版约 24 个任务 | 想快速体验，或 Mod 数量较少 |
| 适中 | 原版约 40 个任务 | 大多数整合包的推荐选择 |
| 丰富 | 原版约 60 个任务 | 希望覆盖更多物品和玩法 |
| 拉满 | 原版约 80 个任务 | 大型整合包，接受更长生成时间 |

每个核心 Mod 还会根据分类追加任务。实际数量会受到 Mod 数量、内容复杂度和重复任务过滤影响，但程序会负责最终配额和任务 ID，不再单纯依赖 AI 自己计数。

### 4. 生成并导入游戏

选择整合包或它的 `mods` 文件夹后，软件会尝试识别 Minecraft、加载器和对应实例的 FTB Quests 目录，并自动填写：

```text
<整合包实例>/config/ftbquests/quests/
```

如果没有识别出实例，留空时才会保存到软件旁边的：

```text
questbook_output/
```

生成采用临时目录写入和失败回滚；完成后还会检查 `data.snbt`、章节文件和任务数量，避免空任务书被误报为成功。然后重新进入游戏或重新加载 FTB Quests。

## 按需检索与质量检查

AutoFTBQ 不再把整合包的全部物品一次性塞入每轮提示词。软件会先建立本地物品、配方和 KubeJS 索引，再根据当前章节按需取出相关内容：

- 每批只提供当前章节允许使用的命名空间和高相关物品。
- 配方前置和未覆盖目标会随着生成进度动态更新。
- 支持 OpenAI 兼容 `tool_calls` 的模型可以主动搜索物品和配方；不支持时会自动降级为软件检索。
- 整本任务书共用覆盖记录，避免相同目标被重复放进不同章节。
- AI 数量不足时只使用实际扫描到的唯一物品补充，不再批量制造确认任务凑数。
- 基础正文属于必需内容；AI 没有返回正文时，程序会按任务目标补全。

生成结束后 `quality_report.txt` 会记录正文补全、全局去重、失效依赖和最终发布状态。AI 润色仍是可选功能，只负责改善表达风格，不再承担“有没有正文”这一基础职责。

## KubeJS 支持

如果选择的是整合包根目录，软件会扫描 `kubejs/` 中常见的内容，包括：

- `startup_scripts/`
- `server_scripts/`
- `client_scripts/`
- `assets/` 中的语言文件
- 常见的物品注册和配方写法

KubeJS 自定义物品通常会按命名空间归类，并在任务规划中作为独立内容处理。

需要注意：软件是静态分析脚本，不会启动 Minecraft，也不会执行 KubeJS。复杂的动态脚本、变量拼接 ID 或自定义事件可能无法完全还原，这时建议在生成后检查 `id_validation_report.txt`。

## Boss 和击杀任务

目前软件不会强行假设所有 Mod 的 Boss 都能被标准击杀任务正确识别。对于暮色森林等以 Boss 为核心的 Mod，当前更稳妥的做法是使用 Boss 掉落物作为任务检查标记。

这样即使不同版本的实体 ID、击杀事件或任务类型存在差异，也能尽量保证任务在游戏里可以完成。

## 输出文件

典型输出结构如下：

```text
questbook_output/
├─ data.snbt
├─ chapter_groups.snbt
├─ chapters/
│  ├─ <chapter>.snbt
│  └─ ...
├─ reward_tables/
├─ ai_raw_output.txt
├─ id_validation_report.txt
├─ quality_report.txt
├─ generation_progress.json   # 生成进度检查点（每完成一章写入，全部完成后自动删除）
└─ partial_report.txt         # 仅“部分生成完成”时出现，说明中断原因与保存情况
```

- `data.snbt`：任务书全局配置。
- `chapter_groups.snbt`：章节分组信息。
- `chapters/`：每个章节的任务、依赖、奖励和坐标。
- `ai_raw_output.txt`：AI 原始输出，方便排查生成问题。
- `id_validation_report.txt`：物品 ID 校验结果。
- `quality_report.txt`：正文补全、全局去重、失效依赖和发布检查结果。
- `generation_progress.json`：分阶段生成的进度检查点。每完成一个章节就会更新一次；如果中途 Token/额度不足或程序异常中断，这个文件里保留了已完成章节，可据此恢复。
- `partial_report.txt`：仅当生成中断且保存了部分任务书时出现，说明中断原因、已完成章节数和存放位置。

### Token 不足/中断时的部分保存

分阶段生成是逐章进行的，每完成一章都会把进度写入检查点。如果生成过程中 Token 或余额不足（例如 API 返回额度不足），软件不会丢失已生成的内容：

1. 已完成章节的任务会立即保存为可用 SNBT（`data.snbt` + `chapters/*.snbt`）。
2. 输出目录中会生成 `partial_report.txt` 说明中断原因和保存情况。
3. 界面会提示“部分生成完成”，可直接查看已保存的任务书，或把该目录内容导入游戏；Token 充足后也可以重新生成。

如果想中途手动停止，直接关闭窗口前会询问是否中断；中断后同样会保留已完成的部分。

## 常见问题

### 生成很慢

这是正常现象。任务密度越高、Mod 越多，AI 调用批次越多；第一次扫描 Mod 还需要读取 JAR 内容。可以先用“精简”或“适中”测试。

### AI 生成了不存在的物品

先确认选择的是正确的 `mods` 文件夹，并查看输出目录中的 `id_validation_report.txt`。KubeJS 动态生成、脚本拼接出来的 ID 可能无法被静态扫描。

### 游戏加载 SNBT 崩溃

不要把整个 `questbook_output` 文件夹嵌套复制进去，也不要混用旧版本生成的章节文件。建议清空目标 `config/ftbquests/quests/` 后，只复制同一次生成产生的完整输出。

### Ollama 没有被检测到

确认 Ollama 已安装并正在后台运行，然后确认本地至少有一个模型，例如：

```bash
ollama pull qwen2.5-coder:7b
```

如果本地模型效果不理想，可以切换回 DeepSeek API。

### 更新检查失败或卡住

软件会依次从 GitHub Raw、jsDelivr 和 GitHub Release API 获取版本信息，单个来源不可用时会自动切换。全部来源都无法访问时，更新检查会显示失败，但不会影响任务生成；也可以直接从 [Releases](https://github.com/Bluelgin/AutoFTBQ/releases) 手动下载最新版。

### Windows 安全中心 / Defender 误报

打包后的 exe 是 PyInstaller 生成、未做代码签名的程序，这类程序偶尔会被 Microsoft Defender 或 SmartScreen 误报。本仓库已做以下缓解：

- 打包时默认**禁用 UPX 压缩**（UPX 是误报的常见触发点）。
- 给 exe 写入**正式的版本资源**（作者、版本、产品名），在文件属性里可以看到详细信息。
- 提供一键白名单脚本 **`add_defender_exclusion.bat`**。

如果仍然被拦截，按下面步骤处理：

1. 把 `add_defender_exclusion.bat` 复制到 exe 所在目录，右键“以管理员身份运行”，自动把该目录加入 Windows 安全中心排除列表。
2. 或者手动添加：`设置 → 隐私和安全性 → Windows 安全中心 → 病毒和威胁防护 → 管理设置 → 排除项`，把 exe 所在文件夹加入排除。
3. 若 exe 已被删除，重新从 [Releases](https://github.com/Bluelgin/AutoFTBQ/releases) 下载。
4. 首次运行出现 SmartScreen 提示时，点“更多信息 → 仍要运行”。
5. 本项目是 GPL-3.0 开源项目，源码完全公开。确认程序来自官方 Releases 后，也可以在 Windows 安全中心中把它“允许”并反馈误报，帮助改进。

## 项目结构

| 文件 | 作用 |
|---|---|
| `main.py` | Tkinter 图形界面、模式选择、配置和生成流程 |
| `ai_module.py` | AI 调用、分阶段生成、任务规划、JSON/SNBT 转换 |
| `mod_scanner.py` | Mod、物品、配方和 KubeJS 静态扫描 |
| `ollama_adapter.py` | Ollama 检测、模型选择和本地 HTTP 调用 |
| `mcwiki_crawler.py` | 可选的 Minecraft Wiki 辅助信息抓取 |
| `playstyle_data/` | 常见 Mod 的玩法提示资料 |
| `snbt_parser.py` | FTB Quests SNBT 文件的读取/写入 |
| `human_corpus.py` | 从 example_all 提取人工任务语料与风格检索 |
| `quest_layout.py` | 人工风格布局重排（主线/分支/信息任务） |
| `quest_polish.py` | AI 文案润色管线（补丁式输出+结构校验） |
| `polish_quests.py` | 命令行：对已有任务书重排/润色 |
| `mod_info.py` | MOD 信息查询：MC百科 / Modrinth / 本地资料 + 平台跳转链接 |
| `AutoFTBQ.spec` | PyInstaller 打包配置（禁用 UPX、内嵌版本信息） |
| `version_info.txt` | exe 的版本资源文件（降低 Defender 误报） |
| `add_defender_exclusion.bat` | 一键把软件加入 Windows 安全中心排除列表 |
| `test_*.py` | KubeJS、SNBT、分阶段生成和更新模块测试 |

## 参与贡献

欢迎提交 Issue 和 Pull Request。

如果是 API 服务商接入，最好同时提供：

- 实际的 Chat Completions 请求格式。
- 模型列表接口是否存在，以及返回 JSON 示例。
- 默认模型或 Endpoint ID 的获取方式。
- 失败响应和限流响应示例。
- 至少一组不需要真实 API Key 的单元测试。

这样会更容易确认不同服务商之间的差异，也能避免“界面能选，但生成时才报错”。

## 许可证

本项目使用 [GPL-3.0](LICENSE) 开源。

作者：[Taki / Bluelgin](https://github.com/Bluelgin)

Powered by [DeepSeek](https://www.deepseek.com/) and [Ollama](https://ollama.com/).
