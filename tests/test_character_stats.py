import unittest

import pygame

from combat.character_stats import adjust_stats, calculate_carry_capacity, calculate_max_hp
from combat.fighter import Fighter
from core import settings
from core.carry_weight import GREEN, NEUTRAL, RED, YELLOW, carried_weight_kg, load_color, movement_speed_multiplier
from scenes.tavern_scene import TavernScene
from ui.character_card import CharacterCard
from ui.character_profile import (
    combat_speed_values,
    derived_values,
    displayed_hp_values,
    normalize_character_profile,
    profile_from_fighter,
)
from ui.character_profile_overlay import CharacterProfileOverlay
from ui.tavern_shop import TavernShop


class CharacterStatTests(unittest.TestCase):
    def test_carry_capacity_uses_strength_and_endurance(self):
        self.assertEqual(calculate_carry_capacity(6, 4), 42)
        self.assertEqual(calculate_carry_capacity(3, 3), 24)

    def test_carry_load_colors_and_movement_thresholds(self):
        self.assertEqual(load_color(30, 100), GREEN)
        self.assertEqual(movement_speed_multiplier(45, 100), 0.7)
        self.assertEqual(movement_speed_multiplier(60, 100), 0.7)
        self.assertEqual(load_color(61, 100), YELLOW)
        self.assertEqual(movement_speed_multiplier(61, 100), 0.5)
        self.assertEqual(load_color(80, 100), YELLOW)
        self.assertEqual(movement_speed_multiplier(80, 100), 0.5)
        self.assertEqual(load_color(81, 100), RED)
        self.assertEqual(movement_speed_multiplier(81, 100), 0.3)
        self.assertEqual(load_color(45, 100), NEUTRAL)

    def test_carried_weight_sums_bag_and_equipment_once(self):
        inventory = [{"weight": 2.5, "quantity": 2}, {"weight": 1, "quantity": 3}]
        equipment = {
            "weapon": {"weight": 4},
            "shield": {"weight": 4, "_two_handed_shadow": True},
            "body": {"weight": 5},
        }
        self.assertEqual(carried_weight_kg(inventory, equipment), 17)

    def test_max_hp_formula_matches_level_and_endurance(self):
        self.assertEqual(calculate_max_hp(1, 5), 60)
        self.assertEqual(calculate_max_hp(3, 7), 84)

    def test_player_max_hp_is_consistent_between_world_server_and_card(self):
        from combat.world_stats import get_world_max_hp
        stats = {"strength": 3, "agility": 3, "intuition": 3, "wisdom": 3,
                 "intellect": 3, "endurance": 5}
        fighter = Fighter("Игрок", level=1)
        fighter.stats.update(stats)
        fighter.recalculate_parameters()
        self.assertEqual(fighter.max_hp, calculate_max_hp(1, 5))
        self.assertEqual(get_world_max_hp(fighter), calculate_max_hp(1, 5))
        server_profile = normalize_character_profile({
            "hp": 60, "max_hp": 60, "stats": stats,
        })
        self.assertEqual(displayed_hp_values(server_profile), (60, 60))

    def test_card_recalculates_stale_saved_max_values_like_combat(self):
        from combat.world_stats import get_world_max_hp, get_world_max_mana
        stats = {"strength": 5, "agility": 5, "intuition": 5, "wisdom": 5,
                 "intellect": 5, "endurance": 5}
        stale_profile = normalize_character_profile({
            "hp": 30, "max_hp": 30, "mp": 15, "max_mp": 15, "stats": stats,
        })
        fighter = Fighter("Игрок", level=1)
        fighter.stats.update(stats)
        self.assertEqual(stale_profile["max_hp"], get_world_max_hp(fighter))
        self.assertEqual(stale_profile["max_mp"], get_world_max_mana(fighter))
        self.assertEqual(stale_profile["max_mp"], 30)

    def test_mana_formula_is_single_source_for_combat_and_profile(self):
        from combat import character_stats
        from combat.world_stats import MANA_PER_INTELLECT
        self.assertEqual(character_stats.MANA_PER_INTELLECT, MANA_PER_INTELLECT)
        self.assertEqual(character_stats.calculate_max_mana(5), MANA_PER_INTELLECT * 5)


    def test_profile_model_normalizes_fighter_and_derived_values(self):
        fighter = Fighter("Тест")
        profile = normalize_character_profile(profile_from_fighter(fighter))

        self.assertEqual(profile["stats"], fighter.stats)
        self.assertEqual(derived_values(profile), {
            "Урон": 3,
            "Уворот": "15%",
            "Крит": "15% × 150%",
            "Маг Урон": 3,
            "HP": 36,
        })

    def test_profile_recovers_weight_when_server_snapshot_has_zero(self):
        profile = normalize_character_profile({
            "id": 1,
            "name": "Носильщик",
            "carried_weight_kg": 0,
            "inventory": {"0": {"weight": 2.5, "quantity": 2}},
            "equipment": {
                "weapon": {"weight": 4},
                "shield": {"weight": 4, "_two_handed_shadow": True},
            },
        })

        self.assertEqual(profile["carried_weight_kg"], 9.0)

    def test_endurance_cannot_increase_manually(self):
        state = adjust_stats(
            {"strength": 5, "agility": 5, "intuition": 5, "endurance": 5},
            6,
            20,
            25,
            1,
            "endurance",
            1,
        )

        self.assertIsNone(state)

    def test_stat_decrease_cannot_go_below_minimum(self):
        state = adjust_stats(
            {"strength": 3, "agility": 5, "intuition": 5, "endurance": 5},
            6,
            25,
            25,
            1,
            "strength",
            -1,
        )

        self.assertIsNone(state)

    def test_card_and_fighter_produce_matching_stat_state(self):
        pygame.init()
        try:
            fighter = Fighter("Тест")
            card = CharacterCard()
            card.sync({
                "name": "Тест",
                "level": fighter.level,
                "hp": fighter.hp,
                "max_hp": fighter.max_hp,
                "stats": fighter.stats,
                "stat_points": fighter.stat_points,
            })

            self.assertTrue(fighter.add_stat("strength"))
            self.assertTrue(card.adjust_stat("strength", 1))
            self.assertEqual(card.data["stats"], fighter.stats)
            self.assertEqual(card.data["stat_points"], fighter.stat_points)
            self.assertEqual(card.data["hp"], fighter.hp)
            self.assertEqual(card.data["max_hp"], fighter.max_hp)
        finally:
            pygame.quit()

    def test_character_card_shows_hp_and_mp_labels_above_bars(self):
        pygame.init()
        try:
            card = CharacterCard()
            rendered = []
            real_font = card.small_font

            class SpyFont:
                def render(self, text, *args, **kwargs):
                    rendered.append(text)
                    return real_font.render(text, *args, **kwargs)

                def get_height(self):
                    return real_font.get_height()

            card.small_font = SpyFont()
            surface = pygame.Surface((400, 300))
            card._draw_resource(surface, 10, 100, 280, 11, "HP", 163, 185, (210, 80, 80))
            card._draw_resource(surface, 10, 140, 280, 11, "MP", 7, 20, (60, 140, 220))

            self.assertIn("HP 163/185", rendered)
            self.assertIn("MP 7/20", rendered)
        finally:
            pygame.quit()

    def test_character_card_shows_attack_and_move_speed_under_carry(self):
        pygame.init()
        try:
            card = CharacterCard()
            rendered = []
            real_font = card.small_font

            class SpyFont:
                def render(self, text, *args, **kwargs):
                    rendered.append(text)
                    return real_font.render(text, *args, **kwargs)

                def get_height(self):
                    return real_font.get_height()

            card.small_font = SpyFont()
            fighter = Fighter("Тест")
            profile = normalize_character_profile(profile_from_fighter(fighter))
            expected = combat_speed_values(profile)
            surface = pygame.Surface((settings.CHARACTER_CARD_WIDTH, settings.CHARACTER_CARD_HEIGHT), pygame.SRCALPHA)
            frame = pygame.Rect(0, 0, settings.CHARACTER_CARD_WIDTH, settings.CHARACTER_CARD_HEIGHT)
            card.draw(surface, frame, profile=profile)

            self.assertIn(f"Скорость атаки: {expected['attack_seconds']:g} с", rendered)
            self.assertIn(f"Скорость передвижения: {expected['move_speed']} px/с", rendered)
        finally:
            pygame.quit()

    def test_equipment_movement_speed_bonus_is_shown_in_green(self):
        pygame.init()
        try:
            card = CharacterCard()
            rendered = []
            real_font = card.small_font

            class SpyFont:
                def render(self, text, *args, **kwargs):
                    rendered.append(text)
                    return real_font.render(text, *args, **kwargs)

                def get_height(self):
                    return real_font.get_height()

                def size(self, text):
                    return real_font.size(text)

            card.small_font = SpyFont()
            fighter = Fighter("Тест")
            profile = normalize_character_profile(profile_from_fighter(fighter))
            profile["equipment_bonuses"] = {"agility": 4}
            expected = combat_speed_values(profile)
            self.assertEqual(expected["move_speed_bonus"], 20)
            surface = pygame.Surface((settings.CHARACTER_CARD_WIDTH, settings.CHARACTER_CARD_HEIGHT), pygame.SRCALPHA)
            frame = pygame.Rect(0, 0, settings.CHARACTER_CARD_WIDTH, settings.CHARACTER_CARD_HEIGHT)
            card.draw(surface, frame, profile=profile)

            self.assertIn(f"Скорость передвижения: {expected['move_speed']} px/с", rendered)
            self.assertIn(" +20", rendered)
        finally:
            pygame.quit()

    def test_mob_card_shows_attack_and_move_speed_without_carry(self):
        pygame.init()
        try:
            card = CharacterCard()
            rendered = []
            real_font = card.small_font

            class SpyFont:
                def render(self, text, *args, **kwargs):
                    rendered.append(text)
                    return real_font.render(text, *args, **kwargs)

                def get_height(self):
                    return real_font.get_height()

                def size(self, text):
                    return real_font.size(text)

            card.small_font = SpyFont()
            fighter = Fighter("Скелет", level=1)
            fighter.stats.update({"strength": 3, "agility": 3, "intuition": 3, "wisdom": 3,
                                  "intellect": 3, "endurance": 4})
            profile = profile_from_fighter(fighter)
            expected = combat_speed_values(normalize_character_profile(profile))
            surface = pygame.Surface((settings.CHARACTER_CARD_WIDTH, settings.CHARACTER_CARD_HEIGHT), pygame.SRCALPHA)
            frame = pygame.Rect(0, 0, settings.CHARACTER_CARD_WIDTH, settings.CHARACTER_CARD_HEIGHT)
            card.draw(surface, frame, profile=profile, mob_mode=True)

            self.assertIn(f"Скорость атаки: {expected['attack_seconds']:g} с", rendered)
            self.assertIn(f"Скорость передвижения: {expected['move_speed']} px/с", rendered)
            self.assertFalse(any(text.startswith("Грузоподъёмность") for text in rendered))
        finally:
            pygame.quit()

    def test_character_card_currency_icons_are_30_pixels(self):
        pygame.init()
        try:
            card = CharacterCard()

            self.assertEqual(card.CURRENCY_ICON_SIZE, 30)
            self.assertEqual(
                {name: icon.get_size() for name, icon in card.currency_icons.items()},
                {
                    "copper": (30, 30),
                    "silver": (30, 30),
                    "gold": (30, 30),
                },
            )
        finally:
            pygame.quit()

    def test_tavern_ale_image_is_100_pixels(self):
        pygame.init()
        try:
            font = pygame.font.Font(None, 18)
            shop = TavernShop(font, font)

            self.assertEqual(shop.DRINK_ICON_SIZE, 100)
            self.assertEqual(shop.ale_image.get_size(), (100, 100))
            self.assertEqual(shop._drink_rect(0).height, 110)
        finally:
            pygame.quit()

    def test_profile_overlay_applies_player_card_stat_click(self):
        pygame.init()
        try:
            overlay = CharacterProfileOverlay(pygame.font.Font(None, 18))
            overlay.open({"name": "Соперник", "stats": {}})
            overlay.player_card.sync({
                "name": "Игрок",
                "level": 1,
                "hp": 25,
                "max_hp": 25,
                "stats": {"strength": 5, "agility": 5, "intuition": 5, "endurance": 5},
                "stat_points": 6,
            })
            _, plus = overlay.player_card._stat_control_rects(
                overlay.player_frame,
                CharacterCard._stat_row_y(overlay.player_frame, 0),
            )

            action, profile = overlay.handle_click(plus.center)

            self.assertEqual(action, "stat_change")
            self.assertEqual(profile["stats"]["strength"], 6)
            self.assertEqual(profile["stat_points"], 5)
        finally:
            pygame.quit()

    def test_profile_overlay_close_cross_sits_in_player_card_corner(self):
        pygame.init()
        try:
            overlay = CharacterProfileOverlay(pygame.font.Font(None, 18))
            overlay.open({"name": "Игрок", "stats": {}})
            overlay._player_only = True

            close = overlay.close_button

            self.assertTrue(overlay.player_frame.collidepoint(close.center))
            self.assertEqual(close.right, overlay.player_frame.right - 10)
            self.assertEqual(close.top, overlay.player_frame.top + 10)
            action, _ = overlay.handle_click(close.center)
            self.assertEqual(action, "close")
            self.assertFalse(overlay.is_open)
        finally:
            pygame.quit()

    def test_stat_buttons_grow_without_moving(self):
        pygame.init()
        try:
            frame = pygame.Rect(20, 120, 500, 955)
            minus, plus = CharacterCard._stat_control_rects(frame, frame.bottom - 92)

            self.assertEqual(minus.topleft, (176 + settings.STAT_CONTROL_SHIFT_X, 988))
            self.assertEqual(plus.topleft, (195 + settings.STAT_CONTROL_SHIFT_X, 988))
            self.assertEqual(minus.size, (13, 13))
            self.assertEqual(plus.size, (13, 13))
        finally:
            pygame.quit()

    def test_tavern_stat_click_saves_updated_profile(self):
        pygame.init()
        try:
            class Session:
                character = {
                    "id": 1,
                    "name": "Игрок",
                    "level": 1,
                    "xp": 0,
                    "hp": 25,
                    "max_hp": 25,
                    "mp": 50,
                    "max_mp": 50,
                    "stats": {"strength": 5, "agility": 5, "intuition": 5, "endurance": 5},
                    "stat_points": 6,
                }

                def __init__(self):
                    self.saved_profiles = []

                def update_presence(self, location):
                    return None

                def list_occupants(self, location):
                    return []

                def list_messages(self, location):
                    return []

                def save_character_profile(self, profile):
                    self.saved_profiles.append(profile)
                    self.character = dict(profile)
                    return self.character

            session = Session()
            scene = TavernScene(session)
            scene.profile_overlay.open({"id": 2, "name": "Соперник", "stats": {}}, counterpart=session.character)
            scene.draw(pygame.Surface((1920, 1080)))
            _, plus = scene.profile_overlay.player_card._stat_control_rects(
                scene.profile_overlay.player_frame,
                CharacterCard._stat_row_y(scene.profile_overlay.player_frame, 0),
            )

            scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": plus.center}))
            scene.draw(pygame.Surface((1920, 1080)))
            scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": plus.center}))

            self.assertEqual(len(session.saved_profiles), 2)
            self.assertEqual(session.saved_profiles[0]["stats"]["strength"], 6)
            self.assertEqual(session.saved_profiles[1]["stats"]["strength"], 7)
        finally:
            pygame.quit()

    def test_derived_values_are_own_and_include_weapon_damage(self):
        warrior = {
            "name": "Воин",
            "type": "warrior",
            "level": 1,
            "max_hp": 40,
            "stats": {"strength": 5, "agility": 5, "intuition": 5, "endurance": 5},
            "equipment_bonuses": {"strength": 1},
            "equipment": {"weapon": {"equip_slot": "weapon", "effects": {"damage": [5, 7]}}},
        }
        mage = {
            "name": "Маг",
            "type": "mage",
            "level": 1,
            "max_hp": 90,
            "stats": {"wisdom": 3, "intellect": 3, "endurance": 4, "agility": 3},
        }

        # Урон = сила 5 + 1 от предмета + меч 5–7
        self.assertEqual(derived_values(warrior), {
            "Урон": "11-13", "Уворот": "25%", "Крит": "25% × 150%",
            "Маг Урон": "6-8", "HP": 40,
        })
        # Показатели одинаковы для всех классов: маг урон идёт от мудрости
        self.assertEqual(derived_values(mage), {
            "Урон": 1, "Уворот": "15%", "Крит": "0% × 150%",
            "Маг Урон": 3, "HP": 90,
        })

    def test_equipped_shield_block_is_displayed_in_derived_values(self):
        profile = normalize_character_profile({
            "stats": {"strength": 3, "agility": 3, "intuition": 3, "wisdom": 3,
                      "intellect": 3, "endurance": 3},
            "equipment_bonuses": {"hp": 20, "block": 5},
        })

        self.assertEqual(derived_values(profile)["Блок"], "5%")

    def test_equipment_hp_bonus_updates_card_max_without_double_counting_fighter(self):
        server_profile = normalize_character_profile({
            "hp": 36, "max_hp": 36,
            "stats": {"strength": 3, "agility": 3, "intuition": 3, "wisdom": 3,
                      "intellect": 3, "endurance": 3},
            "equipment_bonuses": {"hp": 20},
        })
        self.assertEqual(displayed_hp_values(server_profile), (56, 56))
        self.assertEqual(derived_values(server_profile)["HP"], 56)

        fighter = Fighter("Щитоносец")
        fighter.equipment_stat_modifiers = {"hp": 20}
        fighter.recalculate_parameters()
        self.assertEqual(displayed_hp_values(normalize_character_profile(profile_from_fighter(fighter))),
                         (fighter.hp, fighter.max_hp))

    def test_equipped_item_tooltip_contains_description_and_bonuses(self):
        lines = CharacterCard.equipment_tooltip_lines({
            "name": "Деревянный щит",
            "description": "Щит для защиты",
            "weight": 3,
            "bonuses": {"hp": 20, "block": 5},
            "effects": {"block": 5},
        })
        text = " ".join(line for line, _color in lines)
        self.assertIn("Щит для защиты", text)
        self.assertIn("+20 HP", text)
        self.assertIn("+5 % Блок", text)

    def test_hovering_equipped_shield_draws_tooltip(self):
        from unittest.mock import patch
        from ui.equipment_slots import slot_rects

        pygame.init()
        try:
            card = CharacterCard()
            screen = pygame.Surface((900, 1000))
            frame = pygame.Rect(20, 20, 440, 900)
            shield = {
                "name": "Деревянный щит",
                "description": "Щит для защиты",
                "weight": 3,
                "bonuses": {"hp": 20, "block": 5},
                "effects": {"block": 5},
            }
            with patch("pygame.mouse.get_pos", return_value=slot_rects(frame)["shield"].center):
                self.assertTrue(card._draw_equipment_tooltip(screen, frame, {"shield": shield}))
        finally:
            pygame.quit()

    def test_character_comparison_draw_cross_class_does_not_crash(self):
        from ui.character_comparison import CharacterComparison
        pygame.init()
        try:
            comparison = CharacterComparison(pygame.font.Font(None, 18))
            screen = pygame.Surface((1920, 1080))
            mage_player = {
                "id": 1,
                "name": "МагИгрок",
                "type": "mage",
                "level": 1,
                "hp": 90,
                "max_hp": 90,
                "mp": 55,
                "max_mp": 55,
                "stats": {"wisdom": 3, "intellect": 3, "endurance": 4},
                "stat_points": 0,
            }
            warrior_opponent = {
                "id": 2,
                "name": "ВоинБот",
                "type": "warrior",
                "level": 1,
                "hp": 40,
                "max_hp": 40,
                "mp": 50,
                "max_mp": 50,
                "stats": {"strength": 6, "agility": 3, "intuition": 3, "endurance": 4},
                "stat_points": 0,
            }
            comparison.draw(screen, mage_player, warrior_opponent)
            comparison.draw(screen, warrior_opponent, mage_player)
        finally:
            pygame.quit()


if __name__ == "__main__":
    unittest.main()
