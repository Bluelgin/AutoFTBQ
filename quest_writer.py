"""SNBT serialization and rollback-safe output for generated quest books."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from typing import Any, Callable


MARKER_CHAPTER_ID = "ZZZZZZZZZZZZZZZZ"


def _write_text(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _previous_chapter_files(base_dir: str) -> list[str]:
    manifest_path = os.path.join(base_dir, ".autoftbq_manifest.json")
    try:
        with open(manifest_path, "r", encoding="utf-8") as handle:
            value = json.load(handle).get("chapter_files", [])
    except (OSError, ValueError, AttributeError):
        return []
    if not isinstance(value, list):
        return []
    return [name for name in value if isinstance(name, str) and os.path.basename(name) == name]


def _commit_stage(base_dir: str, stage_dir: str, relative_files: list[str], previous_files: list[str]) -> None:
    """Install all staged files or restore the complete previous generated set."""
    parent_dir = os.path.dirname(os.path.abspath(base_dir))
    backup_dir = tempfile.mkdtemp(prefix=".autoftbq-backup-", dir=parent_dir)
    manifest = ".autoftbq_manifest.json"
    install_order = [path for path in relative_files if path != manifest] + [manifest]
    backup_candidates = list(install_order)
    backup_candidates.extend(os.path.join("chapters", name) for name in previous_files)
    backup_candidates = list(dict.fromkeys(backup_candidates))
    backed_up: list[str] = []
    installed: list[str] = []
    keep_backup = False

    try:
        os.makedirs(base_dir, exist_ok=True)
        for relative in backup_candidates:
            target = os.path.join(base_dir, relative)
            if not os.path.isfile(target):
                continue
            backup = os.path.join(backup_dir, relative)
            os.makedirs(os.path.dirname(backup), exist_ok=True)
            os.replace(target, backup)
            backed_up.append(relative)

        for relative in install_order:
            source = os.path.join(stage_dir, relative)
            target = os.path.join(base_dir, relative)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            os.replace(source, target)
            installed.append(relative)
    except Exception as commit_error:
        rollback_errors = []
        for relative in reversed(installed):
            target = os.path.join(base_dir, relative)
            try:
                if os.path.isfile(target):
                    os.remove(target)
            except OSError as exc:
                rollback_errors.append(f"无法移除 {relative}: {exc}")
        for relative in reversed(backed_up):
            backup = os.path.join(backup_dir, relative)
            target = os.path.join(base_dir, relative)
            try:
                if os.path.isfile(backup):
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    os.replace(backup, target)
            except OSError as exc:
                rollback_errors.append(f"无法恢复 {relative}: {exc}")
        if rollback_errors:
            keep_backup = True
            details = "; ".join(rollback_errors)
            raise RuntimeError(
                f"SNBT 写入失败且自动回滚不完整，备份已保留在 {backup_dir}：{details}"
            ) from commit_error
        raise
    finally:
        if not keep_backup:
            shutil.rmtree(backup_dir, ignore_errors=True)


def write_quest_book(
    base_dir: str,
    ai_data: dict,
    *,
    uid: Callable[[], str],
    normalize_item: Callable[[Any], str],
    item_count: Callable[[dict, Any], int],
    to_snbt: Callable[[Any], str],
    double_value: Callable[[float], Any],
    long_value: Callable[[int], Any],
    group_config: dict,
) -> str:
    """Serialize into a temporary tree and commit only after every file succeeds."""
    base_dir = os.path.abspath(base_dir)
    parent_dir = os.path.dirname(base_dir)
    os.makedirs(parent_dir, exist_ok=True)
    stage_dir = tempfile.mkdtemp(prefix=".autoftbq-stage-", dir=parent_dir)
    chapters_dir = os.path.join(stage_dir, "chapters")
    os.makedirs(chapters_dir, exist_ok=True)
    previous_files = _previous_chapter_files(base_dir)
    generated_files: list[str] = []

    try:
        chapters_data = ai_data.get("chapters", [])
        title = ai_data.get("title", "Quest Book")
        chapter_groups = []
        chapter_qid_maps = []
        for chapter_index, chapter in enumerate(chapters_data):
            qid_map = {}
            for quest_index, quest in enumerate(chapter.get("quests", [])):
                source_id = quest.get("id") or f"q_{chapter_index}_{quest_index}"
                qid_map[source_id] = uid().upper()
            chapter_qid_maps.append(qid_map)

        for chapter_index, chapter in enumerate(chapters_data):
            chapter_uid = uid().upper()
            chapter_title = chapter.get("title", f"Chapter {chapter_index + 1}")
            chapter_icon = chapter.get("icon") or ""
            quest_entries = []
            qid_to_uid = chapter_qid_maps[chapter_index]

            for quest_index, quest in enumerate(chapter.get("quests", [])):
                source_id = quest.get("id") or f"q_{chapter_index}_{quest_index}"
                quest_uid = qid_to_uid.get(source_id)
                if not quest_uid:
                    continue
                quest_title = quest.get("title", f"Quest {quest_index + 1}")
                quest_subtitle = quest.get("subtitle", "")
                description = quest.get("description", [])
                if isinstance(description, str):
                    description = [description]

                tasks = []
                for task in quest.get("tasks", []):
                    task_uid = uid().upper()
                    task_type = str(task.get("type", "checkmark")).lower().split(":", 1)[-1]
                    target = task.get("target") or task.get("item", "")
                    count = item_count(task, target)
                    task_entry = {"id": task_uid, "type": task_type}
                    if task_type == "item":
                        item_id = normalize_item(target)
                        if not item_id or ":" not in item_id:
                            continue
                        task_entry["item"] = item_id
                        if count != 1:
                            task_entry["count"] = count
                    elif task_type == "advancement":
                        task_entry["advancement"] = target or "minecraft:story/root"
                        task_entry["criterion"] = ""
                    elif task_type == "kill":
                        task_entry["entity"] = target or "minecraft:zombie"
                        task_entry["value"] = long_value(count) if count > 10 else count
                    elif task_type == "dimension":
                        task_entry["dimension"] = target or "minecraft:overworld"
                    elif task_type == "checkmark":
                        task_entry["value"] = 1
                    tasks.append(task_entry)
                if not tasks:
                    tasks.append({"id": uid().upper(), "type": "checkmark", "value": 1})

                rewards = []
                for reward in quest.get("rewards", []):
                    reward_type = str(reward.get("type", "item")).lower().split(":", 1)[-1]
                    target = reward.get("target") or reward.get("item", "")
                    count = item_count(reward, target)
                    reward_entry = {"id": uid().upper(), "type": reward_type}
                    if reward_type == "item":
                        item_id = normalize_item(target)
                        if not item_id or ":" not in item_id:
                            continue
                        reward_entry["item"] = item_id
                        if count != 1:
                            reward_entry["count"] = count
                    elif reward_type == "command":
                        reward_entry["command"] = target or "/say Hello"
                    elif reward_type == "xp":
                        reward_entry["xp_amount"] = count
                    elif reward_type == "xp_levels":
                        reward_entry["xp_levels"] = count
                    rewards.append(reward_entry)

                dependencies = []
                for dependency in quest.get("dependencies", []):
                    if dependency in qid_to_uid:
                        dependencies.append(qid_to_uid[dependency])
                    else:
                        print(f"[WARN] Dependency '{dependency}' not found in quest '{quest_title}' - removing")

                shape = quest.get("shape", "square")
                if shape not in ("square", "diamond", "hexagon", "gear", "circle", "rsquare"):
                    shape = "square"
                ai_x, ai_y = quest.get("x"), quest.get("y")
                if isinstance(ai_x, (int, float)) and isinstance(ai_y, (int, float)):
                    x_value = double_value(round(float(ai_x), 1))
                    y_value = double_value(round(float(ai_y), 1))
                elif dependencies:
                    ref_x, ref_y = quest_index * 2.0, 0.0
                    for ref_quest in quest_entries:
                        if ref_quest["id"] in dependencies:
                            ref_x = float(str(ref_quest["x"])[:-1])
                            ref_y = float(str(ref_quest["y"])[:-1])
                            break
                    x_value = double_value(round(ref_x + 2.0, 1))
                    y_value = double_value(round(ref_y, 1))
                else:
                    x_value = double_value(round(quest_index * 2.0, 1))
                    y_value = double_value(0.0)

                quest_icon = quest.get("icon") or ""
                if not quest_icon or ":" not in quest_icon:
                    for task in quest.get("tasks", []):
                        task_type = str(task.get("type", "")).lower().split(":", 1)[-1]
                        if task_type != "item":
                            continue
                        candidate = normalize_item(task.get("target") or task.get("item", ""))
                        if candidate and ":" in candidate:
                            quest_icon = candidate
                            break
                if not quest_icon or ":" not in quest_icon:
                    quest_icon = "minecraft:book"

                quest_entry = {
                    "id": quest_uid,
                    "title": quest_title,
                    "icon": quest_icon,
                    "x": x_value,
                    "y": y_value,
                    "shape": shape,
                    "dependencies": dependencies,
                    "tasks": tasks,
                    "rewards": rewards,
                }
                if quest_subtitle:
                    quest_entry["subtitle"] = quest_subtitle
                if description:
                    quest_entry["description"] = description
                quest_entries.append(quest_entry)

            if not chapter_icon or ":" not in chapter_icon:
                chapter_icon = next(
                    (entry["icon"] for entry in quest_entries if ":" in entry.get("icon", "")),
                    "minecraft:wooden_pickaxe",
                )
            group_key = chapter.get("_group", chapter_uid)
            chapter_entry = {
                "default_hide_dependency_lines": False,
                "default_quest_shape": "",
                "filename": chapter_uid,
                "group": group_key,
                "icon": chapter_icon,
                "id": chapter_uid,
                "order_index": chapter_index,
                "quest_links": [],
                "quests": quest_entries,
                "title": chapter_title,
            }
            chapter_filename = f"{chapter_uid}.snbt"
            _write_text(os.path.join(chapters_dir, chapter_filename), to_snbt(chapter_entry))
            generated_files.append(chapter_filename)
            if group_key not in [group.get("id") for group in chapter_groups]:
                config = group_config.get(group_key, {})
                chapter_groups.append({"id": group_key, "title": config.get("title", group_key)})

        marker = {
            "default_hide_dependency_lines": False,
            "default_quest_shape": "",
            "filename": MARKER_CHAPTER_ID,
            "group": MARKER_CHAPTER_ID,
            "icon": "minecraft:writable_book",
            "id": MARKER_CHAPTER_ID,
            "order_index": len(chapter_groups),
            "quest_links": [],
            "quests": [{
                "id": "ZZZZZZZZZZZZZZZ0",
                "title": "本软件完全免费，此章节是用于检测生成结果，可随意删除",
                "subtitle": "",
                "icon": "minecraft:writable_book",
                "x": double_value(0.0),
                "y": double_value(0.0),
                "shape": "square",
                "tasks": [{"id": "ZZZZZZZZZZZZZZZ1", "type": "checkmark"}],
                "dependencies": [],
                "rewards": [],
            }],
            "title": "本软件完全免费，此章节是用于检测生成结果，可随意删除",
        }
        marker_filename = f"{MARKER_CHAPTER_ID}.snbt"
        _write_text(os.path.join(chapters_dir, marker_filename), to_snbt(marker))
        generated_files.append(marker_filename)
        chapter_groups.append({"id": MARKER_CHAPTER_ID, "title": "【生成完毕，右下角打开编辑模式删除】"})

        _write_text(
            os.path.join(stage_dir, "chapter_groups.snbt"),
            to_snbt({"chapter_groups": chapter_groups}),
        )
        data = {
            "default_autoclaim_rewards": "disabled",
            "default_consume_items": False,
            "default_quest_disable_jei": False,
            "default_quest_shape": "circle",
            "default_reward_team": False,
            "detection_delay": 20,
            "disable_gui": False,
            "drop_book_on_death": False,
            "drop_loot_crates": False,
            "emergency_items_cooldown": 300,
            "grid_scale": double_value(0.5),
            "icon": "minecraft:book",
            "lock_message": "",
            "loot_crate_no_drop": {"boss": 0, "monster": 600, "passive": 4000},
            "pause_game": False,
            "progression_mode": "linear",
            "show_lock_icons": True,
            "title": title,
            "version": 13,
        }
        _write_text(os.path.join(stage_dir, "data.snbt"), to_snbt(data))
        _write_text(
            os.path.join(stage_dir, ".autoftbq_manifest.json"),
            json.dumps({"chapter_files": generated_files}, ensure_ascii=False, indent=2),
        )

        relative_files = [os.path.join("chapters", name) for name in generated_files]
        relative_files.extend(["chapter_groups.snbt", "data.snbt", ".autoftbq_manifest.json"])
        _commit_stage(base_dir, stage_dir, relative_files, previous_files)
        return base_dir
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)
