"""Validation and normalization for AI-generated quest JSON."""

from __future__ import annotations

from typing import Any


class QuestValidationError(ValueError):
    """Raised when a response cannot be treated as a quest book."""


def extract_quest_batch(data: Any) -> list[dict]:
    """Extract quest dictionaries from the short staged-response formats."""
    quests: Any = []
    if isinstance(data, list):
        quests = data
    elif isinstance(data, dict):
        direct = data.get("quests")
        chapter = data.get("chapter")
        chapters = data.get("chapters")
        if isinstance(direct, list):
            quests = direct
        elif isinstance(chapter, dict) and isinstance(chapter.get("quests"), list):
            quests = chapter["quests"]
        elif isinstance(chapters, list) and chapters and isinstance(chapters[0], dict):
            nested = chapters[0].get("quests")
            if isinstance(nested, list):
                quests = nested
    return [quest for quest in quests if isinstance(quest, dict)]


def _normalize_entries(value: Any, path: str, issues: list[str]) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list):
        issues.append(f"{path} 应为数组，已按空数组处理")
        return []
    entries = []
    for index, entry in enumerate(value):
        if isinstance(entry, dict):
            entries.append(dict(entry))
        else:
            issues.append(f"{path}[{index}] 应为对象，已忽略")
    return entries


def normalize_quest_book(data: Any) -> tuple[dict, list[str]]:
    """Return a safe quest-book mapping plus non-fatal cleanup messages."""
    if not isinstance(data, dict):
        raise QuestValidationError("任务书 JSON 顶层必须是对象")

    issues: list[str] = []
    raw_chapters = data.get("chapters")
    if raw_chapters is None and isinstance(data.get("chapter"), dict):
        raw_chapters = [data["chapter"]]
    if raw_chapters is None and isinstance(data.get("quests"), list):
        raw_chapters = [{"title": data.get("title", "Quest Book"), "quests": data["quests"]}]
    if not isinstance(raw_chapters, list):
        raise QuestValidationError("任务书 JSON 的 chapters 必须是数组")

    chapters = []
    for chapter_index, raw_chapter in enumerate(raw_chapters):
        if not isinstance(raw_chapter, dict):
            issues.append(f"chapters[{chapter_index}] 应为对象，已忽略")
            continue
        chapter = dict(raw_chapter)
        raw_quests = chapter.get("quests", [])
        quests = _normalize_entries(raw_quests, f"chapters[{chapter_index}].quests", issues)
        normalized_quests = []
        for quest_index, quest in enumerate(quests):
            path = f"chapters[{chapter_index}].quests[{quest_index}]"
            quest["tasks"] = _normalize_entries(quest.get("tasks", []), f"{path}.tasks", issues)
            quest["rewards"] = _normalize_entries(quest.get("rewards", []), f"{path}.rewards", issues)

            dependencies = quest.get("dependencies", [])
            if isinstance(dependencies, str):
                dependencies = [dependencies]
            elif not isinstance(dependencies, list):
                issues.append(f"{path}.dependencies 应为数组，已按空数组处理")
                dependencies = []
            quest["dependencies"] = [item for item in dependencies if isinstance(item, str)]

            description = quest.get("description", [])
            if isinstance(description, str):
                description = [description]
            elif not isinstance(description, list):
                issues.append(f"{path}.description 应为文本或数组，已按空数组处理")
                description = []
            quest["description"] = [str(line) for line in description if isinstance(line, (str, int, float))]
            normalized_quests.append(quest)
        chapter["quests"] = normalized_quests
        chapters.append(chapter)

    if raw_chapters and not chapters:
        detail = issues[0] if issues else "chapters 中没有有效章节"
        raise QuestValidationError(f"任务书 JSON 没有可用章节：{detail}")

    result = dict(data)
    result["title"] = str(data.get("title") or "Quest Book")
    result["chapters"] = chapters
    result.pop("chapter", None)
    return result, issues
