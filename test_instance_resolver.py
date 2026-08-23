import json
import os
import tempfile
import unittest
from unittest.mock import patch

from instance_resolver import application_dir, resolve_instance, suggested_output_dir


class InstanceResolverTests(unittest.TestCase):
    def test_resolves_pcl_style_instance_from_mods_folder(self):
        with tempfile.TemporaryDirectory() as root:
            mods = os.path.join(root, "mods")
            os.makedirs(mods)
            os.makedirs(os.path.join(root, "config"))
            with open(os.path.join(root, "Pack.json"), "w", encoding="utf-8") as handle:
                json.dump({
                    "arguments": {"game": ["--fml.mcVersion", "1.20.1", "forgeclient"]},
                    "libraries": [{"name": "net.minecraftforge:forge:47.4.0"}],
                }, handle)
            open(os.path.join(mods, "ftb-quests-forge-2001.4.17.jar"), "wb").close()

            info = resolve_instance(mods)

            self.assertEqual(info.root, root)
            self.assertEqual(info.minecraft_version, "1.20.1")
            self.assertEqual(info.loader, "Forge")
            self.assertEqual(info.ftb_quests_version, "2001.4.17")
            self.assertEqual(suggested_output_dir(mods), os.path.join(root, "config", "ftbquests", "quests"))

    def test_frozen_application_dir_uses_executable_not_mei_dir(self):
        with patch("instance_resolver.sys.frozen", True, create=True), patch(
            "instance_resolver.sys.executable", r"C:\Apps\AutoFTBQ.exe"
        ):
            self.assertEqual(application_dir(r"C:\Temp\_MEI123"), r"C:\Apps")

    def test_nonstandard_arguments_do_not_block_instance_detection(self):
        for arguments in (None, [], "legacy"):
            with self.subTest(arguments=arguments), tempfile.TemporaryDirectory() as root:
                mods = os.path.join(root, "mods")
                os.makedirs(mods)
                with open(os.path.join(root, "Pack.json"), "w", encoding="utf-8") as handle:
                    json.dump({"id": "forge-1.12.2", "arguments": arguments}, handle)

                info = resolve_instance(mods)

                self.assertIsNotNone(info)
                self.assertEqual(info.minecraft_version, "1.12.2")


if __name__ == "__main__":
    unittest.main()
