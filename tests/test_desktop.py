import tempfile
import unittest
from pathlib import Path
from unittest import mock

from qgui import desktop


class RecentFoldersTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.patch = mock.patch.multiple(desktop, CONFIG_DIR=base / "cfg",
                                         CONFIG_FILE=base / "cfg" / "config.json")
        self.patch.start()
        self.a, self.b = base / "a", base / "b"
        self.a.mkdir()
        self.b.mkdir()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_last_folder_is_most_recent(self):
        self.assertIsNone(desktop.last_folder())
        desktop.remember_folder(self.a)
        desktop.remember_folder(self.b)
        desktop.remember_folder(self.a)
        self.assertEqual(desktop.recent_folders(), [str(self.a.resolve()), str(self.b.resolve())])

    def test_missing_folders_are_skipped_and_forget_works(self):
        desktop.remember_folder(self.a)
        desktop.remember_folder(self.b)
        self.b.rmdir()
        self.assertEqual(desktop.last_folder(), str(self.a.resolve()))
        desktop.forget_folder(str(self.a.resolve()))
        self.assertIsNone(desktop.last_folder())


    def test_limit_and_order_by_use(self):
        base = Path(self.tmp.name)
        dirs = []
        for i in range(8):
            d = base / f"p{i}"
            d.mkdir()
            dirs.append(d)
            desktop.remember_folder(d)
        recent = desktop.recent_folders()
        self.assertEqual(len(recent), desktop.MAX_RECENT)                 # aktuálny + 5
        self.assertEqual(recent[0], str(dirs[7].resolve()))               # najnovší navrchu
        self.assertNotIn(str(dirs[0].resolve()), recent)                  # najstarší zabudnutý
        desktop.remember_folder(dirs[3])                                  # opätovné použitie
        self.assertEqual(desktop.recent_folders()[0], str(dirs[3].resolve()))
        self.assertEqual(len(desktop.recent_folders()), desktop.MAX_RECENT)


if __name__ == "__main__":
    unittest.main()
