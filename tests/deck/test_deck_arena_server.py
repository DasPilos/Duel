"""Серверный бой на арене: сборка встреч, команды, журнал, итоги и срок жизни сессий."""

import json
import unittest

from deck.combat.card_database import class_cards_for_type
from deck.map_config import TILE_SIZE
from deck.server import arena

PROFILE = {
    "id": 7,
    "name": "Тест",
    "level": 5,
    "type": "warrior",
    "stats": {"strength": 6, "agility": 4, "intuition": 3, "wisdom": 2, "intellect": 2, "harmony": 2, "endurance": 6},
    "hp": 60,
    "mp": 20,
    "talents": {},
    "xp": 0,
    "stat_points": 0,
}
DECK_KEYS = [card.key for card in class_cards_for_type("warrior")]
ENEMY_COUNTS = {
    "kobold": 1,
    "kobold_camp": 3,
    "kobold_camp_2": 3,
    "ancient_ent": 2,
    "skeleton": 1,
    "necromancer": 1,
}


def start(source, seed=1):
    tile = arena.ENCOUNTERS[source]["tile"]
    return arena.start_session(
        PROFILE,
        source=source,
        position_x=(tile[0] + 1) * TILE_SIZE + 24,
        position_y=tile[1] * TILE_SIZE + 24,
        equipment={},
        deck_keys=DECK_KEYS,
        seed=seed,
    )


def _play_options(battle, index, card):
    options = [(target, None, None) for target in battle.card_targets(card)]
    options += [(None, None, list(tile)) for tile in battle.card_aim_tiles(card)]
    goal = battle.positions[battle.target]
    summon_tiles = sorted(battle.summon_tiles(), key=lambda tile: arena.hex_distance(tile, goal))
    options += [(None, list(tile), None) for tile in summon_tiles]
    for target, destination, aim in options:
        command = {"type": "play", "card_index": index}
        if target:
            command["target"] = target
        if destination:
            command["destination"] = destination
        if aim:
            command["aim_tile"] = aim
        yield command


def _step(session, send):
    """Один шаг простого игрока: выбор, розыгрыши, шаг к врагу и конец хода."""
    battle = session.battle
    view = arena.session_view(session)
    if view["phase"] == "draft":
        return send({"type": "draft", "card_key": view["draft_cards"][0]["key"]})
    if view["phase"] == "draw_choice":
        return send({"type": "draw_choice", "card_key": view["draw_choices"][0]["key"]})
    for index, card in enumerate(battle.engine.hands["player"]):
        if battle.cards_played >= arena.MAX_CARDS_PER_TURN:
            break
        if not battle.can_play_card(card):
            continue
        for command in _play_options(battle, index, card):
            try:
                return send(command)
            except arena.ArenaError:
                continue
    enemy = battle.positions[battle.enemy_ids[0]]
    here = arena.hex_distance(battle.positions["player"], enemy)
    best = None
    if not battle.moved:
        for tile in battle.reachable_tiles("player"):
            distance = arena.hex_distance(tile, enemy)
            if distance < here and (best is None or distance < best[0]):
                best = (distance, tile)
    if best is not None:
        try:
            send({"type": "move", "tile": list(best[1])})
        except arena.ArenaError:
            pass
    return send({"type": "end_turn"})


def _autoplay(session, send, max_steps=600):
    response = None
    for _ in range(max_steps):
        if session.battle.is_over():
            break
        response = _step(session, send)
    return response


def _finish_draft(session):
    while arena.session_view(session)["phase"] == "draft":
        key = arena.session_view(session)["draft_cards"][0]["key"]
        arena.apply_command(session, {"type": "draft", "card_key": key})


class ArenaEncounterTests(unittest.TestCase):
    def test_encounters_start_in_draft_with_expected_enemies(self):
        for source, count in ENEMY_COUNTS.items():
            with self.subTest(source=source):
                session = start(source)
                battle = session.battle
                view = arena.session_view(session)
                self.assertEqual(view["phase"], "draft")
                self.assertEqual(len(battle.enemy_ids), count)
                self.assertEqual(len(battle.ally_ids), 1 if source == "kobold_camp_2" else 0)
                self.assertEqual(len(view["draft_cards"]), len(battle.engine.table_for("player")))
                json.dumps(view)

    def test_bosses_use_their_names(self):
        self.assertEqual(start("ancient_ent").battle.enemy.name, "ДРЕВНИЙ ЕНТ")
        ent = start("ancient_ent").battle
        self.assertEqual([ent.fighters[eid].name for eid in ent.enemy_ids], ["ДРЕВНИЙ ЕНТ", "Волк"])
        self.assertEqual(start("necromancer").battle.enemy.name, "Некромансер")
        self.assertEqual(start("skeleton").battle.enemy.name, "Скелет")

    def test_unknown_encounter_is_rejected(self):
        with self.assertRaises(arena.ArenaError):
            arena.start_session(PROFILE, source="wolf", position_x=0, position_y=0, deck_keys=DECK_KEYS)

    def test_names_map_to_experience_types(self):
        expected = {
            "Кобольд 2": "kobold",
            "ДРЕВНИЙ ЕНТ": "ancient_ent",
            "Король скелетов": "skeleton_king",
            "Скелет-страж": "skeleton_guard",
            "Некромансер": "necromancer",
            "Скелет": "skeleton",
            "Волк": None,
        }
        for name, npc_type in expected.items():
            with self.subTest(name=name):
                self.assertEqual(arena.npc_xp_type(name), npc_type)


class ArenaCommandTests(unittest.TestCase):
    def test_draft_accepts_only_table_cards(self):
        session = start("kobold")
        with self.assertRaises(arena.ArenaError):
            arena.apply_command(session, {"type": "draft", "card_key": "no_such_card"})
        _finish_draft(session)
        self.assertNotEqual(arena.session_view(session)["phase"], "draft")

    def test_actions_are_rejected_during_draft(self):
        session = start("kobold")
        commands = [
            {"type": "play", "card_index": 0},
            {"type": "move", "tile": [0, 0]},
            {"type": "burn", "card_index": 0},
            {"type": "item", "item_id": 4},
            {"type": "teleport"},
            {"type": "end_turn"},
        ]
        for command in commands:
            with self.subTest(command=command["type"]):
                with self.assertRaises(arena.ArenaError):
                    arena.apply_command(session, command)

    def test_card_index_must_point_to_hand(self):
        session = start("kobold")
        _finish_draft(session)
        with self.assertRaises(arena.ArenaError):
            arena.apply_command(session, {"type": "play", "card_index": 999})

    def test_move_checks_tile_and_single_move_per_turn(self):
        session = start("kobold")
        _finish_draft(session)
        battle = session.battle
        with self.assertRaises(arena.ArenaError):
            arena.apply_command(session, {"type": "move", "tile": [0, 0]})
        tile = next(tile for tile in battle.reachable_tiles("player") if tile != battle.positions["player"])
        arena.apply_command(session, {"type": "move", "tile": list(tile)})
        self.assertEqual(battle.positions["player"], tile)
        self.assertTrue(arena.session_view(session)["moved"])
        with self.assertRaises(arena.ArenaError):
            arena.apply_command(session, {"type": "move", "tile": list(battle.positions["player"])})

    def test_burn_once_per_turn(self):
        session = start("kobold")
        _finish_draft(session)
        arena.apply_command(session, {"type": "burn", "card_index": 0})
        self.assertTrue(arena.session_view(session)["burned_this_turn"])
        with self.assertRaises(arena.ArenaError):
            arena.apply_command(session, {"type": "burn", "card_index": 0})

    def test_item_removes_inventory_before_use(self):
        session = start("kobold")
        _finish_draft(session)
        battle = session.battle
        battle.player.hp = battle.player.max_hp - 10
        removed = []
        arena.apply_command(
            session, {"type": "item", "item_id": 4},
            remove_item=lambda character_id, item_id, quantity: removed.append((character_id, item_id, quantity)),
        )
        self.assertEqual(removed, [(7, 4, 1)])
        self.assertEqual(battle.player.hp, battle.player.max_hp)

    def test_item_failure_keeps_hp_and_skips_use(self):
        session = start("kobold")
        _finish_draft(session)
        battle = session.battle
        battle.player.hp = battle.player.max_hp - 10
        hp_before = battle.player.hp

        def fail(character_id, item_id, quantity):
            raise arena.ArenaError("Предмета нет в инвентаре")

        with self.assertRaises(arena.ArenaError):
            arena.apply_command(session, {"type": "item", "item_id": 4}, remove_item=fail)
        self.assertEqual(battle.player.hp, hp_before)

    def test_item_needs_inventory_and_battle_list(self):
        session = start("kobold")
        _finish_draft(session)
        with self.assertRaises(arena.ArenaError):
            arena.apply_command(session, {"type": "item", "item_id": 4})
        with self.assertRaises(arena.ArenaError):
            arena.apply_command(session, {"type": "item", "item_id": 999}, remove_item=lambda *args: None)


class ArenaBattleFlowTests(unittest.TestCase):
    def test_seeded_battle_is_reproducible(self):
        first = start("kobold", seed=1)
        second = start("kobold", seed=1)
        _autoplay(first, lambda command: arena.apply_command(first, command))
        _autoplay(second, lambda command: arena.apply_command(second, command))
        self.assertEqual(first.journal, second.journal)
        self.assertEqual(first.battle.result, second.battle.result)

    def test_full_battle_reports_rewards(self):
        session = start("kobold", seed=1)
        _autoplay(session, lambda command: arena.apply_command(session, command))
        self.assertTrue(session.battle.is_over())
        report = arena.finish_report(session)
        self.assertEqual(report["result"], "win")
        self.assertEqual(report["defeated_npc_types"], ["kobold"])
        self.assertEqual(report["encounter_id"], "kobold")
        self.assertGreaterEqual(report["player_hp"], 1)

    def test_journal_keeps_lines_beyond_engine_limit(self):
        session = start("skeleton", seed=2)
        _autoplay(session, lambda command: arena.apply_command(session, command))
        self.assertLessEqual(len(session.battle.log), 8)
        self.assertGreater(len(session.journal), 8)

    def test_views_are_json_serializable(self):
        session = start("kobold", seed=3)

        def send(command):
            response = arena.apply_command(session, command)
            json.dumps(arena.session_view(session))
            return response

        _autoplay(session, send, max_steps=200)
        json.dumps(arena.session_view(session))


class ArenaRegistryTests(unittest.TestCase):
    def _start(self, registry, now=None):
        tile = arena.ENCOUNTERS["kobold"]["tile"]
        return registry.start(
            PROFILE, source="kobold", position_x=(tile[0] + 1) * TILE_SIZE + 24,
            position_y=tile[1] * TILE_SIZE + 24, deck_keys=DECK_KEYS, seed=1, now=now,
        )

    def test_one_battle_per_character(self):
        registry = arena.ArenaRegistry()
        session = self._start(registry)
        with self.assertRaises(arena.ArenaError):
            self._start(registry)
        self.assertIs(registry.active(7), session)

    def test_command_finishes_battle_and_releases_character(self):
        registry = arena.ArenaRegistry()
        session = self._start(registry)
        last = _autoplay(session, lambda command: registry.command(7, session.session_id, command))
        self.assertIsNotNone(last["finished"])
        self.assertEqual(last["finished"]["result"], "win")
        self.assertIsNone(registry.active(7))
        with self.assertRaises(arena.ArenaError):
            registry.command(7, session.session_id, {"type": "end_turn"})

    def test_idle_sessions_expire(self):
        registry = arena.ArenaRegistry(ttl_seconds=60)
        self._start(registry, now=0)
        self.assertIsNone(registry.active(7, now=61))
        self.assertIsNotNone(self._start(registry, now=61))


if __name__ == "__main__":
    unittest.main()
