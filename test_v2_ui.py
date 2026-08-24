import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from autoftbq_v2.ui import MainWindow


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


if __name__ == "__main__":
    unittest.main()
