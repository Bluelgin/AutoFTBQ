import json
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    sys.modules["requests"] = types.ModuleType("requests")

from ai_module import QuestBookGenerator


def _quest(quest_id=None, dependency=None, count=1):
    quest = {
        "title": quest_id or "Untitled",
        "tasks": [{"type": "item", "target": "minecraft:stone", "count": count}],
        "rewards": [],
    }
    if quest_id is not None:
        quest["id"] = quest_id
    if dependency is not None:
        quest["dependencies"] = [dependency]
    return quest


class QuestWriterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = self.temp.name
        os.makedirs(os.path.join(self.output, "chapters"), exist_ok=True)
        self.generator = QuestBookGenerator(engine="dummy")

    def tearDown(self):
        self.temp.cleanup()

    def _chapter_texts(self):
        chapter_dir = os.path.join(self.output, "chapters")
        texts = []
        for filename in os.listdir(chapter_dir):
            if filename != "ZZZZZZZZZZZZZZZZ.snbt" and filename.endswith(".snbt"):
                with open(os.path.join(chapter_dir, filename), "r", encoding="utf-8") as f:
                    texts.append(f.read())
        return texts

    def _output_snapshot(self):
        snapshot = {}
        for root, _, files in os.walk(self.output):
            for filename in files:
                path = os.path.join(root, filename)
                relative = os.path.relpath(path, self.output)
                with open(path, "rb") as handle:
                    snapshot[relative] = handle.read()
        return snapshot

    def test_preserves_item_task_count(self):
        data = {"chapters": [{"title": "A", "quests": [_quest("q1", count=64)]}]}

        self.generator._write_snbt_files(self.output, data)

        self.assertIn("count: 64", self._chapter_texts()[0])

    def test_scopes_duplicate_source_ids_to_each_chapter(self):
        data = {
            "chapters": [
                {"title": "A", "quests": [_quest("q1"), _quest("q2", "q1")]},
                {"title": "B", "quests": [_quest("q1"), _quest("q2", "q1")]},
            ],
        }

        self.generator._write_snbt_files(self.output, data)

        texts = self._chapter_texts()
        quest_ids = []
        for text in texts:
            for line in text.splitlines():
                if line.strip().startswith("id: "):
                    quest_ids.append(line.strip())
        self.assertEqual(len(quest_ids), len(set(quest_ids)))

    def test_keeps_quests_without_source_ids(self):
        data = {"chapters": [{"title": "A", "quests": [_quest()]}]}

        self.generator._write_snbt_files(self.output, data)

        self.assertIn('title: "Untitled"', self._chapter_texts()[0])

    def test_removes_only_files_from_previous_manifest(self):
        user_file = os.path.join(self.output, "chapters", "USER_CHAPTER.snbt")
        with open(user_file, "w", encoding="utf-8") as f:
            f.write("user content")
        first = {"chapters": [{"title": "A", "quests": [_quest("q1")]}]}
        self.generator._write_snbt_files(self.output, first)
        with open(os.path.join(self.output, ".autoftbq_manifest.json"), "r", encoding="utf-8") as f:
            first_files = set(json.load(f)["chapter_files"])

        second = {"chapters": [{"title": "B", "quests": [_quest("q2")]}]}
        self.generator._write_snbt_files(self.output, second)
        remaining = set(os.listdir(os.path.join(self.output, "chapters")))

        self.assertTrue(os.path.isfile(user_file))
        self.assertFalse((first_files - {"ZZZZZZZZZZZZZZZZ.snbt"}) & remaining)

    def test_available_namespaces_include_scanned_kubejs_namespaces(self):
        self.generator._all_items = {"kubejs": {}, "pack": {}}

        namespaces = self.generator._build_all_ns().split(", ")

        self.assertIn("kubejs", namespaces)
        self.assertIn("pack", namespaces)

    def test_kill_target_is_not_used_as_an_item_icon(self):
        data = {
            "chapters": [{
                "title": "Combat",
                "quests": [{
                    "id": "kill_zombie",
                    "title": "Kill zombie",
                    "tasks": [{"type": "kill", "target": "minecraft:zombie", "count": 3}],
                    "rewards": [],
                }],
            }],
        }

        self.generator._write_snbt_files(self.output, data)

        text = self._chapter_texts()[0]
        self.assertIn('icon: "minecraft:book"', text)
        self.assertNotIn('icon: "minecraft:zombie"', text)

    def test_flattens_nested_item_references_without_stringifying_dicts(self):
        data = {
            "chapters": [{
                "title": "AE2",
                "quests": [{
                    "id": "p2p",
                    "title": "P2P",
                    "tasks": [{
                        "type": "item",
                        "item": {"id": "appliedenergistics2:p2p_tunnel", "count": 2},
                    }],
                    "rewards": [{
                        "type": "item",
                        "item": {"item": "minecraft:diamond", "count": 4},
                    }],
                }],
            }],
        }

        self.generator._write_snbt_files(self.output, data)

        text = self._chapter_texts()[0]
        self.assertIn('item: "appliedenergistics2:p2p_tunnel"', text)
        self.assertIn('item: "minecraft:diamond"', text)
        self.assertIn("count: 2", text)
        self.assertIn("count: 4", text)
        self.assertNotIn("{'id':", text)

    def test_rejects_description_dict_as_item_id(self):
        data = {
            "chapters": [{
                "title": "Relics",
                "quests": [{
                    "id": "collection",
                    "title": "Collection",
                    "tasks": [{"type": "item", "target": {"title": "Collect ten relics"}}],
                    "rewards": [],
                }],
            }],
        }

        self.generator._write_snbt_files(self.output, data)

        text = self._chapter_texts()[0]
        self.assertNotIn("Collect ten relics", text)
        self.assertIn('type: "checkmark"', text)

    def test_serialization_failure_keeps_previous_output_unchanged(self):
        first = {"chapters": [{"title": "Stable", "quests": [_quest("q1")]}]}
        self.generator._write_snbt_files(self.output, first)
        before = self._output_snapshot()

        second = {"chapters": [{"title": "Broken", "quests": [_quest("q2")]}]}
        with patch("ai_module.to_snbt", side_effect=RuntimeError("serialize failed")):
            with self.assertRaisesRegex(RuntimeError, "serialize failed"):
                self.generator._write_snbt_files(self.output, second)

        self.assertEqual(self._output_snapshot(), before)

    def test_partial_commit_failure_rolls_back_every_generated_file(self):
        first = {"chapters": [{"title": "Stable", "quests": [_quest("q1")]}]}
        self.generator._write_snbt_files(self.output, first)
        before = self._output_snapshot()
        real_replace = os.replace
        staged_replaces = 0

        def fail_second_staged_replace(source, target):
            nonlocal staged_replaces
            if ".autoftbq-stage-" in source:
                staged_replaces += 1
                if staged_replaces == 2:
                    raise PermissionError("simulated lock")
            return real_replace(source, target)

        second = {"chapters": [{"title": "Replacement", "quests": [_quest("q2")]}]}
        with patch("quest_writer.os.replace", side_effect=fail_second_staged_replace):
            with self.assertRaisesRegex(PermissionError, "simulated lock"):
                self.generator._write_snbt_files(self.output, second)

        self.assertEqual(self._output_snapshot(), before)


if __name__ == "__main__":
    unittest.main()
