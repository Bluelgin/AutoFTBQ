"""Extraction, repair, and deduplication for AI-generated quest JSON."""

from __future__ import annotations

import json
import re
from typing import Any

try:
    from .quest_schema import extract_quest_batch
except ImportError:
    from quest_schema import extract_quest_batch


def _missing_closers(text: str) -> str:
    stack = []
    in_string = False
    escaped = False
    pairs = {"}": "{", "]": "["}
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append(char)
        elif char in pairs and stack and stack[-1] == pairs[char]:
            stack.pop()
    return "".join("}" if opener == "{" else "]" for opener in reversed(stack))


def extract_json(text: str) -> str:
    """Extract a likely JSON object while preserving legacy truncation repair."""
    if not text:
        return "{}"
    fenced = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return text
    raw = text[start:end + 1]

    last_good = -1
    endings = [
        "\n    }\n",
        "\n  }\n",
        "\n  ]\n",
        "\n    ]\n",
        "}\n",
        "]\n",
    ]
    for ending in endings:
        last_good = max(last_good, raw.rfind(ending))
    if last_good > len(raw) * 0.5:
        raw = raw[:last_good + 1]
        raw += _missing_closers(raw)
    return raw


def repair_json(text: str) -> str:
    """Repair common commas, delimiters, and invalid escape sequences."""
    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)
    text = re.sub(r"}\s*{", "},{", text)
    text = re.sub(r"]\s*{", "],{", text)
    text = re.sub(r"}\s*\[", "},[", text)
    text = re.sub(r"]\s*\[", "],[", text)
    text += _missing_closers(text)
    text = re.sub(r"\\(?=u(?:[0-9a-fA-F]{0,3}(?:[^0-9a-fA-F\"\\\\]|$)))", r"\\\\", text)
    text = re.sub(r"\\([^\"\\\\/bfnrtu])", r"\\\\\1", text)
    return text


def parse_json_document(raw_text: str, attempts: int = 3) -> tuple[Any | None, str]:
    """Parse extracted JSON after a bounded number of deterministic repairs."""
    candidate = extract_json(raw_text)
    for _ in range(max(1, attempts)):
        try:
            return json.loads(candidate), candidate
        except json.JSONDecodeError:
            candidate = repair_json(candidate)
    return None, candidate


def parse_quest_batch(raw_text: str) -> list[dict]:
    data, _ = parse_json_document(raw_text)
    return extract_quest_batch(data)


def reorganize_json(raw_text: str) -> str:
    data, _ = parse_json_document(raw_text, attempts=1)
    if data is None:
        return raw_text
    return json.dumps(data, ensure_ascii=False)


def deduplicate_quest_book(ai_data: dict) -> tuple[dict, int]:
    """Remove duplicate quest titles and source IDs within each chapter."""
    removed = 0
    for chapter in ai_data.get("chapters", []):
        if not isinstance(chapter, dict):
            continue
        quests = chapter.get("quests", [])
        if not isinstance(quests, list):
            continue
        seen_titles = set()
        seen_ids = set()
        unique = []
        for quest in quests:
            if not isinstance(quest, dict):
                continue
            quest_id = quest.get("id", "")
            title = quest.get("title", "")
            if title and title in seen_titles:
                print(f"[DEDUP] Removing duplicate quest (same title): {title}")
                removed += 1
                continue
            if quest_id and quest_id in seen_ids:
                print(f"[DEDUP] Removing duplicate quest (same id): {quest_id} ({title})")
                removed += 1
                continue
            if title:
                seen_titles.add(title)
            if quest_id:
                seen_ids.add(quest_id)
            unique.append(quest)
        chapter["quests"] = unique
    print(f"[DEDUP] Removed {removed} duplicate quests")
    return ai_data, removed


def repair_json_with_ai(client, broken_text: str, lang: str = "zh"):
    """Ask the configured model to repair syntax only, then parse its response."""
    if client is None:
        return None
    input_text = broken_text[:80000]
    if lang == "zh":
        system_prompt = "你是一个JSON修复专家。只修复语法错误，不改变任何数据内容。"
        user_prompt = (
            "修复下面FTB任务书JSON的语法错误。规则：\n"
            "1. 只修复JSON语法错误（字符串未闭合、括号不匹配、逗号缺失/多余、换行符）\n"
            "2. 不要删除、添加或修改任何章节、任务、物品ID、标题等数据\n"
            "3. 保持所有文本原样\n"
            "4. 只输出修复后的JSON，不要任何解释\n\n"
            f"JSON：\n{input_text}"
        )
    else:
        system_prompt = "You are a JSON repair expert. Fix syntax errors only, do not change any data."
        user_prompt = (
            "Fix the JSON syntax errors below. Rules:\n"
            "1. Only fix JSON syntax errors (unclosed strings, mismatched brackets, missing/extra commas)\n"
            "2. Do not delete, add or modify any chapters, quests, item IDs, titles, etc.\n"
            "3. Keep all text content as-is\n"
            "4. Output ONLY the fixed JSON, no explanation\n\n"
            f"JSON:\n{input_text}"
        )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    max_tokens = min(int(len(input_text) * 1.3), 131072)
    try:
        result_text, _ = client.chat(messages, temperature=0.1, max_tokens=max_tokens)
        fixed = extract_json(result_text)
        return json.loads(fixed)
    except Exception as exc:
        print(f"[AI_REPAIR] Failed: {exc}")
        return None
