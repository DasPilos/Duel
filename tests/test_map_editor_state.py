import unittest
from unittest import mock

from client.map_editor_state import MapEditorState
from core.map_catalog import (
    catalog_definitions, overlay_keys, palette_group_layers, palette_groups, palette_role_keys, road_keys,
    terrain_layer_keys,
)


CATALOG = [
    {"item_key": "grass_1", "kind": "ground", "footprint_w": 1, "footprint_h": 1},
    {"item_key": "rock_01", "kind": "object", "footprint_w": 1, "footprint_h": 1},
    {"item_key": "log_1", "kind": "object", "footprint_w": 2, "footprint_h": 1},
]


def make_state(cells=(), map_w=10, map_h=10):
    return MapEditorState(CATALOG, list(cells), map_w, map_h)


def make_water_state(cells=()):
    catalog = CATALOG + [
        {"item_key": "water_1", "kind": "ground", "category": "water", "footprint_w": 1, "footprint_h": 1},
        {"item_key": "grass_2", "kind": "ground", "category": "grass", "footprint_w": 1, "footprint_h": 1},
        {"item_key": "plank_1", "kind": "ground", "category": "floor", "footprint_w": 1, "footprint_h": 1},
        {"item_key": "water_effect_1", "kind": "ground", "category": "water", "footprint_w": 1, "footprint_h": 1},
        {"item_key": "animal_duck_water", "kind": "object", "category": "animal",
         "footprint_w": 1, "footprint_h": 1},
    ]
    return MapEditorState(catalog, list(cells), 10, 10)


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

    def test_waterfowl_requires_a_water_tile(self):
        state = make_water_state()
        error = state.place("animal_duck_water", 2, 2)
        self.assertEqual(error, "Водных животных можно размещать только на тайлах воды")
        self.assertEqual(state.objects, {})
        self.assertFalse(state.dirty)

        self.assertIsNone(state.place("water_1", 2, 2))
        self.assertIsNone(state.place("animal_duck_water", 2, 2))
        self.assertEqual(state.objects, {(2, 2): "animal_duck_water"})

    def test_waterfowl_cannot_replace_the_water_under_it(self):
        state = make_water_state([
            {"layer": "ground", "x": 2, "y": 2, "key": "water_1"},
            {"layer": "object", "x": 2, "y": 2, "key": "animal_duck_water"},
        ])
        self.assertEqual(
            state.place("grass_2", 2, 2),
            "Водных животных можно размещать только на тайлах воды",
        )
        self.assertEqual(state.ground[(2, 2)], "water_1")

    def test_water_effect_requires_water_and_preserves_its_water_base(self):
        state = make_water_state()
        message = "Водные эффекты можно размещать только на тайлах воды"
        self.assertEqual(state.place("water_effect_1", 2, 2, layer="overlay"), message)
        self.assertEqual(state.overlay, {})
        self.assertFalse(state.dirty)

        self.assertIsNone(state.place("water_1", 2, 2))
        self.assertIsNone(state.place("water_effect_1", 2, 2, layer="overlay"))
        self.assertEqual(state.place("grass_2", 2, 2), message)
        self.assertEqual(state.ground[(2, 2)], "water_1")
        self.assertEqual(state.overlay[(2, 2)], "water_effect_1")

    def test_independent_editor_layers_allow_water_effects_without_local_water(self):
        state = make_water_state()
        state.allow_cross_layer_placements = True

        self.assertIsNone(state.place("water_effect_1", 2, 2, layer="overlay"))
        self.assertEqual(state.overlay, {(2, 2): "water_effect_1"})

    def test_artist_layer_replaces_cells_across_internal_storage_layers(self):
        state = make_water_state()
        state.allow_cross_layer_placements = True
        state.replace_other_layers = True
        self.assertIsNone(state.place("grass_2", 2, 2, layer="ground"))
        self.assertIsNone(state.place("water_effect_1", 2, 2, layer="overlay"))

        self.assertEqual(state.ground, {})
        self.assertEqual(state.overlay, {(2, 2): "water_effect_1"})

        self.assertIsNone(state.place("rock_01", 2, 2))
        self.assertIsNone(state.place("grass_2", 2, 2, layer="ground"))
        self.assertEqual(state.objects, {})
        self.assertEqual(state.ground, {(2, 2): "grass_2"})

    def test_artist_layer_move_replaces_other_storage_at_destination(self):
        state = make_water_state()
        state.allow_cross_layer_placements = True
        state.replace_other_layers = True
        self.assertIsNone(state.place("grass_2", 1, 1, layer="ground"))
        self.assertIsNone(state.place("water_effect_1", 2, 1, layer="overlay"))
        state.select(1, 1, 1, 1)

        self.assertIsNone(state.move_selection(1, 0))

        self.assertEqual(state.ground, {(2, 1): "grass_2"})
        self.assertEqual(state.overlay, {})

    def test_water_effect_stamp_validates_every_tile_before_pasting(self):
        state = make_water_state()
        stamp = state.make_stamp([
            (0, 0, "water_effect_1", "overlay"),
            (1, 0, "water_effect_1", "overlay"),
        ])
        self.assertIsNone(state.place("water_1", 2, 2))
        message = "Водные эффекты можно размещать только на тайлах воды"
        self.assertEqual(state.paste(stamp, 2, 2), message)
        self.assertEqual(state.overlay, {})

        self.assertIsNone(state.place("water_1", 3, 2))
        self.assertIsNone(state.paste(stamp, 2, 2))
        self.assertEqual(state.overlay, {
            (2, 2): "water_effect_1",
            (3, 2): "water_effect_1",
        })

    def test_water_effect_brush_is_atomic_across_wet_and_dry_tiles(self):
        state = make_water_state()
        message = "Водные эффекты можно размещать только на тайлах воды"
        self.assertIsNone(state.place("water_1", 1, 1))
        self.assertEqual(
            state.paint("water_effect_1", 2, 2, size=3, layer="overlay"),
            message,
        )
        self.assertEqual(state.overlay, {})
        for x in range(1, 4):
            for y in range(1, 4):
                self.assertIsNone(state.place("water_1", x, y))
        self.assertIsNone(state.paint("water_effect_1", 2, 2, size=3, layer="overlay"))
        self.assertEqual(len(state.overlay), 9)

    def test_existing_water_effects_do_not_block_edits_on_other_tiles(self):
        state = make_water_state([{
            "layer": "overlay",
            "x": 1,
            "y": 1,
            "key": "water_effect_1",
        }])
        self.assertIsNone(state.place("grass_2", 4, 4))
        self.assertEqual(state.overlay[(1, 1)], "water_effect_1")

    def test_waterfowl_stamp_requires_water_and_accepts_water_in_same_stamp(self):
        state = make_water_state()
        stamp = state.make_stamp([(0, 0, "animal_duck_water")])
        self.assertEqual(
            state.paste(stamp, 2, 2),
            "Водных животных можно размещать только на тайлах воды",
        )
        water_stamp = state.make_stamp([(0, 0, "water_1"), (0, 0, "animal_duck_water")])
        self.assertIsNone(state.paste(water_stamp, 2, 2))
        self.assertEqual(state.objects, {(2, 2): "animal_duck_water"})
        self.assertEqual(state.ground, {(2, 2): "water_1"})

    def test_waterfowl_selection_cannot_move_onto_infrastructure(self):
        state = make_water_state([
            {"layer": "ground", "x": 2, "y": 2, "key": "water_1"},
            {"layer": "infra", "x": 3, "y": 2, "key": "plank_1"},
            {"layer": "object", "x": 2, "y": 2, "key": "animal_duck_water"},
        ])
        state.select(2, 2, 2, 2)
        self.assertEqual(
            state.move_selection(1, 0),
            "Водных животных можно размещать только на тайлах воды",
        )
        self.assertEqual(state.objects, {(2, 2): "animal_duck_water"})
        self.assertEqual(state.ground, {(2, 2): "water_1"})
        state.infra.clear()
        state.select(2, 2, 2, 2)
        self.assertIsNone(state.move_selection(1, 0))
        self.assertEqual(state.objects, {(3, 2): "animal_duck_water"})
        self.assertEqual(state.ground, {(3, 2): "water_1"})

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

    def test_layer_erase_preserves_content_below_it(self):
        state = make_water_state([
            {"layer": "ground", "x": 1, "y": 1, "key": "water_1"},
            {"layer": "overlay", "x": 1, "y": 1, "key": "water_effect_1"},
            {"layer": "elevation", "x": 1, "y": 1, "key": "grass_2"},
        ])

        self.assertTrue(state.erase(1, 1, layer="elevation"))

        self.assertNotIn((1, 1), state.elevation)
        self.assertEqual(state.ground[(1, 1)], "water_1")
        self.assertEqual(state.overlay[(1, 1)], "water_effect_1")

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
    state = MapEditorState(catalog, list(cells), 10, 10)
    state.overlay_keys = frozenset({OVERLAY_KEY})
    return state


class OverlayLayerTests(unittest.TestCase):
    def test_transparent_tile_goes_over_ground_and_keeps_it(self):
        state = make_overlay_state()
        state.place("grass_1", 2, 2)
        state.place(OVERLAY_KEY, 2, 2)
        self.assertEqual(state.ground, {(2, 2): "grass_1"})
        self.assertEqual(state.overlay, {(2, 2): OVERLAY_KEY})

    def test_solid_tile_keeps_overlay(self):
        state = make_overlay_state()
        state.place(OVERLAY_KEY, 2, 2)
        state.place(SOLID_KEY, 2, 2)
        self.assertEqual(state.overlay, {(2, 2): OVERLAY_KEY})
        self.assertEqual(state.ground, {(2, 2): SOLID_KEY})

    def test_objects_survive_ground_overlay_and_infra_painting(self):
        state = make_overlay_state()
        state.place("rock_01", 2, 2)
        state.place(SOLID_KEY, 2, 2)
        state.place(OVERLAY_KEY, 2, 2)
        self.assertEqual(state.objects, {(2, 2): "rock_01"})

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


INFRA_KEY = "ml_r07_c02"


def make_infra_state(cells=()):
    catalog = CATALOG + [
        {"item_key": OVERLAY_KEY, "kind": "ground", "footprint_w": 1, "footprint_h": 1},
        {"item_key": SOLID_KEY, "kind": "ground", "footprint_w": 1, "footprint_h": 1},
        {"item_key": INFRA_KEY, "kind": "ground", "footprint_w": 1, "footprint_h": 1},
    ]
    state = MapEditorState(catalog, list(cells), 10, 10)
    state.overlay_keys = frozenset({OVERLAY_KEY})
    state.infra_keys = frozenset({INFRA_KEY})
    return state


class InfraLayerTests(unittest.TestCase):
    def test_infra_goes_over_ground_and_overlay_and_keeps_them(self):
        state = make_infra_state()
        state.place("grass_1", 2, 2)
        state.place(OVERLAY_KEY, 2, 2)
        state.place(INFRA_KEY, 2, 2)
        self.assertEqual(state.ground, {(2, 2): "grass_1"})
        self.assertEqual(state.overlay, {(2, 2): OVERLAY_KEY})
        self.assertEqual(state.infra, {(2, 2): INFRA_KEY})

    def test_solid_ground_keeps_infra(self):
        state = make_infra_state()
        state.place(INFRA_KEY, 2, 2)
        state.place(SOLID_KEY, 2, 2)
        self.assertEqual(state.infra, {(2, 2): INFRA_KEY})
        self.assertEqual(state.ground, {(2, 2): SOLID_KEY})

    def test_fill_ground_keeps_infra_and_overlay(self):
        state = make_infra_state()
        state.place("grass_1", 0, 0)
        state.place(INFRA_KEY, 0, 0)
        state.place(OVERLAY_KEY, 0, 0)
        state.fill(SOLID_KEY, 0, 0)
        self.assertEqual(state.ground, {(0, 0): SOLID_KEY})
        self.assertEqual(state.infra, {(0, 0): INFRA_KEY})
        self.assertEqual(state.overlay, {(0, 0): OVERLAY_KEY})

    def test_erase_removes_infra_then_overlay_then_ground(self):
        state = make_infra_state()
        state.place("grass_1", 1, 1)
        state.place(OVERLAY_KEY, 1, 1)
        state.place(INFRA_KEY, 1, 1)
        self.assertTrue(state.erase(1, 1))
        self.assertEqual((state.infra, state.overlay), ({}, {(1, 1): OVERLAY_KEY}))
        self.assertTrue(state.erase(1, 1))
        self.assertEqual((state.overlay, state.ground), ({}, {(1, 1): "grass_1"}))

    def test_cells_roundtrip_with_infra_layer(self):
        cells = [{"layer": "infra", "x": 3, "y": 3, "key": INFRA_KEY}]
        state = make_infra_state(cells)
        self.assertEqual(state.infra, {(3, 3): INFRA_KEY})
        self.assertEqual(state.to_cells(), cells)

    def test_loads_ground_cell_with_infra_key_as_infra(self):
        with mock.patch("client.map_editor_state.infrastructure_keys", return_value=frozenset({INFRA_KEY})):
            state = make_infra_state([{"layer": "ground", "x": 4, "y": 4, "key": INFRA_KEY}])
        self.assertEqual(state.infra, {(4, 4): INFRA_KEY})
        self.assertEqual(state.ground, {})

    def test_undo_restores_infra(self):
        state = make_infra_state([{"layer": "infra", "x": 3, "y": 3, "key": INFRA_KEY}])
        state.begin_action()
        state.erase(3, 3)
        state.end_action()
        self.assertEqual(state.infra, {})
        state.undo()
        self.assertEqual(state.infra, {(3, 3): INFRA_KEY})

    def test_move_and_delete_selection_carry_infra(self):
        state = make_infra_state([{"layer": "infra", "x": 1, "y": 1, "key": INFRA_KEY}])
        state.select(0, 0, 2, 2)
        self.assertIsNone(state.move_selection(3, 0))
        self.assertEqual(state.infra, {(4, 1): INFRA_KEY})
        self.assertEqual(state.delete_selection(), 1)
        self.assertEqual(state.infra, {})

    def test_paste_infra_keeps_ground_and_overlay_under_it(self):
        state = make_infra_state([
            {"layer": "ground", "x": 1, "y": 1, "key": "grass_1"},
            {"layer": "infra", "x": 1, "y": 1, "key": INFRA_KEY},
            {"layer": "overlay", "x": 7, "y": 7, "key": OVERLAY_KEY},
        ])
        state.select(1, 1, 1, 1)
        stamp = state.copy_selection()
        self.assertEqual(stamp["infra"], [(0, 0, INFRA_KEY)])
        self.assertIsNone(state.paste(stamp, 5, 5))
        self.assertEqual(state.ground[(5, 5)], "grass_1")
        self.assertEqual(state.infra[(5, 5)], INFRA_KEY)

        infra_only = {"w": 1, "h": 1, "ground": [], "overlay": [], "infra": [(0, 0, INFRA_KEY)], "objects": []}
        self.assertIsNone(state.paste(infra_only, 7, 7))
        self.assertEqual(state.overlay, {(7, 7): OVERLAY_KEY})
        self.assertEqual(state.infra[(7, 7)], INFRA_KEY)


class RoadLayerTests(unittest.TestCase):
    def setUp(self):
        self.catalog = catalog_definitions()
        self.road = min(road_keys())
        base_keys = palette_role_keys("ground") | palette_role_keys("grass")
        by_key = {item["item_key"]: item for item in self.catalog}
        self.grass = next(
            key for key in sorted(base_keys)
            if by_key[key]["category"] == "grass" and key not in overlay_keys()
        )

    def test_road_goes_to_overlay_and_keeps_grass_under_it(self):
        state = MapEditorState(self.catalog, [], 8, 8)
        state.place(self.grass, 2, 2)
        state.place(self.road, 2, 2)
        self.assertEqual(state.ground, {(2, 2): self.grass})
        self.assertEqual(state.overlay, {(2, 2): self.road})

    def test_erasing_road_leaves_grass(self):
        state = MapEditorState(self.catalog, [{"layer": "ground", "x": 1, "y": 1, "key": self.grass}], 8, 8)
        state.place(self.road, 1, 1)
        state.erase(1, 1)
        self.assertEqual(state.ground, {(1, 1): self.grass})
        self.assertEqual(state.overlay, {})

    def test_old_draft_road_in_ground_moves_to_overlay(self):
        state = MapEditorState(self.catalog, [{"layer": "ground", "x": 1, "y": 1, "key": self.road}], 8, 8)
        self.assertEqual(state.overlay, {(1, 1): self.road})
        self.assertNotIn((1, 1), state.ground)

    def test_old_draft_grass_over_road_moves_to_ground_and_road_stays(self):
        cells = [
            {"layer": "ground", "x": 1, "y": 1, "key": self.road},
            {"layer": "overlay", "x": 1, "y": 1, "key": self.grass},
        ]
        state = MapEditorState(self.catalog, cells, 8, 8)
        self.assertEqual(state.ground, {(1, 1): self.grass})
        self.assertEqual(state.overlay, {(1, 1): self.road})

    def test_old_draft_overlay_transition_under_road_moves_to_ground(self):
        transition = min(set(overlay_keys()) - set(road_keys()))
        cells = [
            {"layer": "ground", "x": 1, "y": 1, "key": self.road},
            {"layer": "overlay", "x": 1, "y": 1, "key": transition},
        ]
        state = MapEditorState(self.catalog, cells, 8, 8)
        self.assertEqual(state.ground, {(1, 1): transition})
        self.assertEqual(state.overlay, {(1, 1): self.road})


class ElevationReliefLayerTests(unittest.TestCase):
    def setUp(self):
        self.catalog = catalog_definitions()
        layers = terrain_layer_keys()
        self.elevation_key = min(layers["elevation"])
        self.relief_key = min(layers["relief"])
        by_key = {item["item_key"]: item for item in self.catalog}
        base_keys = {
            key
            for group in palette_groups()
            for layer in palette_group_layers(group)
            if layer["role"] == "ground"
            for key in layer["cells"].values()
        }
        self.ground_key = next(
            key for key in sorted(base_keys)
            if key not in overlay_keys() and by_key[key]["category"] == "grass"
        )
        self.mountain_rock_key = next(
            key for key in sorted(palette_role_keys("mountain"))
            if by_key[key]["category"] == "rock" and key not in overlay_keys()
        )
        self.state = MapEditorState(self.catalog, [], 8, 8)

    def test_ground_paint_preserves_elevation_and_mountain_relief(self):
        self.state.place(self.elevation_key, 2, 2, layer="elevation")
        self.state.place(self.relief_key, 2, 2, layer="relief")
        self.state.paint(self.ground_key, 2, 2, layer="ground")

        self.assertEqual(self.state.ground, {(2, 2): self.ground_key})
        self.assertEqual(self.state.elevation, {(2, 2): self.elevation_key})
        self.assertEqual(self.state.relief, {(2, 2): self.relief_key})

    def test_old_ground_mountain_tiles_are_migrated_to_their_own_layer(self):
        state = MapEditorState(
            self.catalog,
            [
                {"layer": "ground", "x": 1, "y": 1, "key": self.ground_key},
                {"layer": "ground", "x": 2, "y": 1, "key": self.mountain_rock_key},
            ],
            8,
            8,
        )

        self.assertEqual(state.ground, {(1, 1): self.ground_key})
        self.assertEqual(state.relief, {(2, 1): self.mountain_rock_key})
        self.assertEqual(
            {cell["layer"] for cell in state.to_cells()},
            {"ground", "relief"},
        )

    def test_undo_move_and_copy_keep_mountain_layers(self):
        self.state.place(self.relief_key, 1, 1)
        self.state.select(1, 1, 1, 1)
        stamp = self.state.copy_selection()
        self.assertEqual(stamp["relief"], [(0, 0, self.relief_key)])
        self.assertIsNone(self.state.paste(stamp, 4, 4))
        self.assertEqual(self.state.relief[(4, 4)], self.relief_key)
        self.state.begin_action()
        self.state.erase(4, 4)
        self.state.end_action()
        self.state.undo()
        self.assertEqual(self.state.relief[(4, 4)], self.relief_key)


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

    def test_paste_solid_ground_keeps_overlay_and_object_replaces_object(self):
        state = self._state()
        state.overlay[(2, 1)] = OVERLAY_KEY
        stamp = {"w": 1, "h": 1, "ground": [(0, 0, SOLID_KEY)], "overlay": [], "objects": [(0, 1, "rock_01")]}
        state.paste(stamp, 2, 1)
        self.assertEqual(state.ground[(2, 1)], SOLID_KEY)
        self.assertEqual(state.overlay, {(2, 1): OVERLAY_KEY})
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
