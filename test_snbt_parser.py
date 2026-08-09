import os
import unittest

from snbt_parser import parse_snbt, to_snbt, _SNBTFloat, _SNBTTypedArray


class SNBTParserTests(unittest.TestCase):
    def test_parses_real_example_chapter(self):
        path = os.path.join("example_all", "ep_1_quests", "chapters", "0D6A9F55CA8C6D04.snbt")
        if not os.path.isfile(path):
            self.skipTest("example file not present")
        with open(path, "r", encoding="utf-8") as handle:
            data = parse_snbt(handle.read())
        self.assertIsInstance(data, dict)
        self.assertIn("quests", data)
        self.assertTrue(data["quests"])
        first = data["quests"][0]
        self.assertIn("id", first)
        self.assertIn("tasks", first)

    def test_parses_generated_chapter_with_float_coordinates(self):
        path = os.path.join("quests", "chapters", "07278CF7D3984C11.snbt")
        if not os.path.isfile(path):
            self.skipTest("generated chapter not present")
        with open(path, "r", encoding="utf-8") as handle:
            data = parse_snbt(handle.read())
        quest = data["quests"][0]
        self.assertIsInstance(quest.get("x"), _SNBTFloat)
        self.assertIsInstance(quest.get("y"), _SNBTFloat)

    def test_round_trip_preserves_structure(self):
        source = '''{
	title: "Test"
	quests: [
		{
			description: ["第一行", "第二行"]
			id: "ABC123"
			x: 0.0d
			y: -2.5d
			flag: true
			empty: [ ]
			nested: {
				tag: {
					Damage: 0
				}
			}
			typed: [I; -800846297 -1505998786]
		}
	]
}'''
        first = parse_snbt(source)
        second = parse_snbt(to_snbt(first))
        self.assertEqual(first, second)
        quest = second["quests"][0]
        self.assertEqual(quest["x"], 0.0)
        self.assertEqual(quest["y"], -2.5)
        self.assertIs(quest["flag"], True)
        self.assertEqual(quest["typed"], [-800846297, -1505998786])
        self.assertIsInstance(quest["typed"], _SNBTTypedArray)
        self.assertIn("[I;", to_snbt(first))

    def test_round_trip_quotes_namespaced_and_special_keys(self):
        source = '{"curios:inventory": {"#c": "ae2:f"}}'

        first = parse_snbt(source)
        serialized = to_snbt(first)
        second = parse_snbt(serialized)

        self.assertEqual(first, second)
        self.assertIn('"curios:inventory":', serialized)
        self.assertIn('"#c":', serialized)

    def test_parses_escaped_strings(self):
        data = parse_snbt('{a: "he said \\"hi\\"", b: "C:\\\\path"}')
        self.assertEqual(data["a"], 'he said "hi"')
        self.assertEqual(data["b"], "C:\\path")

    def test_optional_commas_are_tolerated(self):
        data = parse_snbt('{a: 1, b: 2, c: [3, 4]}')
        self.assertEqual(data, {"a": 1, "b": 2, "c": [3, 4]})


if __name__ == "__main__":
    unittest.main()
