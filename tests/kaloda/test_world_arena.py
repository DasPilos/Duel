import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pygame

from client.network import ServerError
from kaloda import settings
from kaloda.map_config import (
    ANCIENT_ENT_TILE,
    CARD_SHOP_BOUNDS,
    DUNGEON_ENTRANCE_BOUNDS,
    DUNGEON_ROOM_ORIGIN,
    DUNGEON_ROOM_SIZE,
    GRAVEYARD_BOUNDS,
    LIBRARY_BOUNDS,
    KOBOLD_RESPAWN_SECONDS,
    KOBOLD_SPAWN_TILE,
    RESPAWN_CRYSTAL,
    SUPPLIES_SHOP_BOUNDS,
    is_graveyard_tile,
    is_dungeon_entrance_tile,
    is_library_tile,
    is_card_shop_tile,
    TILE_SIZE as T,
    is_supplies_shop_tile,
)
from kaloda.world_map import terrain_payload
from kaloda.combat.talents import TALENT_TREES


class WorldArenaTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
        from kaloda.scenes.world_map_scene import WorldMapScene

        self.saved = []
        saved = self.saved
        self.xp_claims = []
        xp_claims = self.xp_claims
        self.xp_error = None
        test = self
        self.character = {"id": 1, "name": "Т", "level": 1, "type": "warrior", "hp": 80, "max_hp": 100}
        character = self.character

        class Client:
            def get_map_terrain(self):
                return terrain_payload()

            def save_character(self, character):
                saved.append(dict(character))

            def claim_npc_kill_xp(self, character_id, encounter_id, defeated_types, request_id):
                xp_claims.append((character_id, encounter_id, list(defeated_types), request_id))
                if test.xp_error:
                    raise ServerError(test.xp_error)
                return {"character": {"xp": 5}, "xp": 12}

            def claim_guild_quest_reward(self, character_id, quest_id, request_id):
                reward_coins = {
                    "kill_kobold": 10,
                    "kill_3_kobolds": 40,
                    "kill_ancient_ent": 160,
                    "kill_skeleton": 45,
                    "kill_necromancer": 100,
                    "clear_dungeon": 780,
                }[quest_id]
                character["coins"] = int(character.get("coins", 0) or 0) + reward_coins
                saved.append(dict(character))
                return {"character": dict(character), "reward_coins": reward_coins}

            def remove_inventory_item(self, character_id, item_id, quantity):
                return {}

            def get_supplies_shop_catalog(self):
                return []

            def get_card_shop_catalog(self):
                return [{"key": "universal_trap", "name": "Ловушка", "price": 300}]

            def get_dungeon_card_shop_catalog(self):
                return [
                    {"key": "universal_bonebreaker", "name": "Костолом", "price": 250},
                ]

            def get_card_collection(self, character_id):
                return []

            def list_item_catalog(self):
                return [{
                    "id": 1, "name": "Меч", "item_type": "weapon", "rarity": "common", "price": 120,
                    "description": "Простой клинок.", "can_use": False, "effects": {},
                }]

            def buy_card(self, character_id, card_key):
                return {"card": {"key": card_key}}

            def buy_dungeon_card(self, character_id, card_key):
                return {"card": {"key": card_key}}

        session = SimpleNamespace(character=self.character, client=None, selected_deck=None)
        session.client = Client()
        with patch("kaloda.scenes.world_map_scene.SHOW_OUTSIDE_CITY_LOCATIONS", True):
            self.scene = WorldMapScene(session)

    def tearDown(self):
        pygame.quit()

    def _approach_kobold(self):
        kx, ky = KOBOLD_SPAWN_TILE
        self.scene.player_x, self.scene.player_y = (kx - 1) * T + T // 2, ky * T + T // 2
        self.scene.update(0.016)
        self._finish_arena_draft()

    @staticmethod
    def _finish_walk(arena):
        """Игрок идёт по клеткам во времени: прокручиваем шаги до остановки."""
        for _ in range(60):
            if not arena.walk_path:
                break
            arena.update(arena.WALK_STEP_SECONDS)

    def _finish_arena_draft(self):
        battle = self.scene.arena.battle
        while battle.player_draft:
            battle.choose_starting_card(battle.engine.table[0].key)

    def test_kobold_stands_on_map_and_battle_starts_on_approach(self):
        from kaloda.combat.arena_battle import hex_distance_to_center

        kobold = next(obj for obj in self.scene.objects if obj["id"] == "kobold")
        self.assertEqual((kobold["tile_x"], kobold["tile_y"]), KOBOLD_SPAWN_TILE)

        self._approach_kobold()

        arena = self.scene.arena
        self.assertIsNotNone(arena)
        self.assertFalse(any(obj["id"] == "kobold" for obj in self.scene.objects))
        left, top, width, height = arena.battle.arena_rect
        self.assertEqual((width, height), (11, 11))
        self.assertEqual(arena.battle.player.hp, 80)
        self.assertTrue(arena.battle.in_arena(arena.battle.positions["player"]))
        self.assertTrue(arena.battle.in_arena(arena.battle.positions["enemy"]))
        self.assertTrue(arena.battle.in_arena(arena.battle.center_tile))
        self.assertFalse(arena.battle.occupied(arena.battle.center_tile))
        self.assertLessEqual(
            arena.battle.arena_radius - hex_distance_to_center(
                arena.battle.positions["player"], arena.battle.arena_center
            ),
            1,
        )
        self.scene.draw(pygame.display.get_surface())

    def test_ancient_ent_tree_at_requested_tile_starts_boss_battle(self):
        from kaloda.combat.arena_battle import ANCIENT_ENT_DECK, ANCIENT_ENT_NAME
        from kaloda.quests import quest_log_for

        tree = next(obj for obj in self.scene.objects if obj["id"] == "ancient_ent")
        self.assertEqual((tree["tile_x"], tree["tile_y"]), ANCIENT_ENT_TILE)
        self.assertEqual(ANCIENT_ENT_TILE, (42, 6))
        self.assertTrue(self.scene._check_collision(42.5 * T, 6.75 * T))
        self.scene.player_x = 41.5 * T
        self.scene.player_y = 6.5 * T
        self.scene._last_player_tile = (40, 6)
        quest_log_for(self.scene.session).accept("kill_ancient_ent")
        self.scene._check_kobold_encounter()

        battle = self.scene.arena.battle
        self._finish_arena_draft()
        self.assertEqual(battle.enemy.name, ANCIENT_ENT_NAME)
        self.assertEqual(battle.enemy.hp, 140)
        self.assertEqual(battle.enemy.mp, 50)
        self.assertEqual(battle.enemy_deck, ANCIENT_ENT_DECK)
        battle.roots["player"] = 2
        self.scene.draw(pygame.display.get_surface())

        battle.enemy.hp = 0
        battle.result = "win"
        self.scene.arena.done = True
        self.scene.update(0.016)
        self.assertTrue(self.scene.ancient_ent_defeated)
        self.assertFalse(self.scene.start_ancient_ent_battle())
        log = quest_log_for(self.scene.session)
        self.assertEqual(log.status("kill_ancient_ent"), "completed")
        window = self.scene.guild_window
        window.open()
        window.view = "quests"
        window.selected_id = "kill_ancient_ent"
        window._act()
        self.assertEqual(self.character["coins"], 160)
        self.assertEqual(log.status("kill_ancient_ent"), "available")

    def test_library_and_graveyard_regions_are_rendered_and_library_opens(self):
        library_x, library_y, library_width, library_height = LIBRARY_BOUNDS
        graveyard_x, graveyard_y, graveyard_width, graveyard_height = GRAVEYARD_BOUNDS
        self.assertTrue(is_library_tile(library_x, library_y))
        self.assertTrue(is_library_tile(library_x + library_width - 1,
                                        library_y + library_height - 1))
        self.assertTrue(is_graveyard_tile(graveyard_x, graveyard_y))
        self.assertTrue(is_graveyard_tile(graveyard_x + graveyard_width - 1,
                                          graveyard_y + graveyard_height - 1))
        self.assertFalse(is_graveyard_tile(graveyard_x + graveyard_width, graveyard_y))
        self.assertTrue(self.scene.is_city_tile(library_x, library_y))
        self.assertEqual(terrain_payload()["library_area"]["bounds"], list(LIBRARY_BOUNDS))
        self.assertNotIn("graveyard_area", terrain_payload())

        object_ids = {obj["id"] for obj in self.scene.objects}
        self.assertTrue({"library", "talent_tree", "skeleton", "necromancer"} <= object_ids)
        self.scene.player_x = (library_x + 2.5) * T
        self.scene.player_y = (library_y + 1.5) * T
        self.scene._last_player_tile = (library_x - 1, library_y)
        self.scene._check_kobold_encounter()
        self.assertTrue(self.scene.library_window.is_open)
        self.scene.draw(pygame.display.get_surface())
        self.assertGreater(len(self.scene.library_window.data["Карты"]), 0)
        self.assertGreater(len(self.scene.library_window.data["Предметы"]), 0)
        self.assertGreater(len(self.scene.library_window.data["Классы"]), 0)
        self.assertGreater(len(self.scene.library_window.data["Эффекты"]), 0)
        necromancer = next(entry for entry in self.scene.library_window.data["Существа"]
                           if entry["name"] == "Некромансер")
        self.assertIn("дистанцию 3–4 гекса", necromancer["description"])
        card_descriptions = "\n".join(
            entry["description"] for entry in self.scene.library_window.data["Карты"]
        )
        self.assertIn("Расчёт эффекта:", card_descriptions)
        self.assertIn("Лесной дух:", card_descriptions)
        effect_descriptions = "\n".join(
            entry["description"] for entry in self.scene.library_window.data["Эффекты"]
        )
        self.assertIn("урон реакции = ⌊урон × 0,5⌋", effect_descriptions)

    def test_talent_tree_building_opens_its_window(self):
        building = next(
            obj for obj in self.scene.objects if obj["id"] == "talent_tree"
        )
        self.scene.active_entity = building
        self.scene.player_x = building["x"]
        self.scene.player_y = building["y"]

        self.scene._trigger_active_action()
        self.assertTrue(self.scene.talent_tree_window.is_open)
        self.scene.draw(pygame.display.get_surface())

    def test_talent_descriptions_wrap_inside_their_buttons(self):
        window = self.scene.talent_tree_window
        window_rect = window._row_rects()[0]
        button_width = window._option_rects(window_rect)[0].width - 20
        for profession, tree in TALENT_TREES.items():
            with self.subTest(profession=profession):
                self.character["type"] = profession
                for entry in tree:
                    for option in entry.get("options", []):
                        font, lines = window._wrap_text(
                            option["description"], button_width
                        )
                        self.assertLessEqual(len(lines), 2)
                        self.assertTrue(
                            all(font.size(line)[0] <= button_width for line in lines)
                        )

    def test_dungeon_entry_fade_and_six_room_sequence(self):
        left, top, width, height = DUNGEON_ENTRANCE_BOUNDS
        self.assertTrue(is_dungeon_entrance_tile(left, top))
        self.assertTrue(is_dungeon_entrance_tile(left + width - 1, top + height - 1))
        self.assertFalse(is_dungeon_entrance_tile(left + width, top))
        tile = (left + 1, top + 1)
        self.scene.player_x = (tile[0] + 0.5) * T
        self.scene.player_y = (tile[1] + 0.5) * T
        self.scene._last_player_tile = tile
        self.scene.update(2.1)
        self.assertIsNone(self.scene.dungeon_room)
        self.assertEqual(self.scene.dungeon_fade_alpha, 8)
        self.scene.update(2.9)
        self.assertEqual(self.scene.dungeon_room, 1)
        self.assertIsNone(self.scene.arena)
        room_left, room_top = DUNGEON_ROOM_ORIGIN
        room_right = (room_left + 14) * T
        door_y = (room_top + 5) * T
        self.assertTrue(self.scene._check_dungeon_collision(room_right - 9, door_y))
        self.assertFalse(self.scene._try_dungeon_room_transition())
        self.scene.dungeon_cleared_rooms.add(1)
        self.scene.player_x = room_right - 9
        self.scene.player_y = door_y
        self.assertTrue(self.scene._try_dungeon_room_transition())
        self.assertEqual(self.scene.dungeon_room, 2)
        self.assertIsNone(self.scene.arena)

        actor_x, actor_y = self.scene._dungeon_actor_world_position()
        self.scene.player_x, self.scene.player_y = actor_x, actor_y
        self.scene._interact_dungeon()
        self.assertEqual(self.scene.dungeon_room_window.room, 2)
        self.assertTrue(self.scene.dungeon_room_window.is_open)
        self.scene.advance_dungeon_room()
        self.assertIn(2, self.scene.dungeon_completed_rooms)
        self.scene.player_x = room_right - 9
        self.scene.player_y = door_y
        self.assertTrue(self.scene._try_dungeon_room_transition())
        self.assertEqual(self.scene.dungeon_room, 3)

        self.scene.dungeon_cleared_rooms.add(3)
        self.scene.player_x = room_right - 9
        self.scene.player_y = door_y
        self.assertTrue(self.scene._try_dungeon_room_transition())
        self.assertEqual(self.scene.dungeon_room, 4)
        actor_x, actor_y = self.scene._dungeon_actor_world_position()
        self.scene.player_x, self.scene.player_y = actor_x, actor_y
        self.scene._interact_dungeon()
        self.assertIn(4, self.scene.dungeon_completed_rooms)
        self.scene.player_x = room_right - 9
        self.scene.player_y = door_y
        self.assertTrue(self.scene._try_dungeon_room_transition())
        self.assertEqual(self.scene.dungeon_room, 5)

        self.scene.dungeon_cleared_rooms.add(5)
        self.scene.player_x = room_right - 9
        self.scene.player_y = door_y
        self.assertTrue(self.scene._try_dungeon_room_transition())
        self.assertEqual(self.scene.dungeon_room, 6)
        actor_x, actor_y = self.scene._dungeon_actor_world_position()
        self.scene.player_x, self.scene.player_y = actor_x, actor_y
        self.scene._interact_dungeon()
        self.assertTrue(self.scene.dungeon_room_window.is_open)
        self.assertEqual(self.scene.dungeon_room_window.room, 6)
        self.assertEqual(DUNGEON_ROOM_ORIGIN, (64, 34))

    def test_dungeon_enemies_start_fights_and_unlock_the_exit_when_defeated(self):
        self.scene._enter_dungeon()
        self.scene.dungeon_room = 1
        self.scene.player_x, self.scene.player_y = self.scene._dungeon_actor_world_position()
        self.scene._update_dungeon_encounter()
        self.assertIsNotNone(self.scene.arena)
        self.assertEqual(len(self.scene.arena.battle.enemy_ids), 2)
        self.assertTrue(all(
            self.scene.arena.battle.fighters[eid].name.startswith("Скелет")
            for eid in self.scene.arena.battle.enemy_ids
        ))
        self.scene.arena.battle.result = "win"
        self.scene._finish_arena()
        self.assertEqual(self.scene.dungeon_room, 1)
        self.assertIn(1, self.scene.dungeon_cleared_rooms)
        self.assertFalse(self.scene._check_dungeon_collision(
            (DUNGEON_ROOM_ORIGIN[0] + DUNGEON_ROOM_SIZE[0]) * T - 9,
            (DUNGEON_ROOM_ORIGIN[1] + 5) * T,
        ))

    def test_dungeon_clear_quest_completes_after_treasure_exit(self):
        from kaloda.quests import QuestLog

        self.scene.session.quest_log = QuestLog()
        self.scene.session.quest_log.accept("clear_dungeon")

        self.scene.dungeon_room = 5
        self.scene.exit_dungeon()
        self.assertEqual(self.scene.session.quest_log.status("clear_dungeon"), "active")

        self.scene.dungeon_room = 6
        self.scene.dungeon_room_window.treasure_opened = True
        self.scene.exit_dungeon()
        self.assertEqual(self.scene.session.quest_log.status("clear_dungeon"), "completed")

    def test_card_shop_is_adjacent_to_supplies_and_opens_on_entry(self):
        left, top, width, _ = CARD_SHOP_BOUNDS
        self.assertTrue(is_card_shop_tile(left, top))
        self.assertFalse(is_card_shop_tile(left + width, top))
        self.scene.player_x = (left + 0.5) * T
        self.scene.player_y = (top + 0.5) * T
        self.scene._last_player_tile = (left - 1, top)
        self.scene._check_kobold_encounter()
        self.assertTrue(self.scene.card_shop_window.is_open)
        self.assertEqual(len(self.scene.card_shop_window.cards), 1)

    def test_graveyard_mobs_start_battles_with_configured_stats_and_decks(self):
        from kaloda.combat.arena_battle import (
            NECROMANCER_DECK,
            NECROMANCER_MAX_HP,
            NECROMANCER_MAX_MP,
            SKELETON_DECK,
            SKELETON_MAX_HP,
            SKELETON_MAX_MP,
        )

        self.assertTrue(self.scene.start_graveyard_battle("skeleton"))
        self._finish_arena_draft()
        skeleton_battle = self.scene.arena.battle
        self.assertEqual(skeleton_battle.enemy.hp, SKELETON_MAX_HP)
        self.assertEqual(skeleton_battle.enemy.mp, SKELETON_MAX_MP)
        self.assertEqual(skeleton_battle.enemy.temporary_dodge_chance_modifier, 20)
        self.assertEqual(skeleton_battle.enemy_deck, SKELETON_DECK)

        self.scene.arena = None
        self.assertTrue(self.scene.start_graveyard_battle("necromancer"))
        self._finish_arena_draft()
        necromancer_battle = self.scene.arena.battle
        self.assertEqual(necromancer_battle.enemy.hp, NECROMANCER_MAX_HP)
        self.assertEqual(necromancer_battle.enemy.mp, NECROMANCER_MAX_MP)
        self.assertEqual(necromancer_battle.enemy_deck, NECROMANCER_DECK)

    def test_necromancer_summons_use_distinct_skull_skeleton_and_dog_sprites(self):
        from kaloda.ui import arena_overlay

        self.assertTrue(self.scene.start_graveyard_battle("necromancer"))
        self._finish_arena_draft()
        battle = self.scene.arena.battle
        for kind in ("skull", "skeleton", "bone_dog"):
            self.assertTrue(battle._spawn_enemy_minion("enemy", kind))

        screen = pygame.Surface((settings.WIDTH, settings.HEIGHT))
        with (
            patch.object(arena_overlay, "draw_skull") as skull,
            patch.object(arena_overlay, "draw_skeleton") as skeleton,
            patch.object(arena_overlay, "draw_bone_dog") as bone_dog,
        ):
            self.scene.arena.draw_world(screen)

        skull.assert_called_once()
        skeleton.assert_called_once()
        bone_dog.assert_called_once()
        arena_overlay.draw_skull(screen, 100, 100, 48)
        arena_overlay.draw_skeleton(screen, 160, 100, 48)
        arena_overlay.draw_bone_dog(screen, 220, 100, 48)

    def test_enemy_walk_is_animated_between_hexes(self):
        self.assertTrue(self.scene.start_graveyard_battle("skeleton"))
        self._finish_arena_draft()
        controller = self.scene.arena
        battle = controller.battle
        enemy = battle.enemy_ids[0]
        destination_tile = next(iter(battle.reachable_tiles(enemy)))
        path = battle.movement_path(enemy, destination_tile)
        self.assertTrue(path)

        self.assertTrue(battle._walk_unit_to(enemy, path[0]))
        destination = controller.tile_center(battle.positions[enemy])
        controller.update(controller.WALK_STEP_SECONDS / 2)

        visual_position = controller._unit_world_position(enemy)
        self.assertNotEqual(visual_position, destination)
        self.assertTrue(controller._actor_movement_pending())
        controller.draw_world(pygame.Surface((settings.WIDTH, settings.HEIGHT)))

        controller.update(controller.WALK_STEP_SECONDS / 2)
        self.assertEqual(controller._unit_world_position(enemy), destination)
        self.assertFalse(controller._actor_movement_pending())

    def test_arena_tooltip_lists_corrosion_and_temporary_vulnerability(self):
        self.assertTrue(self.scene.start_graveyard_battle("skeleton"))
        self._finish_arena_draft()
        battle = self.scene.arena.battle
        battle.temporary_damage_taken["enemy"] = [[20, 2]]
        battle.arena_corrosion["enemy"] = [15, 4]

        lines = [text for text, _ in self.scene.arena._unit_lines("enemy")]

        self.assertIn("  • Уязвимость +20%: 2 х.", lines)
        self.assertIn("  • Коррозия: 15 урона за 4 х.", lines)

    def test_graveyard_kill_quests_pay_the_configured_rewards(self):
        from kaloda.quests import quest_log_for

        log = quest_log_for(self.scene.session)
        window = self.scene.guild_window
        for quest_id, mob_id, reward in (
            ("kill_skeleton", "skeleton", 45),
            ("kill_necromancer", "necromancer", 100),
        ):
            log.accept(quest_id)
            self.assertTrue(self.scene.start_graveyard_battle(mob_id))
            self._finish_arena_draft()
            self.scene.arena.battle.result = "win"
            self.scene.arena.done = True
            self.scene.update(0.016)
            self.assertEqual(log.status(quest_id), "completed")

            coins_before = int(self.character.get("coins", 0) or 0)
            window.open()
            window.view = "quests"
            window.selected_id = quest_id
            window._act()
            self.assertEqual(self.character["coins"], coins_before + reward)
            self.assertEqual(log.status(quest_id), "available")

    def test_forest_spirit_can_be_summoned_and_rendered(self):
        from kaloda.combat.card_database import cards_for_type

        self.character["type"] = "archer"
        self.assertTrue(self.scene.start_graveyard_battle("skeleton"))
        self._finish_arena_draft()
        arena = self.scene.arena
        battle = arena.battle
        card = next(card for card in cards_for_type("archer")
                    if card.key == "archer_forest_spirit")
        battle.player.unique_resource_current = battle.player.unique_resource_max
        battle.engine.hands["player"] = [card]

        arena._play(card, battle.summon_tiles()[0])
        spirit_id = next(uid for uid, summon in battle.summons.items()
                         if summon["kind"] == "forest_spirit")
        battle._summon_act(spirit_id)
        self.scene.draw(pygame.display.get_surface())

    def test_arena_b_key_burns_selected_card(self):
        self._approach_kobold()
        arena = self.scene.arena
        battle = arena.battle
        card = battle.engine.hands["player"][0]
        battle.player.unique_resource_current = 0
        arena.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_b))
        card_rect = arena.hand_rects()[0][1]
        arena.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=card_rect.center,
        ))
        arena.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_b))

        self.assertTrue(battle.engine.burned_this_turn["player"])
        self.assertNotIn(card, battle.engine.hands["player"])

    def test_arena_displays_miss_and_critical_markers(self):
        self._approach_kobold()
        arena = self.scene.arena
        messages = []
        with patch.object(self.scene, "_add_floating_message",
                          side_effect=lambda text, *args: messages.append(text)):
            arena._float_combat_outcome({
                "target": "enemy",
                "hit_results": [
                    {"dodged": True, "damage": 0},
                    {"critical": True, "damage": 5},
                ],
            })

        self.assertEqual(messages, ["ПРОМАХ", "КРИТ!"])

    def test_win_removes_kobold_until_respawn(self):
        self._approach_kobold()
        battle = self.scene.arena.battle
        battle.enemy.hp = 0
        battle.result = "win"
        self.scene.arena.done = True
        self.scene.update(0.016)

        self.assertIsNone(self.scene.arena)
        self.assertFalse(any(obj["id"] == "kobold" for obj in self.scene.objects))
        self.assertEqual(self.saved[-1]["hp"], 80)
        self.scene.kobold_respawn_at = time.time() - 1
        self.scene.update(0.016)
        self.assertTrue(any(obj["id"] == "kobold" for obj in self.scene.objects))
        self.assertGreater(KOBOLD_RESPAWN_SECONDS, 0)

    def test_battle_items_heal_restore_mana_damage_and_cleanse_one_effect(self):
        self._approach_kobold()
        battle = self.scene.arena.battle
        battle.player.hp -= 30
        hp = battle.player.hp
        self.assertEqual(battle.use_battle_item(4), (True, "Предмет использован"))
        self.assertEqual(battle.player.hp, hp + 20)

        battle.player.mp = max(0, battle.player.max_mp - 12)
        battle.round += 2
        available, message = battle.can_use_battle_item(5)
        self.assertFalse(available)
        self.assertIn("раз в три хода", message)
        battle.round += 1
        self.assertTrue(battle.use_battle_item(5)[0])
        self.assertEqual(battle.player.mp, battle.player.max_mp)

        battle.round += 3
        enemy = battle.enemy
        hp = enemy.hp
        self.assertTrue(battle.use_battle_item(6, battle.target)[0])
        self.assertEqual(enemy.hp, hp - 9)

        battle.round += 3
        battle.player.mp = 30
        battle.engine.bleeds["player"].append({"damage": 2, "remaining": 2})
        battle.engine.bleeds["player"].append({"damage": 3, "remaining": 2})
        self.assertTrue(battle.use_battle_item(52)[0])
        self.assertEqual(len(battle.engine.bleeds["player"]), 1)
        self.assertEqual(battle.player.mp, 10)

    def test_shop_zone_opens_on_entry_and_battle_item_cooldown_is_three_rounds(self):
        left, top, width, height = SUPPLIES_SHOP_BOUNDS
        self.assertTrue(is_supplies_shop_tile(left, top))
        self.assertFalse(is_supplies_shop_tile(left + width, top))
        self.scene.player_x = (left + 0.5) * T
        self.scene.player_y = (top + 0.5) * T
        self.scene._last_player_tile = (left - 1, top)
        self.scene._check_kobold_encounter()
        self.assertTrue(self.scene.supplies_shop_window.is_open)
        self.character["coins"] = 200
        window = self.scene.supplies_shop_window
        rendered = []

        class RecordingFont:
            def __init__(self, font):
                self.font = font

            def render(self, text, *args, **kwargs):
                rendered.append(text)
                return self.font.render(text, *args, **kwargs)

        window.small_font = RecordingFont(window.small_font)
        self.scene.draw(pygame.display.get_surface())
        self.assertIn("У вас: 200 монет", rendered)

        self._approach_kobold()
        controller = self.scene.arena
        battle = controller.battle
        battle.player.hp = battle.player.max_hp - 20
        battle.last_battle_item_round = battle.round
        controller._use_battle_item({"item_id": 4, "quantity": 1, "name": "Зелье"})
        self.assertEqual(battle.player.hp, battle.player.max_hp - 20)
        self.assertIn("раз в три хода", controller.notice)
        battle.last_battle_item_round = battle.round - 3
        controller._use_battle_item({"item_id": 4, "quantity": 1, "name": "Зелье"})
        self.assertEqual(battle.player.hp, battle.player.max_hp)
    def test_hex_centers_edges_and_clicks_match_at_different_zoom_levels(self):
        import math
        from kaloda.combat.arena_battle import hex_neighbors

        self._approach_kobold()
        arena = self.scene.arena
        left, top, width, height = arena.battle.arena_rect
        self.assertEqual((width, height), (11, 11))
        for zoom in (0.75, 1.0, 1.5):
            self.scene.zoom = zoom
            for y in range(top, top + height):
                for x in range(left, left + width):
                    tile = (x, y)
                    center = arena.tile_center(tile)
                    screen_pos = self.scene.world_to_screen(*center)
                    self.assertEqual(arena.mouse_tile(screen_pos), tile)
                    vertices = arena.tile_polygon(tile)
                    self.assertEqual(len(vertices), 6)
                    radii = [math.dist(center, point) for point in vertices]
                    self.assertAlmostEqual(min(radii), max(radii))
            tile = (left + 5, top + 5)
            vertices = arena.tile_polygon(tile)
            cx, cy = arena.tile_center(tile)
            for edge, neighbor in enumerate(hex_neighbors(tile)):
                a, b = vertices[edge], vertices[(edge + 1) % 6]
                mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
                for factor, expected in ((0.9, tile), (1.1, neighbor)):
                    point = (cx + (mx - cx) * factor, cy + (my - cy) * factor)
                    self.assertEqual(arena.mouse_tile(self.scene.world_to_screen(*point)), expected)
            arena.battle.moved = False
            arena.mode = "move"
            target = (left + 3, arena.battle.positions["player"][1])
            arena.battle.positions["player"] = (left, target[1])
            arena.handle_event(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, button=1,
                pos=self.scene.world_to_screen(*arena.tile_center(target)),
            ))
            self._finish_walk(arena)
            self.assertEqual(arena.battle.positions["player"], target)
            self.assertTrue(arena.battle.moved)
            self.scene.draw(pygame.display.get_surface())

    def test_summon_click_uses_hex_position_and_does_not_resize_arena(self):
        from kaloda.combat.card_database import cards_for_type
        from kaloda.combat.arena_battle import hex_distance

        self.character["type"] = "mage"
        self._approach_kobold()
        arena = self.scene.arena
        battle = arena.battle
        original_rect = battle.arena_rect
        card = next(card for card in cards_for_type("mage") if card.effect_type == "mage_golem")
        battle.engine.hands["player"] = [card]
        battle.player.mp = battle.player.max_mp
        arena.mode = "cards"
        for _ in range(2):
            arena.handle_event(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, button=1, pos=arena.hand_rects()[0][1].center,
            ))
        self.assertTrue(arena.targeting)
        target = battle.summon_tiles()[-1]
        self.assertLessEqual(hex_distance(battle.positions["player"], target), 2)
        arena.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1,
            pos=self.scene.world_to_screen(*arena.tile_center(target)),
        ))
        sid, = battle.summons
        self.assertEqual(battle.positions[sid], target)
        self.assertEqual(battle.arena_rect, original_rect)
        self.assertNotIn(card, battle.engine.hands["player"])
        self.scene.draw(pygame.display.get_surface())

    def _end_arena(self, result, kill_enemies=True):
        battle = self.scene.arena.battle
        if kill_enemies:
            for enemy_id in battle.enemy_ids:
                battle.fighters[enemy_id].hp = 0
        battle.result = result
        self.scene.arena.done = True
        self.scene.update(0.016)

    def test_victory_claims_kill_xp_once_and_saves_the_hero(self):
        from kaloda.quests import quest_log_for

        quest_log_for(self.scene.session).accept("kill_kobold")
        self._approach_kobold()
        request_id = self.scene.arena_reward_request_id

        self._end_arena("win")

        self.assertEqual(self.xp_claims, [(1, "kobold", ["kobold"], request_id)])
        self.assertEqual(self.character["xp"], 5)
        self.assertEqual(self.character["hp"], max(1, self.saved[-1]["hp"]))
        self.assertEqual(quest_log_for(self.scene.session).status("kill_kobold"), "completed")
        self.assertIsNone(self.scene.arena_reward_request_id)

    def test_camp_victory_counts_every_kobold_for_quests(self):
        from kaloda.quests import quest_log_for

        quest_log_for(self.scene.session).accept("kill_3_kobolds")
        self.scene.start_camp_battle("kobold_camp")
        self._finish_arena_draft()

        self._end_arena("win")

        self.assertEqual(self.xp_claims[0][2], ["kobold", "kobold", "kobold"])
        self.assertEqual(quest_log_for(self.scene.session).status("kill_3_kobolds"), "completed")

    def test_defeat_pays_no_experience(self):
        self._approach_kobold()

        self._end_arena("loss", kill_enemies=False)

        self.assertEqual(self.xp_claims, [])
        self.assertEqual(self.character["hp"], 100)

    def test_experience_server_error_is_reported_but_the_battle_still_ends(self):
        self.xp_error = "сервер занят"
        self._approach_kobold()

        self._end_arena("win")

        self.assertIsNone(self.scene.arena)
        self.assertIn("Опыт не начислен", self.scene.action_notice)
        self.assertNotIn("xp", self.character)

    def test_npc_xp_types_check_specific_names_first(self):
        xp_type = self.scene._npc_xp_type
        self.assertEqual(xp_type("Король скелетов"), "skeleton_king")
        self.assertEqual(xp_type("Скелет-страж"), "skeleton_guard")
        self.assertEqual(xp_type("Скелет"), "skeleton")
        self.assertEqual(xp_type("Кобольд 2"), "kobold")
        self.assertIsNone(xp_type("Волк"))

    def test_loss_respawns_player_at_crystal_with_full_health(self):
        self._approach_kobold()
        battle = self.scene.arena.battle
        battle.player.hp = 0
        battle.result = "loss"
        self.scene.arena.done = True
        self.scene.update(0.016)

        self.assertIsNone(self.scene.arena)
        self.assertEqual((self.scene.player_x, self.scene.player_y), tuple(map(float, RESPAWN_CRYSTAL["approach_pos"])))
        self.assertEqual(self.character["hp"], 100)
        self.assertTrue(any(obj["id"] == "kobold" for obj in self.scene.objects))

    def test_arena_buttons_move_and_end_turn(self):
        self._approach_kobold()
        arena = self.scene.arena
        battle = arena.battle
        start = battle.positions["player"]
        target = (start[0] + (1 if start[0] == battle.arena_rect[0] else -1), start[1])

        click = lambda pos: arena.handle_event(SimpleNamespace(type=pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
        click(arena.buttons["move"].center)
        self.assertEqual(arena.mode, "move")
        click(self.scene.world_to_screen(*self.scene.arena.tile_center(target)))
        self._finish_walk(arena)
        self.assertEqual(battle.positions["player"], target)
        self.assertTrue(battle.moved)

        click(arena.buttons["cards"].center)
        playable = [(card, rect) for card, rect in arena.hand_rects() if battle.can_play_card(card)]
        if playable:
            card, rect = playable[0]
            click(rect.center)
            self.assertIs(arena.selected_card, card)
            self.scene.draw(pygame.display.get_surface())
            hand_size = len(battle.engine.hands["player"])
            card_rect = lambda: arena.hand_rects()[[c for c, _ in arena.hand_rects()].index(card)][1]
            click(card_rect().center)
            self.assertTrue(arena.targeting, "2-й клик по карте начинает выбор цели")
            self.assertEqual(battle.cards_played, 0)
            self.assertIn(card, battle.engine.hands["player"])
            self.scene.draw(pygame.display.get_surface())
            arena.handle_event(SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_s))
            self.assertFalse(arena.targeting)
            self.assertIsNone(arena.selected_card)
            self.assertIn(card, battle.engine.hands["player"], "отмена по S не тратит карту")
            click(card_rect().center)
            click(card_rect().center)
            target = arena.valid_targets()[0]
            click(self.scene.world_to_screen(*arena.tile_center(battle.positions[target])))
            self.assertEqual(battle.cards_played, 1)
            self.assertEqual(len(battle.engine.hands["player"]), hand_size - 1)
        else:
            click(arena.hand_rects()[0][1].center)
            self.assertIsNone(arena.selected_card)
            self.assertIsNotNone(arena.notice)
        self.scene.draw(pygame.display.get_surface())

        self.assertEqual(battle.round, 1)
        click(arena.buttons["end"].center)
        for _ in range(60):
            self.scene.update(0.05)
            if battle.round >= 2:
                break
        self.assertEqual(battle.round, 2)
        self.assertEqual(battle.active_side, "player")

    def test_switching_arena_modes_clears_card_targeting_state(self):
        self._approach_kobold()
        arena = self.scene.arena
        arena.mode = "move"
        arena.selected_card = arena.battle.engine.hands["player"][0]
        arena.targeting = True
        arena.transfer_target = "ally"

        arena.handle_event(SimpleNamespace(
            type=pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=arena.buttons["cards"].center,
        ))

        self.assertEqual(arena.mode, "cards")
        self.assertFalse(arena.targeting)
        self.assertIsNone(arena.selected_card)
        self.assertIsNone(arena.transfer_target)

        arena.targeting = True
        arena._click_target((0, 0))
        self.assertFalse(arena.targeting)
        self.assertIn("сброшен", arena.notice)

    def test_arena_buttons_are_reordered_and_teleport_requires_confirmation(self):
        self._approach_kobold()
        arena = self.scene.arena
        order = [key for key, _ in sorted(arena.buttons.items(), key=lambda item: item[1].top)]
        self.assertEqual(order, ["teleport", "inventory", "move", "cards", "end"])

        click = lambda rect: arena.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center,
        ))
        click(arena.buttons["teleport"])
        self.assertTrue(arena.teleport_confirmation)
        self.assertIsNone(arena.pending)
        self.assertFalse(arena.battle.teleport_pending)
        self.scene.draw(pygame.display.get_surface())

        click(arena.buttons["move"])
        self.assertTrue(arena.teleport_confirmation)
        self.assertIsNone(arena.pending)

        click(arena.teleport_cancel_rect)
        self.assertFalse(arena.teleport_confirmation)
        self.assertIsNone(arena.pending)
        self.assertFalse(arena.battle.teleport_pending)

        click(arena.buttons["teleport"])
        arena.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertFalse(arena.teleport_confirmation)
        self.assertIsNone(arena.pending)

        click(arena.buttons["teleport"])
        click(arena.teleport_confirm_rect)
        self.assertFalse(arena.teleport_confirmation)
        self.assertEqual(arena.pending, "teleport")
        self.assertFalse(arena.battle.teleport_pending)

    def test_guild_zone_opens_quest_menu_and_quest_pays_coins(self):
        from kaloda.map_config import GUILD_BOUNDS
        from kaloda.quests import quest_log_for

        gx, gy, _, _ = GUILD_BOUNDS
        self.scene.player_x, self.scene.player_y = (gx + 2) * T + T // 2, (gy - 2) * T + T // 2
        self.scene.update(0.016)
        self.assertFalse(self.scene.guild_window.is_open)
        self.scene.player_x, self.scene.player_y = (gx + 2) * T + T // 2, gy * T + T // 2
        self.scene.update(0.016)
        window = self.scene.guild_window
        self.assertTrue(window.is_open)
        self.scene.draw(pygame.display.get_surface())

        click = lambda pos: self.scene.handle_event(SimpleNamespace(type=pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
        click(window.quests_button.center)
        self.assertEqual(window.view, "quests")
        window.selected_id = "kill_kobold"
        click(window.action_button.center)
        log = quest_log_for(self.scene.session)
        self.assertEqual(log.status("kill_kobold"), "active")
        self.scene.draw(pygame.display.get_surface())
        window.close()

        self._approach_kobold()
        self.scene.arena.battle.result = "win"
        self.scene.arena.done = True
        self.scene.update(0.016)
        self.assertEqual(log.status("kill_kobold"), "completed")

        coins = int(self.character.get("coins", 0) or 0)
        window.open()
        window.view = "quests"
        window.selected_id = "kill_kobold"
        click(window.action_button.center)
        self.assertEqual(self.scene.session.character["coins"], coins + 10)
        self.assertEqual(self.saved[-1]["coins"], coins + 10)
        self.assertEqual(log.status("kill_kobold"), "available")

    def test_kobold_camp_starts_battle_against_three_kobolds(self):
        from kaloda.map_config import KOBOLD_CAMP_TILE
        from kaloda.quests import quest_log_for

        camp = next(obj for obj in self.scene.objects if obj["id"] == "kobold_camp")
        self.assertEqual((camp["tile_x"] + 1, camp["tile_y"] + 1), KOBOLD_CAMP_TILE)
        log = quest_log_for(self.scene.session)
        log.accept("kill_3_kobolds")

        cx, cy = KOBOLD_CAMP_TILE
        self.scene.player_x, self.scene.player_y = (cx - 2) * T + T // 2, cy * T + T // 2
        self.scene.update(0.016)
        arena = self.scene.arena
        self.assertIsNotNone(arena)
        self.assertEqual(len(arena.battle.enemy_ids), 3)
        self.assertEqual(arena.battle.arena_rect[2:], (15, 15))
        self.assertFalse(any(obj["id"] == "kobold_camp" for obj in self.scene.objects))
        self.assertTrue(arena.draw_toasts)
        self.scene.draw(pygame.display.get_surface())

        arena.battle.result = "win"
        arena.done = True
        self.scene.update(0.016)
        self.assertEqual(log.status("kill_3_kobolds"), "completed")
        self.assertFalse(any(obj["id"] == "kobold_camp" for obj in self.scene.objects))
        self.scene.camp_respawn_at = time.time() - 1
        self.scene.update(0.016)
        self.assertTrue(any(obj["id"] == "kobold_camp" for obj in self.scene.objects))

    def test_forest_camp_battle_has_ally_archer(self):
        from kaloda.combat.arena_battle import ALLY_ARCHER_NAME
        from kaloda.map_config import KOBOLD_CAMP2_TILE, is_forest_tile

        self.assertTrue(is_forest_tile(*KOBOLD_CAMP2_TILE))
        camp = next(obj for obj in self.scene.objects if obj["id"] == "kobold_camp_2")
        self.assertEqual((camp["tile_x"] + 1, camp["tile_y"] + 1), KOBOLD_CAMP2_TILE)
        cx, cy = KOBOLD_CAMP2_TILE
        self.scene.player_x, self.scene.player_y = (cx - 2) * T + T // 2, cy * T + T // 2
        self.scene.update(0.016)
        arena = self.scene.arena
        self.assertIsNotNone(arena)
        battle = arena.battle
        self.assertEqual(len(battle.enemy_ids), 3)
        self.assertEqual(battle.ally_ids, ["ally"])
        self.assertEqual(battle.arena_rect[2:], (17, 17))
        ally = battle.fighters["ally"]
        self.assertEqual((ally.name, ally.profession_type), (ALLY_ARCHER_NAME, "archer"))
        self.assertTrue(battle.in_arena(battle.positions["ally"]))
        self.assertLessEqual(battle.dist("player", "ally"), 2)
        battle.engine._add_buff("player", 3, damage_percent=25)
        battle.engine.mage_stuns["enemy"] = 2
        with battle._as_player("ally"):
            battle.engine._add_buff("player", 2, incoming_damage_percent=20)
        from unittest.mock import patch

        with patch.object(battle, "effect_entries_for", wraps=battle.effect_entries_for) as effects:
            arena._draw_unit_effects(pygame.display.get_surface())
        self.assertEqual(
            [call.args[0] for call in effects.call_args_list],
            ["player", "ally", *battle.enemy_ids],
        )
        self.scene.draw(pygame.display.get_surface())

        battle.fighters["enemy_2"].hp = 0
        battle.fighters["ally"].hp = 0
        battle._check_result()
        self.assertEqual(battle.arena_rect[2:], (17, 17), "потери не сжимают поле во время боя")
        arena.battle.result = "win"
        arena.done = True
        self.scene.update(0.016)
        self.assertFalse(any(obj["id"] == "kobold_camp_2" for obj in self.scene.objects))
        self.assertTrue(any(obj["id"] == "kobold_camp" for obj in self.scene.objects))
        self.scene.camp2_respawn_at = time.time() - 1
        self.scene.update(0.016)
        self.assertTrue(any(obj["id"] == "kobold_camp_2" for obj in self.scene.objects))


if __name__ == "__main__":
    unittest.main()
