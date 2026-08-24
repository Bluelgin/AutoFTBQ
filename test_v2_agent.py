import unittest

from autoftbq_v2.agent import ProjectAgent
from autoftbq_v2.project import ProjectStore, QuestBookProject
from quest_tools import QuestToolbox


class FakeToolClient:
    def chat_with_tools(self, messages, tools, handler, **_kwargs):
        summary = handler("get_project_summary", {})
        self.assert_json(summary)
        skills = handler("list_skills", {})
        self.assert_json_list(skills)
        handler("load_skill", {"skill_id": "plan.mod_branch"})
        chapter = handler("create_chapter", {"title": "机械动力"})
        import json
        chapter_id = json.loads(chapter)["chapter_id"]
        handler("search_items", {"namespace": "create", "query": "press"})
        handler("add_quest", {
            "chapter_id": chapter_id,
            "title": "机械压制",
            "description": "制作机械动力压片机。",
            "task_type": "item",
            "target": "create:mechanical_press",
            "count": 1,
        })
        handler("validate_project", {})
        return "已创建机械动力章节并完成检查。", False

    @staticmethod
    def assert_json(value):
        import json
        assert isinstance(json.loads(value), dict)

    @staticmethod
    def assert_json_list(value):
        import json
        assert isinstance(json.loads(value), list)


class FakeActionClient:
    def __init__(self):
        self.responses = iter([
            ('{"actions":[{"tool":"create_chapter","arguments":{"title":"魔法入门"}}],"reply":"正在创建"}', False),
            ('{"actions":[],"reply":"魔法章节已经创建。"}', False),
        ])

    def chat(self, _messages, **_kwargs):
        return next(self.responses)


class V2AgentTests(unittest.TestCase):
    def test_agent_changes_project_only_through_tools(self):
        store = ProjectStore(QuestBookProject())
        toolbox = QuestToolbox({"create": {"create:mechanical_press": "Mechanical Press"}})
        actions = []
        agent = ProjectAgent(store, FakeToolClient(), toolbox, lambda name, *_: actions.append(name))

        reply = agent.run("创建机械动力任务")

        self.assertIn("完成检查", reply)
        self.assertEqual(store.project.chapters[0].title, "机械动力")
        self.assertEqual(store.project.chapters[0].quests[0].tasks[0].target, "create:mechanical_press")
        self.assertEqual(actions, [
            "get_project_summary", "list_skills", "load_skill", "create_chapter", "search_items",
            "add_quest", "validate_project",
        ])

    def test_plain_chat_client_uses_bounded_action_protocol(self):
        store = ProjectStore(QuestBookProject())
        agent = ProjectAgent(store, FakeActionClient())

        reply = agent.run("创建魔法章节")

        self.assertEqual(reply, "魔法章节已经创建。")
        self.assertEqual(store.project.chapters[0].title, "魔法入门")


if __name__ == "__main__":
    unittest.main()
