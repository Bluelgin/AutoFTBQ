import copy
import math
import unittest

from quest_layout import is_info_quest, layout_style_for_chapter, relayout_chapter
from quest_planner import normalize_chapter_quests


def _quest(quest_id, deps=None, tasks=None, shape="square", x=0.0, y=0.0):
    return {
        "id": quest_id,
        "title": f"Quest {quest_id}",
        "tasks": tasks if tasks is not None else [{"type": "item", "target": "minecraft:stone"}],
        "rewards": [],
        "dependencies": deps or [],
        "shape": shape,
        "x": x,
        "y": y,
    }


def _info_quest(quest_id):
    quest = _quest(quest_id, tasks=[{"type": "checkmark"}])
    quest["title"] = f"Info {quest_id}"
    return quest


class QuestLayoutTests(unittest.TestCase):
    def test_mainline_is_horizontal_row(self):
        chapter = {"title": "T", "quests": [
            _quest("a"),
            _quest("b", deps=["a"]),
            _quest("c", deps=["b"]),
        ]}
        relayout_chapter(chapter)
        by_id = {q["id"]: q for q in chapter["quests"]}
        self.assertAlmostEqual(by_id["a"]["y"], 0.0, delta=0.5)
        self.assertAlmostEqual(by_id["b"]["y"], 0.0, delta=0.5)
        self.assertAlmostEqual(by_id["c"]["y"], 0.0, delta=0.5)
        self.assertLess(by_id["a"]["x"], by_id["b"]["x"])
        self.assertLess(by_id["b"]["x"], by_id["c"]["x"])
        self.assertEqual(by_id["a"]["shape"], "square")

    def test_branches_stagger_above_and_below(self):
        chapter = {"title": "T", "quests": [
            _quest("a"),
            _quest("m", deps=["a"]),
            _quest("b1", deps=["a"]),
            _quest("b2", deps=["a"]),
        ]}
        relayout_chapter(chapter)
        branches = [q for q in chapter["quests"] if q["id"] in ("b1", "b2")]
        y_values = [round(q["y"], 1) for q in branches]
        self.assertGreaterEqual(len(set(y_values)), 2)
        self.assertTrue(all(q["shape"] == "diamond" for q in branches))

    def test_info_cards_get_own_row(self):
        chapter = {"title": "T", "quests": [
            _info_quest("info1"),
            _info_quest("info2"),
            _quest("main1"),
        ]}
        relayout_chapter(chapter)
        info = [q for q in chapter["quests"] if q["id"].startswith("info")]
        main = [q for q in chapter["quests"] if q["id"] == "main1"]
        self.assertTrue(all(q["shape"] == "gear" for q in info))
        info_ys = [q["y"] for q in info]
        self.assertLess(max(info_ys) - min(info_ys), 1.0)
        self.assertGreater(abs(info[0]["y"] - main[0]["y"]), 1.0)

    def test_no_overlap_and_existing_coordinates_are_replaced(self):
        quests = [_quest(str(i), deps=[str(i - 1)] if i > 0 else None, x=99.0, y=99.0) for i in range(8)]
        chapter = {"title": "T", "quests": quests}
        relayout_chapter(chapter)
        positions = {}
        for quest in chapter["quests"]:
            key = (quest["x"], quest["y"])
            self.assertNotIn(key, positions, f"overlap at {key}")
            positions[key] = quest["id"]
            self.assertNotEqual(quest["x"], 99.0)
            self.assertNotEqual(quest["y"], 99.0)

    def test_is_info_quest_only_for_checkmark(self):
        self.assertTrue(is_info_quest(_info_quest("x")))
        self.assertFalse(is_info_quest(_quest("x")))
        self.assertFalse(is_info_quest(_quest("milestone", tasks=[{"type": "checkmark"}])))
        self.assertTrue(is_info_quest({"id": "empty", "tasks": []}))

    def test_theme_ids_select_distinct_layout_grammars(self):
        expected = {
            "theme_start": "lanes",
            "theme_food": "lanes",
            "theme_mining": "lanes",
            "theme_tech_2": "lanes",
            "theme_magic": "snowflake",
            "theme_pet": "snowflake",
            "theme_world": "lanes",
            "theme_boss": "tree",
            "kubejs_custom": "lanes",
        }
        for chapter_id, style in expected.items():
            with self.subTest(chapter_id=chapter_id):
                self.assertEqual(layout_style_for_chapter(chapter_id, 30), style)

    def test_structured_layout_is_deterministic_spaced_and_compact(self):
        source = [
            {
                "title": f"Quest {index}",
                "tasks": [{"type": "item", "target": f"example:item_{index}"}],
            }
            for index in range(40)
        ]
        normalized = normalize_chapter_quests("theme_magic", source)
        first = {"id": "theme_magic", "quests": copy.deepcopy(normalized)}
        second = {"id": "theme_magic", "quests": copy.deepcopy(normalized)}

        relayout_chapter(first)
        relayout_chapter(second)
        first_positions = [(quest["x"], quest["y"]) for quest in first["quests"]]
        second_positions = [(quest["x"], quest["y"]) for quest in second["quests"]]

        self.assertEqual(first_positions, second_positions)
        for index, point in enumerate(first_positions):
            for other in first_positions[index + 1:]:
                self.assertGreaterEqual(math.dist(point, other), 1.45)
        self.assertLessEqual(max(abs(value) for point in first_positions for value in point), 100)

        by_id = {quest["id"]: quest for quest in first["quests"]}
        for quest in first["quests"]:
            for dependency in quest.get("dependencies", []):
                parent = by_id[dependency]
                distance = math.dist(
                    (quest["x"], quest["y"]),
                    (parent["x"], parent["y"]),
                )
                self.assertLessEqual(distance, 12.0)

    def test_large_chapters_stay_inside_safe_canvas_bounds(self):
        for chapter_id in (
            "theme_start", "theme_tech", "theme_magic", "theme_world",
            "theme_boss", "kubejs_custom",
        ):
            source = [
                {
                    "title": f"Quest {index}",
                    "tasks": [{"type": "item", "target": f"example:item_{index}"}],
                }
                for index in range(132)
            ]
            chapter = {
                "id": chapter_id,
                "quests": normalize_chapter_quests(chapter_id, source),
            }
            relayout_chapter(chapter)
            coordinates = [
                value for quest in chapter["quests"] for value in (quest["x"], quest["y"])
            ]
            with self.subTest(chapter_id=chapter_id):
                self.assertLessEqual(max(abs(value) for value in coordinates), 100)

    def test_template_routes_keep_crossings_under_control(self):
        def segments_cross(a, b, c, d):
            def orientation(p, q, r):
                return (
                    (q[0] - p[0]) * (r[1] - p[1])
                    - (q[1] - p[1]) * (r[0] - p[0])
                )

            return (
                orientation(a, b, c) * orientation(a, b, d) < 0
                and orientation(c, d, a) * orientation(c, d, b) < 0
            )

        for chapter_id in (
            "theme_start", "theme_tech", "theme_magic", "theme_world", "kubejs_custom"
        ):
            source = [
                {
                    "title": f"Quest {index}",
                    "tasks": [{"type": "item", "target": f"example:item_{index}"}],
                }
                for index in range(60)
            ]
            chapter = {
                "id": chapter_id,
                "quests": normalize_chapter_quests(chapter_id, source),
            }
            relayout_chapter(chapter)
            by_id = {quest["id"]: quest for quest in chapter["quests"]}
            edges = []
            for quest in chapter["quests"]:
                for dependency in quest.get("dependencies", []):
                    parent = by_id[dependency]
                    edges.append((
                        quest["id"],
                        parent["id"],
                        (quest["x"], quest["y"]),
                        (parent["x"], parent["y"]),
                    ))
            crossings = 0
            for index, edge in enumerate(edges):
                for other in edges[index + 1:]:
                    if {edge[0], edge[1]} & {other[0], other[1]}:
                        continue
                    crossings += segments_cross(edge[2], edge[3], other[2], other[3])
            with self.subTest(chapter_id=chapter_id):
                self.assertEqual(crossings, 0)

    def test_info_cards_form_edge_clusters_instead_of_one_long_row(self):
        source = [
            {"title": "Main", "tasks": [{"type": "item", "target": "x:main"}]},
        ] + [
            {"title": f"Note {index}", "tasks": [{"type": "checkmark"}]}
            for index in range(5)
        ]
        chapter = {
            "id": "theme_start",
            "quests": normalize_chapter_quests("theme_start", source),
        }
        relayout_chapter(chapter)
        info = [quest for quest in chapter["quests"] if quest.get("_layout_role") == "info"]

        self.assertEqual(len(info), 5)
        self.assertEqual(len({round(quest["y"], 1) for quest in info}), 1)
        self.assertEqual(
            sorted(round(quest["x"], 1) for quest in info),
            [0.0, 2.5, 5.0, 7.5, 10.0],
        )
        self.assertTrue(all(not quest["dependencies"] for quest in info))
        self.assertTrue(all(quest["shape"] == "gear" for quest in info))

    def test_large_snowflake_keeps_six_clean_arms(self):
        source = [
            {
                "title": f"Quest {index}",
                "tasks": [{"type": "item", "target": f"mod_{index % 12}:item_{index}"}],
            }
            for index in range(150)
        ]
        chapter = {
            "id": "theme_magic",
            "quests": normalize_chapter_quests("theme_magic", source),
        }
        relayout_chapter(chapter)

        arms = {
            quest["_layout_arm"]
            for quest in chapter["quests"]
            if isinstance(quest.get("_layout_arm"), int) and quest["_layout_arm"] >= 0
        }
        self.assertEqual(len(arms), 6)
        by_id = {quest["id"]: quest for quest in chapter["quests"]}
        edge_lengths = []
        for quest in chapter["quests"]:
            for dependency in quest.get("dependencies", []):
                parent = by_id[dependency]
                edge_lengths.append(math.dist(
                    (quest["x"], quest["y"]),
                    (parent["x"], parent["y"]),
                ))
        self.assertLessEqual(max(edge_lengths), 7.1)


if __name__ == "__main__":
    unittest.main()
