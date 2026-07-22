import json
import re
import unittest

from quest_generation import (
    StagedGenerationHooks,
    StagedGenerationService,
    calculate_max_tokens,
)


def _plan(target=5, batch_size=2):
    return [{
        "id": "test",
        "title": "Test",
        "target": target,
        "batch_size": batch_size,
    }]


def _hooks(target=5, batch_size=2):
    def parse_batch(content):
        return json.loads(content)["quests"]

    def fallback(chapter, count, existing):
        start = len(existing)
        return [{"title": f"Fallback {start + index + 1}"} for index in range(count)]

    def normalize(chapter_id, quests):
        return [dict(quest, id=f"{chapter_id}_{index + 1}") for index, quest in enumerate(quests)]

    return StagedGenerationHooks(
        build_plan=lambda: _plan(target, batch_size),
        build_catalog=lambda chapter: "catalog",
        build_prompt=lambda chapter, count, titles, catalog, wiki: (
            f"EXACT_QUEST_COUNT={count}\nWIKI={wiki}"
        ),
        parse_batch=parse_batch,
        deduplicate_batch=lambda quests, titles: [
            quest for quest in quests if quest.get("title") not in titles
        ],
        build_fallback=fallback,
        normalize_chapter=normalize,
        max_tokens=lambda: 9999,
    )


class ExactClient:
    def __init__(self):
        self.calls = []
        self.messages = []
        self.counter = 0

    def chat(self, messages, temperature=0.7, max_tokens=8192):
        count = int(re.search(r"EXACT_QUEST_COUNT=(\d+)", messages[-1]["content"]).group(1))
        self.calls.append((count, temperature, max_tokens))
        self.messages.append(messages)
        quests = []
        for _ in range(count):
            self.counter += 1
            quests.append({"title": f"Quest {self.counter}"})
        return json.dumps({"quests": quests}), False


class EmptyClient:
    def __init__(self):
        self.calls = 0

    def chat(self, messages, temperature=0.7, max_tokens=8192):
        self.calls += 1
        return '{"quests": [{"title": "Ignored"}]}', True


class FailingClient:
    def chat(self, messages, temperature=0.7, max_tokens=8192):
        raise RuntimeError("offline")


class QuestGenerationTests(unittest.TestCase):
    def test_token_policy_matches_existing_limits(self):
        self.assertEqual(calculate_max_tokens(5, "deepseek", "medium"), 16384)
        self.assertEqual(calculate_max_tokens(6, "deepseek", "medium"), 32768)
        self.assertEqual(calculate_max_tokens(30, "ollama", "rich"), 61440)
        self.assertEqual(calculate_max_tokens(30, "ollama", "rich", is_continuation=True), 73728)
        self.assertEqual(calculate_max_tokens(100, "ollama", "max", "7777"), 7777)

    def test_generates_exact_count_in_bounded_batches(self):
        client = ExactClient()
        progress = []
        service = StagedGenerationService(client, "medium", lambda *args: progress.append(args), _hooks())

        result = json.loads(service.generate("notes"))

        self.assertEqual([call[0] for call in client.calls], [2, 2, 1])
        self.assertEqual([call[2] for call in client.calls], [3072, 3072, 3072])
        self.assertEqual(len(result["chapters"][0]["quests"]), 5)
        self.assertIn("EXACT_QUEST_COUNT", client.messages[0][0]["content"])
        self.assertIn("WIKI=notes", client.messages[0][1]["content"])
        self.assertTrue(progress)

    def test_truncated_batches_retry_then_fill_exact_shortfall(self):
        client = EmptyClient()
        service = StagedGenerationService(client, "medium", lambda *args: None, _hooks(3, 3))

        result = json.loads(service.generate())

        quests = result["chapters"][0]["quests"]
        self.assertEqual(client.calls, 3)
        self.assertEqual(len(quests), 3)
        self.assertTrue(all(quest["title"].startswith("Fallback") for quest in quests))

    def test_missing_client_has_clear_error(self):
        service = StagedGenerationService(None, "medium", lambda *args: None, _hooks(1, 1))

        with self.assertRaisesRegex(RuntimeError, "AI 客户端"):
            service.generate()

    def test_client_failure_is_not_hidden(self):
        service = StagedGenerationService(FailingClient(), "medium", lambda *args: None, _hooks(1, 1))

        with self.assertRaisesRegex(RuntimeError, "offline"):
            service.generate()


if __name__ == "__main__":
    unittest.main()
