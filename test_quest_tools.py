import unittest

from quest_tools import QuestToolbox


class QuestToolboxTests(unittest.TestCase):
    def setUp(self):
        self.toolbox = QuestToolbox(
            {
                "create": {
                    "create:shaft": "Shaft",
                    "create:mechanical_press": "Mechanical Press",
                },
                "farmersdelight": {"farmersdelight:skillet": "Skillet"},
            },
            {"create:mechanical_press": ["create:shaft"]},
        )

    def test_search_is_bounded_and_structured(self):
        result = self.toolbox.search_items("create", "press", 10)
        self.assertEqual(result[0]["item_id"], "create:mechanical_press")

    def test_catalog_only_contains_requested_namespace(self):
        catalog = self.toolbox.build_item_catalog(["create"], limit_per_namespace=10)
        self.assertIn("create:mechanical_press", catalog)
        self.assertNotIn("farmersdelight:skillet", catalog)

    def test_recipe_depth_is_limited(self):
        recipe = self.toolbox.get_recipe("create:mechanical_press", depth=2)
        self.assertEqual(recipe["inputs"], ["create:shaft"])

    def test_read_only_tool_dispatch_returns_json(self):
        result = self.toolbox.call_tool(
            "search_items",
            {"namespace": "create", "query": "press", "limit": 5},
        )

        self.assertIn("create:mechanical_press", result)
        self.assertEqual(len(self.toolbox.tool_specs()), 3)


if __name__ == "__main__":
    unittest.main()
