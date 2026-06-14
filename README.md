# AutoFTBQ — MC FTB任务书自动生成器

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

基于 AI 自动生成 Minecraft [FTB Quests](https://www.curseforge.com/minecraft/mc-mods/ftb-quests-forge) 任务书的桌面工具。

## ✨ 功能

- **一键生成**：选择 Mod 文件夹 → 勾选 Mod → AI 生成完整任务指南
- **真实物品ID**：自动扫描 .jar 文件提取真实物品ID，避免图标不显示
- **主线+支线**：自动设计合理的主线/支线任务结构
- **奖励平衡**：按游戏阶段自动分配适当奖励
- **ID校验**：生成后自动校验物品ID有效性，出具报告

## 📦 快速开始

### 方式1：直接运行（推荐）
下载 [Releases](../../releases) 中的 `AutoFTBQ.exe`，双击运行。

### 方式2：源码运行
```bash
pip install requests
python main.py
```

## 🖥️ 截图

![主界面](https://via.placeholder.com/680x550/ffffff/333333?text=简洁白色UI)

## 🔧 使用流程

1. 填写 **DeepSeek API Key**（前往 [platform.deepseek.com](https://platform.deepseek.com) 获取）
2. 选择 **Mod 文件夹**（包含 .jar 文件的 minecraft mods 目录）
3. 点击「选择 Mod」→ 勾选要生成任务书的 Mod
4. 点击「生成任务书」→ 等待 2-4 分钟
5. 生成完成后自动打开输出文件夹

## 📁 输出结构

```
questbook_output/
├── data.snbt              # 任务书主配置
├── chapter_groups.snbt    # 章节列表
├── chapters/              # 各章节SNBT文件
│   ├── XXXXX.snbt
│   └── ...
├── reward_tables/         # 奖励表
├── ai_raw_output.txt      # AI原始输出
└── id_validation_report.txt  # 物品ID校验报告
```

## 🛠️ 技术栈

| 模块 | 说明 |
|------|------|
| `main.py` | Tkinter GUI 主界面 |
| `ai_module.py` | DeepSeek API 调用 + SNBT 生成 |
| `mod_scanner.py` | JAR 文件物品ID扫描器 |

## 📝 物物品ID扫描原理

```
JAR文件 → ZIP解压 → 扫描assets/<modid>/models/item/
                → 扫描data/<modid>/recipes/
                → 加载lang文件获取显示名
                → 注入AI Prompt
                → 生成后校验
```

## ⚠️ 注意事项

- 需要使用 **DeepSeek API Key**（付费，约 ¥1/次生成）
- 首次扫描 JAR 文件需要 10-30 秒（有缓存）
- 输出的 SNBT 文件放入 FTB Quests 的 `config/ftbquests/quests/` 目录即可使用

## 📄 许可证

MIT License

## 👤 作者

**Taki** ([@Bluelgin](https://github.com/Bluelgin))

---

Powered by [DeepSeek AI](https://deepseek.com)