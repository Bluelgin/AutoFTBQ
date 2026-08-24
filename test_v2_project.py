import os
import tempfile
import unittest

from autoftbq_v2.project import ProjectStore, QuestBookProject


class V2ProjectTests(unittest.TestCase):
    def test_commands_undo_and_roundtrip(self):
        store = ProjectStore(QuestBookProject(title="Test"))
        chapter = store.create_chapter("Tech")
        first = store.add_quest(chapter.id, "Get iron", task_type="item", target="minecraft:iron_ingot")
        second = store.add_quest(chapter.id, "Make plate", task_type="item", target="create:iron_sheet")

        self.assertEqual(second.dependencies, [])
        self.assertTrue(store.undo())
        self.assertEqual(len(store.chapter(chapter.id).quests), 1)
        self.assertTrue(store.redo())
        self.assertEqual(len(store.chapter(chapter.id).quests), 2)

        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "book.autoftbq.json")
            store.save(path)
            loaded = ProjectStore.load(path)
        self.assertEqual(loaded.summary(), store.summary())

    def test_validation_reports_bad_item_and_dependency(self):
        store = ProjectStore(QuestBookProject())
        chapter = store.create_chapter("Broken")
        quest = store.add_quest(chapter.id, "Bad", task_type="item", target="not_an_id")
        quest.dependencies.append("missing")

        issues = store.validate()

        self.assertTrue(any("物品 ID" in issue["message"] for issue in issues))
        self.assertTrue(any("依赖不存在" in issue["message"] for issue in issues))

    def test_manual_connection_rejects_cycles(self):
        store = ProjectStore(QuestBookProject())
        chapter = store.create_chapter("Progress")
        first = store.add_quest(chapter.id, "First")
        second = store.add_quest(chapter.id, "Second")

        store.connect(second.id, first.id)
        self.assertEqual(second.dependencies, [first.id])
        with self.assertRaisesRegex(ValueError, "循环依赖"):
            store.connect(first.id, second.id)


if __name__ == "__main__":
    unittest.main()
