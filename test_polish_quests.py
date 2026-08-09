import os
import tempfile
import unittest

from polish_quests import write_chapters
from snbt_parser import parse_snbt


class PolishQuestWriteTests(unittest.TestCase):
    def test_write_preserves_snbt_types_and_creates_backup(self):
        chapter = parse_snbt(
            '{title: "New" "curios:inventory": [I; 1 2 3] "#tag": "c:ingots/iron"}'
        )
        with tempfile.TemporaryDirectory() as output_dir:
            chapters_dir = os.path.join(output_dir, "chapters")
            os.makedirs(chapters_dir)
            destination = os.path.join(chapters_dir, "chapter.snbt")
            with open(destination, "w", encoding="utf-8") as handle:
                handle.write('{title: "Old"}')

            backup_dir = write_chapters(
                [{"filename": "chapter.snbt", "chapter": chapter}],
                output_dir,
                create_backup=True,
            )

            self.assertIsNotNone(backup_dir)
            with open(destination, "r", encoding="utf-8") as handle:
                written = handle.read()
            self.assertEqual(parse_snbt(written), chapter)
            self.assertIn('[I;', written)
            self.assertIn('"curios:inventory":', written)
            with open(
                os.path.join(backup_dir, "chapter.snbt"),
                "r",
                encoding="utf-8",
            ) as handle:
                self.assertEqual(handle.read(), '{title: "Old"}')


if __name__ == "__main__":
    unittest.main()
