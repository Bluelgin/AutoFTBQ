"""Human-written questbook corpus extracted from ``example_all``.

The corpus is used as a style reference for the AI polish pass: for each
chapter batch we retrieve a few real tasks of the same kind (item collection,
combat, guidance card, ...) and feed their wording to the model so the
rewritten subtitles/descriptions read like a human modpack author wrote them.
"""

from __future__ import annotations

import os
import re
import gzip
import json
from dataclasses import dataclass, field
from typing import Iterable

from snbt_parser import parse_snbt


CORPUS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "example_all")
CORPUS_INDEX = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "human_style_corpus.json.gz",
)

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_LATIN_RE = re.compile(r"[a-zA-Z]{4,}")


def detect_language(text: str) -> str:
    """Roughly classify a task as zh, en, or mixed."""
    cjk = len(_CJK_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))
    if not cjk and not latin:
        return "zh"
    if cjk >= latin * 2:
        return "zh"
    if latin >= cjk * 2:
        return "en"
    return "mixed"


def _quest_task_types(quest: dict) -> list[str]:
    types: list[str] = []
    for task in quest.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_type = str(task.get("type", "")).lower().split(":", 1)[-1]
        if task_type:
            types.append(task_type)
    if not types:
        types.append("checkmark")
    return types


def _quest_namespaces(quest: dict) -> list[str]:
    namespaces: set[str] = set()
    for field_name in ("icon",):
        icon = quest.get(field_name)
        if isinstance(icon, str) and ":" in icon:
            namespaces.add(icon.split(":", 1)[0])
        elif isinstance(icon, dict):
            item_id = icon.get("id", "")
            if isinstance(item_id, str) and ":" in item_id:
                namespaces.add(item_id.split(":", 1)[0])
    for task in quest.get("tasks", []):
        if not isinstance(task, dict):
            continue
        for field_name in ("item", "entity", "advancement", "dimension", "structure"):
            target = task.get(field_name)
            if isinstance(target, str) and ":" in target:
                namespaces.add(target.split(":", 1)[0])
            elif isinstance(target, dict):
                item_id = target.get("id", "")
                if isinstance(item_id, str) and ":" in item_id:
                    namespaces.add(item_id.split(":", 1)[0])
    for reward in quest.get("rewards", []):
        if not isinstance(reward, dict):
            continue
        target = reward.get("item", "")
        if isinstance(target, str) and ":" in target:
            namespaces.add(target.split(":", 1)[0])
        elif isinstance(target, dict):
            item_id = target.get("id", "")
            if isinstance(item_id, str) and ":" in item_id:
                namespaces.add(item_id.split(":", 1)[0])
    return sorted(namespaces)


@dataclass(frozen=True)
class HumanQuestExample:
    quest_id: str
    title: str
    subtitle: str
    description: tuple[str, ...]
    task_types: tuple[str, ...]
    namespaces: tuple[str, ...]
    source: str
    chapter_title: str
    language: str

    @property
    def text_block(self) -> str:
        """Compact human-readable rendering used inside the polish prompt."""
        lines = [f"[{self.source}] 任务: {self.title or '(无标题)'}"]
        if self.subtitle:
            lines.append(f"  副标题: {self.subtitle}")
        if self.description:
            joined = " / ".join(self.description)
            lines.append(f"  描述: {joined}")
        return "\n".join(lines)


class HumanQuestCorpus:
    """Load every quest from ``example_all`` and offer type-aware retrieval."""

    def __init__(self, root: str = CORPUS_ROOT):
        self.root = root
        self.examples: list[HumanQuestExample] = []
        self.chapters: list[dict] = []
        self._by_type: dict[str, list[HumanQuestExample]] = {}
        self._by_namespace: dict[str, list[HumanQuestExample]] = {}
        self._load()

    def _load(self) -> None:
        if self._load_index():
            return
        if not os.path.isdir(self.root):
            return
        for ep_name in sorted(os.listdir(self.root)):
            chapters_dir = os.path.join(self.root, ep_name, "chapters")
            if not os.path.isdir(chapters_dir):
                continue
            for filename in sorted(os.listdir(chapters_dir)):
                if not filename.endswith(".snbt"):
                    continue
                path = os.path.join(chapters_dir, filename)
                self._load_file(path, ep_name, filename)

    def _load_index(self) -> bool:
        if not os.path.isfile(CORPUS_INDEX):
            return False
        try:
            with gzip.open(CORPUS_INDEX, "rt", encoding="utf-8") as handle:
                data = json.load(handle)
            for raw in data.get("examples", []):
                example = HumanQuestExample(
                    quest_id=str(raw.get("quest_id", "") or ""),
                    title=str(raw.get("title", "") or ""),
                    subtitle=str(raw.get("subtitle", "") or ""),
                    description=tuple(str(line) for line in raw.get("description", [])),
                    task_types=tuple(str(value) for value in raw.get("task_types", [])),
                    namespaces=tuple(str(value) for value in raw.get("namespaces", [])),
                    source=str(raw.get("source", "") or ""),
                    chapter_title=str(raw.get("chapter_title", "") or ""),
                    language=str(raw.get("language", "zh") or "zh"),
                )
                self._index_example(example)
            self.chapters = [
                chapter for chapter in data.get("chapters", []) if isinstance(chapter, dict)
            ]
            return bool(self.examples)
        except Exception as exc:
            print(f"[CORPUS] bundled index unavailable: {exc}")
            self.examples.clear()
            self.chapters.clear()
            self._by_type.clear()
            self._by_namespace.clear()
            return False

    def _index_example(self, example: HumanQuestExample) -> None:
        self.examples.append(example)
        for task_type in example.task_types:
            self._by_type.setdefault(task_type, []).append(example)
        for namespace in example.namespaces:
            self._by_namespace.setdefault(namespace, []).append(example)

    def _load_file(self, path: str, ep_name: str, filename: str) -> None:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                chapter = parse_snbt(handle.read())
        except Exception as exc:
            print(f"[CORPUS] skip {ep_name}/{filename}: {exc}")
            return
        if not isinstance(chapter, dict):
            return
        chapter_title = str(chapter.get("title", "") or "")
        coords: list[tuple[float, float, str]] = []
        for quest in chapter.get("quests", []):
            if not isinstance(quest, dict):
                continue
            quest_id = str(quest.get("id", "") or "")
            title = str(quest.get("title", "") or "")
            subtitle = str(quest.get("subtitle", "") or "")
            description = quest.get("description", [])
            if isinstance(description, str):
                description = [description]
            description = tuple(
                str(line) for line in description if isinstance(line, (str, int, float))
            )
            task_types = tuple(_quest_task_types(quest))
            namespaces = tuple(_quest_namespaces(quest))
            text = title + "\n" + subtitle + "\n" + "\n".join(description)
            language = detect_language(text)
            example = HumanQuestExample(
                quest_id=quest_id,
                title=title,
                subtitle=subtitle,
                description=description,
                task_types=task_types,
                namespaces=namespaces,
                source=f"{ep_name}/{filename}",
                chapter_title=chapter_title,
                language=language,
            )
            self._index_example(example)
            try:
                coords.append(
                    (
                        float(quest.get("x", 0) or 0),
                        float(quest.get("y", 0) or 0),
                        task_types[0] if task_types else "checkmark",
                    )
                )
            except (TypeError, ValueError):
                pass
        if len(coords) >= 4:
            self.chapters.append(
                {
                    "source": f"{ep_name}/{filename}",
                    "title": chapter_title,
                    "coords": coords,
                }
            )

    def query(
        self,
        task_types: Iterable[str],
        namespaces: Iterable[str] | None = None,
        language: str = "zh",
        limit: int = 3,
        exclude_quest_ids: set[str] | None = None,
    ) -> list[HumanQuestExample]:
        """Pick up to ``limit`` examples matching the requested task types.

        Matching is deterministic: same task type first, then namespace overlap,
        then language preference.
        """
        wanted = list(task_types) or ["checkmark"]
        namespaces = [ns for ns in (namespaces or []) if ns]
        exclude = exclude_quest_ids or set()
        pool: list[HumanQuestExample] = []
        seen: set[str] = set()
        for task_type in wanted:
            candidates = list(self._by_type.get(task_type, []))
            candidates.sort(
                key=lambda ex: (
                    ex.language != language,
                    not bool(ex.title),
                    ex.source,
                    ex.quest_id,
                )
            )
            for example in candidates:
                if example.quest_id in seen or example.quest_id in exclude:
                    continue
                if language == "zh" and example.language == "en":
                    continue
                seen.add(example.quest_id)
                pool.append(example)
                if len(pool) >= max(limit, 6):
                    break
            if len(pool) >= max(limit, 6):
                break

        # Prefer namespace overlap within the pool.
        if namespaces:
            ns_match = [
                example
                for example in pool
                if any(ns in example.namespaces for ns in namespaces)
            ]
            ordered = ns_match + [example for example in pool if example not in ns_match]
        else:
            ordered = pool

        # Keep examples that actually carry some human flavor.
        flavored = [
            example
            for example in ordered
            if example.subtitle or example.description or example.title
        ]
        return flavored[:limit]

    def style_examples_text(
        self,
        task_types: Iterable[str],
        namespaces: Iterable[str] | None = None,
        language: str = "zh",
        limit: int = 3,
        exclude_quest_ids: set[str] | None = None,
    ) -> str:
        examples = self.query(
            task_types,
            namespaces=namespaces,
            language=language,
            limit=limit,
            exclude_quest_ids=exclude_quest_ids,
        )
        if not examples:
            return ""
        blocks = [example.text_block for example in examples]
        return "=== 人工任务书写法示例(仅供风格参考) ===\n" + "\n\n".join(blocks)
