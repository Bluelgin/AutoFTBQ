import base64
import json
import os
import tempfile
import unittest
import zipfile

from autoftbq_v2.asset_index import AssetIndex


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL6WQAAAABJRU5ErkJggg=="
)


class AssetIndexTests(unittest.TestCase):
    def test_resolves_item_model_texture_from_mod_jar(self):
        with tempfile.TemporaryDirectory() as root:
            mods = os.path.join(root, "mods")
            os.makedirs(mods)
            jar_path = os.path.join(mods, "sample.jar")
            with zipfile.ZipFile(jar_path, "w") as archive:
                archive.writestr(
                    "assets/sample/models/item/gear.json",
                    json.dumps({"parent": "minecraft:item/generated", "textures": {"layer0": "sample:item/gear"}}),
                )
                archive.writestr("assets/sample/textures/item/gear.png", PNG)

            index = AssetIndex.build(
                root,
                {"sample": {"sample:gear": "Gear"}},
                os.path.join(root, "cache"),
            )

            icon = index.icon_for("sample:gear")
            self.assertTrue(os.path.isfile(icon))
            with open(icon, "rb") as handle:
                self.assertEqual(handle.read(), PNG)
            self.assertEqual(index.summary()["icons"], 1)

    def test_child_model_inherits_parent_texture(self):
        with tempfile.TemporaryDirectory() as root:
            mods = os.path.join(root, "mods")
            os.makedirs(mods)
            with zipfile.ZipFile(os.path.join(mods, "sample.jar"), "w") as archive:
                archive.writestr(
                    "assets/sample/models/item/machine.json",
                    json.dumps({"parent": "sample:block/machine"}),
                )
                archive.writestr(
                    "assets/sample/models/block/machine.json",
                    json.dumps({"textures": {"all": "sample:block/machine"}}),
                )
                archive.writestr("assets/sample/textures/block/machine.png", PNG)

            index = AssetIndex.build(
                root,
                {"sample": {"sample:machine": "Machine"}},
                os.path.join(root, "cache"),
            )

            self.assertTrue(index.icon_for("sample:machine"))


if __name__ == "__main__":
    unittest.main()
