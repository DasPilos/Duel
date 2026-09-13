# Карточка персонажа-мага
import pygame

from combat.character_stats import is_debug_unlimited
from combat.progression import xp_to_next
from core import settings
from ui.character_profile import (
    adjust_profile_level,
    adjust_profile_stat,
    normalize_character_profile,
)
from ui.hud import draw_bar, draw_button, draw_text, FloatingText, update_and_draw_floating_texts
from ui.sprite_loader import FighterSprite


class MageCard:
    """
    Карточка персонажа-мага с отображением:
    - Основных характеристик (Мудрость, Интеллект, Выносливость)
    - Гармонии магии
    - HP и MP
    
    Отличается от CharacterCard отсутствием Урона, Уворота и Крита.
    """

    def __init__(self, sprite=None):
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, settings.CHARACTER_CARD_NAME_FONT_SIZE)
        self.body_font = pygame.font.SysFont(settings.FONT_NAME, settings.CHARACTER_CARD_BODY_FONT_SIZE)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, settings.CHARACTER_CARD_SMALL_FONT_SIZE)
        self.sprite = sprite or FighterSprite()
        self.state = normalize_character_profile({}, title=None, kind="player")
        self.regen_floating_texts = []
        
        # Закладки для инвентаря
        self.current_tab = "character"  # character, inventory, equipment, battle
        self.inventory_data = []
        self.selected_inventory_item = None

    def show_regen(self, amount):
        """Показать анимацию восстановления маны"""
        self.regen_floating_texts.append(
            FloatingText(
                0,
                0,
                f"+{int(amount)} MP",
                self.small_font,
                color=(60, 140, 220),  # Голубой цвет для маны
                duration=settings.FLOATING_TEXT_DURATION,
            )
        )

    def sync(self, profile, *, title=None, kind="player"):
        """Синхронизировать состояние карточки с профилем"""
        self.state = normalize_character_profile(profile, title=title, kind=kind)
        # Загружаем инвентарь из профиля
        self.inventory_data = []
        if "inventory" in self.state and isinstance(self.state["inventory"], dict):
            for slot_key, item in sorted(
                self.state["inventory"].items(),
                key=lambda x: int(x[0]) if x[0].isdigit() else 999
            ):
                self.inventory_data.append({
                    "slot": slot_key,
                    "name": item.get("name", "Неизвестный предмет"),
                    "quantity": item.get("quantity", 1),
                    "effect": item.get("effect", "")
                })
        return self.state

    @property
    def data(self):
        return self.state

    def adjust_stat(self, stat_name, delta):
        """Изменить mage-стат с единым минимумом 2."""
        if stat_name not in self._stat_names or delta not in (-1, 1):
            return False
        if delta > 0 and self.state["stat_points"] <= 0:
            return False
        current = int(self.state["stats"].get(stat_name, 2))
        if delta < 0 and current <= 2:
            return False
        updated = current + delta
        self.state["stats"][stat_name] = updated
        self.state["stat_points"] -= delta
        if stat_name == "endurance":
            self.state["max_hp"] = 50 + updated * 10
            self.state["hp"] = min(int(self.state["hp"]), self.state["max_hp"])
        if stat_name == "intellect":
            self.state["max_mp"] = 40 + updated * 5
            self.state["mp"] = min(int(self.state["mp"]), self.state["max_mp"])
            self.state["hp"] = min(int(self.state["hp"]), self.state["max_hp"])
        return True

    def adjust_level(self, delta):
        """Применить изменение уровня (только для тестовых персонажей)"""
        return adjust_profile_level(self.state, delta)

    def draw(self, screen, frame, profile=None, border_color=(150, 100, 200), title=None, editable=False):
        if profile is not None:
            self.sync(profile, title=title, kind="player")

        normalized = self.state
        overlay = pygame.Surface(frame.size, pygame.SRCALPHA)
        overlay.fill((30, 25, 40, 225))
        screen.blit(overlay, frame.topleft)
        pygame.draw.rect(screen, border_color, frame, width=2, border_radius=8)

        x = frame.x + 10
        name_y = frame.y + 20
        name_surface = self.title_font.render(normalized["name"], True, (240, 240, 245))
        name_rect = name_surface.get_rect(topleft=(x, name_y))
        screen.blit(name_surface, name_rect)
        character_id = normalized.get("character_id", normalized.get("id", "-"))
        draw_text(screen, self.small_font, f"ID: {character_id}", name_rect.right + 20, name_y, (170, 175, 185))

        level_y = frame.y + 48
        level = int(normalized["level"])
        level_rect = self.small_font.render(f"Уровень {level}", True, (210, 215, 225)).get_rect(topleft=(x, level_y))
        screen.blit(self.small_font.render(f"Уровень {level}", True, (210, 215, 225)), level_rect)
        next_xp = xp_to_next(level)
        xp_text = "XP: максимум" if next_xp == 0 else f"XP: {normalized.get('xp', 0)}/{next_xp}"
        draw_text(screen, self.small_font, xp_text, level_rect.right + 15, level_y, (255, 220, 120))

        hp_y = frame.y + 100
        mp_y = frame.y + 140
        self._draw_resource(screen, x, hp_y, 280, 11, "HP", normalized["hp"], normalized["max_hp"], (210, 80, 80))
        self._draw_resource(screen, x, mp_y, 280, 11, "MP", normalized["mp"], normalized["max_mp"], (60, 140, 220))

        currency_y = mp_y + 25
        currency_text = f"Медяки: {int(normalized.get('copper', 0))}  Серебро: {int(normalized.get('silver', 0))}  Золото: {int(normalized.get('gold', 0))}"
        draw_text(screen, self.small_font, currency_text, x, currency_y, (200, 170, 100))

        stats_header_y = frame.bottom - 110
        stats = normalized.get("stats", {})
        draw_text(screen, self.small_font, "ХАРАКТЕРИСТИКИ МАГА", x, stats_header_y, border_color)
        draw_text(screen, self.small_font, f"Свободные очки: {normalized['stat_points']}", x, stats_header_y - 22, (255, 220, 120))

        rows = (
            ("Мудрость", int(stats.get("wisdom", stats.get("Мудрость", 3))), "(+{} урона)", (93, 199, 145)),
            ("Интеллект", int(stats.get("intellect", stats.get("Интеллект", 3))), "(+{} МР)", (80, 160, 240)),
            ("Выносливость", int(stats.get("endurance", stats.get("Выносливость", 4))), "", (235, 195, 70)),
            ("Гармония", int(stats.get("harmony", stats.get("Гармония", 3))), "", (180, 100, 230)),
        )
        for index, (name, value, suffix, color) in enumerate(rows):
            suffix = suffix.format(value * (2 if name == "Мудрость" else 5)) if suffix else ""
            self._draw_stat_row(screen, frame, x, stats_header_y + 20 + index * 20, name, value, suffix, editable, color)

    def _draw_stat_row(self, screen, frame, x, y, name, value, suffix, editable, color=(200, 200, 200)):
        draw_text(screen, self.small_font, f"{name}: {value} {suffix}", x, y, color)
        if editable:
            minus, plus = self._stat_control_rects(frame, y)
            draw_button(screen, minus, "-", self.small_font, color=(235, 235, 235),
                        hover_color=(210, 80, 80), text_color=(30, 32, 45))
            draw_button(screen, plus, "+", self.small_font, color=(235, 235, 235),
                        hover_color=(80, 200, 120), text_color=(30, 32, 45))

    @staticmethod
    def _stat_control_rects(frame, row_y):
        control_top = row_y - 2
        controls_width = settings.STAT_BTN_W * 2 + settings.STAT_BUTTON_GAP
        text_right = frame.right - 10 - controls_width
        minus = pygame.Rect(text_right, control_top, settings.STAT_BTN_W, settings.STAT_BTN_H)
        plus = pygame.Rect(minus.right + settings.STAT_BUTTON_GAP, control_top, settings.STAT_BTN_W, settings.STAT_BTN_H)
        return minus, plus

    def stat_control_at(self, frame, position):
        stats_header_y = frame.bottom - 110
        rows = [stats_header_y + 20 + index * 20 for index in range(4)]
        for index, row_y in enumerate(rows):
            minus, plus = self._stat_control_rects(frame, row_y)
            if minus.collidepoint(position):
                return self._stat_names[index], -1
            if plus.collidepoint(position):
                return self._stat_names[index], 1
        return None

    _stat_names = ("wisdom", "intellect", "endurance", "harmony")

    def _draw_resource(self, screen, x, y, bar_width, bar_height, label, current, maximum, color):
        """Рисует полоску ресурса (HP или MP)"""
        draw_text(screen, self.small_font, label, x, y - 18, color)
        
        # Фон полоски
        pygame.draw.rect(screen, (40, 40, 50), (x, y, bar_width, bar_height))
        pygame.draw.rect(screen, color, (x, y, bar_width, bar_height), width=1)
        
        # Полоска значения
        if maximum > 0:
            fill_width = (current / maximum) * bar_width
        else:
            fill_width = 0
        pygame.draw.rect(screen, color, (x, y, fill_width, bar_height))
        
        # Текст значения
        text = f"{int(current)}/{int(maximum)}"
        text_surface = self.small_font.render(text, True, (230, 230, 230))
        text_rect = text_surface.get_rect(center=(x + bar_width // 2, y + bar_height // 2))
        screen.blit(text_surface, text_rect)

    def _level_control_rects(self, frame):
        """Возвращает прямоугольники для кнопок изменения уровня (debug)"""
        button_y = frame.y + 48
        minus = pygame.Rect(frame.x + frame.width - 60, button_y, 25, 25)
        plus = pygame.Rect(frame.x + frame.width - 30, button_y, 25, 25)
        return minus, plus
