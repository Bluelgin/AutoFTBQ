import json
import os
import re
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    sys.modules["requests"] = types.ModuleType("requests")

from ai_module import QuestBookGenerator, _uid, to_snbt
from quest_layout import relayout_chapter
from quest_planner import normalize_chapter_quests
from quest_writer import MARKER_CHAPTER_ID


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
            if filename != f"{MARKER_CHAPTER_ID}.snbt" and filename.endswith(".snbt"):
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

    def test_snbt_strings_fold_embedded_control_whitespace(self):
        text = to_snbt({"description": "first line\nsecond\tline\rthird"})

        self.assertIn('description: "first line second line third"', text)
        self.assertNotIn("first line\nsecond", text)

    def test_generated_ids_fit_ftb_quests_signed_long_range(self):
        values = [_uid() for _ in range(1000)]

        self.assertEqual(len(values), len(set(values)))
        self.assertTrue(all(len(value) == 16 for value in values))
        self.assertTrue(all(1 < int(value, 16) <= 0x7FFFFFFFFFFFFFFF for value in values))

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
        self.assertFalse((first_files - {f"{MARKER_CHAPTER_ID}.snbt"}) & remaining)

    def test_chapter_group_references_use_existing_hex_ids(self):
        data = {
            "chapters": [
                {"title": "Tech A", "_group": "tech", "quests": [_quest("q1")]},
                {"title": "Tech B", "_group": "tech", "quests": [_quest("q2")]},
                {"title": "World", "_group": "world", "quests": [_quest("q3")]},
            ],
        }

        self.generator._write_snbt_files(self.output, data)

        with open(os.path.join(self.output, "chapter_groups.snbt"), encoding="utf-8") as handle:
            group_text = handle.read()
        group_ids = set(re.findall(r'\bid: "([0-9A-F]{16})"', group_text))
        chapter_groups = []
        for filename in os.listdir(os.path.join(self.output, "chapters")):
            with open(os.path.join(self.output, "chapters", filename), encoding="utf-8") as handle:
                match = re.search(r'^\s*group: "([0-9A-F]{16})"', handle.read(), re.MULTILINE)
            self.assertIsNotNone(match, filename)
            chapter_groups.append(match.group(1))

        self.assertTrue(set(chapter_groups).issubset(group_ids))
        self.assertEqual(len(chapter_groups), 4)
        self.assertEqual(len(set(chapter_groups)), 3)
        self.assertNotIn('id: "tech"', group_text)

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

    def test_layout_metadata_is_not_written_to_snbt(self):
        source = [
            {
                "title": f"Quest {index}",
                "tasks": [{"type": "item", "target": "minecraft:stone"}],
                "rewards": [],
            }
            for index in range(8)
        ]
        chapter = {
            "id": "theme_tech",
            "title": "Technology",
            "quests": normalize_chapter_quests("theme_tech", source),
        }
        relayout_chapter(chapter)

        self.generator._write_snbt_files(self.output, {"chapters": [chapter]})

        text = self._chapter_texts()[0]
        self.assertNotIn("_layout_", text)
        self.assertIn("dependencies:", text)
        self.assertIn("shape:", text)

    def test_save_pipeline_adds_description_and_quality_report(self):
        output = os.path.join(self.output, "published")
        payload = json.dumps({
            "title": "Pack",
            "chapters": [{
                "title": "Start",
                "quests": [{
                    "id": "q1",
                    "title": "Stone",
                    "subtitle": "Collect stone",
                    "tasks": [{"type": "item", "target": "minecraft:stone"}],
                    "rewards": [],
                }],
            }],
        })

        self.generator._save_snbt_files(
            payload,
            {"minecraft": {"minecraft:stone": "Stone"}},
            output,
        )

        self.assertTrue(os.path.isfile(os.path.join(output, "quality_report.txt")))
        with open(os.path.join(output, "quality_report.txt"), encoding="utf-8") as handle:
            self.assertIn("状态: 可发布", handle.read())
        chapter_files = [
            name for name in os.listdir(os.path.join(output, "chapters"))
            if name.endswith(".snbt") and name != f"{MARKER_CHAPTER_ID}.snbt"
        ]
        with open(os.path.join(output, "chapters", chapter_files[0]), encoding="utf-8") as handle:
            self.assertIn("description:", handle.read())

    def test_save_pipeline_rejects_empty_book(self):
        output = os.path.join(self.output, "empty")

        with self.assertRaisesRegex(Exception, "未通过发布检查"):
            self.generator._save_snbt_files('{"title":"Empty","chapters":[]}', {}, output)

        self.assertFalse(os.path.isfile(os.path.join(output, "data.snbt")))


if __name__ == "__main__":
    unittest.main()
