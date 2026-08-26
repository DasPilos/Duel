import pygame
from types import SimpleNamespace

from combat.progression import xp_to_next
from combat.mechanics import get_critical_chance, get_dodge_chance
from core import settings
from ui.hud import draw_bar, draw_button, draw_text
from ui.sprite_loader import FighterSprite


def normalize_character_profile(profile, *, title=None, kind="player"):
    """Return one canonical card model regardless of scene-specific raw source."""
    data = profile or {}
    if hasattr(data, "stats") and not isinstance(data, dict):
        profile_dict = {
            "id": getattr(data, "id", getattr(data, "character_id", None)),
            "character_id": getattr(data, "character_id", getattr(data, "id", None)),
            "name": getattr(data, "name", "Персонаж"),
            "level": getattr(data, "level", 1),
            "xp": getattr(data, "xp", 0),
            "hp": getattr(data, "hp", 0),
            "max_hp": getattr(data, "max_hp", 0),
            "mp": getattr(data, "mp", 0),
            "max_mp": getattr(data, "max_mp", 0),
            "stats": dict(getattr(data, "stats", {})),
            "stat_points": getattr(data, "stat_points", 0),
            "kind": kind,
        }
    elif isinstance(data, dict):
        profile_dict = {
            "id": data.get("id", data.get("character_id", None)),
            "character_id": data.get("character_id", data.get("id", None)),
            "name": data.get("name", "Персонаж"),
            "level": int(data.get("level", 1)),
            "xp": data.get("xp", 0),
            "hp": data.get("hp", data.get("current_hp", 0)),
            "max_hp": data.get("max_hp", data.get("hp_max", data.get("max_hp", 0))),
            "mp": data.get("mp", data.get("current_mp", 0)),
            "max_mp": data.get("max_mp", data.get("mp_max", data.get("max_mp", 0))),
            "stats": dict(data.get("stats", {})),
            "stat_points": data.get("stat_points", 0),
            "kind": kind,
        }
    else:
        profile_dict = {
            "id": None,
            "character_id": None,
            "name": "Персонаж",
            "level": 1,
            "xp": 0,
            "hp": 0,
            "max_hp": 0,
            "mp": 0,
            "max_mp": 0,
            "stats": {},
            "stat_points": 0,
            "kind": kind,
        }

    profile_dict["max_hp"] = max(int(profile_dict["max_hp"]), 1)
    profile_dict["max_mp"] = max(int(profile_dict["max_mp"]), 1)
    profile_dict["hp"] = min(int(profile_dict["hp"]), profile_dict["max_hp"])
    profile_dict["mp"] = min(int(profile_dict["mp"]), profile_dict["max_mp"])
    profile_dict["title"] = title
    if not profile_dict["stats"]:
        profile_dict["stats"] = {
            "strength": 5,
            "agility": 5,
            "intuition": 5,
            "endurance": 5,
        }

    return profile_dict


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
        stats = self.state["stats"]
        if stat_name not in stats or delta not in (-1, 1):
            return False
        if delta > 0 and self.state["stat_points"] <= 0:
            return False
        if delta < 0 and stats[stat_name] <= 4:
            return False

        previous_max_hp = self.state["max_hp"]
        stats[stat_name] += delta
        self.state["stat_points"] -= delta
        self.state["max_hp"] = 100 + 20 * (self.state["level"] - 1) + stats["endurance"] * 14
        if stat_name == "endurance" and delta > 0:
            self.state["hp"] += self.state["max_hp"] - previous_max_hp
        self.state["hp"] = min(self.state["hp"], self.state["max_hp"])
        return True

    def update_from_fighter(self, fighter, *, title=None, kind="player"):
        self.sync({
            "id": getattr(fighter, "id", None),
            "character_id": getattr(fighter, "character_id", getattr(fighter, "id", None)),
            "name": getattr(fighter, "name", "Персонаж"),
            "level": getattr(fighter, "level", 1),
            "xp": getattr(fighter, "xp", 0),
            "hp": getattr(fighter, "hp", 0),
            "max_hp": getattr(fighter, "max_hp", 0),
            "mp": getattr(fighter, "mp", 0),
            "max_mp": getattr(fighter, "max_mp", 0),
            "stats": getattr(fighter, "stats", {}),
            "stat_points": getattr(fighter, "stat_points", 0),
        }, title=title, kind=kind)
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
        derived_x = self._stat_text_right(frame) + settings.STAT_DERIVED_GAP
        for index, (key, label, derived_key) in enumerate(self._STAT_NAMES):
            row_y = frame.bottom - 92 + index * 20
            draw_text(screen, self.small_font, f"{label}: {stats.get(key, 0)}", x, row_y, (215, 220, 225))
            draw_text(screen, self.small_font, f"{derived_key}: {derived[derived_key]}", derived_x, row_y, (220, 70, 70))
            if editable:
                minus, plus = self._stat_control_rects(frame, row_y)
                draw_button(screen, minus, "-", self.small_font, color=(200, 90, 90))
                draw_button(screen, plus, "+", self.small_font, color=(80, 200, 120))

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
        if opponent is None:
            return {"Урон": "--", "Уворот": "--", "Крит": "--", "HP": profile["max_hp"]}

        opponent = normalize_character_profile(opponent)

        fighter = SimpleNamespace(
            strength=profile["stats"]["strength"],
            agility=profile["stats"]["agility"],
            intuition=profile["stats"]["intuition"],
            endurance=profile["stats"]["endurance"],
        )
        enemy = SimpleNamespace(
            strength=opponent["stats"]["strength"],
            agility=opponent["stats"]["agility"],
            intuition=opponent["stats"]["intuition"],
            endurance=opponent["stats"]["endurance"],
        )
        return {
            "Урон": max(1, int(fighter.strength * 3 - enemy.endurance * 0.5)),
            "Уворот": f"{int(get_dodge_chance(enemy, fighter))}%",
            "Крит": f"{int(get_critical_chance(fighter, enemy))}%",
            "HP": profile["max_hp"],
        }

    @staticmethod
    def _stat_control_rects(frame, row_y):
        # Keep the controls close to the labels with a 6 px gap between buttons.
        text_right = CharacterCard._stat_text_right(frame)
        minus = pygame.Rect(
            text_right + settings.STAT_CONTROL_GAP,
            row_y + 1,
            settings.STAT_BTN_W,
            settings.STAT_BTN_H,
        )
        plus = pygame.Rect(
            minus.right + settings.STAT_BUTTON_GAP,
            row_y + 1,
            settings.STAT_BTN_W,
            settings.STAT_BTN_H,
        )
        return minus, plus

    @staticmethod
    def _value(profile, key, default):
        if isinstance(profile, dict):
            return profile.get(key, default)
        return getattr(profile, key, default)

    def _draw_resource(self, screen, x, y, width, height, name, value, maximum, color):
        draw_text(screen, self.small_font, f"{name}: {value}/{maximum}", x, y - 24, (220, 225, 235))
        draw_bar(screen, x, y, width, height, value, maximum, fg=color)
