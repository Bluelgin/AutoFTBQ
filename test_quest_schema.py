import unittest

from quest_schema import QuestValidationError, extract_quest_batch, normalize_quest_book


class QuestSchemaTests(unittest.TestCase):
    def test_extract_batch_ignores_string_chapter(self):
        self.assertEqual(extract_quest_batch({"chapters": ["bad"]}), [])

    def test_normalization_filters_invalid_nested_entries(self):
        data = {
            "chapters": [{
                "title": "Test",
                "quests": ["bad", {"title": "Good", "tasks": ["bad"], "rewards": None}],
            }],
        }

        normalized, issues = normalize_quest_book(data)

        self.assertEqual(len(normalized["chapters"][0]["quests"]), 1)
        self.assertEqual(normalized["chapters"][0]["quests"][0]["tasks"], [])
        self.assertTrue(issues)

    def test_invalid_chapters_has_clear_validation_error(self):
        with self.assertRaisesRegex(QuestValidationError, "chapters 必须是数组"):
            normalize_quest_book({"chapters": "bad"})


if __name__ == "__main__":
    unittest.main()
