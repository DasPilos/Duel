import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from client import map_drafts

FIRST = [{"layer": "ground", "x": 0, "y": 0, "key": "grass_1"}]
SECOND = [{"layer": "object", "x": 2, "y": 2, "key": "rock_01"}]


class MapDraftsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def _save(self, cells, name, draft_id=None):
        return map_drafts.save_draft(name, cells, 16, 16, draft_id, folder=self.folder)

    def test_save_writes_file_and_lists_it(self):
        saved = self._save(FIRST, "  Степь  ")

        self.assertEqual(saved["name"], "Степь")
        self.assertTrue((self.folder / f"{saved['id']}.json").exists())
        listed = map_drafts.list_drafts(folder=self.folder)
        self.assertEqual([(d["id"], d["name"], d["active_worlds"]) for d in listed], [(saved["id"], "Степь", [])])

    def test_saved_cells_keep_only_position_and_key(self):
        cells = [{"layer": "ground", "x": 0, "y": 0, "key": "grass_1", "extra": 1}]

        saved = self._save(cells, "Степь")

        self.assertEqual(saved["cells"], [{"layer": "ground", "x": 0, "y": 0, "key": "grass_1"}])

    def test_name_clash_with_other_draft_is_rejected(self):
        self._save(FIRST, "Степь")

        with self.assertRaises(map_drafts.DraftError):
            self._save(SECOND, "Степь")

        self.assertEqual(len(map_drafts.list_drafts(folder=self.folder)), 1)

    def test_overwrite_keeps_id_and_replaces_cells_and_name(self):
        saved = self._save(FIRST, "Степь")

        again = self._save(SECOND, "Лес", saved["id"])

        self.assertEqual(again["id"], saved["id"])
        loaded = map_drafts.load_draft(saved["id"], folder=self.folder)
        self.assertEqual(loaded["name"], "Лес")
        self.assertEqual(loaded["cells"], [{"layer": "object", "x": 2, "y": 2, "key": "rock_01"}])
        self.assertEqual(len(map_drafts.list_drafts(folder=self.folder)), 1)

    def test_overwrite_may_keep_own_name(self):
        saved = self._save(FIRST, "Степь")

        again = self._save(SECOND, "Степь", saved["id"])

        self.assertEqual(again["id"], saved["id"])

    def test_empty_or_long_name_is_rejected(self):
        with self.assertRaises(map_drafts.DraftError):
            self._save(FIRST, "   ")
        with self.assertRaises(map_drafts.DraftError):
            self._save(FIRST, "x" * 65)

    def test_size_is_kept(self):
        saved = map_drafts.save_draft("Большая", FIRST, 20, 30, folder=self.folder)

        loaded = map_drafts.load_draft(saved["id"], folder=self.folder)

        self.assertEqual((loaded["map_w"], loaded["map_h"]), (20, 30))

    def test_list_is_newest_first(self):
        with mock.patch("client.map_drafts.time.time", return_value=100.0):
            self._save(FIRST, "Первая")
        with mock.patch("client.map_drafts.time.time", return_value=200.0):
            self._save(SECOND, "Вторая")

        names = [d["name"] for d in map_drafts.list_drafts(folder=self.folder)]

        self.assertEqual(names, ["Вторая", "Первая"])

    def test_missing_draft_cannot_be_loaded(self):
        with self.assertRaises(map_drafts.DraftError):
            map_drafts.load_draft("0" * 32, folder=self.folder)

    def test_broken_file_is_skipped(self):
        self._save(FIRST, "Степь")
        (self.folder / "broken.json").write_text("{не json", encoding="utf-8")

        names = [d["name"] for d in map_drafts.list_drafts(folder=self.folder)]

        self.assertEqual(names, ["Степь"])

    def test_missing_folder_gives_empty_list(self):
        self.assertEqual(map_drafts.list_drafts(folder=self.folder / "нет"), [])

    def test_mark_published_shows_world_in_list(self):
        saved = self._save(FIRST, "Степь")

        map_drafts.mark_published(saved["id"], 2, "Башня", folder=self.folder)

        listed = map_drafts.list_drafts(folder=self.folder)
        self.assertEqual(listed[0]["active_worlds"], ["Башня"])

    def test_one_world_keeps_only_one_map(self):
        first = self._save(FIRST, "Степь")
        second = self._save(SECOND, "Лес")
        map_drafts.mark_published(first["id"], 2, "Башня", folder=self.folder)

        map_drafts.mark_published(second["id"], 2, "Башня", folder=self.folder)

        active = {d["name"]: d["active_worlds"] for d in map_drafts.list_drafts(folder=self.folder)}
        self.assertEqual(active, {"Степь": [], "Лес": ["Башня"]})

    def test_map_can_be_active_in_several_worlds(self):
        saved = self._save(FIRST, "Степь")

        map_drafts.mark_published(saved["id"], 1, "Мир 1", folder=self.folder)
        map_drafts.mark_published(saved["id"], 2, "Башня", folder=self.folder)

        listed = map_drafts.list_drafts(folder=self.folder)
        self.assertEqual(sorted(listed[0]["active_worlds"]), ["Башня", "Мир 1"])

    def test_overwrite_keeps_publication_marks(self):
        saved = self._save(FIRST, "Степь")
        map_drafts.mark_published(saved["id"], 2, "Башня", folder=self.folder)

        self._save(SECOND, "Степь", saved["id"])

        loaded = map_drafts.load_draft(saved["id"], folder=self.folder)
        self.assertEqual(loaded["published"], [{"world_id": 2, "world_name": "Башня"}])

    def test_draft_file_is_json_with_utf8_name(self):
        saved = self._save(FIRST, "Степь")

        raw = (self.folder / f"{saved['id']}.json").read_text(encoding="utf-8")

        self.assertEqual(json.loads(raw)["name"], "Степь")


if __name__ == "__main__":
    unittest.main()
