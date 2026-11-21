import contextlib
import io
import os
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from client import map_drafts
from core import map_catalog
from core.tiled_bridge import export_draft_to_tmx, import_tmx
from client.map_editor_state import MapEditorState
from scenes.map_editor_scene import MapEditorScene
from scripts import tiled_bridge as tiled_cli

GAME_FIELDS = {"mode", "mobs", "spawns", "crystals", "harvest_enabled"}


class TiledBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1920, 1080))
        shared = tempfile.TemporaryDirectory()
        cls.addClassCleanup(shared.cleanup)
        cls.shared_root = Path(shared.name)
        cls.catalog = {
            item["item_key"]: item
            for item in map_catalog.catalog_definitions()
        }
        cls.specs = map_catalog.desert_tile_specs()
        cls.ground_key = next(
            key for key, spec in cls.specs.items()
            if key in cls.catalog
            and cls.catalog[key]["kind"] == "ground"
            and spec.get("tile_id") is not None
        )
        cls.object_key = next(
            key for key, item in cls.catalog.items()
            if key.startswith("desert_objects_sprite_")
            and item["kind"] == "object"
        )

    def _draft(self):
        editor_layers = [[] for _ in range(8)]
        editor_layers[3].append({
            "layer": "elevation",
            "x": 1,
            "y": 2,
            "key": self.ground_key,
        })
        editor_layers[5].append({
            "layer": "object",
            "x": 3,
            "y": 2,
            "key": self.object_key,
        })
        return {
            "name": "TMX round trip",
            "map_w": 5,
            "map_h": 4,
            "mode": "tower",
            "cells": [],
            "editor_layers": editor_layers,
            "mobs": [{"kind": "imp_vanilla", "x": 2, "y": 1}],
            "spawns": [{"x": 4, "y": 3}],
            "crystals": {"red": {"count": 2}},
            "harvest_enabled": True,
        }

    def test_round_trip_preserves_game_map_content(self):
        draft = self._draft()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = export_draft_to_tmx(
                draft,
                root / "roundtrip.tmx",
                tilesets_dir=root / "tilesets",
            )
            tree = ET.parse(path)
            layer_ids = [
                node.get("id")
                for node in tree.getroot().iter()
                if node.tag in {"group", "layer", "objectgroup"}
            ]
            object_ids = [
                node.get("id")
                for node in tree.getroot().iter("object")
            ]
            self.assertEqual(len(layer_ids), len(set(layer_ids)))
            self.assertEqual(len(object_ids), len(set(object_ids)))
            result = import_tmx(path)

        self.assertEqual(result.warnings, [])
        self.assertEqual(result.explicit, GAME_FIELDS)
        restored = result.draft
        cells = [
            cell
            for layer in [restored["cells"], *restored["editor_layers"]]
            for cell in layer
        ]
        self.assertEqual(
            {(cell["key"], cell["layer"], cell["x"], cell["y"]) for cell in cells},
            {
                (self.ground_key, "elevation", 1, 2),
                (self.object_key, "object", 3, 2),
            },
        )
        self.assertEqual((restored["map_w"], restored["map_h"]), (5, 4))
        self.assertEqual(restored["mode"], "tower")
        self.assertEqual(restored["mobs"], draft["mobs"])
        self.assertEqual(restored["spawns"], draft["spawns"])
        self.assertEqual(restored["crystals"], draft["crystals"])
        self.assertTrue(restored["harvest_enabled"])
        editor = object.__new__(MapEditorScene)
        editor.catalog = list(self.catalog.values())
        editor.palette_overrides = {}
        editor.state = MapEditorState(
            editor.catalog,
            restored["cells"],
            restored["map_w"],
            restored["map_h"],
        )
        MapEditorScene._restore_editor_layers(
            editor,
            restored["editor_layers"],
            mark_saved=False,
        )
        restored_cells = [
            cell for layer in editor.editor_layers for cell in layer.to_cells()
        ]
        self.assertEqual(len(restored_cells), len(cells))
        editor.state.load_mobs(restored["mobs"])
        editor.state.load_spawns(restored["spawns"])
        self.assertEqual(editor.state.to_mobs(), draft["mobs"])
        self.assertEqual(editor.state.to_spawns(), draft["spawns"])

    def test_unknown_gid_is_reported_without_failing_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = export_draft_to_tmx(
                self._draft(),
                root / "unknown.tmx",
                tilesets_dir=root / "tilesets",
            )
            tree = ET.parse(path)
            data = tree.find(".//layer/data")
            values = [value.strip() for value in (data.text or "").split(",")]
            values = [value for value in values if value]
            values[0] = "999999"
            data.text = ",".join(values)
            tree.write(path, encoding="utf-8", xml_declaration=True)
            result = import_tmx(path)

        self.assertTrue(any("unknown tile ids" in item for item in result.warnings))
        self.assertEqual(result.draft["mobs"], [{"kind": "imp_vanilla", "x": 2, "y": 1}])

    def test_flat_tiled_object_group_uses_catalog_editor_layer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = export_draft_to_tmx(
                self._draft(),
                root / "flat_object.tmx",
                tilesets_dir=root / "tilesets",
            )
            tree = ET.parse(path)
            map_root = tree.getroot()
            object_group = next(
                group.find("objectgroup")
                for group in map_root.findall("group")
                if group.find("objectgroup") is not None
                and group.find("objectgroup").get("name") == "objects"
            )
            next(
                group for group in map_root.findall("group")
                if object_group in list(group)
            ).remove(object_group)
            map_root.append(object_group)
            tree.write(path, encoding="utf-8", xml_declaration=True)
            result = import_tmx(path)

        restored = result.draft["editor_layers"][5]
        self.assertEqual(
            [(cell["key"], cell["layer"], cell["x"], cell["y"]) for cell in restored],
            [(self.object_key, "object", 3, 2)],
        )

    def _shared_tmx(self, stem, draft):
        """Exports a map once per test class: an export rewrites the biome tilesets, which is slow."""
        path = self.shared_root / f"{stem}.tmx"
        if not path.exists():
            export_draft_to_tmx(draft, path, tilesets_dir=self.shared_root / "tilesets")
        return path

    def _tmx_copy(self, source, stem):
        # A copy stays next to the original, so its relative tileset paths remain valid.
        target = source.with_name(f"{stem}.tmx")
        shutil.copyfile(source, target)
        return target

    def _edit_tmx(self, path, edit):
        tree = ET.parse(path)
        edit(tree.getroot())
        tree.write(path, encoding="utf-8", xml_declaration=True)

    def _drop_map_properties(self, path, names):
        def edit(root):
            properties = root.find("properties")
            for prop in list(properties):
                if prop.get("name") in names:
                    properties.remove(prop)

        self._edit_tmx(path, edit)

    def test_import_saves_a_draft_the_map_editor_can_open(self):
        draft = self._draft()
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "map_drafts"
            result = tiled_cli.import_to_drafts(self._shared_tmx("base", draft), folder)
            saved = result.draft
            self.assertTrue(result.created)
            self.assertEqual(result.warnings, [])
            self.assertTrue((folder / f"{saved['id']}.json").is_file())
            self.assertEqual(
                [(item["id"], item["name"]) for item in map_drafts.list_drafts(folder)],
                [(saved["id"], "TMX round trip")],
            )
            loaded = map_drafts.load_draft(saved["id"], folder)
            scene = MapEditorScene(None, list(self.catalog.values()), lambda: False)
            with mock.patch.object(map_drafts, "load_draft", return_value=loaded):
                scene._open_draft(saved["id"])

        self.assertTrue(scene.has_map)
        self.assertEqual(scene.draft_id, saved["id"])
        self.assertEqual(scene.state.name, "TMX round trip")
        self.assertEqual((scene.state.map_w, scene.state.map_h), (5, 4))
        self.assertEqual(scene.mode, "tower")
        self.assertTrue(scene.state.harvest_enabled)
        self.assertEqual(scene.state.to_mobs(), draft["mobs"])
        self.assertEqual(scene.state.to_spawns(), draft["spawns"])
        self.assertEqual(
            {
                (cell["key"], cell["layer"], cell["x"], cell["y"])
                for layer in scene.editor_layers
                for cell in layer.to_cells()
            },
            {
                (self.ground_key, "elevation", 1, 2),
                (self.object_key, "object", 3, 2),
            },
        )

    def test_reimport_updates_the_draft_and_keeps_game_only_data(self):
        draft = self._draft()
        redrawn = dict(
            draft,
            map_w=6,
            mobs=[],
            spawns=[],
            crystals={},
            harvest_enabled=False,
        )
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "map_drafts"
            first = tiled_cli.import_to_drafts(self._shared_tmx("base", draft), folder).draft
            map_drafts.mark_published(first["id"], "world-1", "Мир", folder)
            mobs = first["mobs"] + [{"kind": "imp_vanilla", "x": 0, "y": 0}]
            spawns = first["spawns"] + [{"x": 1, "y": 1}]
            map_drafts.save_draft(
                first["name"], first["cells"], first["map_w"], first["map_h"], first["id"],
                folder=folder, mode="deck", mobs=mobs, spawns=spawns,
                crystals={"red": {"count": 5}}, harvest_enabled=True,
                editor_layers=first["editor_layers"],
            )
            second_tmx = self._tmx_copy(self._shared_tmx("redrawn", redrawn), "redrawn_without_game_data")
            self._drop_map_properties(second_tmx, {"game_mode", "crystals", "harvest_enabled"})
            result = tiled_cli.import_to_drafts(second_tmx, folder)
            drafts = map_drafts.list_drafts(folder)
            loaded = map_drafts.load_draft(first["id"], folder)

        self.assertFalse(result.created)
        self.assertEqual(result.kept, ("mobs", "spawns", "crystals"))
        self.assertEqual([item["id"] for item in drafts], [first["id"]])
        self.assertEqual(loaded["map_w"], 6)
        self.assertEqual(loaded["mode"], "deck")
        self.assertEqual(loaded["mobs"], mobs)
        self.assertEqual(loaded["spawns"], spawns)
        self.assertEqual(loaded["crystals"], {"red": {"count": 5}})
        self.assertTrue(loaded["harvest_enabled"])
        self.assertEqual(loaded["published"], [{"world_id": "world-1", "world_name": "Мир"}])

    def test_reimport_takes_mobs_from_a_tmx_that_has_a_mobs_layer(self):
        draft = self._draft()

        def clear_mobs(root):
            for group in root.iter("objectgroup"):
                if group.get("name") == "mobs":
                    for mob in group.findall("object"):
                        group.remove(mob)

        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "map_drafts"
            base = self._shared_tmx("base", draft)
            first = tiled_cli.import_to_drafts(base, folder).draft
            cleared = self._tmx_copy(base, "mobs_cleared")
            self._edit_tmx(cleared, clear_mobs)
            result = tiled_cli.import_to_drafts(cleared, folder)
            loaded = map_drafts.load_draft(first["id"], folder)

        self.assertEqual(first["mobs"], draft["mobs"])
        self.assertEqual(loaded["mobs"], [])
        self.assertEqual(loaded["spawns"], draft["spawns"])
        self.assertEqual(result.kept, ())

    def test_invalid_game_properties_are_reported_and_not_explicit(self):
        def break_properties(root):
            for prop in root.find("properties"):
                if prop.get("name") == "crystals":
                    prop.set("value", "[1, 2]")
                elif prop.get("name") == "game_mode":
                    prop.set("value", "arena")
                elif prop.get("name") == "harvest_enabled":
                    prop.set("type", "string")
                    prop.set("value", "false")

        tmx = self._tmx_copy(self._shared_tmx("base", self._draft()), "broken_properties")
        self._edit_tmx(tmx, break_properties)
        result = import_tmx(tmx)

        self.assertEqual(result.explicit, {"mobs", "spawns", "harvest_enabled"})
        self.assertEqual(result.draft["mode"], "tower")
        self.assertEqual(result.draft["crystals"], {})
        self.assertFalse(result.draft["harvest_enabled"])
        self.assertTrue(any("unknown game mode" in item for item in result.warnings))
        self.assertTrue(any("invalid crystals" in item for item in result.warnings))

    def test_import_command_creates_then_updates_and_reports_errors(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "map_drafts"
            tmx = self._shared_tmx("base", self._draft())
            arguments = ["import", str(tmx), "--folder", str(folder)]
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                created = tiled_cli.main([*arguments, "--name", "Моя карта"])
                updated = tiled_cli.main([*arguments, "--name", "Моя карта"])
                too_long = tiled_cli.main([*arguments, "--name", "x" * 65])
            names = [item["name"] for item in map_drafts.list_drafts(folder)]

        self.assertEqual((created, updated, too_long), (0, 0, 1))
        self.assertEqual(names, ["Моя карта"])
        self.assertIn("Created draft: Моя карта", out.getvalue())
        self.assertIn("Updated draft: Моя карта", out.getvalue())
        self.assertIn("Ctrl+L", out.getvalue())
        self.assertIn("1 до 64", err.getvalue())

    def test_export_finds_a_draft_by_name_id_or_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / "map_drafts"
            saved = map_drafts.save_draft("Лес", [], 4, 4, folder=folder)
            by_name = tiled_cli.load_draft_for_export("Лес", folder)
            by_id = tiled_cli.load_draft_for_export(saved["id"], folder)
            by_file = tiled_cli.load_draft_for_export(folder / f"{saved['id']}.json", folder)
            with self.assertRaises(ValueError):
                tiled_cli.load_draft_for_export("Нет такого", folder)

        self.assertEqual(by_name["id"], saved["id"])
        self.assertEqual(by_id["id"], saved["id"])
        self.assertEqual(by_file["id"], saved["id"])


if __name__ == "__main__":
    unittest.main()
