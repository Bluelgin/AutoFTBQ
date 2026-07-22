import unittest

from quest_planner import (
    build_fallback_quests,
    build_generation_plan,
    deduplicate_stage_quests,
    normalize_chapter_quests,
)


class QuestPlannerTests(unittest.TestCase):
    def test_density_quotas_are_exact_and_increasing(self):
        mod = {"mod_id": "example", "mod_name": "Example"}
        expected_vanilla = {"light": 24, "medium": 40, "rich": 60, "max": 80}
        totals = []

        for density in expected_vanilla:
            plan = build_generation_plan(density, [mod], [], [], [mod])
            vanilla_total = sum(
                chapter["target"]
                for chapter in plan
                if chapter["namespaces"] == ["minecraft"]
            )
            totals.append(sum(chapter["target"] for chapter in plan))
            self.assertEqual(vanilla_total, expected_vanilla[density])
            self.assertTrue(all(chapter["target"] > 0 for chapter in plan))
            self.assertTrue(all(chapter["batch_size"] > 0 for chapter in plan))

        self.assertEqual(totals, sorted(totals))

    def test_kubejs_plan_excludes_namespaces_already_owned_by_mods(self):
        known = {"mod_id": "known", "mod_name": "Known"}

        plan = build_generation_plan(
            "medium",
            [known],
            [],
            [],
            [known],
            {"known", "pack_custom"},
        )

        custom = next(chapter for chapter in plan if chapter["id"] == "kubejs_custom")
        self.assertEqual(custom["namespaces"], ["pack_custom"])
        self.assertEqual(custom["target"], 10)

    def test_fallback_always_fills_exact_count_without_reusing_items(self):
        chapter = {
            "title": "Machines",
            "namespaces": ["example"],
        }
        all_items = {
            "example": {
                "example:first": "First",
                "example:second": "Second",
            },
        }
        existing = [{
            "title": "Existing",
            "tasks": [{"type": "item", "target": "example:first"}],
        }]

        fallback = build_fallback_quests(chapter, 3, existing, all_items)

        self.assertEqual(len(fallback), 3)
        self.assertEqual(fallback[0]["tasks"][0]["target"], "example:second")
        self.assertEqual(fallback[1]["tasks"][0]["type"], "checkmark")

    def test_normalized_layout_uses_only_valid_dependencies(self):
        source = [
            {"title": "Main 1", "tasks": []},
            {"title": "支线·Branch", "tasks": []},
            {"title": "Main 2", "tasks": []},
        ]

        normalized = normalize_chapter_quests("chapter", source)

        ids = {quest["id"] for quest in normalized}
        self.assertEqual(len(ids), 3)
        for quest in normalized:
            self.assertTrue(set(quest.get("dependencies", [])).issubset(ids))
            self.assertIsInstance(quest["x"], float)
            self.assertIsInstance(quest["y"], float)
        self.assertNotIn("id", source[0])

    def test_stage_deduplication_respects_existing_titles(self):
        quests = [
            {"title": "Already", "tasks": []},
            {"title": "Fresh", "tasks": []},
            {"title": "Fresh", "tasks": []},
        ]

        result = deduplicate_stage_quests(quests, ["already"])

        self.assertEqual([quest["title"] for quest in result], ["Fresh"])


if __name__ == "__main__":
    unittest.main()
