import json
import os
import tempfile
import unittest
import zipfile

import mod_scanner


class KubeJSScannerTests(unittest.TestCase):
    def setUp(self):
        mod_scanner.clear_cache()
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        os.makedirs(os.path.join(self.root, "mods"))
        os.makedirs(os.path.join(self.root, "kubejs", "startup_scripts"))
        os.makedirs(os.path.join(self.root, "kubejs", "server_scripts"))
        os.makedirs(os.path.join(self.root, "kubejs", "assets", "kubejs", "lang"))

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, relative_path, content):
        path = os.path.join(self.root, relative_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def test_scans_registered_items_and_common_recipes(self):
        self._write(
            "kubejs/startup_scripts/items.js",
            """
            StartupEvents.registry('item', event => {
              event.create('compressed_iron')
              event.create('pack:quest_core')
            })
            """,
        )
        self._write(
            "kubejs/server_scripts/recipes.js",
            """
            ServerEvents.recipes(event => {
              event.shaped('kubejs:compressed_iron', ['II'], {I: 'minecraft:iron_ingot'})
              event.recipes.create.crushing(['2x pack:iron_dust'], 'minecraft:iron_ore')
            })
            """,
        )
        self._write(
            "kubejs/assets/kubejs/lang/zh_cn.json",
            json.dumps({"item.kubejs.compressed_iron": "Compressed Iron"}),
        )

        items = mod_scanner.scan_folder_items(self.root)

        self.assertEqual(items["kubejs"]["kubejs:compressed_iron"], "Compressed Iron")
        self.assertIn("pack:quest_core", items["pack"])
        self.assertIn("pack:iron_dust", items["pack"])
        self.assertEqual(
            mod_scanner._recipe_inputs_cache["kubejs:compressed_iron"],
            ["minecraft:iron_ingot"],
        )
        self.assertEqual(
            mod_scanner._recipe_inputs_cache["pack:iron_dust"],
            ["minecraft:iron_ore"],
        )
        quest_data = {
            "chapters": [{
                "title": "KubeJS",
                "quests": [{
                    "title": "Custom item",
                    "tasks": [{"target": "kubejs:compressed_iron"}],
                    "rewards": [],
                }],
            }],
        }
        _, fix_count, unfixable = mod_scanner.auto_fix_item_ids(quest_data, items)
        self.assertEqual(fix_count, 0)
        self.assertEqual(unfixable, [])
        catalog = mod_scanner.build_item_catalog_for_prompt(items, [])
        self.assertIn("kubejs:compressed_iron", catalog)
        self.assertIn("pack:quest_core", catalog)
        recipe_hints = mod_scanner.build_recipe_chain_hints([])
        self.assertIn("kubejs:compressed_iron", recipe_hints)
        self.assertIn("minecraft:iron_ingot", recipe_hints)

    def test_mods_directory_resolves_sibling_kubejs_folder(self):
        self._write(
            "kubejs/startup_scripts/items.js",
            "StartupEvents.registry('item', event => event.create('visible_from_mods_dir'))",
        )

        items = mod_scanner.scan_folder_items(os.path.join(self.root, "mods"))

        self.assertIn("kubejs:visible_from_mods_dir", items["kubejs"])

    def test_dynamic_ids_are_not_claimed_as_valid(self):
        self._write(
            "kubejs/startup_scripts/dynamic.js",
            "items.forEach(name => event.create(`dynamic_${name}`))",
        )

        items = mod_scanner.scan_folder_items(self.root)

        self.assertNotIn("kubejs", items)

    def test_json_recipe_uses_only_ingredient_fields(self):
        recipe = {
            "type": "minecraft:crafting_shaped",
            "key": {"I": {"item": "minecraft:iron_ingot"}},
            "result": {"item": "kubejs:iron_plate"},
        }
        self._write("kubejs/data/kubejs/recipes/iron_plate.json", json.dumps(recipe))

        mod_scanner.scan_folder_items(self.root)

        self.assertEqual(
            mod_scanner._recipe_inputs_cache["kubejs:iron_plate"],
            ["minecraft:iron_ingot"],
        )

    def test_recipe_cache_is_scoped_to_current_scan_and_survives_jar_cache(self):
        jar_path = os.path.join(self.root, "mods", "sample.jar")
        recipe = {
            "type": "minecraft:crafting_shaped",
            "key": {"I": {"item": "minecraft:iron_ingot"}},
            "result": {"item": "sample:plate"},
        }
        smelting_recipe = {
            "type": "minecraft:smelting",
            "ingredient": {"item": "minecraft:raw_iron"},
            "result": "sample:ingot",
        }
        with zipfile.ZipFile(jar_path, "w") as jar:
            jar.writestr("data/sample/recipes/plate.json", json.dumps(recipe))
            jar.writestr("data/sample/recipes/ingot.json", json.dumps(smelting_recipe))

        mod_scanner.scan_folder_items(self.root)
        self.assertIn("sample:plate", mod_scanner._recipe_inputs_cache)
        mod_scanner._recipe_inputs_cache["old:stale"] = ["minecraft:dirt"]

        mod_scanner.scan_folder_items(self.root)

        self.assertNotIn("old:stale", mod_scanner._recipe_inputs_cache)
        self.assertEqual(
            mod_scanner._recipe_inputs_cache["sample:plate"],
            ["minecraft:iron_ingot"],
        )
        self.assertEqual(
            mod_scanner._recipe_inputs_cache["sample:ingot"],
            ["minecraft:raw_iron"],
        )

    def test_recipe_hint_sections_keep_their_mod_order(self):
        mod_scanner._recipe_inputs_cache.update({
            "first:machine": ["minecraft:iron_ingot"],
            "second:altar": ["minecraft:diamond"],
        })
        mods = [
            {"mod_id": "first", "mod_name": "First"},
            {"mod_id": "second", "mod_name": "Second"},
        ]

        hints = mod_scanner.build_recipe_chain_hints(mods)

        self.assertLess(hints.index("First (first)"), hints.index("first:machine"))
        self.assertLess(hints.index("first:machine"), hints.index("Second (second)"))
        self.assertLess(hints.index("Second (second)"), hints.index("second:altar"))


if __name__ == "__main__":
    unittest.main()
