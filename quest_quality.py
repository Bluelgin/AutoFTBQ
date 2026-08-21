"""Deterministic quality repair and publish checks for generated quest books."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable

from quest_knowledge import quest_task_signatures


@dataclass
class QualityReport:
    chapters: int = 0
    quests: int = 0
    descriptions_added: int = 0
    duplicate_goals_removed: int = 0
    duplicate_titles_renamed: int = 0
    broken_dependencies_removed: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def publishable(self) -> bool:
        return not self.errors and self.chapters > 0 and self.quests > 0


def _target_label(target: object, all_items: dict) -> str:
    if not isinstance(target, str) or not target:
        return "当前目标"
    if ":" in target:
        namespace = target.split(":", 1)[0]
        name = all_items.get(namespace, {}).get(target) if isinstance(all_items.get(namespace), dict) else None
        if name:
            return str(name)
        return target.split(":", 1)[1].replace("_", " ")
    return target


def _basic_description(quest: dict, all_items: dict) -> list[str]:
    subtitle = str(quest.get("subtitle", "") or "").strip()
    lines = [subtitle] if subtitle else []
    tasks = quest.get("tasks", []) if isinstance(quest.get("tasks"), list) else []
    details = []
    for task in tasks[:3]:
        if not isinstance(task, dict):
            continue
        task_type = str(task.get("type", "checkmark")).lower().split(":", 1)[-1]
        target = task.get("target") or task.get("item") or task.get("entity") or task.get("advancement") or task.get("dimension")
        label = _target_label(target, all_items)
        count = task.get("count", 1)
        if task_type == "item":
            details.append(f"准备并提交 {label}" + (f" × {count}" if count not in (None, 1, "1") else ""))
        elif task_type == "kill":
            details.append(f"击败 {label}" + (f" × {count}" if count not in (None, 1, "1") else ""))
        elif task_type == "dimension":
            details.append(f"前往维度 {label}")
        elif task_type == "advancement":
            details.append(f"完成进度 {label}")
        else:
            details.append("阅读提示并确认已经完成本阶段目标")
    if details:
        detail = "；".join(details) + "。"
        if detail not in lines:
            lines.append(detail)
    if not lines:
        lines.append("完成这个阶段的目标，为后续任务做好准备。")
    return lines


def _iter_item_targets(quest: dict) -> Iterable[str]:
    for collection in ("tasks", "rewards"):
        entries = quest.get(collection, [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            entry_type = str(entry.get("type", "item")).lower().split(":", 1)[-1]
            target = entry.get("target") or entry.get("item", "")
            if entry_type == "item" and isinstance(target, str) and ":" in target:
                yield target


def repair_and_validate_quest_book(ai_data: dict, all_items=None) -> QualityReport:
    """Repair safe quality issues in place and return a publish gate report."""
    all_items = all_items or {}
    report = QualityReport()
    chapters = ai_data.get("chapters", [])
    if not isinstance(chapters, list) or not chapters:
        report.errors.append("任务书没有有效章节")
        return report

    global_signatures = set()
    title_counts = Counter()
    valid_chapters = []
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        quests = chapter.get("quests", [])
        if not isinstance(quests, list):
            chapter["quests"] = []
            quests = []
        unique = []
        for quest in quests:
            if not isinstance(quest, dict):
                continue
            signatures = quest_task_signatures(quest)
            if signatures and signatures.issubset(global_signatures):
                report.duplicate_goals_removed += 1
                continue
            global_signatures.update(signatures)
            title = str(quest.get("title", "") or "未命名任务").strip()
            title_counts[title.casefold()] += 1
            if title_counts[title.casefold()] > 1:
                quest["title"] = f"{title} · {chapter.get('title', '本章')}"
                report.duplicate_titles_renamed += 1
            description = quest.get("description")
            if not isinstance(description, list) or not any(str(line).strip() for line in description):
                quest["description"] = _basic_description(quest, all_items)
                report.descriptions_added += 1
            if not isinstance(quest.get("tasks"), list) or not quest["tasks"]:
                quest["tasks"] = [{"type": "checkmark"}]
                report.warnings.append(f"任务“{quest['title']}”没有有效目标，已改为确认任务")
            unique.append(quest)
        valid_ids = {str(quest.get("id")) for quest in unique if quest.get("id")}
        for quest in unique:
            dependencies = quest.get("dependencies", [])
            if not isinstance(dependencies, list):
                dependencies = []
            cleaned = [value for value in dependencies if str(value) in valid_ids]
            report.broken_dependencies_removed += len(dependencies) - len(cleaned)
            quest["dependencies"] = cleaned
        chapter["quests"] = unique
        if not unique:
            report.warnings.append(f"空章节“{chapter.get('title', '未命名章节')}”已跳过")
            continue
        valid_chapters.append(chapter)
        report.quests += len(unique)
        report.chapters += 1

    ai_data["chapters"] = valid_chapters
    for chapter in valid_chapters:
        for quest in chapter.get("quests", []):
            for item_id in _iter_item_targets(quest):
                namespace = item_id.split(":", 1)[0]
                namespace_items = all_items.get(namespace)
                if (
                    namespace != "minecraft"
                    and isinstance(namespace_items, dict)
                    and namespace_items
                    and item_id not in namespace_items
                ):
                    report.warnings.append(f"无法确认物品 ID：{item_id}（{quest.get('title', '未命名任务')}）")

    if report.quests == 0:
        report.errors.append("任务书中没有可写入的任务")
    return report


def quality_report_text(report: QualityReport) -> str:
    status = "可发布" if report.publishable else "未通过"
    lines = [
        "=== AutoFTBQ 生成质量报告 ===",
        f"状态: {status}",
        f"章节: {report.chapters}",
        f"任务: {report.quests}",
        f"补全正文: {report.descriptions_added}",
        f"移除重复目标: {report.duplicate_goals_removed}",
        f"重命名重复标题: {report.duplicate_titles_renamed}",
        f"移除失效依赖: {report.broken_dependencies_removed}",
    ]
    if report.errors:
        lines.append("\n--- 阻止发布的问题 ---")
        lines.extend(f"- {value}" for value in report.errors)
    if report.warnings:
        lines.append("\n--- 建议检查 ---")
        lines.extend(f"- {value}" for value in report.warnings[:200])
        if len(report.warnings) > 200:
            lines.append(f"- 其余 {len(report.warnings) - 200} 项已省略")
    return "\n".join(lines) + "\n"
