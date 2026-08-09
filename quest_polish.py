"""AI polish pass: rewrite quest wording to read like a human-made quest book."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Callable

from human_corpus import HumanQuestCorpus


STYLE_GUIDE = (
    "你是 FTB Quests 任务书的文案润色师。整合包作者手工写的任务书，"
    "读起来像导游在跟玩家说话，而不是功能说明书。\n\n"
    "【人类写法风格】\n"
    "1. subtitle 是点睛之笔：一句口语化的引导或提示，例如：\n"
    "   - \"世界那么大 肯定去看看啦\"\n"
    "   - \"先找个安全的地方定居安家吧！\"\n"
    "   - \"更加nb的附魔台\"\n"
    "2. description 是实用干货：告诉玩家怎么做、去哪找、有什么要注意，"
    "而不是复述任务目标。可以分多行，允许用 Minecraft 颜色代码"
    "（&a &b &c &d &e &f &6 &9 等）突出重点词。\n"
    "3. 语气口语化，可以玩梗，但信息必须准确。\n"
    "4. 不要写教科书式套话，不要写\"本任务的目标是……\"，不要重复任务标题。\n"
    "5. 保留任务原有结构：只能修改 subtitle 和 description，其他字段一律不动。\n\n"
    "【输出格式】\n"
    "只输出 JSON，不要 markdown：\n"
    '{"patches": [{"quest": "任务ID", "subtitle": "新副标题", '
    '"description": ["第一行", "第二行"]}]}\n'
    "- subtitle 和 description 至少输出一个\n"
    "- description 必须是字符串数组\n"
    "- quest 必须是给出的任务 ID，不能编造\n"
)


_PATCH_RE = re.compile(r"\{.*\}", re.DOTALL)
_FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)```", re.DOTALL)


def _task_type_summary(quest: dict) -> str:
    types: list[str] = []
    for task in quest.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_type = str(task.get("type", "")).lower().split(":", 1)[-1]
        if task_type:
            types.append(task_type)
    return ",".join(types) or "checkmark"


def _quest_brief(quest: dict) -> str:
    quest_id = str(quest.get("id", "") or "")
    title = str(quest.get("title", "") or "")
    subtitle = str(quest.get("subtitle", "") or "")
    description = quest.get("description", [])
    if isinstance(description, str):
        description = [description]
    description_text = " / ".join(str(line) for line in description if line)
    return (
        f"- id: {quest_id} | 标题: {title or '(无)'} | 类型: {_task_type_summary(quest)}"
        f" | 当前副标题: {subtitle or '(无)'} | 当前描述: {description_text or '(无)'}"
    )


def is_polished(quest: dict) -> bool:
    """A quest counts as polished when it has both a subtitle and a description."""
    return bool(str(quest.get("subtitle", "") or "").strip()) and bool(
        quest.get("description")
    )


class QuestPolishService:
    """Polish subtitle/description chapter by chapter with human examples."""

    def __init__(
        self,
        client: Any,
        corpus: HumanQuestCorpus | None = None,
        progress: Callable[[str, int | None], None] | None = None,
        max_quests_per_batch: int = 12,
    ):
        self.client = client
        self.corpus = corpus if corpus is not None else HumanQuestCorpus()
        self.progress = progress
        self.max_quests_per_batch = max(3, int(max_quests_per_batch))

    def _report(self, message: str) -> None:
        print(f"[POLISH] {message}")
        if self.progress:
            self.progress(message, None)

    def _build_prompt(self, quests: list[dict]) -> str:
        task_types = [_task_type_summary(quest) for quest in quests]
        namespaces: set[str] = set()
        for quest in quests:
            for task in quest.get("tasks", []):
                if not isinstance(task, dict):
                    continue
                for field in ("item", "entity", "advancement", "dimension"):
                    target = task.get(field) or task.get("target")
                    if isinstance(target, str) and ":" in target:
                        namespaces.add(target.split(":", 1)[0])
        examples = self.corpus.style_examples_text(
            task_types,
            namespaces=namespaces,
            language="zh",
            limit=3,
        )
        lines = ["=== 需要润色的任务 ==="]
        lines.extend(_quest_brief(quest) for quest in quests)
        if examples:
            lines.append("")
            lines.append(examples)
        lines.append("")
        lines.append("请为以上每个任务输出 subtitle 和 description 的润色补丁。")
        return "\n".join(lines)

    def _parse_patch(self, text: str) -> list[dict]:
        """Extract the patch list, tolerating markdown fences and stray text."""
        candidates: list[str] = []
        stripped = str(text or "").strip()
        if stripped:
            candidates.append(stripped)
        fence = _FENCE_RE.search(stripped)
        if fence:
            candidates.append(fence.group(1).strip())
        match = _PATCH_RE.search(stripped)
        if match:
            candidates.append(match.group(0))

        data = None
        last_error: Exception | None = None
        for candidate in candidates:
            try:
                data = json.loads(candidate)
                break
            except Exception as exc:
                last_error = exc
                try:
                    from quest_parser import repair_json
                    data = json.loads(repair_json(candidate))
                    break
                except Exception:
                    continue
        if data is None:
            raise ValueError(f"no valid JSON in polish response: {last_error}")
        patches = data.get("patches", data) if isinstance(data, dict) else data
        if not isinstance(patches, list):
            raise ValueError("patches is not a list")
        return [patch for patch in patches if isinstance(patch, dict)]

    def _apply_patch(self, chapter: dict, patches: list[dict]) -> tuple[int, list[str]]:
        quest_by_id = {
            str(quest.get("id", "") or ""): quest
            for quest in chapter.get("quests", [])
            if isinstance(quest, dict)
        }
        applied = 0
        warnings: list[str] = []
        for patch in patches:
            quest_id = str(patch.get("quest", "") or "")
            quest = quest_by_id.get(quest_id)
            if quest is None:
                warnings.append(f"未知任务ID，跳过: {quest_id}")
                continue
            allowed = {"quest", "subtitle", "description"}
            extra = set(patch.keys()) - allowed
            if extra:
                warnings.append(f"任务 {quest_id} 含不允许修改的字段 {sorted(extra)}，忽略这些字段")
            changed = False
            if "subtitle" in patch:
                subtitle = patch.get("subtitle")
                if subtitle is None:
                    quest.pop("subtitle", None)
                elif isinstance(subtitle, str):
                    quest["subtitle"] = subtitle
                changed = True
            if "description" in patch:
                description = patch.get("description")
                if isinstance(description, str):
                    description = [description]
                if isinstance(description, list):
                    lines = [
                        str(line)
                        for line in description
                        if isinstance(line, (str, int, float))
                    ]
                    if lines:
                        quest["description"] = lines
                    else:
                        quest.pop("description", None)
                changed = True
            if changed:
                applied += 1
        return applied, warnings

    def _polish_batch(self, quests: list[dict]) -> tuple[list[dict], str | None]:
        prompt = self._build_prompt(quests)
        messages = [
            {"role": "system", "content": STYLE_GUIDE},
            {"role": "user", "content": prompt},
        ]
        # Each quest only needs a short subtitle plus a few description lines;
        # keep the cap low so batches finish quickly and avoid long timeouts.
        max_tokens = max(2048, len(quests) * 500)
        for attempt in range(2):
            content = ""
            try:
                started = time.time()
                print(f"[POLISH] 调用 API(批 {len(quests)} 任务, 尝试 {attempt + 1})...", flush=True)
                content, truncated = self.client.chat(
                    messages,
                    temperature=0.75,
                    max_tokens=max_tokens,
                )
                print(f"[POLISH] API 返回耗时 {round(time.time() - started, 1)}s", flush=True)
                if truncated:
                    raise ValueError("polish response truncated")
                return self._parse_patch(content), content
            except Exception as exc:
                if content:
                    try:
                        os.makedirs("polish_debug", exist_ok=True)
                        debug_path = os.path.join(
                            "polish_debug",
                            f"failed_{int(time.time())}_{attempt}.txt",
                        )
                        with open(debug_path, "w", encoding="utf-8") as handle:
                            handle.write(str(content)[:30000])
                    except Exception:
                        pass
                if attempt == 0:
                    self._report(f"批次润色失败，重试一次: {exc}")
                else:
                    return [], None
        return [], None

    def polish_chapter(self, chapter: dict) -> tuple[dict, dict]:
        quests = [
            quest
            for quest in chapter.get("quests", [])
            if isinstance(quest, dict)
        ]
        if not quests:
            return chapter, {"applied": 0, "warnings": []}
        pending = [quest for quest in quests if not is_polished(quest)]
        if not pending:
            return chapter, {
                "applied": 0,
                "warnings": [],
                "skipped": len(quests),
                "quests": len(quests),
            }
        applied_total = 0
        warnings: list[str] = []
        for start in range(0, len(pending), self.max_quests_per_batch):
            batch = pending[start:start + self.max_quests_per_batch]
            patches, _raw = self._polish_batch(batch)
            if patches:
                applied, batch_warnings = self._apply_patch(chapter, patches)
                applied_total += applied
                warnings.extend(batch_warnings)
        return chapter, {
            "applied": applied_total,
            "warnings": warnings,
            "skipped": len(quests) - len(pending),
            "quests": len(quests),
        }

    def polish_book(self, ai_data: dict) -> tuple[dict, dict]:
        """Polish every chapter and return (data, report)."""
        report: dict[str, dict] = {}
        chapters = ai_data.get("chapters", [])
        for index, chapter in enumerate(chapters):
            if not isinstance(chapter, dict):
                continue
            chapter_title = str(chapter.get("title", "") or f"Chapter {index + 1}")
            self._report(f"润色章节 {index + 1}/{len(chapters)}: {chapter_title}")
            self.polish_chapter(chapter)
            report[chapter_title] = {
                "quests": len(chapter.get("quests", [])),
            }
        return ai_data, report
