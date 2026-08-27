import pygame

from combat.progression import xp_to_next
from core import settings
from ui.character_profile import (
    adjust_profile_stat,
    derived_values,
    normalize_character_profile,
    profile_from_fighter,
)
from ui.hud import draw_bar, draw_button, draw_text
from ui.sprite_loader import FighterSprite


class CharacterCard:
    """The authoritative state container and renderer for a character card."""

    def __init__(self, sprite=None):
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, settings.CHARACTER_CARD_NAME_FONT_SIZE)
        self.body_font = pygame.font.SysFont(settings.FONT_NAME, settings.CHARACTER_CARD_BODY_FONT_SIZE)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, settings.CHARACTER_CARD_SMALL_FONT_SIZE)
        self.sprite = sprite or FighterSprite()
        self.state = normalize_character_profile({}, title=None, kind="player")

    def sync(self, profile, *, title=None, kind="player"):
        self.state = normalize_character_profile(profile, title=title, kind=kind)
        return self.state

    @property
    def data(self):
        return self.state

    @staticmethod
    def stat_control_at(frame, position):
        """Return the requested stat change for a click inside this card."""
        for index, (stat_name, _, _) in enumerate(CharacterCard._STAT_NAMES):
            row_y = frame.bottom - 92 + index * 20
            minus, plus = CharacterCard._stat_control_rects(frame, row_y)
            if plus.collidepoint(position):
                return stat_name, 1
            if minus.collidepoint(position):
                return stat_name, -1
        return None

    def adjust_stat(self, stat_name, delta):
        """Apply a stat change to the canonical card state."""
        return adjust_profile_stat(self.state, stat_name, delta)

    def update_from_fighter(self, fighter, *, title=None, kind="player"):
        self.sync(profile_from_fighter(fighter), title=title, kind=kind)
        return self.state

    def draw(
        self,
        screen,
        frame,
        profile=None,
        border_color=(80, 180, 120),
        title=None,
        editable=False,
        opponent=None,
    ):
        if profile is not None:
            self.sync(profile, title=title, kind="player")
        normalized = self.state
        overlay = pygame.Surface(frame.size, pygame.SRCALPHA)
        overlay.fill((30, 32, 45, 225))
        screen.blit(overlay, frame.topleft)
        pygame.draw.rect(screen, border_color, frame, width=2, border_radius=8)

        x = frame.x + 20
        name_y = frame.y + 20
        name = normalized["name"]
        name_surface = self.title_font.render(name, True, (240, 240, 245))
        name_rect = name_surface.get_rect(topleft=(x, name_y))
        screen.blit(name_surface, name_rect)
        character_id = normalized.get("character_id", normalized.get("id", "-"))
        draw_text(screen, self.small_font, f"ID: {character_id}", name_rect.right + 20, name_y + 5, (170, 175, 185))

        level_y = frame.y + 58
        level = int(normalized["level"])
        level_surface = self.small_font.render(f"Уровень {level}", True, (210, 215, 225))
        level_rect = level_surface.get_rect(topleft=(x, level_y))
        screen.blit(level_surface, level_rect)
        next_xp = xp_to_next(level)
        xp_text = "XP: максимум" if next_xp == 0 else f"XP: {normalized.get('xp', 0)}/{next_xp}"
        draw_text(screen, self.small_font, xp_text, level_rect.right + 20, level_y, (255, 220, 120))

        hp_y = frame.y + 100
        mp_y = frame.y + 140
        bar_width = 280
        bar_height = 11
        self._draw_resource(screen, x, hp_y, bar_width, bar_height, "HP", normalized["hp"], normalized["max_hp"], (210, 80, 80))
        self._draw_resource(screen, x, mp_y, bar_width, bar_height, "MP", normalized["mp"], normalized["max_mp"], (60, 140, 220))

        stats_header_y = frame.bottom - 120
        sprite_center_y = (mp_y + bar_height + stats_header_y) / 2
        sprite_height = self.sprite.image.get_height() * settings.FIGHTER_SPRITE_SCALE if self.sprite.image is not None else 0
        sprite_feet_y = int(sprite_center_y + sprite_height / 2)
        self.sprite.draw(screen, frame.centerx, sprite_feet_y, scale=settings.FIGHTER_SPRITE_SCALE)

        draw_text(screen, self.small_font, "ХАРАКТЕРИСТИКИ", x, stats_header_y, border_color)
        stats = normalized.get("stats", {})
        draw_text(screen, self.small_font, f"Свободные очки: {normalized['stat_points']}", x, stats_header_y - 22, (255, 220, 120))
        derived = self._derived_values(normalized, opponent)
        derived_x = self._stat_text_right(frame) + settings.STAT_DERIVED_GAP + 50
        stat_value_colors = {
            "Урон": (255, 255, 255),
            "Уворот": (150, 220, 255),
            "Крит": (255, 90, 90),
            "HP": (110, 235, 120),
        }
        for index, (key, label, derived_key) in enumerate(self._STAT_NAMES):
            row_y = frame.bottom - 92 + index * 20
            draw_text(screen, self.small_font, f"{label}: {stats.get(key, 0)}", x, row_y, (215, 220, 225))
            draw_text(
                screen,
                self.small_font,
                f"{derived_key}: {derived[derived_key]}",
                derived_x,
                row_y,
                stat_value_colors.get(derived_key, (220, 70, 70)),
            )
            if editable:
                minus, plus = self._stat_control_rects(frame, row_y)
                draw_button(
                    screen,
                    minus,
                    "-",
                    self.small_font,
                    color=(235, 235, 235),
                    hover_color=(210, 80, 80),
                    text_color=(30, 32, 45),
                )
                draw_button(
                    screen,
                    plus,
                    "+",
                    self.small_font,
                    color=(235, 235, 235),
                    hover_color=(80, 200, 120),
                    text_color=(30, 32, 45),
                )

    _STAT_NAMES = (
        ("strength", "Сила", "Урон"),
        ("agility", "Ловкость", "Уворот"),
        ("intuition", "Интуиция", "Крит"),
        ("endurance", "Выносливость", "HP"),
    )

    @staticmethod
    def _stat_text_right(frame):
        return frame.x + 20 + pygame.font.SysFont(
            settings.FONT_NAME,
            settings.CHARACTER_CARD_SMALL_FONT_SIZE,
        ).size("Выносливость: 30")[0]

    @staticmethod
    def _derived_values(profile, opponent):
        return derived_values(profile, opponent)

    @staticmethod
    def _stat_control_rects(frame, row_y):
        text_right = CharacterCard._stat_text_right(frame) + settings.STAT_DERIVED_GAP + 7
        control_top = row_y + 5
        minus = pygame.Rect(
            text_right + settings.STAT_CONTROL_GAP,
            control_top,
            settings.STAT_BTN_W,
            settings.STAT_BTN_H,
        )
        plus = pygame.Rect(
            minus.right + settings.STAT_BUTTON_GAP,
            control_top,
            settings.STAT_BTN_W,
            settings.STAT_BTN_H,
        )
        return minus, plus

    def _draw_resource(self, screen, x, y, width, height, name, value, maximum, color):
        draw_text(screen, self.small_font, f"{name}: {value}/{maximum}", x, y - 24, (220, 225, 235))
        draw_bar(screen, x, y, width, height, value, maximum, fg=color)
