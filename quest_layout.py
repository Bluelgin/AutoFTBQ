"""Human-style quest layout engine.

AI output tends to place every quest on one or two straight rows with a single
square shape, which reads as robotic. Real human-made quest books arrange the
main line horizontally, hang branches above/below it in staggered rows, and
group guidance/info checkmark cards into their own row near the top. This
module re-lays-out a chapter's quests following those conventions while
guaranteeing no two quests overlap.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any
import math


MAIN_Y = 0.0
BRANCH_Y_STEP = 2.0
INFO_Y = -8.0
FREE_Y = 2.0
X_STEP = 2.0

SHAPE_MAIN = "square"
SHAPE_BRANCH = "diamond"
SHAPE_INFO = "gear"
SHAPE_FREE = "circle"

_ALLOWED_SHAPES = {"square", "diamond", "hexagon", "gear", "circle", "rsquare"}


def is_info_quest(quest: dict) -> bool:
    """Identify checkmark cards that are genuinely guidance, not milestones."""
    tasks = quest.get("tasks", [])
    if not isinstance(tasks, list) or not tasks:
        return True
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_type = str(task.get("type", "")).lower().split(":", 1)[-1]
        if task_type != "checkmark":
            return False
    title = str(quest.get("title", "")).lower()
    shape = str(quest.get("shape", "")).lower()
    info_keywords = (
        "说明", "提示", "指南", "须知", "介绍", "关于", "欢迎",
        "guide", "info", "note", "tips", "read me", "welcome",
    )
    return shape == "gear" or any(keyword in title for keyword in info_keywords)


def _quest_id(quest: dict) -> str:
    return str(quest.get("id", "") or "")


def _dependencies(quest: dict) -> list[str]:
    deps = quest.get("dependencies", [])
    if isinstance(deps, str):
        deps = [deps]
    if not isinstance(deps, list):
        return []
    return [str(dep) for dep in deps if isinstance(dep, str) and dep]


def _longest_path(dag: dict[str, list[str]], start: str) -> list[str]:
    """Return the longest directed path starting at ``start``."""
    visited: dict[str, list[str]] = {}

    def visit(node: str) -> list[str]:
        if node in visited:
            return visited[node]
        best: list[str] = []
        for child in dag.get(node, []):
            candidate = visit(child)
            if len(candidate) > len(best):
                best = candidate
        visited[node] = [node] + best
        return visited[node]

    return visit(start)


def layout_style_for_chapter(chapter_id: str, quest_count: int = 0) -> str:
    """Choose a stable visual grammar from the generated theme id."""
    chapter_id = str(chapter_id or "").lower()
    if chapter_id.startswith(("theme_magic", "theme_pet")):
        return "snowflake"
    if chapter_id.startswith("theme_boss"):
        return "tree"
    return "lanes"


def _group_centers(style: str, count: int) -> list[tuple[float, float]]:
    if count <= 0:
        return []
    if style == "lanes":
        columns = 4
        centers = []
        for index in range(count):
            row, column = divmod(index, columns)
            if row % 2:
                column = columns - 1 - column
            x = column * 7.5
            y = row * 8.0
            centers.append((x, y))
        return centers
    if style == "tree":
        children = {
            index: [child for child in (index * 2 + 1, index * 2 + 2) if child < count]
            for index in range(count)
        }
        y_by_index: dict[int, float] = {}
        next_leaf_y = 0.0

        def place(index: int) -> float:
            nonlocal next_leaf_y
            child_indexes = children[index]
            if not child_indexes:
                y_by_index[index] = next_leaf_y
                next_leaf_y += 7.0
            else:
                child_ys = [place(child) for child in child_indexes]
                y_by_index[index] = sum(child_ys) / len(child_ys)
            return y_by_index[index]

        root_y = place(0)
        return [
            (int(math.log2(index + 1)) * 7.5, y_by_index[index] - root_y)
            for index in range(count)
        ]
    return [(float(index) * 7.5, 0.0) for index in range(count)]


_LOCAL_OFFSETS = (
    (0.0, 0.0),
    (2.5, 0.0),
    (0.0, -2.5),
    (5.0, 0.0),
    (2.5, 2.5),
    (5.0, -2.5),
)


def _oriented_offset(
    style: str,
    centers: list[tuple[float, float]],
    center_index: int,
    offset: tuple[float, float],
) -> tuple[float, float]:
    """Point each cluster along its route instead of always facing right."""
    if style == "lanes":
        row = center_index // 4
        direction = 1.0 if row % 2 == 0 else -1.0
        return offset[0] * direction, offset[1]
    return offset


def _safe_position(
    x: float,
    y: float,
    occupied: list[tuple[float, float]],
    quest_id: str,
) -> tuple[float, float]:
    """Resolve rare collisions on a strict half-block grid."""
    base = (round(x * 2) / 2, round(y * 2) / 2)
    offsets = [(0.0, 0.0)]
    for ring in range(1, 9):
        distance = ring * 2.5
        offsets.extend((
            (0.0, -distance),
            (0.0, distance),
            (-distance, 0.0),
            (distance, 0.0),
        ))
    for dx, dy in offsets:
        candidate = (base[0] + dx, base[1] + dy)
        if all(math.dist(candidate, other) >= 2.0 for other in occupied):
            occupied.append(candidate)
            return candidate
    occupied.append(base)
    return base


def _place_info_panel(info_quests: list[dict], occupied: list[tuple[float, float]]) -> None:
    if not info_quests:
        return
    min_x = min((x for x, _ in occupied), default=0.0)
    min_y = min((y for _, y in occupied), default=0.0)
    columns = min(8, max(1, len(info_quests)))
    for index, quest in enumerate(sorted(info_quests, key=lambda q: q.get("_layout_order", 0))):
        row, column = divmod(index, columns)
        x, y = _safe_position(
            min_x + column * 2.5,
            min_y - 5.0 - row * 2.5,
            occupied,
            _quest_id(quest),
        )
        quest["x"], quest["y"], quest["shape"] = float(x), float(y), "gear"
        quest["dependencies"] = []


def _safe_radial_position(
    x: float,
    y: float,
    angle: float,
    occupied: list[tuple[float, float]],
) -> tuple[float, float]:
    """Resolve snowflake collisions outward without bending an arm sideways."""
    for attempt in range(10):
        distance = attempt * 2.5
        candidate = (
            round(x + math.cos(angle) * distance, 1),
            round(y + math.sin(angle) * distance, 1),
        )
        if all(math.dist(candidate, other) >= 2.0 for other in occupied):
            occupied.append(candidate)
            return candidate
    candidate = (round(x, 1), round(y, 1))
    occupied.append(candidate)
    return candidate


def _relayout_snowflake(chapter: dict, quests: list[dict]) -> dict:
    hub = next((quest for quest in quests if quest.get("_layout_role") == "hub"), None)
    info_quests = [quest for quest in quests if quest.get("_layout_role") == "info"]
    arm_quests = [
        quest for quest in quests
        if isinstance(quest.get("_layout_arm"), int) and quest.get("_layout_arm") >= 0
        and quest.get("_layout_role") != "info"
    ]
    occupied: list[tuple[float, float]] = []
    if hub is not None:
        hub["x"], hub["y"], hub["shape"] = 0.0, 0.0, "hexagon"
        occupied.append((0.0, 0.0))

    arm_indexes = sorted({int(quest["_layout_arm"]) for quest in arm_quests})
    arm_count = len(arm_indexes)
    angle_by_arm = {}
    for position, arm_index in enumerate(arm_indexes):
        slots = 6 if arm_count >= 5 else max(1, arm_count)
        angle_by_arm[arm_index] = -math.pi / 2 + 2 * math.pi * position / slots

    def snowflake_order(quest):
        role_priority = 1 if quest.get("_layout_role") == "branch" else 0
        return (
            role_priority,
            quest.get("_layout_step", 0),
            quest.get("_layout_arm", 0),
            quest.get("_layout_order", 0),
        )

    # Reserve every radial backbone before placing decorative side crystals.
    for quest in sorted(arm_quests, key=snowflake_order):
        arm_index = int(quest.get("_layout_arm", 0))
        angle = angle_by_arm.get(arm_index, -math.pi / 2)
        step = int(quest.get("_layout_step", 0))
        # Keep the first crystal ring clear of neighbouring arms. This lets
        # branches stay close to their parent instead of being pushed outward.
        radius = 7.0 + step * 3.0
        side = int(quest.get("_layout_side", 0))
        x = math.cos(angle) * radius
        y = math.sin(angle) * radius
        if side:
            x += math.cos(angle) * 1.0
            y += math.sin(angle) * 1.0
            x += math.cos(angle + math.pi / 2) * side * 1.9
            y += math.sin(angle + math.pi / 2) * side * 1.9
        x, y = _safe_radial_position(x, y, angle, occupied)
        quest["x"], quest["y"] = float(x), float(y)
        role = quest.get("_layout_role")
        quest["shape"] = {
            "main": "square",
            "branch": "diamond",
            "milestone": "hexagon",
        }.get(role, "square")

    _place_info_panel(info_quests, occupied)
    chapter["_layout_style"] = "snowflake"
    return chapter


def _relayout_structured_chapter(chapter: dict, quests: list[dict]) -> dict:
    chapter_id = str(chapter.get("id", ""))
    style = layout_style_for_chapter(chapter_id, len(quests))
    if style == "snowflake":
        return _relayout_snowflake(chapter, quests)
    grouped: dict[int, list[dict]] = defaultdict(list)
    info_quests = []
    milestones = []
    for quest in quests:
        role = str(quest.get("_layout_role", ""))
        if role == "info":
            info_quests.append(quest)
        elif role == "milestone":
            milestones.append(quest)
        elif isinstance(quest.get("_layout_group"), int):
            grouped[int(quest["_layout_group"])].append(quest)

    group_indexes = sorted(grouped)
    centers = _group_centers(style, len(group_indexes))
    occupied: list[tuple[float, float]] = []
    by_id = {_quest_id(quest): quest for quest in quests if _quest_id(quest)}

    for center_index, (center, group_index) in enumerate(zip(centers, group_indexes)):
        group = sorted(grouped[group_index], key=lambda quest: quest.get("_layout_order", 0))
        for local_index, quest in enumerate(group):
            offset = _oriented_offset(
                style,
                centers,
                center_index,
                _LOCAL_OFFSETS[min(local_index, len(_LOCAL_OFFSETS) - 1)],
            )
            x, y = _safe_position(
                center[0] + offset[0],
                center[1] + offset[1],
                occupied,
                _quest_id(quest),
            )
            quest["x"], quest["y"] = float(x), float(y)
            role = quest.get("_layout_role")
            quest["shape"] = {
                "main": "square",
                "branch": "diamond" if local_index % 2 == 0 else "circle",
                "boss": "hexagon",
            }.get(role, "square")

    for quest in milestones:
        dependencies = _dependencies(quest)
        parent = by_id.get(dependencies[0]) if dependencies else None
        if parent is not None:
            base_x = float(parent.get("x", 0.0)) + 2.5
            base_y = float(parent.get("y", 0.0))
        else:
            base_x = max((x for x, _ in occupied), default=0.0) + 2.5
            base_y = 0.0
        x, y = _safe_position(base_x, base_y, occupied, _quest_id(quest))
        quest["x"], quest["y"], quest["shape"] = float(x), float(y), "hexagon"

    _place_info_panel(info_quests, occupied)

    chapter["_layout_style"] = style
    return chapter


def relayout_chapter(chapter: dict, info_y: float = INFO_Y) -> dict:
    """Structure-driven layout: mainline, hanging branches, forks, merges,
    hub-and-spoke, then info cards. Rewrites x/y/shape in place."""
    quests = chapter.get("quests", [])
    if not isinstance(quests, list) or not quests:
        return chapter
    if any(isinstance(quest, dict) and "_layout_group" in quest for quest in quests):
        return _relayout_structured_chapter(chapter, quests)

    by_id = {_quest_id(quest): quest for quest in quests if isinstance(quest, dict) and _quest_id(quest)}
    info_ids = {
        _quest_id(quest)
        for quest in quests
        if isinstance(quest, dict) and is_info_quest(quest)
    }
    active_ids = [quest_id for quest_id in by_id if quest_id not in info_ids]

    dag: dict[str, list[str]] = {quest_id: [] for quest_id in active_ids}
    indegree: dict[str, int] = {quest_id: 0 for quest_id in active_ids}
    outdegree: dict[str, int] = {quest_id: 0 for quest_id in active_ids}
    for quest_id in active_ids:
        for dep in _dependencies(by_id[quest_id]):
            if dep in by_id and dep not in info_ids and dep in dag:
                dag[dep].append(quest_id)
                indegree[quest_id] += 1
                outdegree[dep] += 1

    roots = [quest_id for quest_id in active_ids if indegree[quest_id] == 0]
    mainline: list[str] = []
    for root in roots:
        path = _longest_path(dag, root)
        if len(path) > len(mainline):
            mainline = path
    mainline_set = set(mainline)

    occupied: set[tuple[float, float]] = set()
    placed_ids: set[str] = set()
    branch_slots: dict[str, int] = defaultdict(int)
    free_index = 0

    def occupy(x: float, y: float) -> tuple[float, float]:
        candidate = (x, y)
        while candidate in occupied:
            candidate = (candidate[0] + X_STEP, candidate[1])
        occupied.add(candidate)
        return candidate

    def place(quest_id: str, x: float, y: float, shape: str) -> None:
        quest = by_id[quest_id]
        quest["x"] = float(x)
        quest["y"] = float(y)
        if shape in _ALLOWED_SHAPES:
            quest["shape"] = shape
        placed_ids.add(quest_id)

    # 1. Main line: horizontal row.
    for index, quest_id in enumerate(mainline):
        x, y = occupy(float(index) * X_STEP, MAIN_Y)
        place(quest_id, x, y, SHAPE_MAIN)

    # 2. Remaining active quests, shallow dependencies first.
    def depth_of(quest_id: str, visiting=None) -> int:
        visiting = set(visiting or ())
        if quest_id in visiting:
            return 0
        visiting.add(quest_id)
        deps = _dependencies(by_id[quest_id])
        placed_deps = [dep for dep in deps if dep in by_id and dep not in info_ids]
        return 1 + max(
            (depth_of(dep, visiting) for dep in placed_deps),
            default=0,
        )

    pending = [quest_id for quest_id in active_ids if quest_id not in placed_ids]
    pending.sort(key=depth_of)
    queue = deque(pending)
    while queue:
        quest_id = queue.popleft()
        if quest_id in placed_ids:
            continue
        quest = by_id[quest_id]
        deps = [dep for dep in _dependencies(quest) if dep in by_id and dep not in info_ids]
        placed_deps = [dep for dep in deps if dep in placed_ids]

        if len(placed_deps) >= 2:
            # Pattern 3: merge -- parents fan in from both sides.
            cx = sum(float(by_id[dep]["x"]) for dep in placed_deps) / len(placed_deps) + 2.0
            cy = sum(float(by_id[dep]["y"]) for dep in placed_deps) / len(placed_deps)
            x, y = occupy(cx, cy)
            place(quest_id, x, y, SHAPE_BRANCH)
            continue

        anchor = placed_deps[0] if placed_deps else None
        if anchor is None:
            x, y = occupy(float(free_index) * X_STEP, FREE_Y)
            free_index += 1
            place(quest_id, x, y, SHAPE_FREE)
            continue

        slot = branch_slots.get(anchor, 0)
        branch_slots[anchor] = slot + 1
        sign = -1.0 if slot % 2 == 0 else 1.0
        depth = 1 + (slot // 2)
        anchor_x = float(by_id[anchor]["x"])
        anchor_y = float(by_id[anchor]["y"])
        has_descendants = bool(dag.get(quest_id))
        if has_descendants:
            # Pattern 2: fork chain extends to the right with staggered y.
            x, y = occupy(anchor_x + X_STEP, anchor_y + sign * depth * 0.8)
            place(quest_id, x, y, SHAPE_BRANCH)
        else:
            # Pattern 1 / 4: hanging leaf, staggered above/below the anchor.
            x, y = occupy(anchor_x, anchor_y + sign * depth * BRANCH_Y_STEP)
            place(quest_id, x, y, SHAPE_BRANCH)

    # 3. Info cards: their own row near the top.
    info_index = 0
    for quest_id in info_ids:
        quest = by_id.get(quest_id)
        if quest is None:
            continue
        x, y = occupy(float(info_index) * X_STEP, info_y)
        place(quest_id, x, y, SHAPE_INFO)
        info_index += 1

    return chapter


def relayout_quest_book(ai_data: dict, info_y: float = INFO_Y) -> dict:
    """Re-layout every chapter of a normalized quest book."""
    for chapter in ai_data.get("chapters", []):
        if isinstance(chapter, dict):
            relayout_chapter(chapter, info_y=info_y)
    return ai_data
