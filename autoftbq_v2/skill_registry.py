"""Progressively disclosed built-in quest-authoring skills."""

from __future__ import annotations

import json
import os


class SkillRegistry:
    def __init__(self, root: str | None = None):
        self.root = root or os.path.join(os.path.dirname(__file__), "skills")
        with open(os.path.join(self.root, "index.json"), "r", encoding="utf-8") as handle:
            raw = json.load(handle)
        self._skills = {
            str(item["id"]): item
            for item in raw
            if isinstance(item, dict) and item.get("id") and item.get("file")
        }

    def catalog(self) -> list[dict]:
        return [
            {
                "skill_id": skill_id,
                "title": value.get("title", skill_id),
                "description": value.get("description", ""),
                "triggers": value.get("triggers", []),
            }
            for skill_id, value in self._skills.items()
        ]

    def load(self, skill_id: str) -> dict:
        value = self._skills.get(str(skill_id))
        if value is None:
            return {"error": f"未知 Skill：{skill_id}", "available": list(self._skills)}
        path = os.path.abspath(os.path.join(self.root, value["file"]))
        if os.path.commonpath([path, os.path.abspath(self.root)]) != os.path.abspath(self.root):
            return {"error": "Skill 路径越界"}
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read().strip()
        return {
            "skill_id": skill_id,
            "title": value.get("title", skill_id),
            "instructions": content,
        }
