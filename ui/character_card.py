import pygame

from combat.character_stats import is_debug_unlimited
from combat.progression import xp_to_next
from core import settings
from ui.character_profile import (
    adjust_profile_level,
    adjust_profile_stat,
    derived_values,
    normalize_character_profile,
    profile_from_fighter,
)
from ui.hud import draw_bar, draw_button, draw_text, FloatingText, update_and_draw_floating_texts
from ui.sprite_loader import FighterSprite


class CharacterCard:
    """The authoritative state container and renderer for a character card."""

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
        self.regen_floating_texts.append(
            FloatingText(
                0,
                0,
                f"+{int(amount)} HP",
                self.small_font,
                color=(110, 235, 120),
                duration=settings.FLOATING_TEXT_DURATION,
            )
        )

    def sync(self, profile, *, title=None, kind="player"):
        self.state = normalize_character_profile(profile, title=title, kind=kind)
        # Загружаем инвентарь из профиля
        self.inventory_data = []
        if "inventory" in self.state and isinstance(self.state["inventory"], dict):
            for slot_key, item in sorted(self.state["inventory"].items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
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

    def level_control_at(self, frame, position):
        """Return the requested level change for a click on the debug level buttons."""
        character_id = self.state.get("character_id", self.state.get("id"))
        if not is_debug_unlimited(character_id):
            return None
        minus, plus = CharacterCard._level_control_rects(frame)
        if plus.collidepoint(position):
            return 1
        if minus.collidepoint(position):
            return -1
        return None

    def adjust_stat(self, stat_name, delta):
        """Apply a stat change to the canonical card state."""
        return adjust_profile_stat(self.state, stat_name, delta)

    def adjust_level(self, delta):
        """Apply a level change to the canonical card state (test characters only)."""
        return adjust_profile_level(self.state, delta)

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
        card_preview=None,
        show_tabs=False,  # Новый параметр для показа закладок
    ):
        if profile is not None:
            self.sync(profile, title=title, kind="player")
        normalized = self.state
        overlay = pygame.Surface(frame.size, pygame.SRCALPHA)
        overlay.fill((30, 32, 45, 225))
        screen.blit(overlay, frame.topleft)
        pygame.draw.rect(screen, border_color, frame, width=2, border_radius=8)
        
        # Рисуем закладки если нужно
        if show_tabs:
            self._draw_tabs(screen, frame, border_color)

        x = frame.x + 20
        name_y = frame.y + 20
        name = normalized["name"]
        name_surface = self.title_font.render(name, True, (240, 240, 245))
        name_rect = name_surface.get_rect(topleft=(x, name_y))
        screen.blit(name_surface, name_rect)
        character_id = normalized.get("character_id", normalized.get("id", "-"))
        draw_text(screen, self.small_font, f"ID: {character_id}", name_rect.right + 20, name_y, (170, 175, 185))

        level_y = frame.y + 48
        level = int(normalized["level"])
        level_surface = self.small_font.render(f"Уровень {level}", True, (210, 215, 225))
        level_rect = level_surface.get_rect(topleft=(x, level_y))
        screen.blit(level_surface, level_rect)
        xp_x = level_rect.right + 15
        if editable and is_debug_unlimited(character_id):
            minus, plus = self._level_control_rects(frame)
            draw_button(screen, minus, "-", self.small_font, color=(235, 235, 235), hover_color=(210, 80, 80), text_color=(30, 32, 45))
            draw_button(screen, plus, "+", self.small_font, color=(235, 235, 235), hover_color=(80, 200, 120), text_color=(30, 32, 45))
            xp_x = plus.right + 20
        next_xp = xp_to_next(level)
        xp_text = "XP: максимум" if next_xp == 0 else f"XP: {normalized.get('xp', 0)}/{next_xp}"
        draw_text(screen, self.small_font, xp_text, xp_x, level_y, (255, 220, 120))

        hp_y = frame.y + 100
        mp_y = frame.y + 140
        bar_width = 280
        bar_height = 11
        self._draw_resource(screen, x, hp_y, bar_width, bar_height, "HP", normalized["hp"], normalized["max_hp"], (210, 80, 80))
        self._draw_resource(screen, x, mp_y, bar_width, bar_height, "MP", normalized["mp"], normalized["max_mp"], (60, 140, 220))
        
        # Отображение валюты под MP шкалой
        copper = int(normalized.get("copper", 0))
        silver = int(normalized.get("silver", 0))
        gold = int(normalized.get("gold", 0))
        currency_y = mp_y + 25
        currency_text = f"Медяки: {copper}  Серебро: {silver}  Золото: {gold}"
        draw_text(screen, self.small_font, currency_text, x, currency_y, (200, 170, 100))
        
        # Отображение инвентаря (если есть элементы)
        if self.inventory_data:
            inventory_y = currency_y + 30
            draw_text(screen, self.small_font, "РЮКЗАК", x, inventory_y, (100, 200, 255))
            
            # Отображаем элементы инвентаря
            for idx, item in enumerate(self.inventory_data):
                item_y = inventory_y + 25 + idx * 22
                if item_y > frame.bottom - 50:
                    break
                
                # Основная информация о предмете
                quantity_text = f" x{item['quantity']}" if item['quantity'] > 1 else ""
                item_text = f"{item['name']}{quantity_text}"
                draw_text(screen, self.small_font, item_text, x, item_y, (220, 200, 150))

        stats_header_y = frame.bottom - 120
        sprite_center_y = (mp_y + bar_height + stats_header_y) / 2
        sprite_height = self.sprite.image.get_height() * settings.FIGHTER_SPRITE_SCALE if self.sprite.image is not None else 0
        sprite_feet_y = int(sprite_center_y + sprite_height / 2)
        self.sprite.draw(screen, frame.centerx, sprite_feet_y, scale=settings.FIGHTER_SPRITE_SCALE)
        for floating_text in self.regen_floating_texts:
            floating_text.x = frame.centerx
            floating_text.y = sprite_center_y - sprite_height / 2 - 12
        update_and_draw_floating_texts(screen, self.regen_floating_texts)

        draw_text(screen, self.small_font, "ХАРАКТЕРИСТИКИ", x, stats_header_y, border_color)
        stats = normalized.get("stats", {})
        draw_text(screen, self.small_font, f"Свободные очки: {normalized['stat_points']}", x, stats_header_y - 22, (255, 220, 120))
        derived = self._derived_values(normalized, opponent)
        preview = self._card_preview(card_preview or [])
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
                f"{derived_key}: {derived[derived_key]}{preview.get(derived_key, '')}",
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
    def _card_preview(cards):
        damage_dice = []
        dodge_bonus = 0
        critical_bonus = 0
        heal_dice = []
        for card in cards:
            data = card.effect_data
            if card.effect_type in ("damage", "damage_reduce", "damage_recoil", "multi_damage"):
                dice = data.get("dice")
                if dice:
                    damage_dice.append((dice, data.get("hits", 1)))
            if card.effect_type == "dodge":
                dodge_bonus += int(data.get("bonus", 0))
            if card.effect_type == "critical":
                critical_bonus += int(data.get("bonus", 0))
            if card.effect_type == "heal":
                dice = data.get("dice")
                if dice:
                    heal_dice.append(dice)

        preview = {}
        damage_range = CharacterCard._dice_range(damage_dice)
        heal_range = CharacterCard._dice_range([(dice, 1) for dice in heal_dice])
        if damage_range:
            preview["Урон"] = f" + {damage_range}"
        if dodge_bonus:
            preview["Уворот"] = f" + {dodge_bonus}%"
        if critical_bonus:
            preview["Крит"] = f" + {critical_bonus}%"
        if heal_range:
            preview["HP"] = f" + {heal_range}"
        return preview

    @staticmethod
    def _dice_range(dice_parts):
        minimum = maximum = 0
        for expression, multiplier in dice_parts:
            try:
                count, sides = expression.lower().split("d")
                minimum += int(multiplier)
                maximum += int(count) * int(sides) * int(multiplier)
            except (AttributeError, TypeError, ValueError):
                continue
        if not maximum:
            return ""
        return str(minimum) if minimum == maximum else f"{minimum}-{maximum}"

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

    @staticmethod
    def _level_control_rects(frame):
        level_y = frame.y + 58
        control_top = level_y - 3
        text_right = frame.x + 20 + pygame.font.SysFont(
            settings.FONT_NAME,
            settings.CHARACTER_CARD_SMALL_FONT_SIZE,
        ).size("Уровень 1000")[0]
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
    
    def _draw_tabs(self, screen, frame, border_color):
        """Рисует закладки (вкладки) для инвентаря"""
        tabs = {
            "character": "👤 ПЕРСОНАЖ",
            "inventory": "🎒 РЮКЗАК",
            "personal": "✨ ЛИЧНЫЕ",
            "battle": "⚔️ БОЕВЫЕ",
        }
        
        tab_width = 110
        tab_height = 35
        start_y = frame.y + frame.height + 10
        
        for idx, (tab_key, tab_label) in enumerate(tabs.items()):
            tab_x = frame.x + 20 + idx * (tab_width + 5)
            tab_rect = pygame.Rect(tab_x, start_y, tab_width, tab_height)
            
            is_active = tab_key == self.current_tab
            
            # Цвет в зависимости от активности
            tab_color = border_color if is_active else (50, 60, 80)
            text_color = (255, 255, 255) if is_active else (150, 160, 170)
            
            pygame.draw.rect(screen, tab_color, tab_rect, border_radius=4)
            pygame.draw.rect(screen, (100, 100, 120), tab_rect, 2, border_radius=4)
            
            tab_surface = self.small_font.render(tab_label, True, text_color)
            tab_text_rect = tab_surface.get_rect(center=tab_rect.center)
            screen.blit(tab_surface, tab_text_rect)
    
    def set_tab(self, tab_name):
        """Устанавливает активную закладку"""
        self.current_tab = tab_name
    
    def get_tab_rect(self, frame, tab_index):
        """Возвращает rect закладки по индексу для обработки кликов"""
        tab_width = 110
        tab_height = 35
        start_y = frame.y + frame.height + 10
        tab_x = frame.x + 20 + tab_index * (tab_width + 5)
        return pygame.Rect(tab_x, start_y, tab_width, tab_height)

