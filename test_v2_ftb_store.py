import os
import tempfile
import unittest

from snbt_parser import parse_snbt, to_snbt

from autoftbq_v2.ftb_store import FTBQuestStore, locate_quest_root
from autoftbq_v2.agent import ProjectAgent


CHAPTER = {
    "id": "1000000000000001",
    "filename": "1000000000000001",
    "title": "Real chapter",
    "icon": {"id": "minecraft:book", "count": 1},
    "unknown_chapter_field": {"keep": "yes"},
    "quests": [
        {
            "id": "2000000000000001",
            "title": "First",
            "subtitle": "Before",
            "x": 1.0,
            "y": 2.0,
            "shape": "diamond",
            "dependencies": [],
            "unknown_quest_field": 77,
            "tasks": [
                {"id": "3000000000000001", "type": "item", "item": {"id": "minecraft:stone", "components": {"x": 1}}, "count": 2, "extra": True},
                {"id": "3000000000000002", "type": "checkmark", "custom": "untouched"},
            ],
            "rewards": [{"id": "4000000000000001", "type": "custom", "custom_data": {"keep": 1}}],
            "description": ["Line one"],
        }
    ],
}


class FTBQuestStoreTests(unittest.TestCase):
    def make_book(self, root):
        quest_root = os.path.join(root, "config", "ftbquests", "quests")
        chapters = os.path.join(quest_root, "chapters")
        os.makedirs(chapters)
        path = os.path.join(chapters, "1000000000000001.snbt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(to_snbt(CHAPTER))
        return quest_root, path

    def test_locates_and_loads_real_book(self):
        with tempfile.TemporaryDirectory() as root:
            quest_root, _ = self.make_book(root)
            self.assertEqual(locate_quest_root(root), quest_root)
            store = FTBQuestStore.load_directory(quest_root, root)
            quest = store.project.chapters[0].quests[0]
            self.assertEqual(quest.x, 1.0)
            self.assertEqual(quest.tasks[0].target, "minecraft:stone")
            self.assertEqual(len(quest.tasks), 2)

    def test_edits_real_fields_and_preserves_unknown_snbt(self):
        with tempfile.TemporaryDirectory() as root:
            quest_root, path = self.make_book(root)
            store = FTBQuestStore.load_directory(quest_root, root)
            quest = store.project.chapters[0].quests[0]

            store.update_quest(
                quest.id, title="Changed", subtitle="After", task_type="item",
                target="minecraft:diamond", count=3, shape="hexagon",
            )
            store.move_quest(quest.id, 4.5, -2.0)
            result = store.save_all()

            self.assertEqual(result["saved"], 1)
            self.assertTrue(os.path.isdir(result["backup"]))
            with open(path, "r", encoding="utf-8") as handle:
                raw = parse_snbt(handle.read())
            saved = raw["quests"][0]
            self.assertEqual(saved["title"], "Changed")
            self.assertEqual(saved["x"], 4.5)
            self.assertEqual(saved["tasks"][0]["item"]["id"], "minecraft:diamond")
            self.assertEqual(saved["tasks"][0]["item"]["components"], {"x": 1})
            self.assertEqual(saved["tasks"][1]["custom"], "untouched")
            self.assertEqual(saved["rewards"][0]["custom_data"], {"keep": 1})
            self.assertEqual(saved["unknown_quest_field"], 77)
            self.assertEqual(raw["unknown_chapter_field"], {"keep": "yes"})

    def test_undo_restores_raw_sections_and_view(self):
        with tempfile.TemporaryDirectory() as root:
            quest_root, _ = self.make_book(root)
            store = FTBQuestStore.load_directory(quest_root, root)
            quest = store.project.chapters[0].quests[0]
            store.replace_quest_sections(quest.id, [{"id": "5", "type": "kill", "entity": "minecraft:zombie"}], [])
            self.assertEqual(store.quest(quest.id)[1].tasks[0].type, "kill")
            self.assertTrue(store.undo())
            self.assertEqual(store.quest(quest.id)[1].tasks[0].type, "item")
            self.assertEqual(store.raw_sections(quest.id)[0][0]["extra"], True)

    def test_agent_tools_edit_same_real_document(self):
        with tempfile.TemporaryDirectory() as root:
            quest_root, _ = self.make_book(root)
            store = FTBQuestStore.load_directory(quest_root, root)
            quest = store.project.chapters[0].quests[0]
            agent = ProjectAgent(store, None)

            result = agent.call_tool("replace_quest_sections", {
                "quest_id": quest.id,
                "rewards": [{"id": "5000000000000001", "type": "xp", "xp": 50}],
            })

            self.assertIn('"rewards":1', result)
            self.assertEqual(store.raw_sections(quest.id)[1][0]["xp"], 50)
            self.assertIn(store.project.chapters[0].id, store.dirty_chapters)


if __name__ == "__main__":
    unittest.main()
