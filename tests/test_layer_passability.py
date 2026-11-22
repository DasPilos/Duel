import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from server import map_editor


def _terrain(impassable, animals=()):
    return {"impassable": frozenset(impassable), "animals": list(animals)}


class LayerPassabilityTests(unittest.TestCase):
    def test_default_flags_by_layer_type(self):
        layers = [
            {"id": 1, "type": "tile", "cells": [{"x": 0, "y": 0}]},
            {"id": 2, "type": "object", "cells": [{"x": 1, "y": 0}]},
            {"id": 3, "type": "animal", "cells": [{"x": 2, "y": 0}]},
        ]
        blocked, covered = map_editor.layer_passability(layers, 10, 10)
        self.assertEqual(blocked, {(1, 0)})
        self.assertEqual(covered, {(0, 0), (1, 0), (2, 0)})

    def test_top_visible_layer_decides(self):
        layers = [
            {"id": 1, "type": "tile", "passable": False, "cells": [{"x": 1, "y": 1}]},
            {"id": 2, "type": "tile", "passable": True, "cells": [{"x": 1, "y": 1}]},
            {"id": 3, "type": "tile", "passable": False, "cells": [{"x": 2, "y": 2}]},
        ]
        blocked, _ = map_editor.layer_passability(layers, 10, 10)
        self.assertEqual(blocked, {(2, 2)})

    def test_hidden_layer_and_hidden_group_are_ignored(self):
        layers = [
            {"id": 1, "type": "group", "visible": False, "cells": []},
            {"id": 2, "type": "tile", "passable": False, "parent_id": 1, "cells": [{"x": 0, "y": 0}]},
            {"id": 3, "type": "object", "visible": False, "cells": [{"x": 1, "y": 0}]},
        ]
        blocked, covered = map_editor.layer_passability(layers, 10, 10)
        self.assertEqual(blocked, set())
        self.assertEqual(covered, set())

    def test_secret_passage_on_impassable_object_layer(self):
        # Непроходимый слой объектов, поверх него проходимый слой тайлов: клетка открыта (секретный проход).
        layers = [
            {"id": 1, "type": "object", "passable": False, "cells": [{"x": 4, "y": 4}]},
            {"id": 2, "type": "tile", "passable": True, "cells": [{"x": 4, "y": 4}]},
        ]
        blocked, _ = map_editor.layer_passability(layers, 10, 10)
        self.assertEqual(blocked, set())

    def test_malformed_and_out_of_bounds_cells_are_skipped(self):
        layers = [
            "not a layer",
            {"id": 1, "type": "tile", "passable": False, "cells": [
                {"x": 99, "y": 0}, {"x": "a", "y": 0}, "junk", {"y": 1}, {"x": 1, "y": 1},
            ]},
        ]
        blocked, covered = map_editor.layer_passability(layers, 10, 10)
        self.assertEqual(blocked, {(1, 1)})
        self.assertEqual(covered, {(1, 1)})

    def test_apply_overrides_only_covered_cells(self):
        terrain = _terrain({(1, 1), (5, 5)})
        layers = [{"id": 1, "type": "tile", "passable": True, "cells": [{"x": 1, "y": 1}]}]
        result = map_editor.apply_layer_passability(terrain, layers, 10, 10)
        self.assertEqual(result["impassable"], {(5, 5)})

    def test_apply_keeps_animal_tiles_free(self):
        terrain = _terrain(set(), animals=[{"x": 3, "y": 3}])
        layers = [{"id": 1, "type": "animal", "passable": False, "cells": [{"x": 3, "y": 3}]}]
        result = map_editor.apply_layer_passability(terrain, layers, 10, 10)
        self.assertEqual(result["impassable"], frozenset())

    def test_apply_without_layers_changes_nothing(self):
        terrain = _terrain({(2, 2)})
        self.assertIs(map_editor.apply_layer_passability(terrain, [], 10, 10), terrain)
        self.assertIsNone(map_editor.apply_layer_passability(None, [], 10, 10))

    def test_passable_bridge_is_not_blocked_by_water(self):
        terrain = {"impassable": frozenset({(1, 1)}), "animals": [], "water": frozenset({(1, 1), (5, 5)}),
                   "forest": frozenset(), "dry": frozenset(), "mountain": frozenset()}
        layers = [
            {"id": 1, "type": "tile", "passable": False, "cells": [{"x": 1, "y": 1}, {"x": 5, "y": 5}]},
            {"id": 2, "type": "tile", "passable": True, "cells": [{"x": 1, "y": 1}]},
        ]
        result = map_editor.apply_layer_passability(terrain, layers, 10, 10)
        self.assertNotIn((1, 1), result["impassable"])
        self.assertNotIn((1, 1), result["water"])
        self.assertIn((5, 5), result["water"])
        self.assertIn((5, 5), result["impassable"])

    def test_load_published_map_uses_saved_layers(self):
        database = MagicMock()
        database.published_map.return_value = {"map_w": 10, "map_h": 10, "saved_id": 7}
        database.map_live_cells.return_value = []
        database.map_catalog.return_value = []
        database.get_saved_map.return_value = {
            "editor_layers": [{"id": 1, "type": "tile", "passable": True, "cells": [{"x": 1, "y": 1}]}],
        }
        terrain = _terrain({(1, 1)})
        with unittest.mock.patch.object(map_editor, "terrain_from_cells", return_value=terrain), \
                unittest.mock.patch.object(map_editor, "load_partial_masks", return_value={}):
            loaded, published = map_editor.load_published_map(database)
        self.assertEqual(loaded["impassable"], frozenset())
        self.assertEqual(published["saved_id"], 7)
        database.get_saved_map.assert_called_once_with(7)

    def test_load_published_map_survives_missing_saved_map(self):
        database = MagicMock()
        database.published_map.return_value = {"map_w": 10, "map_h": 10, "saved_id": 9}
        database.get_saved_map.side_effect = ValueError("Карта на сервере не найдена")
        terrain = _terrain({(2, 2)})
        with unittest.mock.patch.object(map_editor, "terrain_from_cells", return_value=terrain), \
                unittest.mock.patch.object(map_editor, "load_partial_masks", return_value={}):
            loaded, _ = map_editor.load_published_map(database)
        self.assertEqual(loaded["impassable"], {(2, 2)})


if __name__ == "__main__":
    unittest.main()
