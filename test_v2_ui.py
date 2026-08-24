import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from autoftbq_v2.ui import DependencyLine, MainWindow, QuestNode


class V2UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_two_click_connection_updates_project(self):
        window = MainWindow()
        chapter = window.store.chapter(window.current_chapter_id)
        first = chapter.quests[0]
        second = window.store.add_quest(chapter.id, "Second")
        third = window.store.add_quest(chapter.id, "Third")
        third.dependencies.clear()
        window.refresh_all()

        window.toggle_connect_mode(True)
        window._handle_connection_click(first)
        window._handle_connection_click(third)

        self.assertIn(first.id, window.store.quest(third.id)[1].dependencies)
        self.assertTrue(window.connect_mode)
        window.close()

    def test_agent_mutation_action_refreshes_canvas(self):
        window = MainWindow()
        chapter = window.store.chapter(window.current_chapter_id)
        window.store.add_quest(chapter.id, "Live quest")

        window.append_action("add_quest", "live")

        node_ids = {
            item.data(0)
            for item in window.scene.items()
            if hasattr(item, "data") and item.data(0)
        }
        self.assertEqual(len(node_ids), len(chapter.quests))
        window.close()

    def test_dependency_line_follows_moved_node(self):
        window = MainWindow()
        chapter = window.store.chapter(window.current_chapter_id)
        second = window.store.add_quest(chapter.id, "Second")
        window.store.connect(second.id, chapter.quests[0].id)
        window.refresh_all()
        edge = next(item for item in window.scene.items() if isinstance(item, DependencyLine))
        source = next(
            item for item in window.scene.items()
            if isinstance(item, QuestNode) and item.quest.id == chapter.quests[0].id
        )
        before = QPointF(edge.line().p1())

        source.setPos(source.pos() + QPointF(100, 40))

        self.assertNotEqual(edge.line().p1(), before)
        self.assertEqual(edge.line().p1(), source.sceneBoundingRect().center())
        window.close()

    def test_manual_add_creates_unique_unconnected_quest(self):
        window = MainWindow()
        chapter = window.store.chapter(window.current_chapter_id)

        window.add_quest()
        window.add_quest()

        self.assertEqual([quest.title for quest in chapter.quests[-2:]], ["新任务 2", "新任务 3"])
        self.assertEqual(chapter.quests[-1].dependencies, [])
        window.close()


if __name__ == "__main__":
    unittest.main()
