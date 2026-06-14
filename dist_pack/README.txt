AutoFTBQ - MC FTB任务书生成器 v1.0
=====================================

功能简介
-------
基于所选Mod，自动生成Minecraft FTB Quests任务书。
扫描JAR文件提取真实物品ID，通过AI生成完整的任务指南（含主线+支线）。

使用方法
-------
方式1：直接运行 dist/AutoFTBQ.exe（无需Python）
方式2：运行 install.bat 自动安装到系统
方式3：python source/main.py（需要Python 3.10+）

系统要求
-------
- Windows 10+
- 如需源码运行：Python 3.10+ + requests
- 网络连接（用于调用DeepSeek API）

文件结构
--------
dist_pack/
  ├── dist/AutoFTBQ.exe      ← 可执行文件（无需Python）
  ├── source/                 ← 完整源代码
  │   ├── main.py            ← 主程序（GUI）
  │   ├── ai_module.py       ← AI生成引擎
  │   └── mod_scanner.py     ← JAR物品扫描器
  ├── install.bat            ← 一键安装脚本
  ├── AutoFTBQ.spec          ← PyInstaller配置
  └── README.txt             ← 本文件

作者
----
Taki

Powered by DeepSeek AI