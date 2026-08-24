"""Loss-minimizing editor store for real FTB Quests SNBT directories."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import os
import shutil
import tempfile
import uuid

from snbt_parser import parse_snbt, to_snbt

from .project import Chapter, ProjectStore, Quest, QuestBookProject, Task


def new_ftb_id() -> str:
    return f"{uuid.uuid4().int & 0x7FFFFFFFFFFFFFFF:016X}"


def locate_quest_root(pack_root: str) -> str:
    root = os.path.abspath(pack_root)
    candidates = [
        os.path.join(root, "config", "ftbquests", "quests"),
        os.path.join(root, "ftbquests", "quests"),
        root,
    ]
    for candidate in candidates:
        if os.path.isdir(os.path.join(candidate, "chapters")):
            return candidate
    return ""


def _icon_id(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return str(value.get("id") or value.get("item") or "")
    return ""


def _task_target(raw: dict) -> str:
    for key in ("item", "entity", "dimension", "advancement", "biome", "structure", "fluid"):
        value = raw.get(key)
        if isinstance(value, dict):
            value = value.get("id") or value.get("fluid") or value.get("item")
        if value not in (None, ""):
            return str(value)
    return ""


def _target_key(task_type: str) -> str:
    return {
        "kill": "entity",
        "dimension": "dimension",
        "advancement": "advancement",
        "biome": "biome",
        "structure": "structure",
        "fluid": "fluid",
    }.get(task_type, "item")


class FTBQuestStore(ProjectStore):
    """ProjectStore facade backed by untouched real chapter compounds."""

    is_real = True

    def __init__(self, quest_root: str, project: QuestBookProject):
        super().__init__(project)
        self.quest_root = os.path.abspath(quest_root)
        self.raw_chapters: dict[str, dict] = {}
        self.raw_quests: dict[str, dict] = {}
        self.chapter_files: dict[str, str] = {}
        self.dirty_chapters: set[str] = set()
        self._undo = []
        self._redo = []

    @classmethod
    def load_directory(cls, quest_root: str, mod_folder: str = "") -> "FTBQuestStore":
        chapters_dir = os.path.join(os.path.abspath(quest_root), "chapters")
        if not os.path.isdir(chapters_dir):
            raise ValueError("所选位置没有 config/ftbquests/quests/chapters")
        project = QuestBookProject(
            title=os.path.basename(os.path.abspath(mod_folder or quest_root)) or "FTB Quests",
            mod_folder=os.path.abspath(mod_folder or quest_root),
        )
        store = cls(quest_root, project)
        errors = []
        for filename in sorted(os.listdir(chapters_dir)):
            if not filename.lower().endswith(".snbt"):
                continue
            path = os.path.join(chapters_dir, filename)
            try:
                with open(path, "r", encoding="utf-8-sig") as handle:
                    raw = parse_snbt(handle.read())
                if not isinstance(raw, dict):
                    raise ValueError("章节根节点不是 compound")
                chapter = store._chapter_from_raw(raw, filename)
                project.chapters.append(chapter)
                store.raw_chapters[chapter.id] = raw
                store.chapter_files[chapter.id] = path
                for raw_quest in raw.get("quests", []):
                    if isinstance(raw_quest, dict) and raw_quest.get("id"):
                        store.raw_quests[str(raw_quest["id"])] = raw_quest
            except Exception as exc:
                errors.append(f"{filename}: {exc}")
        if not project.chapters and errors:
            raise ValueError("无法读取章节：" + "; ".join(errors[:3]))
        store.load_errors = errors
        return store

    @staticmethod
    def _chapter_from_raw(raw: dict, filename: str) -> Chapter:
        chapter_id = str(raw.get("id") or raw.get("filename") or os.path.splitext(filename)[0])
        quests = []
        for raw_quest in raw.get("quests", []) if isinstance(raw.get("quests"), list) else []:
            if not isinstance(raw_quest, dict):
                continue
            tasks = []
            for raw_task in raw_quest.get("tasks", []) if isinstance(raw_quest.get("tasks"), list) else []:
                if isinstance(raw_task, dict):
                    tasks.append(Task(
                        type=str(raw_task.get("type") or "checkmark"),
                        target=_task_target(raw_task),
                        count=max(1, int(raw_task.get("count", 1) or 1)),
                    ))
            quests.append(Quest(
                id=str(raw_quest.get("id") or new_ftb_id()),
                title=str(raw_quest.get("title") or "未命名任务"),
                subtitle=str(raw_quest.get("subtitle") or ""),
                icon=_icon_id(raw_quest.get("icon")),
                description=[str(line) for line in raw_quest.get("description", [])]
                if isinstance(raw_quest.get("description"), list) else [],
                tasks=tasks or [Task()],
                rewards=deepcopy(raw_quest.get("rewards", []))
                if isinstance(raw_quest.get("rewards"), list) else [],
                dependencies=[str(value) for value in raw_quest.get("dependencies", [])],
                x=float(raw_quest.get("x", 0) or 0),
                y=float(raw_quest.get("y", 0) or 0),
                shape=str(raw_quest.get("shape") or "circle"),
            ))
        return Chapter(
            id=chapter_id,
            title=str(raw.get("title") or raw.get("filename") or os.path.splitext(filename)[0]),
            icon=_icon_id(raw.get("icon")) or "minecraft:book",
            quests=quests,
        )

    def _snapshot(self):
        return (
            deepcopy(self.project),
            deepcopy(self.raw_chapters),
            deepcopy(self.raw_quests),
            dict(self.chapter_files),
            set(self.dirty_chapters),
        )

    def _restore(self, snapshot) -> None:
        self.project, self.raw_chapters, self.raw_quests, self.chapter_files, self.dirty_chapters = deepcopy(snapshot)

    def _checkpoint(self) -> None:
        self._undo.append(self._snapshot())
        self._undo = self._undo[-100:]
        self._redo.clear()

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(self._snapshot())
        self._restore(self._undo.pop())
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(self._snapshot())
        self._restore(self._redo.pop())
        return True

    def _mark_quest(self, quest_id: str) -> None:
        found = self.quest(quest_id)
        if found:
            self.dirty_chapters.add(found[0].id)

    def create_chapter(self, title: str, icon: str = "minecraft:book") -> Chapter:
        self._checkpoint()
        chapter = Chapter(id=new_ftb_id(), title=title.strip() or "新章节", icon=icon or "minecraft:book")
        raw = {
            "default_hide_dependency_lines": False,
            "default_quest_shape": "",
            "filename": chapter.id,
            "icon": chapter.icon,
            "id": chapter.id,
            "order_index": len(self.project.chapters),
            "quest_links": [],
            "quests": [],
            "title": chapter.title,
        }
        self.project.chapters.append(chapter)
        self.raw_chapters[chapter.id] = raw
        self.chapter_files[chapter.id] = os.path.join(self.quest_root, "chapters", f"{chapter.id}.snbt")
        self.dirty_chapters.add(chapter.id)
        return chapter

    def add_quest(self, chapter_id: str, title: str, description: str = "", task_type: str = "checkmark", target: str = "", count: int = 1) -> Quest:
        chapter = self.chapter(chapter_id)
        if chapter is None:
            raise ValueError(f"找不到章节：{chapter_id}")
        self._checkpoint()
        quest = Quest(
            id=new_ftb_id(), title=title.strip() or "新任务",
            description=[description.strip()] if description.strip() else [],
            tasks=[Task(task_type or "checkmark", target.strip(), max(1, int(count or 1)))],
            x=float(len(chapter.quests) * 2.5), y=0.0,
        )
        if chapter.quests:
            quest.dependencies = [chapter.quests[-1].id]
        chapter.quests.append(quest)
        self.raw_quests[quest.id] = {}
        self.dirty_chapters.add(chapter_id)
        return quest

    def update_quest(self, quest_id: str, **changes) -> Quest:
        found = self.quest(quest_id)
        if found is None:
            raise ValueError(f"找不到任务：{quest_id}")
        self._checkpoint()
        quest = found[1]
        if "title" in changes:
            quest.title = str(changes["title"]).strip() or quest.title
        if "subtitle" in changes:
            quest.subtitle = str(changes["subtitle"]).strip()
        if "icon" in changes:
            quest.icon = str(changes["icon"]).strip()
        if "shape" in changes:
            quest.shape = str(changes["shape"]).strip() or quest.shape
        if "description" in changes:
            value = str(changes["description"]).strip()
            quest.description = value.splitlines() if value else []
        task = quest.tasks[0] if quest.tasks else Task()
        if "task_type" in changes:
            task.type = str(changes["task_type"]).strip() or task.type
        if "target" in changes:
            task.target = str(changes["target"]).strip()
        if "count" in changes:
            task.count = max(1, int(changes["count"] or 1))
        if not quest.tasks:
            quest.tasks.append(task)
        self.dirty_chapters.add(found[0].id)
        return quest

    def move_quest(self, quest_id: str, x: float, y: float) -> Quest:
        quest = super().move_quest(quest_id, x, y)
        self._mark_quest(quest_id)
        return quest

    def connect(self, quest_id: str, dependency_id: str) -> Quest:
        quest = super().connect(quest_id, dependency_id)
        self._mark_quest(quest_id)
        return quest

    def disconnect(self, quest_id: str, dependency_id: str) -> Quest:
        quest = super().disconnect(quest_id, dependency_id)
        self._mark_quest(quest_id)
        return quest

    def remove_quest(self, quest_id: str) -> bool:
        found = self.quest(quest_id)
        if found is None:
            return False
        chapter_id = found[0].id
        removed = super().remove_quest(quest_id)
        self.raw_quests.pop(quest_id, None)
        self.dirty_chapters.add(chapter_id)
        return removed

    def replace_quest_sections(self, quest_id: str, tasks, rewards) -> Quest:
        found = self.quest(quest_id)
        if found is None:
            raise ValueError(f"找不到任务：{quest_id}")
        if not isinstance(tasks, list) or not all(isinstance(value, dict) for value in tasks):
            raise ValueError("任务 SNBT 必须是 compound 列表")
        if not isinstance(rewards, list) or not all(isinstance(value, dict) for value in rewards):
            raise ValueError("奖励 SNBT 必须是 compound 列表")
        self._checkpoint()
        quest = found[1]
        quest.tasks = [Task(str(raw.get("type") or "checkmark"), _task_target(raw), max(1, int(raw.get("count", 1) or 1))) for raw in tasks] or [Task()]
        quest.rewards = deepcopy(rewards)
        raw = self.raw_quests.setdefault(quest_id, {})
        raw["tasks"] = deepcopy(tasks)
        raw["rewards"] = deepcopy(rewards)
        self.dirty_chapters.add(found[0].id)
        return quest

    def raw_sections(self, quest_id: str) -> tuple[list, list]:
        raw = self.raw_quests.get(quest_id, {})
        return deepcopy(raw.get("tasks", [])), deepcopy(raw.get("rewards", []))

    def _sync_task(self, task: Task, raw: dict) -> dict:
        raw = deepcopy(raw) if isinstance(raw, dict) else {}
        raw.setdefault("id", new_ftb_id())
        old_type = str(raw.get("type") or "")
        raw["type"] = task.type
        key = _target_key(task.type)
        if old_type and old_type != task.type:
            for candidate in ("item", "entity", "dimension", "advancement", "biome", "structure", "fluid"):
                if candidate != key:
                    raw.pop(candidate, None)
        if task.target:
            existing = raw.get(key)
            if isinstance(existing, dict):
                existing["id"] = task.target
            else:
                raw[key] = task.target
        if task.count > 1 or "count" in raw:
            raw["count"] = task.count
        return raw

    def _sync_quest(self, quest: Quest) -> dict:
        raw = deepcopy(self.raw_quests.get(quest.id, {}))
        raw["id"] = quest.id
        raw["title"] = quest.title
        if quest.subtitle or "subtitle" in raw:
            raw["subtitle"] = quest.subtitle
        if quest.icon or "icon" in raw:
            if isinstance(raw.get("icon"), dict):
                raw["icon"]["id"] = quest.icon
            else:
                raw["icon"] = quest.icon
        raw["x"] = float(quest.x)
        raw["y"] = float(quest.y)
        raw["shape"] = quest.shape
        raw["dependencies"] = list(quest.dependencies)
        old_tasks = raw.get("tasks", []) if isinstance(raw.get("tasks"), list) else []
        raw["tasks"] = [
            self._sync_task(task, old_tasks[index] if index < len(old_tasks) else {})
            for index, task in enumerate(quest.tasks)
        ]
        raw["rewards"] = deepcopy(quest.rewards)
        raw["description"] = list(quest.description)
        self.raw_quests[quest.id] = raw
        return raw

    def _sync_chapter(self, chapter: Chapter) -> dict:
        raw = deepcopy(self.raw_chapters.get(chapter.id, {}))
        raw["id"] = chapter.id
        raw.setdefault("filename", chapter.id)
        raw["title"] = chapter.title
        if isinstance(raw.get("icon"), dict):
            raw["icon"]["id"] = chapter.icon
        else:
            raw["icon"] = chapter.icon
        raw["quests"] = [self._sync_quest(quest) for quest in chapter.quests]
        self.raw_chapters[chapter.id] = raw
        return raw

    def save_all(self) -> dict:
        if not self.dirty_chapters:
            return {"saved": 0, "backup": ""}
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_root = os.path.join(self.quest_root, ".autoftbq-backups", stamp)
        saved = []
        os.makedirs(os.path.join(self.quest_root, "chapters"), exist_ok=True)
        try:
            for chapter_id in list(self.dirty_chapters):
                chapter = self.chapter(chapter_id)
                if chapter is None:
                    continue
                target = self.chapter_files[chapter_id]
                if os.path.isfile(target):
                    backup = os.path.join(backup_root, "chapters", os.path.basename(target))
                    os.makedirs(os.path.dirname(backup), exist_ok=True)
                    shutil.copy2(target, backup)
                content = to_snbt(self._sync_chapter(chapter)) + "\n"
                fd, temporary = tempfile.mkstemp(prefix=".autoftbq-", suffix=".tmp", dir=os.path.dirname(target))
                try:
                    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                        handle.write(content)
                    os.replace(temporary, target)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
                saved.append(target)
        except Exception:
            for target in saved:
                backup = os.path.join(backup_root, "chapters", os.path.basename(target))
                if os.path.isfile(backup):
                    shutil.copy2(backup, target)
            raise
        self.dirty_chapters.clear()
        return {"saved": len(saved), "backup": backup_root if os.path.isdir(backup_root) else ""}

    def save(self, _path: str = "") -> None:
        self.save_all()
