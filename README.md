# AutoFTBQ

一个帮你把 Minecraft 整合包变成 FTB Quests 任务书的小工具。

你只需要选择整合包或 `mods` 文件夹，AutoFTBQ 会扫描 Mod、物品、配方和部分 KubeJS 内容，再交给 AI 规划任务，最后输出可以放进 FTB Quests 的 SNBT 文件。

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)
![License](https://img.shields.io/badge/License-GPL--3.0-green.svg)
![Version](https://img.shields.io/badge/Version-1.3.3-orange.svg)
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
| 自定义 URL | 完整的 Chat Completions 地址，通常以 `/chat/completions` 结尾 |
| 模型 | 服务商实际提供的模型 ID，必须和接口支持的名称完全一致 |

例如，OpenAI 兼容接口通常类似这样：

```text
API URL: https://example.com/v1/chat/completions
模型: your-model-id
```

本地代理也可以这样填写：

```text
API URL: http://127.0.0.1:1234/v1/chat/completions
模型: local-model-name
```

这里的 URL 不是网页地址，也不是只到 `/v1` 的基础地址，最好直接填写完整的 `/chat/completions` 接口。

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

生成完成后，默认输出到：

```text
questbook_output/
```

把输出目录中的内容复制到对应整合包的：

```text
.minecraft/config/ftbquests/quests/
```

然后重新进入游戏或重新加载 FTB Quests。

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
└─ id_validation_report.txt
```

- `data.snbt`：任务书全局配置。
- `chapter_groups.snbt`：章节分组信息。
- `chapters/`：每个章节的任务、依赖、奖励和坐标。
- `ai_raw_output.txt`：AI 原始输出，方便排查生成问题。
- `id_validation_report.txt`：物品 ID 校验结果。

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

软件会从 GitHub 获取版本信息。网络无法访问 GitHub 时，更新检查可能失败，但不应该影响任务生成。也可以直接从 [Releases](https://github.com/Bluelgin/AutoFTBQ/releases) 手动下载最新版。

## 项目结构

| 文件 | 作用 |
|---|---|
| `main.py` | Tkinter 图形界面、模式选择、配置和生成流程 |
| `ai_module.py` | AI 调用、分阶段生成、任务规划、JSON/SNBT 转换 |
| `mod_scanner.py` | Mod、物品、配方和 KubeJS 静态扫描 |
| `ollama_adapter.py` | Ollama 检测、模型选择和本地 HTTP 调用 |
| `mcwiki_crawler.py` | 可选的 Minecraft Wiki 辅助信息抓取 |
| `playstyle_data/` | 常见 Mod 的玩法提示资料 |
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
