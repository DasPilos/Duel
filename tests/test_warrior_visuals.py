import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from core import settings
from core.carry_weight import OVERLOAD_RATIO, character_carry_capacity, is_overloaded
from scenes.player_sprites import (
    FEET_MARGIN,
    PLAYER_DIRECTIONS,
    PLAYER_SPRITE_HEIGHT,
    WARRIOR_ANIMATIONS,
    WARRIOR_ATTACK_ANIMATIONS,
    _warrior_source_direction,
    load_warrior_directional_frames,
    player_anim_state,
    player_frame,
    player_label_top,
    player_profession,
)
from ui.profession_icons import PROFESSION_ICON_SIZE, profession_icon
from ui.sprite_loader import fit_figure_to


def _warrior(**extra):
    character = {"type": "warrior", "stats": {"strength": 10, "endurance": 10}, "carried_weight_kg": 0}
    character.update(extra)
    return character


class _Scene:
    pass


class WarriorVisualsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)

    def test_every_warrior_animation_covers_all_directions(self):
        frames = load_warrior_directional_frames()
        self.assertEqual(set(frames), set(WARRIOR_ANIMATIONS))
        for anim in WARRIOR_ANIMATIONS:
            self.assertEqual(set(frames[anim]), set(PLAYER_DIRECTIONS), anim)
            for direction in PLAYER_DIRECTIONS:
                self.assertTrue(frames[anim][direction], f"{anim}/{direction}")

    def test_frames_share_a_canvas_per_group(self):
        frames = load_warrior_directional_frames()
        base = {frames[a][d][0].get_size() for a in ("idle", "run", "walking") for d in PLAYER_DIRECTIONS}
        attack = {frames[a][d][0].get_size() for a in WARRIOR_ATTACK_ANIMATIONS for d in PLAYER_DIRECTIONS}
        self.assertEqual(len(base), 1, base)
        self.assertEqual(len(attack), 1, attack)
        # В атаках меч и тень выходят за фигуру, поэтому их холст больше
        self.assertGreater(attack.copy().pop()[0], base.copy().pop()[0])

    def test_one_scale_gives_the_figure_target_height(self):
        frames = load_warrior_directional_frames()
        for anim in ("idle", "run", "walking"):
            for d in PLAYER_DIRECTIONS:
                heights = sorted(f.get_bounding_rect(min_alpha=201).height for f in frames[anim][d])
                median = heights[len(heights) // 2]
                self.assertLessEqual(abs(median - PLAYER_SPRITE_HEIGHT), 8, (anim, d, median))

    def test_feet_stand_at_the_bottom_centre_in_every_state(self):
        frames = load_warrior_directional_frames()
        for anim in WARRIOR_ANIMATIONS:
            for d in PLAYER_DIRECTIONS:
                sample = frames[anim][d][0]
                width, height = sample.get_size()
                bottoms = sorted(f.get_bounding_rect(min_alpha=201).bottom for f in frames[anim][d])
                median_bottom = bottoms[len(bottoms) // 2]
                self.assertLessEqual(height - median_bottom, FEET_MARGIN + 3, (anim, d, median_bottom, height))
                self.assertLessEqual(median_bottom, height, (anim, d))
                feet_x = sample.get_bounding_rect(min_alpha=201).centerx
                self.assertLessEqual(abs(feet_x - width // 2), width // 4, (anim, d, feet_x, width))

    def test_both_attacks_exist_and_differ(self):
        frames = load_warrior_directional_frames()
        first, second = (frames[anim]["s"] for anim in WARRIOR_ATTACK_ANIMATIONS)
        self.assertNotEqual((len(first), len(second)), (0, 0))
        self.assertNotEqual(len(first), len(second))
        self.assertEqual(first[0].get_size(), second[0].get_size())

    def test_real_directions_are_not_mirrored_copies(self):
        frames = load_warrior_directional_frames()
        for anim in WARRIOR_ANIMATIONS:
            for direction in ("e", "n", "s", "w"):
                self.assertTrue(frames[anim][direction], f"{anim}/{direction}")
            self.assertIsNot(frames[anim]["w"], frames[anim]["e"], anim)

    def test_missing_directions_fall_back_to_partner_or_neighbour(self):
        # Все 8 направлений есть в спрайте, но запасная замена остаётся для будущих неполных наборов
        self.assertEqual(_warrior_source_direction("w", {"e": 1, "n": 2}), ("e", True))
        self.assertEqual(_warrior_source_direction("nw", {"n": 1, "w": 2}), ("w", False))
        self.assertEqual(_warrior_source_direction("sw", {}), (None, False))

    def test_overload_threshold_matches_red_zone(self):
        base = _warrior()
        capacity = character_carry_capacity(base)
        self.assertGreater(capacity, 0)
        at_limit = _warrior(carried_weight_kg=capacity * OVERLOAD_RATIO)
        above = _warrior(carried_weight_kg=capacity * OVERLOAD_RATIO + 1.0)
        self.assertFalse(is_overloaded(at_limit))
        self.assertTrue(is_overloaded(above))
        self.assertFalse(is_overloaded(base))

    def test_warrior_anim_state_priority(self):
        self.assertEqual(player_anim_state(_warrior(), moving=False), "idle")
        self.assertEqual(player_anim_state(_warrior(), moving=True), "run")
        self.assertEqual(player_anim_state(_warrior(), moving=True, attacking=True), "attack")
        self.assertEqual(player_anim_state(_warrior(), moving=False, attacking=True), "attack")
        capacity = character_carry_capacity(_warrior())
        heavy = _warrior(carried_weight_kg=capacity * 2)
        self.assertEqual(player_anim_state(heavy, moving=True), "walking")
        self.assertEqual(player_anim_state(heavy, moving=False), "idle")

    def test_non_warrior_never_gets_warrior_states(self):
        citizen = {"name": "житель"}
        self.assertIsNone(player_profession(citizen))
        self.assertEqual(player_anim_state(citizen, moving=True), "run")
        self.assertEqual(player_anim_state(citizen, moving=True, attacking=True), "run")
        self.assertEqual(player_anim_state(citizen, moving=False), "idle")
        self.assertEqual(player_anim_state({"type": "mage"}, moving=True, attacking=True), "run")

    def test_player_frame_returns_warrior_frames(self):
        scene = _Scene()
        frames = load_warrior_directional_frames()
        idle = player_frame(scene, _warrior(), "e", 0.0, moving=False)
        self.assertIsNotNone(idle)
        self.assertEqual(idle.get_size(), frames["idle"]["e"][0].get_size())
        for variant, anim in enumerate(WARRIOR_ATTACK_ANIMATIONS):
            start = player_frame(scene, _warrior(), "e", 0.0, moving=True, attacking=True,
                                 attack_progress=0.0, attack_variant=variant)
            self.assertIs(start, frames[anim]["e"][0])
            end = player_frame(scene, _warrior(), "e", 0.0, moving=False, attacking=True,
                               attack_progress=1.0, attack_variant=variant)
            self.assertIs(end, frames[anim]["e"][-1])

    def test_attack_variant_wraps_and_defaults_to_the_first_attack(self):
        scene = _Scene()
        frames = load_warrior_directional_frames()
        default = player_frame(scene, _warrior(), "s", 0.0, moving=False, attacking=True, attack_progress=0.0)
        self.assertIs(default, frames[WARRIOR_ATTACK_ANIMATIONS[0]]["s"][0])
        wrapped = player_frame(scene, _warrior(), "s", 0.0, moving=False, attacking=True,
                               attack_progress=0.0, attack_variant=len(WARRIOR_ATTACK_ANIMATIONS))
        self.assertIs(wrapped, default)

    def test_label_top_does_not_jump_when_attacking(self):
        scene = _Scene()
        character = _warrior()
        tops = set()
        for attacking in (False, True):
            frame = player_frame(scene, character, "s", 0.0, moving=False, attacking=attacking, attack_progress=0.3)
            tops.add(player_label_top(character, frame.get_rect(midbottom=(100, 400))))
        self.assertEqual(len(tops), 1, tops)
        citizen = {"type": "citizen"}
        rect = pygame.Rect(0, 10, 20, 30)
        self.assertEqual(player_label_top(citizen, rect), 10)

    def test_profession_icon_is_32_pixels(self):
        icon = profession_icon("warrior")
        self.assertEqual(icon.get_size(), (PROFESSION_ICON_SIZE, PROFESSION_ICON_SIZE))
        self.assertEqual(PROFESSION_ICON_SIZE, 32)
        self.assertEqual(profession_icon("mage").get_size(), (PROFESSION_ICON_SIZE, PROFESSION_ICON_SIZE))

    def test_card_sprite_matches_reference_size(self):
        from ui.sprite_loader import FighterSprite, WARRIOR_SPRITE_PATH, FIGHTER_SPRITE_PATH

        reference = FighterSprite(FIGHTER_SPRITE_PATH)
        warrior = FighterSprite(WARRIOR_SPRITE_PATH, fit_to=reference).image
        self.assertIsNotNone(reference.image)
        self.assertIsNotNone(warrior)
        self.assertEqual(warrior.get_size(), reference.image.get_size())

    def test_warrior_card_sprite_shifted_left_without_moving_slots(self):
        from unittest import mock
        from ui import equipment_slots
        from ui.character_card import WARRIOR_CARD_SPRITE_OFFSET_X

        class _Sprite:
            image = pygame.Surface((10, 100), pygame.SRCALPHA)

            def __init__(self):
                self.x = None

            def draw(self, screen, x, y, scale=1.0):
                self.x = x

        frame = pygame.Rect(0, 0, 300, 400)
        sprite = _Sprite()
        with mock.patch.object(equipment_slots, "draw_slots") as slots:
            equipment_slots.draw_paperdoll(self.screen, frame, sprite, {}, None, {}, sprite_offset_x=WARRIOR_CARD_SPRITE_OFFSET_X)
        self.assertEqual(WARRIOR_CARD_SPRITE_OFFSET_X, -30)
        self.assertEqual(sprite.x, frame.centerx - 30)
        self.assertEqual(slots.call_args[0][1], frame)

        reference = pygame.Surface((100, 200), pygame.SRCALPHA)
        reference.fill((255, 0, 0, 255), (30, 0, 40, 200))
        source = pygame.Surface((50, 50), pygame.SRCALPHA)
        source.fill((0, 255, 0, 255), (10, 10, 20, 40))
        fitted = fit_figure_to(source, reference)
        self.assertEqual(fitted.get_size(), reference.get_size())
        self.assertEqual(fitted.get_bounding_rect().height, 200)


if __name__ == "__main__":
    unittest.main()
