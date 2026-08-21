import unittest

from quest_planner import (
    build_fallback_quests,
    build_generation_plan,
    deduplicate_stage_quests,
    normalize_chapter_quests,
)


class QuestPlannerTests(unittest.TestCase):
    def test_theme_plan_groups_mods_and_keeps_vanilla_progression(self):
        mods = [
            {"mod_id": "create", "mod_name": "Create", "category": "tech"},
            {"mod_id": "touhoulittlemaid", "mod_name": "Maid", "category": "unknown"},
        ]
        plan = build_generation_plan("medium", mods, [], [], mods)
        ids = [chapter["id"] for chapter in plan]
        self.assertEqual(ids[:5], [
            "theme_start", "theme_food", "theme_mining", "theme_tech", "theme_magic"
        ])
        self.assertIn("theme_pet", ids)
        self.assertIn("theme_world", ids)
        self.assertIn("theme_boss", ids)
        tech = next(chapter for chapter in plan if chapter["id"] == "theme_tech")
        self.assertEqual(tech["namespaces"], ["minecraft", "create"])
        pet = next(chapter for chapter in plan if chapter["id"] == "theme_pet")
        self.assertEqual(pet["mods"][0]["mod_id"], "touhoulittlemaid")
        self.assertTrue(all(chapter["target"] > 0 for chapter in plan))
        self.assertTrue(all(chapter["batch_size"] > 0 for chapter in plan))

    def test_density_preserves_vanilla_and_per_mod_quotas(self):
        core = {"mod_id": "create", "mod_name": "Create", "category": "tech"}
        utility = {"mod_id": "waystones", "mod_name": "Waystones", "category": "utility"}
        expected = {
            "light": 24 + 6 + 2,
            "medium": 40 + 10 + 3,
            "rich": 60 + 16 + 5,
            "max": 80 + 24 + 8,
        }
        for density, total in expected.items():
            plan = build_generation_plan(
                density,
                [core],
                [utility],
                [],
                [core, utility],
            )
            self.assertEqual(sum(chapter["target"] for chapter in plan), total)

    def test_large_theme_splits_without_capping_mod_coverage(self):
        mods = [
            {"mod_id": f"tech_{index}", "mod_name": f"Tech {index}", "category": "tech"}
            for index in range(12)
        ]
        plan = build_generation_plan("medium", mods, [], [], mods)
        tech_chapters = [chapter for chapter in plan if chapter["id"].startswith("theme_tech")]

        self.assertEqual([len(chapter["mods"]) for chapter in tech_chapters], [5, 5, 2])
        self.assertEqual(sum(chapter["target"] for chapter in plan), 40 + 12 * 10)

    def test_world_mod_stays_in_world_theme_not_mining(self):
        mod = {"mod_id": "twilightforest", "mod_name": "Twilight", "category": "world"}
        plan = build_generation_plan("medium", [mod], [], [], [mod])
        world = next(chapter for chapter in plan if chapter["id"] == "theme_world")
        self.assertIn("twilightforest", world["namespaces"])

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

    def test_fallback_stops_when_unique_evidence_is_exhausted(self):
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

        self.assertEqual(len(fallback), 1)
        self.assertEqual(fallback[0]["tasks"][0]["target"], "example:second")
        self.assertTrue(fallback[0]["description"])

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

    def test_normalized_layout_builds_small_progression_groups(self):
        source = [
            {
                "title": f"Quest {index}",
                "tasks": [{"type": "item", "target": f"example:item_{index}"}],
            }
            for index in range(18)
        ]

        normalized = normalize_chapter_quests("theme_tech", source)
        groups = {}
        for quest in normalized:
            groups.setdefault(quest["_layout_group"], []).append(quest)

        self.assertGreater(len(groups), 1)
        self.assertTrue(all(1 <= len(group) <= 6 for group in groups.values()))
        self.assertTrue(any(quest["_layout_role"] == "branch" for quest in normalized))
        self.assertFalse(all(
            quest.get("dependencies") == [normalized[index - 1]["id"]]
            for index, quest in enumerate(normalized[1:], start=1)
        ))

    def test_summary_info_and_boss_receive_semantic_roles(self):
        source = [
            {"title": "First", "tasks": [{"type": "item", "target": "x:first"}]},
            {"title": "Hydra Boss", "tasks": [{"type": "kill", "entity": "x:hydra"}]},
            {"title": "A useful note", "tasks": [{"type": "checkmark"}]},
            {"title": "Chapter Summary", "tasks": [{"type": "checkmark"}]},
        ]

        normalized = normalize_chapter_quests("theme_boss", source)
        by_title = {quest["title"]: quest for quest in normalized}

        self.assertEqual(by_title["Hydra Boss"]["_layout_role"], "boss")
        self.assertEqual(by_title["Hydra Boss"]["shape"], "hexagon")
        self.assertEqual(by_title["A useful note"]["_layout_role"], "info")
        self.assertEqual(by_title["Chapter Summary"]["_layout_role"], "milestone")
        self.assertTrue(by_title["Chapter Summary"]["dependencies"])

    def test_checkmark_progress_is_not_detached_as_an_info_card(self):
        source = [
            {"title": "First", "tasks": [{"type": "item", "target": "x:first"}]},
            {"title": "Stage complete", "tasks": [{"type": "checkmark"}]},
        ]

        normalized = normalize_chapter_quests("theme_start", source)
        stage = next(quest for quest in normalized if quest["title"] == "Stage complete")

        self.assertNotEqual(stage.get("_layout_role"), "info")
        self.assertTrue(stage["dependencies"])

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
