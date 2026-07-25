"""Chapter-scoped knowledge retrieval for staged quest generation."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


MILESTONE_KEYWORDS = (
    "controller", "machine", "generator", "furnace", "crusher", "press",
    "assembler", "altar", "table", "core", "terminal", "drive", "cell",
    "gear", "plate", "ingot", "crystal", "pickaxe", "sword", "drill",
)


@dataclass(frozen=True)
class KnowledgeDocument:
    namespace: str
    source: str
    text: str
    title: str = ""


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _trim_lines(text: str, limit: int) -> str:
    if not text or limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    lines = []
    used = 0
    for line in text.splitlines():
        required = len(line) + (1 if lines else 0)
        if used + required > limit:
            break
        lines.append(line)
        used += required
    return "\n".join(lines)


def _task_signature(task: object) -> tuple[str, str] | None:
    if not isinstance(task, dict):
        return None
    task_type = str(task.get("type", "")).strip().lower()
    target = task.get("target") or task.get("item") or task.get("entity", "")
    if task_type == "checkmark" or not isinstance(target, str) or not target.strip():
        return None
    return task_type, target.strip().lower()


def quest_task_signatures(quest: object) -> set[tuple[str, str]]:
    if not isinstance(quest, dict):
        return set()
    tasks = quest.get("tasks", [])
    if not isinstance(tasks, list):
        return set()
    return {
        signature
        for signature in (_task_signature(task) for task in tasks)
        if signature is not None
    }


class QuestKnowledgeBase:
    """Build compact, deterministic context for one chapter and one batch."""

    def __init__(
        self,
        all_items: dict | None = None,
        recipe_inputs: dict | None = None,
        max_context_chars: int = 14000,
    ):
        self.all_items = all_items or {}
        self.recipe_inputs = recipe_inputs or {}
        self.max_context_chars = max(4000, int(max_context_chars))
        self.documents: list[KnowledgeDocument] = []

    def add_document(
        self,
        namespace: str,
        source: str,
        text: str,
        title: str = "",
    ) -> None:
        cleaned = str(text or "").strip()
        if not namespace or not cleaned:
            return
        self.documents.append(
            KnowledgeDocument(
                namespace=str(namespace),
                source=str(source or "notes"),
                text=cleaned,
                title=str(title or ""),
            )
        )

    def _chapter_namespaces(self, chapter: dict) -> set[str]:
        requested = {
            str(namespace)
            for namespace in chapter.get("namespaces", [])
            if namespace
        }
        requested.update(
            str(mod.get("mod_id"))
            for mod in chapter.get("mods", [])
            if isinstance(mod, dict) and mod.get("mod_id")
        )
        if not requested and str(chapter.get("id", "")).startswith("vanilla_"):
            requested.add("minecraft")

        available = set(self.all_items)
        available.update(
            output.split(":", 1)[0]
            for output in self.recipe_inputs
            if isinstance(output, str) and ":" in output
        )
        resolved = set(requested)
        for namespace in requested:
            needle = _normalized(namespace)
            if len(needle) < 3:
                continue
            for candidate in available:
                normalized_candidate = _normalized(candidate)
                if needle in normalized_candidate or normalized_candidate in needle:
                    resolved.add(candidate)
        return resolved

    def _chapter_documents(self, namespaces: set[str]) -> list[KnowledgeDocument]:
        normalized_namespaces = {_normalized(namespace) for namespace in namespaces}
        selected = []
        for document in self.documents:
            document_namespace = _normalized(document.namespace)
            if document_namespace in normalized_namespaces:
                selected.append(document)
                continue
            if len(document_namespace) >= 3 and any(
                document_namespace in namespace or namespace in document_namespace
                for namespace in normalized_namespaces
                if len(namespace) >= 3
            ):
                selected.append(document)
        return selected

    def _chapter_items(self, namespaces: set[str]) -> list[tuple[str, str]]:
        items = []
        for namespace in sorted(namespaces):
            namespace_items = self.all_items.get(namespace, {})
            if isinstance(namespace_items, dict):
                items.extend(
                    (str(item_id), str(display_name))
                    for item_id, display_name in namespace_items.items()
                )
        return sorted(set(items))

    def _ranked_candidates(
        self,
        namespaces: set[str],
        covered_targets: set[str],
    ) -> list[str]:
        recipe_outputs = [
            output
            for output in self.recipe_inputs
            if isinstance(output, str)
            and ":" in output
            and output.split(":", 1)[0] in namespaces
        ]
        depth_cache = {}

        def recipe_depth(item_id: str, visiting=None) -> int:
            if item_id in depth_cache:
                return depth_cache[item_id]
            visiting = set(visiting or ())
            if item_id in visiting:
                return 0
            visiting.add(item_id)
            inputs = self.recipe_inputs.get(item_id, [])
            child_depths = [
                recipe_depth(input_id, visiting)
                for input_id in inputs
                if input_id in self.recipe_inputs
            ]
            depth = 1 + (max(child_depths) if child_depths else 0)
            depth_cache[item_id] = depth
            return depth

        recipe_outputs.sort(
            key=lambda item_id: (
                recipe_depth(item_id),
                not any(keyword in item_id.lower() for keyword in MILESTONE_KEYWORDS),
                item_id,
            )
        )
        items = [item_id for item_id, _ in self._chapter_items(namespaces)]
        milestones = [
            item_id
            for item_id in items
            if any(keyword in item_id.lower() for keyword in MILESTONE_KEYWORDS)
        ]
        ordered = recipe_outputs + milestones + items
        result = []
        seen = set()
        for item_id in ordered:
            normalized_item = item_id.lower()
            if normalized_item in seen or normalized_item in covered_targets:
                continue
            seen.add(normalized_item)
            result.append(item_id)
        return result

    def _coverage_section(
        self,
        chapter: dict,
        existing_quests: list[dict],
        namespaces: set[str],
    ) -> str:
        covered_signatures = set()
        for quest in existing_quests:
            covered_signatures.update(quest_task_signatures(quest))
        covered_targets = {
            target
            for task_type, target in covered_signatures
            if task_type == "item"
        }
        uncovered = self._ranked_candidates(namespaces, covered_targets)
        summaries = []
        for quest in existing_quests[-24:]:
            title = str(quest.get("title", "")).strip()
            targets = sorted(target for _, target in quest_task_signatures(quest))
            summary = title
            if targets:
                summary += " -> " + ", ".join(targets[:3])
            if summary:
                summaries.append(summary)

        lines = [
            "=== CHAPTER COVERAGE LEDGER ===",
            f"Chapter target: {chapter.get('target', 0)} quests",
            f"Accepted so far: {len(existing_quests)} quests",
        ]
        if summaries:
            lines.append("Already accepted (do not repeat these goals):")
            lines.extend(f"- {summary}" for summary in summaries)
        else:
            lines.append("Already accepted: none; start with entry-level progression.")
        if uncovered:
            lines.append("Recommended uncovered item goals, in priority order:")
            lines.append(", ".join(uncovered[:40]))
        else:
            lines.append(
                "Item catalog coverage is complete; use distinct mechanics, exploration, "
                "kill, advancement, dimension, or checkmark guidance tasks."
            )
        return "\n".join(lines)

    def _recipe_section(self, namespaces: set[str]) -> str:
        outputs = self._ranked_candidates(namespaces, set())
        lines = []
        for output in outputs:
            inputs = self.recipe_inputs.get(output)
            if not isinstance(inputs, list) or not inputs:
                continue
            lines.append(f"- {output} <- {' + '.join(map(str, inputs[:6]))}")
            for item_id in inputs[:3]:
                sub_inputs = self.recipe_inputs.get(item_id)
                if isinstance(sub_inputs, list) and sub_inputs:
                    lines.append(
                        f"  prerequisite: {item_id} <- {' + '.join(map(str, sub_inputs[:5]))}"
                    )
                    break
            if len(lines) >= 30:
                break
        if not lines:
            return ""
        return "=== RELEVANT RECIPE PROGRESSION ===\n" + "\n".join(lines)

    def _document_section(self, namespaces: set[str]) -> str:
        documents = self._chapter_documents(namespaces)
        if not documents:
            return ""
        parts = ["=== CHAPTER-SPECIFIC GUIDES ==="]
        remaining = 3600
        for document in documents:
            heading = f"[{document.source}] {document.title or document.namespace}"
            body = _trim_lines(document.text, min(2200, remaining))
            if not body:
                continue
            parts.extend((heading, body))
            remaining -= len(heading) + len(body)
            if remaining <= 200:
                break
        return "\n".join(parts)

    def build_context(
        self,
        chapter: dict,
        existing_quests: list[dict],
        item_catalog: str,
    ) -> str:
        namespaces = self._chapter_namespaces(chapter)
        sections = [
            _trim_lines(
                self._coverage_section(chapter, existing_quests, namespaces),
                2800,
            ),
            _trim_lines(self._recipe_section(namespaces), 2600),
            _trim_lines(self._document_section(namespaces), 3800),
        ]
        catalog = _trim_lines(str(item_catalog or ""), 4400)
        if catalog:
            sections.append("=== ALLOWED ITEM CATALOG ===\n" + catalog)
        sections.append(
            "Use only this chapter context. Prefer uncovered goals and follow recipe "
            "prerequisites. Do not repeat accepted task targets under a new title."
        )
        return _trim_lines(
            "\n\n".join(section for section in sections if section),
            self.max_context_chars,
        )

    def filter_new_quests(
        self,
        chapter: dict,
        candidates: Iterable[dict],
        existing_quests: list[dict],
    ) -> list[dict]:
        del chapter  # Reserved for chapter-specific validation rules.
        seen_signatures = set()
        for quest in existing_quests:
            seen_signatures.update(quest_task_signatures(quest))

        accepted = []
        for quest in candidates:
            signatures = quest_task_signatures(quest)
            if signatures and signatures.intersection(seen_signatures):
                continue
            accepted.append(quest)
            seen_signatures.update(signatures)
        return accepted
