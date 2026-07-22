"""Orchestration for deterministic staged quest generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

try:
    from .quest_prompts import STAGED_SYSTEM_PROMPT
except ImportError:
    from quest_prompts import STAGED_SYSTEM_PROMPT


def calculate_max_tokens(
    mod_count: int,
    engine: str,
    density: str,
    custom_max_tokens=None,
    is_continuation: bool = False,
) -> int:
    """Apply the existing model-count, engine, and density token policy."""
    if custom_max_tokens is not None:
        return int(custom_max_tokens)
    if mod_count <= 5:
        base = 16384
    elif mod_count <= 10:
        base = 32768
    elif mod_count <= 20:
        base = 49152
    elif mod_count <= 30:
        base = 65536
    elif mod_count <= 50:
        base = 98304
    else:
        base = 131072
    if engine == "ollama":
        base = min(base, 49152 if is_continuation else 40960)
    multiplier = {
        "light": 0.7,
        "medium": 1.0,
        "rich": 1.5,
        "max": 2.0,
    }.get(density, 1.0)
    return int(base * multiplier) if multiplier != 1.0 else base


@dataclass(frozen=True)
class StagedGenerationHooks:
    build_plan: Callable[[], list[dict]]
    build_catalog: Callable[[dict], str]
    build_prompt: Callable[[dict, int, list[str], str, str], str]
    parse_batch: Callable[[str], list[dict]]
    deduplicate_batch: Callable[[list[dict], list[str]], list[dict]]
    build_fallback: Callable[[dict, int, list[dict]], list[dict]]
    normalize_chapter: Callable[[str, list[dict]], list[dict]]
    max_tokens: Callable[[], int]


class StagedGenerationService:
    """Coordinate bounded model calls while application code owns the quota."""

    def __init__(self, client, density: str, progress, hooks: StagedGenerationHooks):
        self.client = client
        self.density = density
        self.progress = progress
        self.hooks = hooks

    def generate(self, wiki_text: str = "") -> str:
        if self.client is None:
            raise RuntimeError("未配置可用的 AI 客户端")
        plan = self.hooks.build_plan()
        total_target = sum(chapter["target"] for chapter in plan)
        print(f"[STAGED] density={self.density}, chapters={len(plan)}, target={total_target}")
        self.progress(f"已规划 {len(plan)} 个章节，共 {total_target} 个任务", 14)
        completed = 0
        chapters = []

        for chapter in plan:
            catalog = self.hooks.build_catalog(chapter)
            quests = []
            while len(quests) < chapter["target"]:
                requested = min(chapter["batch_size"], chapter["target"] - len(quests))
                remaining = requested
                attempts = 0
                while remaining > 0 and attempts < 3:
                    existing_titles = [quest.get("title", "") for quest in quests]
                    prompt = self.hooks.build_prompt(
                        chapter,
                        remaining,
                        existing_titles,
                        catalog,
                        wiki_text,
                    )
                    batch_tokens = max(3072, min(12288, remaining * 1100))
                    max_tokens = min(batch_tokens, self.hooks.max_tokens())
                    content, truncated = self.client.chat(
                        [
                            {"role": "system", "content": STAGED_SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.45,
                        max_tokens=max_tokens,
                    )
                    parsed = [] if truncated else self.hooks.parse_batch(content)
                    parsed = self.hooks.deduplicate_batch(parsed, existing_titles)
                    accepted = parsed[:remaining]
                    quests.extend(accepted)
                    remaining -= len(accepted)
                    attempts += 1
                if remaining > 0:
                    quests.extend(self.hooks.build_fallback(chapter, remaining, quests))
                completed += requested
                percent = 15 + int(60 * completed / max(1, total_target))
                self.progress(
                    f"分阶段生成：{chapter['title']} {len(quests)}/{chapter['target']}",
                    percent,
                )

            normalized = self.hooks.normalize_chapter(
                chapter["id"],
                quests[:chapter["target"]],
            )
            chapters.append({
                "id": chapter["id"],
                "title": chapter["title"],
                "quests": normalized,
            })
        return json.dumps({"title": "整合包任务指南", "chapters": chapters}, ensure_ascii=False)
