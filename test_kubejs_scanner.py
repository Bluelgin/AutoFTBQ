import json
import os
import tempfile
import unittest
import zipfile
from unittest.mock import patch

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

    def test_scanner_keeps_large_mod_item_catalogs(self):
        jar_path = os.path.join(self.root, "mods", "large-mod.jar")
        with zipfile.ZipFile(jar_path, "w") as archive:
            for index in range(5105):
                archive.writestr(
                    f"assets/large/models/item/item_{index:03d}.json",
                    "{}",
                )

        items = mod_scanner.scan_jar_items(jar_path)

        self.assertEqual(len(items["large"]), 5105)

    def test_limited_scan_does_not_poison_unlimited_cache(self):
        jar_path = os.path.join(self.root, "mods", "cache-limit.jar")
        with zipfile.ZipFile(jar_path, "w") as archive:
            for index in range(5):
                archive.writestr(
                    f"assets/cachelimit/models/item/item_{index}.json",
                    "{}",
                )

        limited = mod_scanner.scan_jar_items(jar_path, max_items_per_ns=2)
        complete = mod_scanner.scan_jar_items(jar_path)

        self.assertEqual(len(limited["cachelimit"]), 2)
        self.assertEqual(len(complete["cachelimit"]), 5)

    def test_scanner_rejects_abnormally_large_archive_entry_counts(self):
        jar_path = os.path.join(self.root, "mods", "suspicious.jar")
        with zipfile.ZipFile(jar_path, "w") as archive:
            for index in range(3):
                archive.writestr(f"assets/test/models/item/item_{index}.json", "{}")

        with patch.object(mod_scanner, "MAX_ARCHIVE_ENTRIES", 2):
            items = mod_scanner.scan_jar_items(jar_path)

        self.assertEqual(items, {})

    def test_legacy_prompt_catalog_stays_bounded_after_full_scan(self):
        items = {
            "huge": {
                f"huge:item_{index:03d}": f"Item {index}"
                for index in range(240)
            },
        }

        catalog = mod_scanner.build_item_catalog_for_prompt(
            items,
            [{"mod_id": "huge", "filename": "huge-1.0.jar"}],
        )

        self.assertIn("showing 160", catalog)
        self.assertIn("80 more available through on-demand tools", catalog)
        self.assertNotIn("huge:item_239", catalog)

    def test_namespace_resolution_does_not_use_unrelated_mod_filenames(self):
        catalog = mod_scanner.build_item_catalog_for_prompt(
            {"goety": {"goety:focus": "Focus"}},
            [
                {"mod_id": "missing", "filename": "missing-1.0.jar"},
                {"mod_id": "goety", "filename": "goety-1.0.jar"},
            ],
        )

        self.assertIn("missing: (no items scanned", catalog)

    def test_non_item_task_targets_are_not_fuzzy_fixed_as_items(self):
        quest_data = {
            "chapters": [{
                "title": "Boss",
                "quests": [{
                    "title": "Defeat boss",
                    "tasks": [
                        {"type": "kill", "target": "bossmod:ancient_guardian"},
                        {"type": "dimension", "target": "bossmod:dark_realm"},
                    ],
                    "rewards": [],
                }],
            }],
        }

        fixed, fix_count, unfixable = mod_scanner.auto_fix_item_ids(
            quest_data,
            {"bossmod": {"bossmod:ancient_guardian_spawn_egg": "Spawn Egg"}},
        )

        self.assertEqual(fixed, quest_data)
        self.assertEqual(fix_count, 0)
        self.assertEqual(unfixable, [])

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

    def test_detect_library_mods_keeps_playstyle_mods_and_filters_libs(self):
        mods = [
            {"mod_id": "farmersdelight", "mod_name": "Farmer's Delight", "category": "food"},
            {"mod_id": "touhoulittlemaid", "mod_name": "Maid", "category": "unknown"},
            {"mod_id": "architectury", "mod_name": "Architectury", "category": "unknown"},
            {"mod_id": "oculus", "mod_name": "Oculus", "category": "unknown"},
            {"mod_id": "randomplaymod", "mod_name": "Random", "category": "unknown"},
            {"mod_id": "c3me", "mod_name": "C3ME", "category": "unknown"},
        ]
        all_items = {
            "farmersdelight": {"farmersdelight:knife": "Knife"},
            "touhoulittlemaid": {},
            "architectury": {},
            "oculus": {},
            "randomplaymod": {},
            "c3me": {},
        }
        mod_scanner.detect_library_mods(mods, all_items)
        by_id = {m["mod_id"]: m for m in mods}
        self.assertFalse(by_id["farmersdelight"]["is_library"])
        self.assertFalse(by_id["touhoulittlemaid"]["is_library"])
        self.assertTrue(by_id["architectury"]["is_library"])
        self.assertTrue(by_id["oculus"]["is_library"])
        self.assertTrue(by_id["randomplaymod"]["is_library"])
        self.assertTrue(by_id["c3me"]["is_library"])


if __name__ == "__main__":
    unittest.main()
