import random
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from front_line.server.world import BUILDING_FOOTPRINT_TILES, FrontLineWorldService
from server.world_map import TILE


def _saved_with_building(hp=500, regen=0, slots=None):
    return {"spawns": [{
        "type": "building", "x": 10, "y": 12, "sprite": "castle_5",
        "settings": {
            "hp": hp, "hp_regen_per_minute": regen,
            "defense_slots": slots if slots is not None else [],
        },
    }]}


def _mob(x, y, hp=40):
    return SimpleNamespace(
        id="m", alive=True, state="idle", x=float(x), y=float(y),
        fighter=SimpleNamespace(hp=hp), damage_by={}, hurt_id=0, respawn_delay=30.0,
        windup=0.0, windup_total=0.0, is_boss=False,
    )


def _service(buildings, mobs=None):
    service = object.__new__(FrontLineWorldService)
    service._building_states = buildings
    service._mobs = mobs or {}
    service._rng = random.Random(3)
    service._round_mobs_killed = 0
    service._players = {}
    return service


class BuildingParsingTests(unittest.TestCase):
    def test_building_is_parsed_with_slots_in_pixels(self):
        slots = [{"attack": "arrow", "damage_min": 5, "damage_max": 9, "radius_units": 400, "interval_seconds": 1.5}]
        buildings = FrontLineWorldService._buildings_from_saved(_saved_with_building(hp=800, regen=60, slots=slots))
        self.assertEqual(len(buildings), 1)
        building = buildings[0]
        self.assertEqual((building["x"], building["y"], building["sprite"]), (10, 12, "castle_5"))
        self.assertEqual((building["hp"], building["max_hp"], building["regen_per_minute"]), (800.0, 800.0, 60.0))
        self.assertAlmostEqual(building["slots"][0]["radius_px"], 400 * TILE / 50)

    def test_footprint_blocks_five_by_five_tiles(self):
        tiles = FrontLineWorldService._building_tiles(FrontLineWorldService._buildings_from_saved(_saved_with_building()))
        self.assertEqual(len(tiles), BUILDING_FOOTPRINT_TILES ** 2)
        self.assertIn((10, 12), tiles)
        self.assertIn((14, 16), tiles)
        self.assertNotIn((15, 12), tiles)

    def test_non_building_spawns_are_ignored(self):
        saved = {"spawns": [{"type": "hero", "x": 1, "y": 1}, {"type": "objective", "settings": {}}]}
        self.assertEqual(FrontLineWorldService._buildings_from_saved(saved), [])


class BuildingDefenseTests(unittest.TestCase):
    def _building(self, interval=2.0, radius_units=400, regen=0, hp=500.0):
        slot = {
            "attack": "arrow", "damage_min": 7, "damage_max": 7,
            "radius_px": radius_units * TILE / 50, "interval_seconds": interval, "cooldown": 0.0,
        }
        return {"x": 0, "y": 0, "sprite": "castle_8", "hp": hp, "max_hp": 500.0,
                "regen_per_minute": regen, "slots": [slot]}

    def test_slot_shoots_nearest_mob_in_radius_and_respects_interval(self):
        center = (2.5 * TILE, 2.5 * TILE)
        mob = _mob(center[0] + 50, center[1])
        service = _service([self._building()], {"m": mob})
        service._update_buildings(0.1)
        self.assertEqual(mob.fighter.hp, 40 - 7)
        service._update_buildings(0.5)
        self.assertEqual(mob.fighter.hp, 40 - 7, "перезарядка не даёт второго выстрела раньше интервала")
        service._update_buildings(2.0)
        self.assertEqual(mob.fighter.hp, 40 - 14, "после интервала слот стреляет снова")

    def test_mob_outside_radius_is_not_shot(self):
        far = _mob(2.5 * TILE + 5000, 2.5 * TILE)
        service = _service([self._building(radius_units=100)], {"m": far})
        service._update_buildings(0.1)
        self.assertEqual(far.fighter.hp, 40)

    def test_regeneration_restores_hp_up_to_max(self):
        service = _service([self._building(regen=60, hp=100.0)])
        service._update_buildings(10.0)
        self.assertAlmostEqual(service._building_states[0]["hp"], 110.0)
        service._building_states[0]["hp"] = 499.9
        service._update_buildings(10.0)
        self.assertEqual(service._building_states[0]["hp"], 500.0)

    def test_defense_can_defeat_a_mob(self):
        center = (2.5 * TILE, 2.5 * TILE)
        mob = _mob(center[0] + 10, center[1], hp=5)
        service = _service([self._building()], {"m": mob})
        # Гибель моба (награды, таймеры) проверяется в тестах мира; здесь важен только вызов из обороны.
        service._defeat_mob = lambda target, killer: setattr(target, "state", "dead")
        service._update_buildings(0.1)
        self.assertEqual(mob.state, "dead")


class BuildingObjectiveTests(unittest.TestCase):
    def _buildings(self):
        return FrontLineWorldService._buildings_from_saved({"spawns": [
            {"type": "building", "x": 10, "y": 10, "sprite": "castle_8", "settings": {"hp": 300}},
            {"type": "building", "x": 40, "y": 10, "sprite": "castle_5", "settings": {"hp": 200}},
        ]})

    def test_nearest_alive_building_is_chosen_by_footprint_distance(self):
        service = _service(self._buildings())
        near_first, _ = service._nearest_alive_building(12 * TILE, 12 * TILE)
        self.assertEqual((near_first["x"], near_first["y"]), (10, 10))
        near_second, _ = service._nearest_alive_building(41 * TILE, 12 * TILE)
        self.assertEqual((near_second["x"], near_second["y"]), (40, 10))

    def test_destroyed_building_is_not_a_target(self):
        buildings = self._buildings()
        buildings[0]["hp"] = 0.0
        service = _service(buildings)
        target, _ = service._nearest_alive_building(12 * TILE, 12 * TILE)
        self.assertEqual((target["x"], target["y"]), (40, 10))
        buildings[1]["hp"] = 0.0
        self.assertFalse(service._any_building_alive())

    def test_approach_point_is_left_of_the_building(self):
        point = FrontLineWorldService._objective_point({"x": 10, "y": 10})
        self.assertEqual(point.x, 10 * TILE - TILE)
        self.assertEqual(point.y, (10 + BUILDING_FOOTPRINT_TILES / 2) * TILE)

    def test_wall_cells_cover_every_living_building(self):
        service = _service(self._buildings())
        service._map_width = service._map_height = 64
        walkable = set()
        walls = service._objective_wall_cells(walkable)
        self.assertIn((10, 10), walls)
        self.assertIn((44, 14), walls)
        self.assertEqual(len(walls), 2 * BUILDING_FOOTPRINT_TILES ** 2)


class BuildingEngineTests(unittest.TestCase):
    def _service(self, buildings, size=40):
        service = _service(buildings)
        service._map_width = service._map_height = size
        blocked = FrontLineWorldService._building_tiles(buildings)
        service._walkable_cells = lambda: {(x, y) for x in range(size) for y in range(size)} - blocked
        service._terrain_segment_clear = lambda *args: True
        service._objective_flow_cache = None
        service._finish_calls = []
        service._finish_match = lambda result: service._finish_calls.append(result)
        return service

    def _attacker(self):
        return SimpleNamespace(
            state="idle", facing=0.0, backswing=0.0, backswing_time=0.25,
            windup=0.0, windup_time=0.0, windup_total=0.0, swing_id=0,
            fighter=SimpleNamespace(), x=0.0, y=0.0,
        )

    def test_mob_strike_damages_nearest_building(self):
        buildings = [{"x": 10, "y": 10, "sprite": "castle_8", "hp": 300.0, "max_hp": 300.0,
                      "regen_per_minute": 0.0, "slots": []}]
        service = self._service(buildings)
        mob = self._attacker()
        mob.x, mob.y = 9 * TILE, 12 * TILE
        with patch("front_line.server.world.world_stats.get_world_base_damage", return_value=40):
            service._attack_objective(mob, 0.1)
        self.assertEqual(buildings[0]["hp"], 260.0)
        self.assertEqual(service._finish_calls, [])

    def test_destroying_the_last_building_loses_the_match(self):
        buildings = [{"x": 10, "y": 10, "sprite": "castle_8", "hp": 10.0, "max_hp": 300.0,
                      "regen_per_minute": 0.0, "slots": []}]
        service = self._service(buildings)
        mob = self._attacker()
        mob.x, mob.y = 9 * TILE, 12 * TILE
        with patch("front_line.server.world.world_stats.get_world_base_damage", return_value=40):
            service._attack_objective(mob, 0.1)
        self.assertEqual(buildings[0]["hp"], 0.0)
        self.assertEqual(service._finish_calls, ["lost"])

    def test_flow_leads_mobs_to_the_approach_point_left_of_a_building(self):
        buildings = [{"x": 10, "y": 10, "sprite": "castle_8", "hp": 300.0, "max_hp": 300.0,
                      "regen_per_minute": 0.0, "slots": []}]
        service = self._service(buildings)
        flow = service._objective_flow()
        approach = FrontLineWorldService._objective_point(buildings[0])
        approach_cell = (int(approach.x // TILE), int(approach.y // TILE))
        self.assertEqual(flow["distance"].get(approach_cell), 0.0)
        self.assertEqual(approach_cell, (9, 12))

    def test_walls_are_not_walkable_for_flow(self):
        buildings = [{"x": 10, "y": 10, "sprite": "castle_8", "hp": 300.0, "max_hp": 300.0,
                      "regen_per_minute": 0.0, "slots": []}]
        service = self._service(buildings)
        flow = service._objective_flow()
        self.assertNotIn((12, 12), flow["distance"])


if __name__ == "__main__":
    unittest.main()
