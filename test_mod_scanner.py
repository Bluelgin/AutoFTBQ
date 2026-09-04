import unittest

from mod_scanner import (
    _best_match_scores,
    _find_best_match,
    _normalize_item_key,
    auto_fix_item_ids,
)


class NormalizeTests(unittest.TestCase):
    def test_ignores_separators_and_case(self):
        self.assertEqual(_normalize_item_key("Brass_Ingot"), "brassingot")
        self.assertEqual(_normalize_item_key("Brass Ingot"), "brassingot")
        self.assertEqual(_normalize_item_key("brass-ingot"), "brassingot")
        self.assertEqual(_normalize_item_key(""), "")


class FindBestMatchTests(unittest.TestCase):
    def setUp(self):
        self.items = {
            "create": {
                "create:brass_ingot": "黄铜锭",
                "create:brass_block": "黄铜块",
                "create:copper_nugget": "铜粒",
                "create:andesite_alloy": "安山合金",
                "create:mechanical_press": "动力压制器",
            },
            "tconstruct": {
                "tconstruct:seared_bricks": "焦黑砖",
                "tconstruct:seared_furnace": "焦黑熔炉",
            },
        }

    def test_exact_norm_match(self):
        best, sug, score = _find_best_match("create:BRASS_INGOT", self.items, "create")
        self.assertEqual(best, "create:brass_ingot")
        self.assertIn("create:brass_ingot", sug)
        self.assertGreaterEqual(score, 400)

    def test_plural_match(self):
        best, _sug, _score = _find_best_match("create:brass_ingots", self.items, "create")
        self.assertEqual(best, "create:brass_ingot")

    def test_typo_edit_distance(self):
        best, _sug, score = _find_best_match("create:brass_ingto", self.items, "create")
        self.assertEqual(best, "create:brass_ingot")
        self.assertLess(score, 400)  # 低置信：不自动替换

    def test_substring_match_returns_sorted_candidates(self):
        best, sug, _score = _find_best_match("create:brass", self.items, "create")
        self.assertEqual(best, "create:brass_block")
        self.assertIn("create:brass_ingot", sug)
        self.assertLessEqual(len(sug), 3)

    def test_no_match_returns_empty_suggestions(self):
        best, sug, score = _find_best_match("create:zzz_unknown", self.items, "create")
        self.assertIsNone(best)
        self.assertEqual(sug, [])
        self.assertEqual(score, 0)

    def test_unknown_namespace_returns_empty(self):
        best, sug, _score = _find_best_match("notinstalled:thing", self.items, "notinstalled")
        self.assertIsNone(best)
        self.assertEqual(sug, [])

    def test_scores_descending(self):
        scored = _best_match_scores("brass", self.items["create"])
        scores = [s for _, s in scored]
        self.assertEqual(scores, sorted(scores, reverse=True))


class AutoFixSuggestionsTests(unittest.TestCase):
    def setUp(self):
        self.items = {
            "create": {
                "create:brass_ingot": "黄铜锭",
                "create:brass_block": "黄铜块",
            },
        }

    def test_auto_fix_fixes_near_match_and_reports_unfixable(self):
        quest = {
            "title": "book",
            "chapters": [{
                "id": "c1", "title": "C1",
                "quests": [{
                    "title": "Q1",
                    "tasks": [{"type": "item", "target": "create:brass_ingots", "count": 1}],
                    "rewards": [{"type": "item", "target": "create:brass_ingto", "count": 1}],
                }],
            }],
        }
        fixed, fix_count, unfixable = auto_fix_item_ids(quest, self.items)
        # 复数匹配（高置信）→ 自动修正
        self.assertEqual(fix_count, 1)
        task_target = fixed["chapters"][0]["quests"][0]["tasks"][0]["target"]
        self.assertEqual(task_target, "create:brass_ingot")
        # 编辑距离匹配（低置信）→ 不擅自替换，报告里给建议替代
        self.assertEqual(len(unfixable), 1)
        self.assertEqual(unfixable[0]["id"], "create:brass_ingto")
        self.assertIn("create:brass_ingot", unfixable[0]["suggestions"])


if __name__ == "__main__":
    unittest.main()
