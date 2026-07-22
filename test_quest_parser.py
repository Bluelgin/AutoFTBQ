import json
import unittest

from quest_parser import (
    deduplicate_quest_book,
    extract_json,
    parse_json_document,
    parse_quest_batch,
    repair_json_with_ai,
    reorganize_json,
)


class RepairClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def chat(self, messages, temperature=0.7, max_tokens=8192):
        self.calls.append((messages, temperature, max_tokens))
        return self.response, False


class QuestParserTests(unittest.TestCase):
    def test_extracts_json_from_markdown_fence(self):
        raw = 'prefix\n```json\n{"quests": []}\n```\nsuffix'

        self.assertEqual(extract_json(raw), '{"quests": []}')

    def test_repairs_trailing_commas_and_nested_missing_closers(self):
        raw = '{"chapters":[{"quests":[{"title":"A",}],}'

        data, repaired = parse_json_document(raw)

        self.assertEqual(data["chapters"][0]["quests"][0]["title"], "A")
        self.assertEqual(json.loads(repaired), data)

    def test_invalid_plain_text_returns_no_document(self):
        data, candidate = parse_json_document("not json")

        self.assertIsNone(data)
        self.assertEqual(candidate, "not json")

    def test_batch_parser_ignores_malformed_chapter_shape(self):
        self.assertEqual(parse_quest_batch('{"chapters":["bad"]}'), [])

    def test_reorganize_preserves_invalid_original_text(self):
        raw = "not json"

        self.assertEqual(reorganize_json(raw), raw)

    def test_deduplicates_titles_and_ids_within_chapter(self):
        data = {
            "chapters": [{
                "quests": [
                    {"id": "q1", "title": "First"},
                    {"id": "q2", "title": "First"},
                    {"id": "q1", "title": "Another"},
                ],
            }],
        }

        result, removed = deduplicate_quest_book(data)

        self.assertEqual(removed, 2)
        self.assertEqual(len(result["chapters"][0]["quests"]), 1)

    def test_ai_repair_uses_shared_extractor_and_low_temperature(self):
        client = RepairClient('```json\n{"chapters": []}\n```')

        result = repair_json_with_ai(client, '{"chapters": [', "zh")

        self.assertEqual(result, {"chapters": []})
        self.assertEqual(client.calls[0][1], 0.1)
        self.assertIn("只修复语法错误", client.calls[0][0][0]["content"])


if __name__ == "__main__":
    unittest.main()
