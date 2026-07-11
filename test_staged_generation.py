import json
import re
import sys
import types
import unittest

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    sys.modules["requests"] = types.ModuleType("requests")

from ai_module import QuestBookGenerator


class ExactClient:
    def __init__(self):
        self.calls = []
        self.counter = 0

    def chat(self, messages, temperature=0.7, max_tokens=8192):
        prompt = messages[-1]["content"]
        count = int(re.search(r"EXACT_QUEST_COUNT=(\d+)", prompt).group(1))
        self.calls.append(count)
        quests = []
        for _ in range(count):
            self.counter += 1
            prefix = "支线·" if self.counter % 3 == 0 else "主线·"
            quests.append({
                "title": f"{prefix}任务 {self.counter}",
                "subtitle": "test",
                "tasks": [{"type": "item", "target": "minecraft:stone", "count": 1}],
                "rewards": [],
            })
        return json.dumps({"quests": quests}, ensure_ascii=False), False


class EmptyClient:
    def __init__(self):
        self.calls = 0

    def chat(self, messages, temperature=0.7, max_tokens=8192):
        self.calls += 1
        return '{"quests": []}', False


def _small_plan(target=5, batch_size=2):
    return [{
        "id": "test_chapter",
        "title": "Test Chapter",
        "focus": "Testing",
        "target": target,
        "batch_size": batch_size,
        "mods": [],
        "namespaces": ["minecraft"],
    }]


class StagedGenerationTests(unittest.TestCase):
    def setUp(self):
        self.generator = QuestBookGenerator(engine="dummy")
        self.generator.density = "medium"
        self.generator._all_items = {"minecraft": {"minecraft:stone": "Stone"}}

    def test_generates_exact_quota_in_bounded_batches(self):
        client = ExactClient()
        self.generator.client = client
        self.generator._build_generation_plan = lambda: _small_plan(5, 2)

        result = json.loads(self.generator._generate_questbook_staged())

        quests = result["chapters"][0]["quests"]
        self.assertEqual(client.calls, [2, 2, 1])
        self.assertEqual(len(quests), 5)
        ids = {quest["id"] for quest in quests}
        for quest in quests:
            self.assertTrue(set(quest.get("dependencies", [])).issubset(ids))
            self.assertIn("x", quest)
            self.assertIn("y", quest)

    def test_fills_model_shortfall_to_exact_quota(self):
        client = EmptyClient()
        self.generator.client = client
        self.generator._build_generation_plan = lambda: _small_plan(3, 3)

        result = json.loads(self.generator._generate_questbook_staged())

        quests = result["chapters"][0]["quests"]
        self.assertEqual(client.calls, 3)
        self.assertEqual(len(quests), 3)
        self.assertEqual(quests[0]["tasks"][0]["target"], "minecraft:stone")

    def test_density_plan_is_deterministic_and_increasing(self):
        mod = {"mod_id": "example", "mod_name": "Example", "category": "tech"}
        generator = QuestBookGenerator(selected_mods=[mod], engine="dummy")
        totals = []
        for density in ("light", "medium", "rich", "max"):
            generator.density = density
            plan = generator._build_generation_plan()
            totals.append(sum(chapter["target"] for chapter in plan))
            self.assertTrue(all(isinstance(chapter["target"], int) for chapter in plan))
        self.assertEqual(totals, sorted(totals))
        self.assertEqual(len(totals), len(set(totals)))


if __name__ == "__main__":
    unittest.main()
