import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from combat.dash import DASH_RANGE
from core import mob_modes
from server import world_map
from server.world_mobs import MOB_RESPAWN_DELAY, WorldService

IMP = "imp_sword"  # моб из редактора карт: других видов в мире нет


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def _corpse_view(corpse):
    return {key: corpse[key] for key in ("id", "x", "y", "copper")}


class FakeDatabase:
    def __init__(self, owners):
        self.owners = owners
        self.saved = []
        self.currency = []
        self.progression = []
        self.wallet = {}
        self.corpses = {}
        self.next_corpse_id = 1

    def create_player_corpse(self, user_id, character_id, x, y, coin_percent):
        lost = self.wallet.get(character_id, 0) * coin_percent // 100
        if lost <= 0:
            return None
        self.wallet[character_id] -= lost
        corpse = {"id": self.next_corpse_id, "x": float(x), "y": float(y), "copper": lost, "character_id": character_id}
        self.next_corpse_id += 1
        self.corpses[corpse["id"]] = corpse
        return _corpse_view(corpse), {"copper": self.wallet[character_id], "silver": 0, "gold": 0}

    def list_player_corpses(self, character_id):
        return [_corpse_view(corpse) for corpse in self.corpses.values() if corpse["character_id"] == character_id]

    def loot_player_corpse(self, user_id, character_id, corpse_id):
        corpse = self.corpses.get(corpse_id)
        if corpse is None or corpse["character_id"] != character_id:
            raise ValueError("Труп не найден")
        del self.corpses[corpse_id]
        self.wallet[character_id] = self.wallet.get(character_id, 0) + corpse["copper"]
        return {"copper": self.wallet[character_id], "silver": 0, "gold": 0}, corpse["copper"]

    def map_live_spawns(self):
        return list(getattr(self, "spawns", []))

    def map_live_mobs(self):
        return list(getattr(self, "mobs", []))

    def world_mode(self):
        return "tower"

    def get_character(self, user_id, character_id=None):
        if self.owners.get(character_id) != user_id:
            return None
        return {
            "id": character_id,
            "name": "Тест",
            "type": "warrior",
            "level": 1,
            "xp": 0,
            "hp": 50,
            "max_hp": 50,
            "mp": 10,
            "max_mp": 10,
            "stats": {"strength": 3, "agility": 3, "intuition": 3, "wisdom": 3,
                      "intellect": 3, "endurance": 3},
            "stat_points": 0,
            "equipment": {},
            "equipment_bonuses": {},
            "position_x": None,
            "position_y": None,
        }

    def connection(self):
        return FakeConnection()

    def save_world_vitals(self, user_id, character_id, hp, mp):
        self.saved.append((hp, mp))
        return {"hp": hp, "mp": mp, "max_hp": 50, "max_mp": 10}

    def add_world_currency(self, user_id, character_id, copper):
        self.currency.append(copper)
        return {"copper": copper, "silver": 0, "gold": 0}

    def save_world_progression(self, user_id, character_id, level, xp, stats, stat_points, max_hp):
        self.progression.append({"character_id": character_id, "level": level, "xp": xp, "max_hp": max_hp})

    def rest_character(self, user_id, character_id):
        return {"hp": 50, "mp": 10, "max_hp": 50, "max_mp": 10}


class FakeItems:
    def get_catalog_items(self, item_ids):
        catalog = {
            "20": {"id": 20, "name": "Железный меч", "equip_slot": "weapon", "bonuses": {}, "icon": "sword"},
            "23": {"id": 23, "name": "Дубина", "equip_slot": "weapon", "bonuses": {}, "icon": "club"},
            "38": {"id": 38, "name": "Круглый щит", "equip_slot": "shield", "bonuses": {}, "icon": "shield"},
        }
        return {str(item_id): dict(catalog[str(item_id)]) for item_id in item_ids if str(item_id) in catalog}

    def carry_weight_state(self, connection, character_id):
        return {"carried_weight_kg": 0.0, "carry_capacity_kg": 100.0}


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class WorldMobsTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        modes = patch.object(mob_modes, "MODES_DIR", Path(folder.name))
        modes.start()
        self.addCleanup(modes.stop)
        live = patch.object(world_map, "LIVE_MAP", True)
        live.start()
        self.addCleanup(live.stop)
        self.clock = FakeClock()
        self.database = FakeDatabase({1: 7, 2: 8})
        # Мобы стоят на тех же тайлах, где раньше были скелет и бандит: геометрия тестов не меняется
        self.database.mobs = [{"kind": IMP, "x": 30, "y": 40}, {"kind": IMP, "x": 30, "y": 70}]
        self.service = WorldService(
            self.database, FakeItems(), clock=self.clock, rng=random.Random(3))
        # Тесты проверяют правила боя и движения, а не карту: рельеф открыт
        self.service._terrain_blocked = lambda x, y: False
        self.mob = self.service._mobs["mob_0_imp_sword"]
        self.far_mob = self.service._mobs["mob_1_imp_sword"]

    def sync(self, character_id=1, x=None, y=None, **extra):
        user_id = self.database.owners[character_id]
        payload = {"x": x if x is not None else 0, "y": y if y is not None else 0}
        payload.update(extra)
        return self.service.sync(user_id, character_id, payload)

    def test_first_sync_accepts_client_position(self):
        snapshot = self.sync(x=700.0, y=1296.0)
        self.assertTrue(snapshot["accepted"])
        self.assertEqual(snapshot["player"]["x"], 700.0)
        self.assertEqual(len(snapshot["mobs"]), 2)

    def test_move_beyond_speed_is_rejected(self):
        self.sync(x=700.0, y=1296.0)
        self.clock.now += 0.1
        snapshot = self.sync(x=1200.0, y=1296.0)
        self.assertFalse(snapshot["accepted"])
        self.assertEqual(snapshot["player"]["x"], 700.0)

    def test_small_move_is_accepted(self):
        self.sync(x=700.0, y=1296.0)
        self.clock.now += 0.1
        snapshot = self.sync(x=705.0, y=1296.0)
        self.assertTrue(snapshot["accepted"])
        self.assertEqual(snapshot["player"]["x"], 705.0)

    def test_move_into_mob_body_is_rejected(self):
        mob_x, mob_y = self.mob.home_x, self.mob.home_y
        self.sync(x=mob_x - 200.0, y=mob_y)
        self.clock.now += 2.0
        snapshot = self.sync(x=mob_x, y=mob_y)
        self.assertFalse(snapshot["accepted"])
        self.assertEqual(snapshot["player"]["x"], mob_x - 200.0)

    def test_dash_hits_mob_on_path_and_starts_cooldown(self):
        mob_x, mob_y = self.mob.home_x, self.mob.home_y
        self.sync(x=mob_x - 300.0, y=mob_y)
        self.sync(x=mob_x - 300.0, y=mob_y, dash_target={"x": mob_x + 100.0, "y": mob_y})
        self.service.advance(2.0)
        self.assertLess(self.mob.fighter.hp, self.mob.fighter.max_hp)
        player = self.service._players[1]
        self.assertIsNone(player.dash)
        self.assertGreater(player.x, mob_x)
        self.assertGreater(player.dash_cooldown, 0)

    def test_dash_rejected_during_cooldown(self):
        mob_x, mob_y = self.mob.home_x, self.mob.home_y
        self.sync(x=mob_x - 300.0, y=mob_y)
        self.sync(x=mob_x - 300.0, y=mob_y, dash_target={"x": mob_x + 100.0, "y": mob_y})
        self.service.advance(2.0)
        player = self.service._players[1]
        position = (player.x, player.y)
        self.sync(x=player.x, y=player.y, dash_target={"x": player.x + 300.0, "y": player.y})
        self.assertIsNone(player.dash)
        self.assertEqual((player.x, player.y), position)

    def test_mob_defeat_grants_reward_then_respawns(self):
        self.sync(x=700.0, y=1296.0)
        player = self.service._players[1]
        self.service._dash_damage_mob(player, self.mob, 999, "Рывок")
        self.assertFalse(self.mob.alive)
        self.assertEqual(self.mob.respawn_timer, MOB_RESPAWN_DELAY)
        self.assertEqual(self.database.currency, [mob_modes.DEFAULT_REWARD_COPPER])
        self.assertEqual(self.mob.coins_copper, 0)
        self.assertEqual(self.database.progression[-1]["character_id"], 1)
        self.assertEqual(self.database.progression[-1]["xp"], self.mob.reward_xp)
        self.service.advance(MOB_RESPAWN_DELAY + 0.5)
        self.assertTrue(self.mob.alive)
        self.assertEqual(self.mob.fighter.hp, self.mob.fighter.max_hp)
        self.assertEqual(self.mob.coins_copper, mob_modes.DEFAULT_REWARD_COPPER)

    def _prepare_split_fight(self, max_hp=400, copper=300, xp=100):
        self.database.owners[3] = 9
        self.mob.fighter.max_hp = max_hp
        self.mob.fighter.hp = max_hp
        self.mob.coins_copper = copper
        self.mob.reward_xp = xp
        for character_id, x in ((1, 700.0), (2, 710.0), (3, 720.0)):
            self.sync(character_id=character_id, x=x, y=1296.0)
        return self.service._players[1], self.service._players[2], self.service._players[3]

    def test_mob_reward_is_split_by_damage_share(self):
        first, second, _third = self._prepare_split_fight()
        self.service._damage_mob(self.mob, 100, first)
        self.service._damage_mob(self.mob, 999, second)
        self.service._defeat_mob(self.mob, second)
        # 25% урона у первого, 75% у второго: монеты 300 и опыт 100 делятся так же
        self.assertEqual(self.database.currency, [75, 225])
        self.assertEqual(self.service._players[1].fighter.xp, 25)
        self.assertEqual(self.service._players[2].fighter.xp, 75)

    def test_mob_reward_rounding_never_exceeds_reward(self):
        first, second, third = self._prepare_split_fight(max_hp=3, copper=10, xp=10)
        for player in (first, second, third):
            self.service._damage_mob(self.mob, 1, player)
        self.service._defeat_mob(self.mob, third)
        self.assertLessEqual(sum(self.database.currency), 10)
        self.assertLessEqual(sum(entry["xp"] for entry in self.database.progression), 10)
        self.assertEqual(self.database.currency, [3, 3, 3])

    def test_offline_contributor_gets_share_in_database(self):
        first, second, _third = self._prepare_split_fight()
        self.service._damage_mob(self.mob, 100, second)
        self.service.leave(8, 2)
        self.assertNotIn(2, self.service._players)
        self.service._damage_mob(self.mob, 999, first)
        self.service._defeat_mob(self.mob, first)
        offline = [entry for entry in self.database.progression if entry["character_id"] == 2]
        self.assertEqual(offline[-1]["xp"], 25)
        self.assertEqual(self.database.currency, [75, 225])

    def test_rest_restores_loaded_player_and_flushes(self):
        self.sync(x=700.0, y=1296.0)
        player = self.service._players[1]
        player.fighter.hp = 1
        vitals = self.service.rest(7, 1)
        self.assertEqual(vitals["hp"], player.fighter.max_hp)
        self.assertEqual(self.database.saved[-1][0], player.fighter.max_hp)

    def test_hp_regenerates_over_time(self):
        self.sync(x=700.0, y=1296.0)
        player = self.service._players[1]
        player.fighter.hp = 1
        self.service.advance(10.0)
        self.assertGreater(player.fighter.hp, 1)

    def test_leave_flushes_and_unloads_player(self):
        self.sync(x=700.0, y=1296.0)
        self.service.leave(7, 1)
        self.assertNotIn(1, self.service._players)
        self.assertTrue(self.database.saved)

    def test_death_leaves_corpse_with_coins_and_respawns(self):
        self.sync(x=700.0, y=1296.0)
        player = self.service._players[1]
        self.database.wallet[1] = 1000
        player.fighter.hp = 0
        self.service._player_died(player)
        self.assertEqual(self.database.wallet[1], 800)
        self.assertEqual(len(player.corpses), 1)
        self.assertEqual(player.corpses[0]["copper"], 200)
        self.assertEqual((player.corpses[0]["x"], player.corpses[0]["y"]), (700.0, 1296.0))
        self.assertEqual(player.fighter.hp, player.fighter.max_hp)
        snapshot = self.service.sync(7, 1, {"x": player.x, "y": player.y, "since": 0})
        self.assertEqual(len(snapshot["corpses"]), 1)

    def test_death_without_coins_leaves_no_corpse(self):
        self.sync(x=700.0, y=1296.0)
        player = self.service._players[1]
        self.database.wallet[1] = 0
        self.service._player_died(player)
        self.assertEqual(player.corpses, [])

    def test_loot_near_corpse_returns_coins(self):
        self.sync(x=700.0, y=1296.0)
        player = self.service._players[1]
        self.database.wallet[1] = 1000
        self.service._player_died(player)
        corpse_id = player.corpses[0]["id"]
        player.x, player.y = 700.0, 1296.0
        result = self.service.loot_corpse(7, 1, corpse_id)
        self.assertEqual(self.database.wallet[1], 1000)
        self.assertEqual(result["corpses"], [])
        self.assertEqual(player.corpses, [])
        self.assertEqual(result["currency"]["copper"], 1000)

    def test_loot_far_from_corpse_is_refused(self):
        self.sync(x=700.0, y=1296.0)
        player = self.service._players[1]
        self.database.wallet[1] = 1000
        self.service._player_died(player)
        corpse_id = player.corpses[0]["id"]
        self.clock.now += 10.0
        self.sync(x=1000.0, y=1296.0)
        with self.assertRaises(ValueError):
            self.service.loot_corpse(7, 1, corpse_id)
        self.assertEqual(self.database.wallet[1], 800)
        self.assertEqual(len(player.corpses), 1)

    def test_loot_is_refused_for_other_user(self):
        self.sync(x=700.0, y=1296.0)
        player = self.service._players[1]
        self.database.wallet[1] = 1000
        self.service._player_died(player)
        corpse_id = player.corpses[0]["id"]
        with self.assertRaises(ValueError):
            self.service.loot_corpse(8, 1, corpse_id)
        self.assertEqual(len(self.database.corpses), 1)

    def test_corpse_survives_reload_of_player(self):
        self.sync(x=700.0, y=1296.0)
        player = self.service._players[1]
        self.database.wallet[1] = 1000
        self.service._player_died(player)
        self.service.leave(7, 1)
        self.sync(x=700.0, y=1296.0)
        self.assertEqual(len(self.service._players[1].corpses), 1)

    def test_character_of_other_user_is_refused(self):
        with self.assertRaises(ValueError):
            self.service.sync(7, 2, {"x": 700.0, "y": 1296.0})

    def test_mob_without_editor_equipment_has_no_gear(self):
        self.assertEqual(self.mob.equipment, {})
        self.assertEqual(WorldService._mob_payload(self.mob)["equipment"], {})

    def test_mob_gets_weapon_and_shield_chosen_in_editor(self):
        settings = mob_modes.default_settings(IMP)
        settings["equipment"] = {"weapon": 20, "shield": 38}
        mob_modes.save_mob_settings("tower", IMP, settings)
        service = WorldService(self.database, FakeItems(), clock=self.clock, rng=random.Random(3))
        mob = service._mobs["mob_0_imp_sword"]
        self.assertEqual(mob.equipment["weapon"]["name"], "Железный меч")
        self.assertEqual(mob.equipment["shield"]["name"], "Круглый щит")
        self.assertEqual(WorldService._mob_payload(mob)["equipment"]["shield"]["name"], "Круглый щит")

    def test_item_in_wrong_slot_is_not_given_to_mob(self):
        settings = mob_modes.default_settings(IMP)
        settings["equipment"] = {"weapon": 38, "shield": None}  # щит в слоте оружия
        mob_modes.save_mob_settings("tower", IMP, settings)
        service = WorldService(self.database, FakeItems(), clock=self.clock, rng=random.Random(3))
        self.assertEqual(service._mobs["mob_0_imp_sword"].equipment, {})

    def test_item_missing_from_catalog_leaves_slot_empty(self):
        settings = mob_modes.default_settings(IMP)
        settings["equipment"] = {"weapon": 999, "shield": None}
        mob_modes.save_mob_settings("tower", IMP, settings)
        service = WorldService(self.database, FakeItems(), clock=self.clock, rng=random.Random(3))
        self.assertEqual(service._mobs["mob_0_imp_sword"].equipment, {})

    def _park_mobs(self):
        for index, mob in enumerate(self.service._mobs.values()):
            mob.x, mob.y = 9000.0 + index * 500.0, 9000.0

    def _dash(self, start_x, target_x, y=1296.0):
        """Запускает рывок на сервере и двигает его до конца, без ИИ мобов.

        Рывок всегда летит на полную дальность DASH_RANGE (500) в сторону цели,
        поэтому конец рывка находится в start_x + 500, а не в target_x.
        """
        self.sync(x=start_x, y=y, dash_target={"x": target_x, "y": y})
        player = self.service._players[1]
        self.service._update_dash(player, 2.0)
        return player

    def test_dash_flies_full_dash_range_on_open_ground(self):
        self._park_mobs()
        player = self._dash(1000.0, 1800.0)
        self.assertIsNone(player.dash)
        self.assertAlmostEqual(player.x, 1000.0 + DASH_RANGE, delta=1e-6)
        self.assertAlmostEqual(player.y, 1296.0, delta=1e-6)

    def test_wall_stops_dash_before_it(self):
        self._park_mobs()
        wall_x = 1200.0
        self.service._terrain_blocked = lambda x, y: x >= wall_x
        player = self._dash(1000.0, 1800.0)
        self.assertIsNone(player.dash)
        self.assertLess(player.x, wall_x)

    def test_dash_ending_inside_mob_passes_it_to_far_side(self):
        self._park_mobs()
        mob = self.mob
        mob.x, mob.y = 1500.0, 1296.0
        player = self._dash(1000.0, 1800.0)
        self.assertIsNone(player.dash)
        self.assertGreater(player.x, mob.x + 40.0)

    def test_whirl_strike_hits_mob_near_end_but_not_on_path(self):
        self._park_mobs()
        near = self.mob
        near.x, near.y = 1500.0, 1296.0 + 75.0
        far = self.far_mob
        far.x, far.y = 1500.0, 1296.0 + 250.0
        self._dash(1000.0, 1800.0)
        self.assertLess(near.fighter.hp, near.fighter.max_hp)
        self.assertEqual(far.fighter.hp, far.fighter.max_hp)

    def test_whirl_strike_sends_whirl_event_even_without_mobs(self):
        self._park_mobs()
        player = self._dash(1000.0, 1800.0)
        self.assertIn("whirl", [e["type"] for e in player.events])

    def test_dash_trail_disappears_after_five_seconds(self):
        self._park_mobs()
        player = self._dash(1000.0, 1800.0)
        self.assertTrue(player.trails)
        self.service.advance(5.5)
        self.assertEqual(player.trails, [])


if __name__ == "__main__":
    unittest.main()
