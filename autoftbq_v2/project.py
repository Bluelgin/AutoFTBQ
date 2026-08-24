"""Editable project model shared by the v2 UI and agent tools."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
import json
import uuid


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


@dataclass
class Task:
    type: str = "checkmark"
    target: str = ""
    count: int = 1


@dataclass
class Quest:
    id: str = field(default_factory=lambda: new_id("quest"))
    title: str = "新任务"
    subtitle: str = ""
    icon: str = ""
    description: list[str] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=lambda: [Task()])
    rewards: list[dict] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    x: float = 0.0
    y: float = 0.0
    shape: str = "circle"


@dataclass
class Chapter:
    id: str = field(default_factory=lambda: new_id("chapter"))
    title: str = "新章节"
    icon: str = "minecraft:book"
    quests: list[Quest] = field(default_factory=list)


@dataclass
class QuestBookProject:
    title: str = "未命名任务书"
    chapters: list[Chapter] = field(default_factory=list)
    mod_folder: str = ""
    format_version: int = 1

    def to_dict(self) -> dict:
        return asdict(self)

    def to_ai_data(self) -> dict:
        return {
            "title": self.title,
            "chapters": [
                {
                    "id": chapter.id,
                    "title": chapter.title,
                    "icon": chapter.icon,
                    "quests": [asdict(quest) for quest in chapter.quests],
                }
                for chapter in self.chapters
            ],
        }

    @classmethod
    def from_dict(cls, value: dict) -> "QuestBookProject":
        chapters = []
        for raw_chapter in value.get("chapters", []) if isinstance(value, dict) else []:
            if not isinstance(raw_chapter, dict):
                continue
            quests = []
            for raw_quest in raw_chapter.get("quests", []):
                if not isinstance(raw_quest, dict):
                    continue
                tasks = [
                    Task(
                        type=str(task.get("type", "checkmark")),
                        target=str(task.get("target", "") or task.get("item", "")),
                        count=max(1, int(task.get("count", 1) or 1)),
                    )
                    for task in raw_quest.get("tasks", [])
                    if isinstance(task, dict)
                ] or [Task()]
                quests.append(Quest(
                    id=str(raw_quest.get("id") or new_id("quest")),
                    title=str(raw_quest.get("title") or "新任务"),
                    subtitle=str(raw_quest.get("subtitle") or ""),
                    icon=str(raw_quest.get("icon") or ""),
                    description=[str(line) for line in raw_quest.get("description", [])]
                    if isinstance(raw_quest.get("description"), list)
                    else [str(raw_quest.get("description", ""))],
                    tasks=tasks,
                    rewards=list(raw_quest.get("rewards", []))
                    if isinstance(raw_quest.get("rewards"), list) else [],
                    dependencies=[str(item) for item in raw_quest.get("dependencies", [])],
                    x=float(raw_quest.get("x", 0) or 0),
                    y=float(raw_quest.get("y", 0) or 0),
                    shape=str(raw_quest.get("shape", "circle")),
                ))
            chapters.append(Chapter(
                id=str(raw_chapter.get("id") or new_id("chapter")),
                title=str(raw_chapter.get("title") or "新章节"),
                icon=str(raw_chapter.get("icon") or "minecraft:book"),
                quests=quests,
            ))
        return cls(
            title=str(value.get("title") or "未命名任务书"),
            chapters=chapters,
            mod_folder=str(value.get("mod_folder", "")),
            format_version=int(value.get("format_version", 1) or 1),
        )


class ProjectStore:
    """Transactional project commands with undo/redo and validation."""

    def __init__(self, project: QuestBookProject | None = None):
        self.project = project or QuestBookProject()
        self._undo: list[QuestBookProject] = []
        self._redo: list[QuestBookProject] = []

    def _checkpoint(self) -> None:
        self._undo.append(deepcopy(self.project))
        self._undo = self._undo[-100:]
        self._redo.clear()

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(deepcopy(self.project))
        self.project = self._undo.pop()
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(deepcopy(self.project))
        self.project = self._redo.pop()
        return True

    def chapter(self, chapter_id: str) -> Chapter | None:
        return next((chapter for chapter in self.project.chapters if chapter.id == chapter_id), None)

    def quest(self, quest_id: str) -> tuple[Chapter, Quest] | None:
        for chapter in self.project.chapters:
            for quest in chapter.quests:
                if quest.id == quest_id:
                    return chapter, quest
        return None

    def create_chapter(self, title: str, icon: str = "minecraft:book") -> Chapter:
        self._checkpoint()
        chapter = Chapter(title=title.strip() or "新章节", icon=icon.strip() or "minecraft:book")
        self.project.chapters.append(chapter)
        return chapter

    def update_chapter(self, chapter_id: str, **changes) -> Chapter:
        chapter = self.chapter(chapter_id)
        if chapter is None:
            raise ValueError(f"找不到章节：{chapter_id}")
        self._checkpoint()
        if "title" in changes:
            chapter.title = str(changes["title"]).strip() or chapter.title
        if "icon" in changes:
            chapter.icon = str(changes["icon"]).strip() or chapter.icon
        return chapter

    def add_quest(
        self,
        chapter_id: str,
        title: str,
        description: str = "",
        task_type: str = "checkmark",
        target: str = "",
        count: int = 1,
    ) -> Quest:
        chapter = self.chapter(chapter_id)
        if chapter is None:
            raise ValueError(f"找不到章节：{chapter_id}")
        self._checkpoint()
        index = len(chapter.quests)
        quest = Quest(
            title=title.strip() or "新任务",
            description=[description.strip()] if description.strip() else [],
            tasks=[Task(task_type.strip() or "checkmark", target.strip(), max(1, int(count)))],
            x=float(index * 3),
            y=0.0,
        )
        if chapter.quests:
            quest.dependencies = [chapter.quests[-1].id]
        chapter.quests.append(quest)
        return quest

    def update_quest(self, quest_id: str, **changes) -> Quest:
        found = self.quest(quest_id)
        if found is None:
            raise ValueError(f"找不到任务：{quest_id}")
        _, quest = found
        self._checkpoint()
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
            quest.description = [value] if value else []
        task = quest.tasks[0] if quest.tasks else Task()
        if "task_type" in changes:
            task.type = str(changes["task_type"]).strip() or "checkmark"
        if "target" in changes:
            task.target = str(changes["target"]).strip()
        if "count" in changes:
            task.count = max(1, int(changes["count"] or 1))
        quest.tasks = [task]
        return quest

    def move_quest(self, quest_id: str, x: float, y: float) -> Quest:
        found = self.quest(quest_id)
        if found is None:
            raise ValueError(f"找不到任务：{quest_id}")
        self._checkpoint()
        found[1].x = float(x)
        found[1].y = float(y)
        return found[1]

    def remove_quest(self, quest_id: str) -> bool:
        found = self.quest(quest_id)
        if found is None:
            return False
        chapter, _ = found
        self._checkpoint()
        chapter.quests = [quest for quest in chapter.quests if quest.id != quest_id]
        for current in chapter.quests:
            current.dependencies = [value for value in current.dependencies if value != quest_id]
        return True

    def connect(self, quest_id: str, dependency_id: str) -> Quest:
        found = self.quest(quest_id)
        dependency = self.quest(dependency_id)
        if found is None or dependency is None:
            raise ValueError("依赖任务不存在")
        if found[0].id != dependency[0].id:
            raise ValueError("MVP 暂不支持跨章节依赖")
        if dependency_id == quest_id:
            raise ValueError("任务不能依赖自身")
        if self._depends_on(dependency_id, quest_id):
            raise ValueError("这条连线会形成循环依赖")
        if dependency_id not in found[1].dependencies:
            self._checkpoint()
            found[1].dependencies.append(dependency_id)
        return found[1]

    def disconnect(self, quest_id: str, dependency_id: str) -> Quest:
        found = self.quest(quest_id)
        if found is None:
            raise ValueError("任务不存在")
        if dependency_id in found[1].dependencies:
            self._checkpoint()
            found[1].dependencies.remove(dependency_id)
        return found[1]

    def _depends_on(self, quest_id: str, dependency_id: str) -> bool:
        visited = set()
        pending = [quest_id]
        while pending:
            current_id = pending.pop()
            if current_id == dependency_id:
                return True
            if current_id in visited:
                continue
            visited.add(current_id)
            found = self.quest(current_id)
            if found:
                pending.extend(found[1].dependencies)
        return False

    def summary(self) -> dict:
        return {
            "title": self.project.title,
            "chapters": [
                {"id": chapter.id, "title": chapter.title, "quests": len(chapter.quests)}
                for chapter in self.project.chapters
            ],
            "quest_count": sum(len(chapter.quests) for chapter in self.project.chapters),
        }

    def validate(self, known_items: dict | None = None) -> list[dict]:
        known_items = known_items or {}
        issues = []
        if not self.project.chapters:
            issues.append({"severity": "warning", "location": "任务书", "message": "还没有章节"})
        for chapter in self.project.chapters:
            ids = {quest.id for quest in chapter.quests}
            titles = set()
            if not chapter.quests:
                issues.append({"severity": "warning", "location": chapter.title, "message": "章节中没有任务"})
            for quest in chapter.quests:
                location = f"{chapter.title} / {quest.title}"
                folded = quest.title.casefold()
                if folded in titles:
                    issues.append({"severity": "warning", "location": location, "message": "任务标题重复"})
                titles.add(folded)
                for dependency in quest.dependencies:
                    if dependency not in ids:
                        issues.append({"severity": "error", "location": location, "message": f"依赖不存在：{dependency}"})
                for task in quest.tasks:
                    if task.type == "item" and task.target and ":" not in task.target:
                        issues.append({"severity": "error", "location": location, "message": f"物品 ID 格式错误：{task.target}"})
                    if task.type == "item" and ":" in task.target:
                        namespace = task.target.split(":", 1)[0]
                        items = known_items.get(namespace)
                        if isinstance(items, dict) and items and task.target not in items:
                            issues.append({"severity": "warning", "location": location, "message": f"扫描结果中未找到：{task.target}"})
        return issues

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.project.to_dict(), handle, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> "ProjectStore":
        with open(path, "r", encoding="utf-8") as handle:
            return cls(QuestBookProject.from_dict(json.load(handle)))
