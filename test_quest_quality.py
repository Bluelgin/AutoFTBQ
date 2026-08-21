import unittest

from quest_quality import repair_and_validate_quest_book


class QuestQualityTests(unittest.TestCase):
    def test_adds_descriptions_and_removes_global_duplicate_goals(self):
        data = {
            "chapters": [
                {"title": "A", "quests": [{
                    "id": "a1", "title": "Stone", "subtitle": "Collect it",
                    "tasks": [{"type": "item", "target": "minecraft:stone", "count": 8}],
                    "rewards": [],
                }]},
                {"title": "B", "quests": [{
                    "id": "b1", "title": "Stone again",
                    "tasks": [{"type": "item", "target": "minecraft:stone", "count": 1}],
                    "rewards": [],
                }]},
            ],
        }

        report = repair_and_validate_quest_book(data, {"minecraft": {"minecraft:stone": "Stone"}})

        self.assertEqual(report.descriptions_added, 1)
        self.assertEqual(report.duplicate_goals_removed, 1)
        self.assertTrue(report.publishable)
        self.assertEqual(report.chapters, 1)
        self.assertTrue(data["chapters"][0]["quests"][0]["description"])

    def test_publishable_book_requires_real_chapter_and_task(self):
        data = {"chapters": [{"title": "A", "quests": [{"title": "Read", "tasks": []}]}]}

        report = repair_and_validate_quest_book(data)

        self.assertTrue(report.publishable)
        self.assertEqual(data["chapters"][0]["quests"][0]["tasks"][0]["type"], "checkmark")


if __name__ == "__main__":
    unittest.main()
