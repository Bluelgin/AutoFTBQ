"""Bounded tool-using agent for the editable v2 project."""

from __future__ import annotations

import json
import re
from typing import Callable

from quest_tools import QuestToolbox

from .project import ProjectStore
from .skill_registry import SkillRegistry


AGENT_SYSTEM_PROMPT = """You are the AutoFTBQ project agent.
You edit the current FTB Quests project only through the provided tools.
Inspect the project before changing it. Search real item IDs instead of guessing.
Choose and load the smallest relevant built-in skill before planning substantial edits.
Make small, reviewable changes and call validate_project after edits.
Never output a complete quest book JSON. Reply briefly in Chinese and summarize actions taken.
If native tool calls are unavailable, return this exact fallback format:
{"actions":[{"tool":"tool_name","arguments":{}}],"reply":"short status"}
"""


class ProjectAgent:
    def __init__(
        self,
        store: ProjectStore,
        client,
        toolbox: QuestToolbox | None = None,
        on_action: Callable[[str, dict, object], None] | None = None,
        skills: SkillRegistry | None = None,
    ):
        self.store = store
        self.client = client
        self.toolbox = toolbox or QuestToolbox()
        self.skills = skills or SkillRegistry()
        self.on_action = on_action
        self.history: list[dict] = []

    def tool_specs(self) -> list[dict]:
        def spec(name, description, properties, required=()):
            return {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": list(required),
                    },
                },
            }

        return [
            spec("get_project_summary", "Inspect chapters and quest counts.", {}),
            spec("list_skills", "List built-in quest-authoring skills and their triggers.", {}),
            spec("load_skill", "Load one relevant built-in workflow before planning or repairing.", {
                "skill_id": {"type": "string"},
            }, ("skill_id",)),
            spec("create_chapter", "Create one chapter.", {
                "title": {"type": "string"}, "icon": {"type": "string"},
            }, ("title",)),
            spec("add_quest", "Add one quest to an existing chapter.", {
                "chapter_id": {"type": "string"}, "title": {"type": "string"},
                "description": {"type": "string"},
                "task_type": {"type": "string", "enum": ["item", "checkmark", "kill", "dimension", "advancement"]},
                "target": {"type": "string"}, "count": {"type": "integer"},
            }, ("chapter_id", "title", "task_type")),
            spec("update_quest", "Update one existing quest.", {
                "quest_id": {"type": "string"}, "title": {"type": "string"},
                "description": {"type": "string"}, "task_type": {"type": "string"},
                "target": {"type": "string"}, "count": {"type": "integer"},
            }, ("quest_id",)),
            spec("connect_quests", "Make a quest depend on another quest.", {
                "quest_id": {"type": "string"}, "dependency_id": {"type": "string"},
            }, ("quest_id", "dependency_id")),
            spec("search_items", "Search real item IDs scanned from this modpack.", {
                "namespace": {"type": "string"}, "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 30},
            }, ("query",)),
            spec("get_recipe", "Read recipe inputs for an exact item ID.", {
                "item_id": {"type": "string"}, "depth": {"type": "integer"},
            }, ("item_id",)),
            spec("validate_project", "Validate IDs, dependencies and duplicate titles.", {}),
        ]

    def _emit(self, name: str, arguments: dict, result: object) -> None:
        if self.on_action:
            self.on_action(name, arguments, result)

    def call_tool(self, name: str, arguments: dict) -> str:
        arguments = arguments if isinstance(arguments, dict) else {}
        if name == "get_project_summary":
            result = self.store.summary()
        elif name == "list_skills":
            result = self.skills.catalog()
        elif name == "load_skill":
            result = self.skills.load(arguments.get("skill_id", ""))
        elif name == "create_chapter":
            chapter = self.store.create_chapter(arguments.get("title", ""), arguments.get("icon", "minecraft:book"))
            result = {"chapter_id": chapter.id, "title": chapter.title}
        elif name == "add_quest":
            quest = self.store.add_quest(
                arguments.get("chapter_id", ""), arguments.get("title", ""),
                arguments.get("description", ""), arguments.get("task_type", "checkmark"),
                arguments.get("target", ""), arguments.get("count", 1),
            )
            result = {"quest_id": quest.id, "title": quest.title}
        elif name == "update_quest":
            changes = {key: value for key, value in arguments.items() if key != "quest_id"}
            quest = self.store.update_quest(arguments.get("quest_id", ""), **changes)
            result = {"quest_id": quest.id, "title": quest.title}
        elif name == "connect_quests":
            quest = self.store.connect(arguments.get("quest_id", ""), arguments.get("dependency_id", ""))
            result = {"quest_id": quest.id, "dependencies": quest.dependencies}
        elif name == "search_items":
            result = self.toolbox.search_items(
                arguments.get("namespace", ""), arguments.get("query", ""), arguments.get("limit", 20),
            )
        elif name == "get_recipe":
            result = self.toolbox.get_recipe(arguments.get("item_id", ""), arguments.get("depth", 1))
        elif name == "validate_project":
            result = self.store.validate(self.toolbox.all_items)
        else:
            result = {"error": f"不允许的工具：{name}"}
        self._emit(name, arguments, result)
        return json.dumps(result, ensure_ascii=False, separators=(",", ":"))

    def run(self, user_message: str) -> str:
        if self.client is None:
            raise RuntimeError("尚未连接 AI，请先配置 API 或 Ollama")
        context = json.dumps(self.store.summary(), ensure_ascii=False)
        skill_catalog = json.dumps(self.skills.catalog(), ensure_ascii=False)
        messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            *self.history[-10:],
            {
                "role": "user",
                "content": (
                    f"当前项目摘要：{context}\n"
                    f"可按需加载的 Skills：{skill_catalog}\n\n"
                    f"用户要求：{user_message}"
                ),
            },
        ]
        if hasattr(self.client, "chat_with_tools"):
            content, _ = self.client.chat_with_tools(
                messages, self.tool_specs(), self.call_tool,
                temperature=0.35, max_tokens=4096, max_rounds=5,
            )
        else:
            content = self._run_action_protocol(messages)
        envelope = self._action_envelope(content)
        if envelope and envelope.get("actions"):
            content = self._run_action_protocol(messages, content)
        elif envelope:
            content = str(envelope.get("reply", "") or content)
        content = content.strip() or "操作已完成，请在左侧检查任务书。"
        self.history.extend([
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": content},
        ])
        return content

    @staticmethod
    def _action_envelope(content: str) -> dict | None:
        text = str(content or "").strip()
        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        candidates = [fenced.group(1)] if fenced else []
        candidates.append(text)
        for candidate in candidates:
            try:
                value = json.loads(candidate)
            except (TypeError, ValueError):
                continue
            if isinstance(value, dict) and isinstance(value.get("actions", []), list):
                return value
        return None

    def _run_action_protocol(self, messages: list[dict], first_content: str | None = None) -> str:
        specs = [spec["function"] for spec in self.tool_specs()]
        conversation = [
            *messages,
            {
                "role": "system",
                "content": (
                    "Native tools are unavailable. Use only this JSON Action protocol. "
                    f"Available tools: {json.dumps(specs, ensure_ascii=False)}"
                ),
            },
        ]
        content = first_content
        last_reply = ""
        for _round in range(5):
            if content is None:
                content, _ = self.client.chat(conversation, temperature=0.35, max_tokens=4096)
            envelope = self._action_envelope(content)
            if envelope is None:
                return str(content)
            last_reply = str(envelope.get("reply", "") or last_reply)
            actions = envelope.get("actions", [])[:8]
            if not actions:
                return last_reply or "操作已完成，请在左侧检查任务书。"
            results = []
            for action in actions:
                if not isinstance(action, dict):
                    continue
                name = str(action.get("tool", ""))
                arguments = action.get("arguments", {})
                try:
                    result = json.loads(self.call_tool(name, arguments))
                except Exception as exc:
                    result = {"error": str(exc)}
                results.append({"tool": name, "result": result})
            conversation.extend([
                {"role": "assistant", "content": str(content)},
                {
                    "role": "user",
                    "content": (
                        f"工具结果：{json.dumps(results, ensure_ascii=False)}\n"
                        "继续完成用户目标。需要操作就返回下一批 actions；完成后返回 actions 为空的 JSON。"
                    ),
                },
            ])
            content = None
        return last_reply or "已达到本轮工具调用上限，请检查当前项目后继续。"
