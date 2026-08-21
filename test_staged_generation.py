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
from instance_resolver import InstanceInfo


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
                "tasks": [{
                    "type": "item",
                    "target": f"minecraft:test_item_{self.counter}",
                    "count": 1,
                }],
                "rewards": [],
            })
        return json.dumps({"quests": quests}, ensure_ascii=False), False


class EmptyClient:
    def __init__(self):
        self.calls = 0

    def chat(self, messages, temperature=0.7, max_tokens=8192):
        self.calls += 1
        return '{"quests": []}', False


class InvalidShapeClient:
    def __init__(self):
        self.calls = 0

    def chat(self, messages, temperature=0.7, max_tokens=8192):
        self.calls += 1
        return '{"chapters": ["not-a-chapter"]}', False


class FailingClient:
    def chat(self, messages, temperature=0.7, max_tokens=8192):
        raise RuntimeError("offline")


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

    def test_model_shortfall_uses_only_evidence_backed_fallbacks(self):
        client = EmptyClient()
        self.generator.client = client
        self.generator._build_generation_plan = lambda: _small_plan(3, 3)

        result = json.loads(self.generator._generate_questbook_staged())

        quests = result["chapters"][0]["quests"]
        self.assertEqual(client.calls, 3)
        self.assertEqual(len(quests), 3)
        self.assertEqual(quests[0]["tasks"][0]["target"], "minecraft:stone")
        self.assertTrue(all(quest["description"] for quest in quests))
        self.assertEqual(
            len({quest["tasks"][0]["target"] for quest in quests}),
            len(quests),
        )

    def test_malformed_ollama_shape_falls_back_without_attribute_error(self):
        client = InvalidShapeClient()
        self.generator.client = client
        self.generator._build_generation_plan = lambda: _small_plan(2, 2)

        result = json.loads(self.generator._generate_questbook_staged())

        self.assertEqual(len(result["chapters"][0]["quests"]), 2)
        self.assertTrue(all(
            quest["tasks"][0]["type"] == "item"
            for quest in result["chapters"][0]["quests"]
        ))
        self.assertEqual(client.calls, 3)

    def test_staged_failure_is_not_hidden_by_legacy_generation(self):
        self.generator.client = FailingClient()
        self.generator._build_generation_plan = lambda: _small_plan(1, 1)
        self.generator._generate_questbook_legacy = lambda *args: self.fail("legacy flow should not run")

        with self.assertRaisesRegex(RuntimeError, "offline"):
            self.generator._generate_questbook("mods", "minecraft")

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

    def test_fallback_targets_are_unique_across_chapters(self):
        self.generator.client = EmptyClient()
        self.generator._build_generation_plan = lambda: [
            {**_small_plan(2, 2)[0], "id": "first", "title": "First"},
            {**_small_plan(2, 2)[0], "id": "second", "title": "Second"},
        ]

        result = json.loads(self.generator._generate_questbook_staged())

        targets = [
            quest["tasks"][0]["target"]
            for chapter in result["chapters"]
            for quest in chapter["quests"]
        ]
        self.assertEqual(len(targets), len(set(targets)))

    def test_chapter_context_contains_detected_instance_version(self):
        self.generator.instance_info = InstanceInfo(
            root="pack",
            mods_dir="pack/mods",
            quests_dir="pack/config/ftbquests/quests",
            minecraft_version="1.20.1",
            loader="Forge",
            ftb_quests_version="2001.4.17",
        )

        context = self.generator._build_chapter_context(
            _small_plan(1, 1)[0],
            [],
            "minecraft:stone",
        )

        self.assertIn("Minecraft: 1.20.1", context)
        self.assertIn("Loader: Forge", context)


if __name__ == "__main__":
    unittest.main()
