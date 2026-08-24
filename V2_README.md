# AutoFTBQ v2 Agent Workspace MVP

这是用于验证 v2 产品方向的最小可运行版本，不替代稳定的 1.x。

## 当前可以体验

- 左侧先选择整合包，建立物品 ID、配方、资源模型和图标索引。
- 直接打开整合包现有的 `config/ftbquests/quests/chapters/*.snbt`，使用真实坐标显示章节任务图。
- 离线任务书编辑器：拖动真实节点、修改属性、编辑完整任务/奖励 SNBT，并实时查看 Agent 的修改。
- 连线模式：依次点击前置任务 A 与后置任务 B，写入 B 对 A 的依赖，并阻止循环连线。
- 项目保存与打开：使用可继续编辑的 `*.autoftbq.json` 文件。
- 撤销与重做，以及不消耗 Token 的本地结构检查。
- Agent 根据用户目标按需加载主线、支线、融合、Boss 或修复 Skill，再调用白名单工具逐步修改项目。
- 右侧 Agent 对话区：显示每次查询、创建、修改和检查操作。
- 原生 function calling；不支持时自动使用受控 JSON Action 协议。
- 将当前项目导出为 FTB Quests SNBT。
- 真实任务书按变更章节安全写回，保存前自动建立 `.autoftbq-backups` 备份。

## 运行

```powershell
python -m pip install -r requirements-v2.txt
python v2_main.py
```

也可以直接双击 `start_v2.bat`。Agent 暂时读取 1.x 保存在软件目录中的 `config.json`，不会把 API Key 写入项目文件。

## MVP 暂有限制

- 常规 2D 物品材质可以离线预览；复杂 3D 模型、自定义渲染器和动态材质暂时使用文字占位。
- 节点画布支持空白处左键拖动平移、滚轮缩放、节点拖动、点击连线和适应画布；框选批量操作与可视化断线仍待完善。
- Agent 工具以创建和修改任务为主，暂不允许删除章节或直接写文件。
- SNBT 导入、完整奖励编辑和多人协作留到后续阶段。
- Ollama 可以使用 JSON Action 协议，但小模型的工具规划稳定性取决于模型能力。
