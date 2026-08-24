import unittest

from autoftbq_v2.skill_registry import SkillRegistry


class SkillRegistryTests(unittest.TestCase):
    def test_catalog_exposes_stable_skill_ids(self):
        registry = SkillRegistry()
        skill_ids = {item["skill_id"] for item in registry.catalog()}
        self.assertIn("plan.mainline", skill_ids)
        self.assertIn("plan.mod_branch", skill_ids)
        self.assertIn("repair.questbook", skill_ids)

    def test_skill_body_is_loaded_only_when_requested(self):
        result = SkillRegistry().load("plan.merge_progression")
        self.assertEqual(result["skill_id"], "plan.merge_progression")
        self.assertIn("主线", result["instructions"])

    def test_unknown_skill_returns_available_ids(self):
        result = SkillRegistry().load("missing")
        self.assertIn("error", result)
        self.assertIn("plan.mainline", result["available"])


if __name__ == "__main__":
    unittest.main()
