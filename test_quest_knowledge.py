import unittest

from quest_knowledge import QuestKnowledgeBase


class QuestKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.items = {
            "alpha": {
                "alpha:controller": "Controller",
                "alpha:machine": "Machine",
                "alpha:plate": "Plate",
            },
            "beta": {
                "beta:altar": "Altar",
            },
        }
        self.recipes = {
            "alpha:controller": ["alpha:machine", "alpha:plate"],
            "alpha:machine": ["minecraft:iron_ingot"],
            "beta:altar": ["minecraft:stone"],
        }
        self.chapter = {
            "id": "mod_alpha",
            "title": "Alpha",
            "target": 4,
            "mods": [{"mod_id": "alpha"}],
            "namespaces": ["alpha"],
        }

    def test_context_retrieves_only_current_mod_documents_and_recipes(self):
        knowledge = QuestKnowledgeBase(self.items, self.recipes)
        knowledge.add_document("alpha", "wiki", "ALPHA GUIDE")
        knowledge.add_document("beta", "wiki", "BETA GUIDE")

        context = knowledge.build_context(self.chapter, [], "alpha:controller")

        self.assertIn("ALPHA GUIDE", context)
        self.assertNotIn("BETA GUIDE", context)
        self.assertIn("alpha:controller <- alpha:machine + alpha:plate", context)
        self.assertNotIn("beta:altar <-", context)

    def test_coverage_ledger_changes_after_a_goal_is_accepted(self):
        knowledge = QuestKnowledgeBase(self.items, self.recipes)
        existing = [{
            "title": "Build the controller",
            "tasks": [{"type": "item", "target": "alpha:controller"}],
        }]

        context = knowledge.build_context(self.chapter, existing, "alpha:controller")

        self.assertIn("Accepted so far: 1 quests", context)
        self.assertIn("Build the controller -> alpha:controller", context)
        uncovered_line = context.split(
            "Recommended uncovered item goals, in priority order:\n", 1
        )[1].splitlines()[0]
        self.assertNotIn("alpha:controller", uncovered_line)
        self.assertIn("alpha:machine", uncovered_line)

    def test_filter_rejects_repeated_targets_but_keeps_checkmarks(self):
        knowledge = QuestKnowledgeBase(self.items, self.recipes)
        existing = [{
            "title": "First machine",
            "tasks": [{"type": "item", "target": "alpha:machine"}],
        }]
        candidates = [
            {
                "title": "Renamed duplicate",
                "tasks": [{"type": "item", "target": "alpha:machine"}],
            },
            {
                "title": "New controller",
                "tasks": [{"type": "item", "target": "alpha:controller"}],
            },
            {"title": "Read this", "tasks": [{"type": "checkmark"}]},
            {"title": "Read this too", "tasks": [{"type": "checkmark"}]},
        ]

        filtered = knowledge.filter_new_quests(self.chapter, candidates, existing)

        self.assertEqual(
            [quest["title"] for quest in filtered],
            ["New controller", "Read this", "Read this too"],
        )

    def test_namespace_alias_matches_scanned_namespace(self):
        knowledge = QuestKnowledgeBase(
            {"appliedenergistics2": {"appliedenergistics2:controller": "Controller"}},
            {},
        )
        knowledge.add_document("appliedenergistics2", "guide", "AE GUIDE")
        chapter = {
            "id": "mod_appliedenergistics2",
            "title": "AE2",
            "target": 2,
            "mods": [{"mod_id": "appliedenergistics2"}],
            "namespaces": ["appliedenergistics2"],
        }

        context = knowledge.build_context(
            chapter,
            [],
            "appliedenergistics2:controller",
        )

        self.assertIn("AE GUIDE", context)
        self.assertIn("appliedenergistics2:controller", context)


if __name__ == "__main__":
    unittest.main()
