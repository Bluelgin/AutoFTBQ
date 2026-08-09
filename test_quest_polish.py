import json
import unittest

from quest_polish import QuestPolishService


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def chat(self, messages, temperature=0.7, max_tokens=8192):
        self.calls.append((messages, temperature, max_tokens))
        return self.response, False


def _chapter():
    return {
        "title": "Twilight Forest",
        "quests": [
            {
                "id": "Q1",
                "title": "进入暮色森林",
                "subtitle": "",
                "description": ["制作传送门"],
                "tasks": [{"type": "item", "target": "minecraft:oak_log"}],
                "rewards": [],
                "x": 0.0,
                "y": 0.0,
                "shape": "square",
            },
            {
                "id": "Q2",
                "title": "九头蛇",
                "description": ["击败九头蛇。"],
                "tasks": [{"type": "kill", "entity": "twilightforest:hydra"}],
                "rewards": [],
                "x": 2.0,
                "y": 0.0,
                "shape": "square",
            },
        ],
    }


class QuestPolishTests(unittest.TestCase):
    def test_applies_subtitle_and_description_patch(self):
        response = json.dumps({"patches": [
            {"quest": "Q1", "subtitle": "先找个安全的地方安家吧！", "description": ["去森林砍几棵树吧"]},
            {"quest": "Q2", "subtitle": "小心它的三个头", "description": ["带好弓箭再去"]},
        ]}, ensure_ascii=False)
        service = QuestPolishService(FakeClient(response))
        chapter = _chapter()
        service.polish_chapter(chapter)
        by_id = {q["id"]: q for q in chapter["quests"]}
        self.assertEqual(by_id["Q1"]["subtitle"], "先找个安全的地方安家吧！")
        self.assertEqual(by_id["Q1"]["description"], ["去森林砍几棵树吧"])
        self.assertEqual(by_id["Q2"]["subtitle"], "小心它的三个头")
        self.assertEqual(by_id["Q2"]["description"], ["带好弓箭再去"])

    def test_rejects_unknown_quest_ids_with_warning(self):
        response = json.dumps({"patches": [
            {"quest": "NOPE", "subtitle": "x"},
            {"quest": "Q1", "subtitle": "ok"},
        ]}, ensure_ascii=False)
        service = QuestPolishService(FakeClient(response))
        chapter = _chapter()
        _, report = service.polish_chapter(chapter)
        self.assertEqual(report["applied"], 1)
        self.assertTrue(any("NOPE" in warning for warning in report["warnings"]))

    def test_ignores_disallowed_fields(self):
        response = json.dumps({"patches": [
            {"quest": "Q1", "subtitle": "ok", "dependencies": ["other"], "tasks": []},
        ]}, ensure_ascii=False)
        service = QuestPolishService(FakeClient(response))
        chapter = _chapter()
        _, report = service.polish_chapter(chapter)
        quest = chapter["quests"][0]
        self.assertNotIn("dependencies", quest)
        self.assertTrue(any("不允许修改" in warning for warning in report["warnings"]))

    def test_retries_then_gives_up_on_bad_response(self):
        class BrokenClient:
            def __init__(self):
                self.calls = 0

            def chat(self, messages, temperature=0.7, max_tokens=8192):
                self.calls += 1
                return "not json at all", False

        client = BrokenClient()
        service = QuestPolishService(client)
        chapter = _chapter()
        _, report = service.polish_chapter(chapter)
        self.assertEqual(report["applied"], 0)
        self.assertGreaterEqual(client.calls, 2)

    def test_truncated_response_retries(self):
        class TruncatingClient:
            def __init__(self):
                self.calls = 0

            def chat(self, messages, temperature=0.7, max_tokens=8192):
                self.calls += 1
                return "", True

        client = TruncatingClient()
        service = QuestPolishService(client)
        service.polish_chapter(_chapter())
        self.assertGreaterEqual(client.calls, 2)

    def test_network_error_retries_without_masking_original_failure(self):
        class RaisingClient:
            def __init__(self):
                self.calls = 0

            def chat(self, messages, temperature=0.7, max_tokens=8192):
                self.calls += 1
                raise ConnectionError("offline")

        client = RaisingClient()
        service = QuestPolishService(client)
        _, report = service.polish_chapter(_chapter())
        self.assertEqual(report["applied"], 0)
        self.assertGreaterEqual(client.calls, 2)


if __name__ == "__main__":
    unittest.main()
