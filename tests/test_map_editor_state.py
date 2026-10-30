import unittest

from client.map_editor_state import MapEditorState


CATALOG = [
    {"item_key": "grass_1", "kind": "ground", "footprint_w": 1, "footprint_h": 1},
    {"item_key": "rock_01", "kind": "object", "footprint_w": 1, "footprint_h": 1},
    {"item_key": "log_1", "kind": "object", "footprint_w": 2, "footprint_h": 1},
]


def make_state(cells=(), map_w=10, map_h=10):
    return MapEditorState(CATALOG, list(cells), map_w, map_h)


class MapEditorStateTests(unittest.TestCase):
    def test_loads_saved_cells_and_skips_unknown_keys(self):
        state = make_state([
            {"layer": "ground", "x": 1, "y": 2, "key": "grass_1"},
            {"layer": "object", "x": 3, "y": 3, "key": "rock_01"},
            {"layer": "object", "x": 4, "y": 4, "key": "gone"},
        ])
        self.assertEqual(state.ground, {(1, 2): "grass_1"})
        self.assertEqual(state.objects, {(3, 3): "rock_01"})
        self.assertFalse(state.dirty)

    def test_place_ground_replaces_tile_and_marks_dirty(self):
        state = make_state()
        self.assertIsNone(state.place("grass_1", 2, 2))
        self.assertTrue(state.dirty)
        self.assertEqual(state.ground, {(2, 2): "grass_1"})

    def test_place_object_outside_map_is_refused(self):
        state = make_state(map_w=10, map_h=10)
        self.assertIsNotNone(state.place("log_1", 9, 0))
        self.assertEqual(state.objects, {})
        self.assertFalse(state.dirty)

    def test_wide_object_replaces_overlapping_objects(self):
        state = make_state([{"layer": "object", "x": 4, "y": 4, "key": "rock_01"}])
        self.assertIsNone(state.place("log_1", 3, 4))
        self.assertEqual(state.objects, {(3, 4): "log_1"})
        self.assertEqual(state.cover, {(3, 4): (3, 4), (4, 4): (3, 4)})

    def test_erase_removes_object_before_ground(self):
        state = make_state([
            {"layer": "ground", "x": 1, "y": 1, "key": "grass_1"},
            {"layer": "object", "x": 1, "y": 1, "key": "rock_01"},
        ])
        self.assertTrue(state.erase(1, 1))
        self.assertEqual(state.objects, {})
        self.assertEqual(state.ground, {(1, 1): "grass_1"})
        self.assertTrue(state.erase(1, 1))
        self.assertEqual(state.ground, {})
        self.assertFalse(state.erase(1, 1))

    def test_erase_wide_object_from_any_covered_tile(self):
        state = make_state([{"layer": "object", "x": 2, "y": 2, "key": "log_1"}])
        self.assertTrue(state.erase(3, 2))
        self.assertEqual(state.objects, {})
        self.assertEqual(state.cover, {})

    def test_to_cells_is_sorted_and_matches_server_shape(self):
        state = make_state([
            {"layer": "object", "x": 5, "y": 1, "key": "rock_01"},
            {"layer": "ground", "x": 2, "y": 0, "key": "grass_1"},
            {"layer": "ground", "x": 1, "y": 0, "key": "grass_1"},
        ])
        self.assertEqual(state.to_cells(), [
            {"layer": "ground", "x": 1, "y": 0, "key": "grass_1"},
            {"layer": "ground", "x": 2, "y": 0, "key": "grass_1"},
            {"layer": "object", "x": 5, "y": 1, "key": "rock_01"},
        ])
    def test_fill_covers_connected_region_of_same_ground(self):
        state = make_state([{"layer": "ground", "x": 0, "y": 0, "key": "grass_1"}], map_w=3, map_h=3)
        state.ground[(1, 0)] = "grass_1"
        self.assertEqual(state.fill("grass_1", 0, 0), 0)
        self.assertEqual(state.fill("log_1", 0, 0), 0)
        self.assertEqual(state.fill("grass_1", 2, 2), len(state.ground) - 2)
        self.assertEqual(len(state.ground), 9)

    def test_fill_stops_at_other_ground_tiles(self):
        state = make_state([{"layer": "ground", "x": 1, "y": 0, "key": "grass_1"}], map_w=3, map_h=1)
        self.assertEqual(state.fill("grass_1", 0, 0), 1)
        self.assertEqual(state.ground, {(0, 0): "grass_1", (1, 0): "grass_1"})

    def test_paint_square_brush_stays_on_map(self):
        state = make_state(map_w=4, map_h=4)
        state.paint("grass_1", 0, 0, size=3)
        self.assertEqual(len(state.ground), 4)
        self.assertEqual(state.paint("log_1", 1, 1, size=3), None)
        self.assertEqual(state.objects, {(1, 1): "log_1"})

    def test_undo_and_redo_restore_one_action(self):
        state = make_state()
        state.begin_action()
        state.place("grass_1", 1, 1)
        self.assertTrue(state.end_action())
        state.begin_action()
        state.place("rock_01", 2, 2)
        state.end_action()
        self.assertTrue(state.undo())
        self.assertEqual(state.objects, {})
        self.assertEqual(state.ground, {(1, 1): "grass_1"})
        self.assertTrue(state.redo())
        self.assertEqual(state.objects, {(2, 2): "rock_01"})
        self.assertFalse(state.redo())

    def test_empty_action_is_not_recorded(self):
        state = make_state([{"layer": "ground", "x": 1, "y": 1, "key": "grass_1"}])
        state.begin_action()
        state.place("grass_1", 1, 1)
        self.assertFalse(state.end_action())
        self.assertEqual(state.undo_stack, [])

    def test_new_action_clears_redo_history(self):
        state = make_state()
        state.begin_action()
        state.place("grass_1", 1, 1)
        state.end_action()
        state.undo()
        state.begin_action()
        state.place("grass_1", 2, 2)
        state.end_action()
        self.assertFalse(state.redo())

    def test_move_selection_moves_ground_and_objects_together(self):
        state = make_state([
            {"layer": "ground", "x": 1, "y": 1, "key": "grass_1"},
            {"layer": "object", "x": 2, "y": 1, "key": "rock_01"},
            {"layer": "ground", "x": 8, "y": 8, "key": "grass_1"},
        ])
        state.select(0, 0, 3, 3)
        self.assertIsNone(state.move_selection(2, 3))
        self.assertEqual(state.ground, {(3, 4): "grass_1", (8, 8): "grass_1"})
        self.assertEqual(state.objects, {(4, 4): "rock_01"})
        self.assertEqual(state.selection, (2, 3, 5, 6))

    def test_move_selection_out_of_map_changes_nothing(self):
        state = make_state([{"layer": "object", "x": 9, "y": 9, "key": "rock_01"}])
        state.select(9, 9, 9, 9)
        before = state.to_cells()
        self.assertIsNotNone(state.move_selection(1, 0))
        self.assertEqual(state.to_cells(), before)

    def test_move_selection_overwrites_objects_outside_selection(self):
        state = make_state([
            {"layer": "object", "x": 1, "y": 1, "key": "rock_01"},
            {"layer": "object", "x": 4, "y": 4, "key": "rock_01"},
        ])
        state.select(0, 0, 1, 1)
        self.assertIsNone(state.move_selection(3, 3))
        self.assertEqual(state.objects, {(4, 4): "rock_01"})

    def test_delete_selection_removes_entries_inside_only(self):
        state = make_state([
            {"layer": "ground", "x": 1, "y": 1, "key": "grass_1"},
            {"layer": "ground", "x": 5, "y": 5, "key": "grass_1"},
            {"layer": "object", "x": 2, "y": 2, "key": "rock_01"},
        ])
        state.select(0, 0, 3, 3)
        self.assertEqual(state.delete_selection(), 2)
        self.assertEqual(state.ground, {(5, 5): "grass_1"})
        self.assertEqual(state.objects, {})

    def test_clear_resets_map_and_marks_dirty(self):
        state = make_state([{"layer": "ground", "x": 1, "y": 1, "key": "grass_1"}])
        state.mark_saved()
        state.clear()
        self.assertEqual(state.ground, {})
        self.assertTrue(state.dirty)


OVERLAY_KEY = "ml_r00_c01"
SOLID_KEY = "ml_r04_c05"


def make_overlay_state(cells=()):
    catalog = CATALOG + [
        {"item_key": OVERLAY_KEY, "kind": "ground", "footprint_w": 1, "footprint_h": 1},
        {"item_key": SOLID_KEY, "kind": "ground", "footprint_w": 1, "footprint_h": 1},
    ]
    return MapEditorState(catalog, list(cells), 10, 10)


class OverlayLayerTests(unittest.TestCase):
    def test_transparent_tile_goes_over_ground_and_keeps_it(self):
        state = make_overlay_state()
        state.place("grass_1", 2, 2)
        state.place(OVERLAY_KEY, 2, 2)
        self.assertEqual(state.ground, {(2, 2): "grass_1"})
        self.assertEqual(state.overlay, {(2, 2): OVERLAY_KEY})

    def test_solid_tile_clears_overlay(self):
        state = make_overlay_state()
        state.place(OVERLAY_KEY, 2, 2)
        state.place(SOLID_KEY, 2, 2)
        self.assertEqual(state.overlay, {})
        self.assertEqual(state.ground, {(2, 2): SOLID_KEY})

    def test_erase_removes_overlay_before_ground(self):
        state = make_overlay_state()
        state.place("grass_1", 1, 1)
        state.place(OVERLAY_KEY, 1, 1)
        self.assertTrue(state.erase(1, 1))
        self.assertEqual((state.overlay, state.ground), ({}, {(1, 1): "grass_1"}))
        self.assertTrue(state.erase(1, 1))
        self.assertEqual(state.ground, {})

    def test_cells_roundtrip_and_undo_include_overlay(self):
        state = make_overlay_state([{"layer": "overlay", "x": 3, "y": 3, "key": OVERLAY_KEY}])
        self.assertEqual(state.overlay, {(3, 3): OVERLAY_KEY})
        self.assertEqual(state.to_cells(), [{"layer": "overlay", "x": 3, "y": 3, "key": OVERLAY_KEY}])
        state.begin_action()
        state.erase(3, 3)
        state.end_action()
        self.assertEqual(state.overlay, {})
        state.undo()
        self.assertEqual(state.overlay, {(3, 3): OVERLAY_KEY})

    def test_move_and_delete_selection_carry_overlay(self):
        state = make_overlay_state([{"layer": "overlay", "x": 1, "y": 1, "key": OVERLAY_KEY}])
        state.select(0, 0, 2, 2)
        self.assertIsNone(state.move_selection(3, 0))
        self.assertEqual(state.overlay, {(4, 1): OVERLAY_KEY})
        self.assertEqual(state.delete_selection(), 1)
        self.assertEqual(state.overlay, {})


class StampTests(unittest.TestCase):
    def _state(self):
        return make_overlay_state([
            {"layer": "ground", "x": 1, "y": 1, "key": "grass_1"},
            {"layer": "overlay", "x": 2, "y": 1, "key": OVERLAY_KEY},
            {"layer": "object", "x": 2, "y": 2, "key": "rock_01"},
            {"layer": "ground", "x": 8, "y": 8, "key": "grass_1"},
        ])

    def test_copy_keeps_layers_and_offsets_from_selection_corner(self):
        state = self._state()
        state.select(1, 1, 3, 3)
        stamp = state.copy_selection()
        self.assertEqual((stamp["w"], stamp["h"]), (3, 3))
        self.assertEqual(stamp["ground"], [(0, 0, "grass_1")])
        self.assertEqual(stamp["overlay"], [(1, 0, OVERLAY_KEY)])
        self.assertEqual(stamp["objects"], [(1, 1, "rock_01")])

    def test_copy_without_selection_or_content_is_none(self):
        state = self._state()
        self.assertIsNone(state.copy_selection())
        state.select(5, 5, 6, 6)
        self.assertIsNone(state.copy_selection())

    def test_paste_places_all_layers_and_selects_pasted_area(self):
        state = self._state()
        state.select(1, 1, 3, 3)
        stamp = state.copy_selection()
        self.assertIsNone(state.paste(stamp, 5, 5))
        self.assertEqual(state.ground[(5, 5)], "grass_1")
        self.assertEqual(state.overlay[(6, 5)], OVERLAY_KEY)
        self.assertEqual(state.objects[(6, 6)], "rock_01")
        self.assertEqual(state.selection, (5, 5, 7, 7))
        self.assertTrue(state.dirty)

    def test_paste_keeps_map_under_empty_stamp_cells_and_is_one_undo_step(self):
        state = self._state()
        stamp = {"w": 2, "h": 1, "ground": [(1, 0, SOLID_KEY)], "overlay": [], "objects": []}
        state.begin_action()
        state.paste(stamp, 7, 8)
        state.end_action()
        self.assertEqual(state.ground[(8, 8)], SOLID_KEY)
        self.assertNotIn((7, 8), state.ground)
        state.undo()
        self.assertEqual(state.ground[(8, 8)], "grass_1")

    def test_paste_solid_ground_clears_overlay_and_object_replaces_object(self):
        state = self._state()
        stamp = {"w": 1, "h": 1, "ground": [(0, 0, SOLID_KEY)], "overlay": [], "objects": [(0, 1, "rock_01")]}
        state.paste(stamp, 2, 1)
        self.assertNotIn((2, 1), state.overlay)
        self.assertEqual(state.ground[(2, 1)], SOLID_KEY)
        self.assertEqual(state.objects, {(2, 2): "rock_01"})

    def test_paste_outside_map_is_refused_without_changes(self):
        state = self._state()
        stamp = {"w": 3, "h": 1, "ground": [(0, 0, SOLID_KEY), (2, 0, SOLID_KEY)], "overlay": [], "objects": []}
        before = dict(state.ground)
        self.assertIsNotNone(state.paste(stamp, 8, 0))
        self.assertEqual(state.ground, before)

    def test_make_stamp_routes_items_to_layers(self):
        state = make_overlay_state()
        stamp = state.make_stamp([(0, 0, "grass_1"), (1, 0, OVERLAY_KEY), (1, 1, "rock_01"), (3, 3, "gone")])
        self.assertEqual((stamp["w"], stamp["h"]), (2, 2))
        self.assertEqual(stamp["ground"], [(0, 0, "grass_1")])
        self.assertEqual(stamp["overlay"], [(1, 0, OVERLAY_KEY)])
        self.assertEqual(stamp["objects"], [(1, 1, "rock_01")])
        self.assertIsNone(state.make_stamp([(0, 0, "gone")]))


if __name__ == "__main__":
    unittest.main()
