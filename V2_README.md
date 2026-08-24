# AutoFTBQ v2 Agent Workspace MVP

这是用于验证 v2 产品方向的最小可运行版本，不替代稳定的 1.x。

## 当前可以体验

- 左侧任务书项目区：章节列表、任务节点、依赖连线和属性编辑。
- 项目保存与打开：使用可继续编辑的 `*.autoftbq.json` 文件。
- 撤销与重做，以及不消耗 Token 的本地结构检查。
- 扫描整合包物品和配方，供 Agent 按需查询。
- 右侧 Agent 对话区：显示每次查询、创建、修改和检查操作。
- 原生 function calling；不支持时自动使用受控 JSON Action 协议。
- 将当前项目导出为 FTB Quests SNBT。

## 运行

```powershell
python -m pip install -r requirements-v2.txt
python v2_main.py
```

也可以直接双击 `start_v2.bat`。Agent 暂时读取 1.x 保存在软件目录中的 `config.json`，不会把 API Key 写入项目文件。

## MVP 暂有限制

- 节点画布用于确认结构方向，还没有完整的框选连线、缩放导航和游戏图标渲染。
- Agent 工具以创建和修改任务为主，暂不允许删除章节或直接写文件。
- SNBT 导入、完整奖励编辑和多人协作留到后续阶段。
- Ollama 可以使用 JSON Action 协议，但小模型的工具规划稳定性取决于模型能力。
