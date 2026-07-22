import unittest

from quest_prompts import (
    build_stage_prompt,
    build_system_prompt,
    build_user_prompt,
    build_web_prompt,
    milestone_to_prompt,
)


class QuestPromptTests(unittest.TestCase):
    def test_system_prompt_contains_requested_range_and_json_contract(self):
        prompt = build_system_prompt("zh", "80-150")

        self.assertIn("共 80-150 个任务", prompt)
        self.assertIn("只输出JSON", prompt)
        self.assertIn("dependencies", prompt)

    def test_stage_prompt_uses_exact_count_and_only_recent_titles(self):
        titles = [f"Quest {index}" for index in range(35)]
        chapter = {"title": "Machines", "focus": "Automation"}

        prompt = build_stage_prompt("en", chapter, 7, titles, "ITEM_CATALOG", "WIKI")

        self.assertIn("EXACT_QUEST_COUNT=7", prompt)
        self.assertNotIn("Quest 4,", prompt)
        self.assertIn("Quest 5", prompt)
        self.assertIn("Quest 34", prompt)
        self.assertIn("ITEM_CATALOG", prompt)

    def test_user_prompt_includes_context_and_milestones(self):
        prompt = build_user_prompt(
            "zh",
            "MOD_LIST",
            "minecraft, example",
            "WIKI_CONTEXT",
            "ITEM_CATALOG",
            "MILESTONES",
        )

        for expected in ("MOD_LIST", "WIKI_CONTEXT", "ITEM_CATALOG", "MILESTONES"):
            self.assertIn(expected, prompt)

    def test_web_prompt_keeps_item_ids_and_output_rule(self):
        prompt = build_web_prompt(
            "en",
            "50-80",
            "MOD_LIST",
            "minecraft, example",
            "example:machine",
            "MILESTONES",
        )

        self.assertIn("50-80", prompt)
        self.assertIn("example:machine", prompt)
        self.assertIn("Output ONLY JSON", prompt)
        self.assertTrue(prompt.endswith("MILESTONES"))

    def test_milestones_support_both_languages(self):
        milestones = {"example": ["example:machine"]}

        chinese = milestone_to_prompt(milestones, "zh")
        english = milestone_to_prompt(milestones, "en")

        self.assertIn("必须覆盖", chinese)
        self.assertIn("Must Cover", english)
        self.assertIn("example:machine", chinese)
        self.assertIn("example:machine", english)


if __name__ == "__main__":
    unittest.main()
