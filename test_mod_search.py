import unittest

from main import _mod_matches_query


class ModSearchTests(unittest.TestCase):
    def setUp(self):
        self.mod = {
            "mod_name": "Farmer's Delight",
            "mod_id": "farmersdelight",
            "filename": "FarmersDelight-1.20.1.jar",
            "category": "food",
        }

    def test_empty_query_matches_every_mod(self):
        self.assertTrue(_mod_matches_query(self.mod, ""))

    def test_matches_name_id_filename_and_category(self):
        for query in ("farmer", "FARMERSDELIGHT", "1.20.1", "food"):
            with self.subTest(query=query):
                self.assertTrue(_mod_matches_query(self.mod, query))

    def test_unrelated_query_does_not_match(self):
        self.assertFalse(_mod_matches_query(self.mod, "mekanism"))


if __name__ == "__main__":
    unittest.main()
