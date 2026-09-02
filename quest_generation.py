"""Orchestration for deterministic staged quest generation."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Callable

try:
    from .quest_prompts import STAGED_SYSTEM_PROMPT
except ImportError:
    from quest_prompts import STAGED_SYSTEM_PROMPT


class GenerationInterrupted(RuntimeError):
    """Raised when staged generation stops early (e.g. balance/tokens exhausted).

    Subclasses :class:`RuntimeError` so existing callers that catch runtime
    failures keep working. ``partial_json`` carries every completed chapter
    plus the current chapter's quests generated so far, so the caller can save
    a usable partial quest book instead of losing all work.
    """

    def __init__(self, partial_json, completed_chapters=0, total_chapters=0, reason=""):
        super().__init__(reason or "生成被中断")
        self.partial_json = partial_json
        self.completed_chapters = int(completed_chapters)
        self.total_chapters = int(total_chapters)
        self.reason = str(reason or "生成被中断")


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
    build_context: Callable[[dict, list[dict], str], str] | None = None
    filter_batch: Callable[[dict, list[dict], list[dict]], list[dict]] | None = None
    chat_batch: Callable[[list[dict], float, int], tuple[str, bool]] | None = None


class StagedGenerationService:
    """Coordinate bounded model calls while application code owns the quota."""

    def __init__(self, client, density: str, progress, hooks: StagedGenerationHooks, checkpoint_path=None):
        self.client = client
        self.density = density
        self.progress = progress
        self.hooks = hooks
        self.checkpoint_path = checkpoint_path

    def _save_checkpoint(self, chapters, plan, interrupted=False, current_quests=None, current_chapter=None):
        """Persist generation progress after every completed chapter."""
        if not self.checkpoint_path:
            return
        data = {
            "title": "整合包任务指南",
            "chapters": chapters,
            "_progress": {
                "completed_chapters": len(chapters),
                "total_chapters": len(plan),
                "interrupted": bool(interrupted),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
        }
        if interrupted and current_chapter is not None:
            data["_progress"]["current_chapter"] = {
                "id": current_chapter.get("id", ""),
                "title": current_chapter.get("title", ""),
                "quests_generated": len(current_quests or []),
                "target": current_chapter.get("target", 0),
            }
        try:
            path = os.path.abspath(self.checkpoint_path)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp_path = path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
            print(f"[CHECKPOINT] 进度已保存: {len(chapters)}/{len(plan)} 章节 -> {path}")
        except OSError as exc:
            print(f"[CHECKPOINT] 保存进度失败（不影响生成）: {exc}")

    def generate(self, wiki_text: str = "") -> str:
        if self.client is None:
            raise RuntimeError("未配置可用的 AI 客户端")
        plan = self.hooks.build_plan()
        total_target = sum(chapter["target"] for chapter in plan)
        print(f"[STAGED] density={self.density}, chapters={len(plan)}, target={total_target}")
        self.progress(f"已规划 {len(plan)} 个章节，共 {total_target} 个任务", 14)
        completed = 0
        chapters = []
        global_quests = []

        for chapter in plan:
            catalog = self.hooks.build_catalog(chapter)
            quests = []
            exhausted = False
            interrupted = False
            interrupted_reason = ""
            try:
                while len(quests) < chapter["target"] and not exhausted:
                    requested = min(chapter["batch_size"], chapter["target"] - len(quests))
                    remaining = requested
                    attempts = 0
                    while remaining > 0 and attempts < 3:
                        known_quests = global_quests + quests
                        existing_titles = [quest.get("title", "") for quest in known_quests]
                        batch_catalog = catalog
                        batch_wiki_text = wiki_text
                        if self.hooks.build_context is not None:
                            batch_catalog = self.hooks.build_context(chapter, known_quests, catalog)
                            batch_wiki_text = ""
                        prompt = self.hooks.build_prompt(
                            chapter,
                            remaining,
                            existing_titles,
                            batch_catalog,
                            batch_wiki_text,
                        )
                        batch_tokens = max(3072, min(12288, remaining * 1100))
                        max_tokens = min(batch_tokens, self.hooks.max_tokens())
                        messages = [
                            {"role": "system", "content": STAGED_SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ]
                        if self.hooks.chat_batch is not None:
                            content, truncated = self.hooks.chat_batch(messages, 0.45, max_tokens)
                        else:
                            content, truncated = self.client.chat(
                                messages,
                                temperature=0.45,
                                max_tokens=max_tokens,
                            )
                        parsed = [] if truncated else self.hooks.parse_batch(content)
                        parsed = self.hooks.deduplicate_batch(parsed, existing_titles)
                        if self.hooks.filter_batch is not None:
                            parsed = self.hooks.filter_batch(chapter, parsed, known_quests)
                        accepted = parsed[:remaining]
                        quests.extend(accepted)
                        remaining -= len(accepted)
                        attempts += 1
                    if remaining > 0:
                        fallback = self.hooks.build_fallback(
                            chapter,
                            remaining,
                            global_quests + quests,
                        )
                        quests.extend(fallback)
                        if len(fallback) < remaining:
                            exhausted = True
                    completed += requested - remaining + (len(fallback) if remaining > 0 else 0)
                    percent = 15 + int(60 * completed / max(1, total_target))
                    self.progress(
                        f"分阶段生成：{chapter['title']} {len(quests)}/{chapter['target']}",
                        percent,
                    )
            except Exception as exc:
                # Token/额度不足、网络中断等都会走到这里：
                # 把当前章节已生成的 quest 与已完成章节一并保存下来。
                interrupted = True
                interrupted_reason = str(exc) or type(exc).__name__
                print(f"[STAGED] 章节生成中断：{chapter.get('title', '?')} -> {interrupted_reason}")

            normalized = self.hooks.normalize_chapter(
                chapter["id"],
                quests[:chapter["target"]],
            )
            chapters.append({
                "id": chapter["id"],
                "title": chapter["title"],
                "quests": normalized,
            })
            global_quests.extend(normalized)
            # 每完成/中断一个章节，立即保存进度。
            self._save_checkpoint(
                chapters,
                plan,
                interrupted=interrupted,
                current_quests=quests,
                current_chapter=chapter,
            )
            if interrupted:
                partial_json = json.dumps(
                    {"title": "整合包任务指南", "chapters": chapters},
                    ensure_ascii=False,
                )
                raise GenerationInterrupted(
                    partial_json,
                    completed_chapters=len(chapters),
                    total_chapters=len(plan),
                    reason=interrupted_reason,
                )
        return json.dumps({"title": "整合包任务指南", "chapters": chapters}, ensure_ascii=False)
