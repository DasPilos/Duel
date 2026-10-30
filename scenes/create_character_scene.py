from pathlib import Path
from types import SimpleNamespace

import pygame

from client.network import ServerError
from combat.character_stats import (
    BASE_STAT_VALUE,
    CREATION_ALLOCATABLE_STATS,
    calculate_max_hp,
    calculate_max_mana,
    creation_stats,
)
from combat.world_stats import get_attack_reach
from core import settings
from core.carry_weight import character_carry_capacity, load_color
from ui import equipment_slots
from ui.character_card import CharacterCard
from ui.character_profile import STAT_ROWS, combat_speed_values, displayed_hp_values
from ui.hud import draw_button, draw_text
from ui.inventory_window import IconCache
from ui.profession_icons import PROFESSION_ICON_GAP, PROFESSION_ICON_SIZE, profession_icon
from ui.sprite_loader import FighterSprite


CLASS_SPRITE_DIR = Path(__file__).resolve().parent.parent / "assets" / "classes"

CARD_WIDTH = 450
CARD_HEIGHT = 1000
CARD_GAP = 30
CARD_MARGIN = 15
CARD_TOP = 80


class CreateCharacterScene:
    PROFESSION_ORDER = ("warrior", "archer", "assassin", "mage")

    CLASS_INFO = {
        "warrior": {"name": "ВОИН", "sprite": "warrior.png", "sprite_offset_x": -20, "card_bg": (110, 34, 38)},
        "archer": {"name": "ЛУЧНИК", "sprite": "archer.png", "sprite_offset_x": 10, "card_bg": (34, 96, 48)},
        "assassin": {"name": "АСАСИН", "sprite": "assassin.png", "sprite_offset_x": 0, "card_bg": (88, 44, 120)},
        "mage": {"name": "МАГ", "sprite": "mage.png", "sprite_offset_x": -10, "card_bg": (36, 62, 130)},
    }

    def __init__(self, session):
        self.session = session
        self.finished = False
        self.cancelled = False
        self.error = ""
        self.created_character = None
        self.font = pygame.font.SysFont(settings.FONT_NAME, 22)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 16)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 36)
        # Шрифты шапки и полосок совпадают с карточкой персонажа
        self.card_name_font = pygame.font.SysFont(settings.FONT_NAME, settings.CHARACTER_CARD_NAME_FONT_SIZE)
        self.card_small_font = pygame.font.SysFont(settings.FONT_NAME, settings.CHARACTER_CARD_SMALL_FONT_SIZE)

        # Узкая полоса сверху: заголовок, имя и кнопки
        self.name = ""
        # Фокус на поле имени: пока он есть, ввод идёт в поле и показывается курсор
        self.name_focused = True
        self.name_rect = pygame.Rect(640, 17, 380, 46)
        self.create_button = pygame.Rect(1490, 17, 200, 46)
        self.back_button = pygame.Rect(1700, 17, 200, 46)

        self.profession = "warrior"
        # Очки сверх базовых 3 на каждую характеристику, отдельно для каждого класса
        self.extra_points = {
            profession: {stat: 0 for stat in CREATION_ALLOCATABLE_STATS}
            for profession in self.PROFESSION_ORDER
        }
        self.card_rects = {
            profession: pygame.Rect(
                CARD_MARGIN + index * (CARD_WIDTH + CARD_GAP),
                CARD_TOP,
                CARD_WIDTH,
                CARD_HEIGHT,
            )
            for index, profession in enumerate(self.PROFESSION_ORDER)
        }
        base_sprite = FighterSprite()
        self.sprites = {
            profession: FighterSprite(CLASS_SPRITE_DIR / info["sprite"], fit_to=base_sprite)
            for profession, info in self.CLASS_INFO.items()
        }
        self.icons = IconCache()

    def allocation(self, profession):
        """Абсолютные значения распределяемых характеристик для отправки на сервер."""
        return {
            stat: BASE_STAT_VALUE + self.extra_points[profession][stat]
            for stat in CREATION_ALLOCATABLE_STATS
        }

    def free_points(self, profession):
        _, free = creation_stats(self.allocation(profession))
        return free

    def adjust_stat(self, profession, stat, delta):
        extra = self.extra_points[profession]
        if delta > 0:
            if self.free_points(profession) <= 0:
                return
            extra[stat] += 1
        elif extra[stat] > 0:
            extra[stat] -= 1

    def stat_control_at(self, profession, position):
        """Возвращает (характеристика, +1/-1) для клика по кнопке на карточке класса."""
        frame = self.card_rects[profession]
        for index, (stat, _, _) in enumerate(STAT_ROWS):
            if stat not in CREATION_ALLOCATABLE_STATS:
                continue
            row_y = CharacterCard._stat_row_y(frame, index)
            minus, plus = CharacterCard._stat_control_rects(frame, row_y)
            if plus.collidepoint(position):
                return stat, 1
            if minus.collidepoint(position):
                return stat, -1
        return None

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                # Back to character selection
                self.cancelled = True
                self.finished = True
            elif event.key == pygame.K_BACKSPACE:
                if self.name_focused:
                    self.name = self.name[:-1]
            elif event.key == pygame.K_RETURN:
                self.create()
        elif event.type == pygame.TEXTINPUT:
            if self.name_focused and len(self.name) < 15:
                self.name += event.text
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.name_focused = self.name_rect.collidepoint(event.pos)
            if self.name_focused:
                return

            if self.create_button.collidepoint(event.pos):
                self.create()
                return

            if self.back_button.collidepoint(event.pos):
                self.cancelled = True
                self.finished = True
                return

            for profession, frame in self.card_rects.items():
                if not frame.collidepoint(event.pos):
                    continue
                self.profession = profession
                control = self.stat_control_at(profession, event.pos)
                if control:
                    self.adjust_stat(profession, *control)
                return

    def create(self):
        name = self.name.strip()
        if not name:
            self.error = "Введите имя персонажа"
            return

        try:
            character = self.session.create_character(
                name,
                profession_type=self.profession,
                stats=self.allocation(self.profession),
            )
            self.created_character = character
            self.finished = True
        except ServerError as error:
            self.error = str(error)

    def update(self, dt):
        pass

    def draw(self, screen):
        screen.fill((16, 18, 28))

        title = self.title_font.render("СОЗДАНИЕ ПЕРСОНАЖА", True, (240, 240, 255))
        screen.blit(title, title.get_rect(midleft=(30, 40)))

        label = self.small_font.render("Имя персонажа:", True, (200, 200, 200))
        screen.blit(label, label.get_rect(midright=(self.name_rect.x - 10, 40)))

        border_color = (120, 190, 255) if self.name_focused else (70, 140, 220)
        pygame.draw.rect(screen, (28, 30, 43), self.name_rect, border_radius=6)
        pygame.draw.rect(screen, border_color, self.name_rect, width=2, border_radius=6)
        text_x = self.name_rect.x + 12
        text_y = self.name_rect.y + 11
        draw_text(screen, self.font, self.name, text_x, text_y, (240, 240, 245))
        # Мигающая черта под местом ввода, видна пока поле в фокусе
        if self.name_focused and (pygame.time.get_ticks() // 500) % 2 == 0:
            text_width = self.font.size(self.name)[0]
            underline_y = text_y + self.font.get_height() - 2
            pygame.draw.rect(screen, (240, 240, 245), (text_x + text_width + 2, underline_y, 12, 2))

        for profession in self.PROFESSION_ORDER:
            self._draw_card(screen, profession)

        draw_button(screen, self.create_button, "СОЗДАТЬ", self.font, color=(70, 140, 220))
        draw_button(screen, self.back_button, "НАЗАД", self.font, color=(220, 100, 100))

        if self.error:
            error = self.small_font.render(self.error, True, (255, 100, 100))
            screen.blit(error, error.get_rect(midright=(self.create_button.x - 15, 40)))

    def _draw_card(self, screen, profession):
        frame = self.card_rects[profession]
        selected = self.profession == profession
        pygame.draw.rect(screen, self.CLASS_INFO[profession]["card_bg"], frame, border_radius=10)
        pygame.draw.rect(
            screen,
            (100, 200, 100) if selected else (70, 140, 220),
            frame,
            width=3 if selected else 2,
            border_radius=10,
        )

        class_name = self.CLASS_INFO[profession]["name"]
        profile = self._card_profile(profession)
        self._draw_header(screen, frame, profession, profile, class_name)

        equipment_slots.draw_paperdoll(
            screen, frame, self.sprites[profession], self.icons, self.small_font, {},
            sprite_offset_x=self.CLASS_INFO[profession]["sprite_offset_x"],
        )
        self._draw_info_lines(screen, frame, profile)

        stats, free = creation_stats(self.allocation(profession))
        header_y = CharacterCard._stats_header_y(frame)
        draw_text(screen, self.small_font, "ХАРАКТЕРИСТИКИ", frame.x + 20, header_y, (200, 200, 220))
        free_surface = self.small_font.render(f"Свободные очки: {free}", True, (255, 220, 120))
        screen.blit(free_surface, free_surface.get_rect(topright=(frame.right - 20, header_y)))
        for index, (stat, label, _) in enumerate(STAT_ROWS):
            row_y = CharacterCard._stat_row_y(frame, index)
            draw_text(screen, self.small_font, f"{label}: {stats[stat]}", frame.x + 20, row_y, (255, 255, 255))
            if stat not in CREATION_ALLOCATABLE_STATS:
                continue
            minus, plus = CharacterCard._stat_control_rects(frame, row_y)
            draw_button(
                screen, minus, "-", self.small_font,
                color=(235, 235, 235), hover_color=(210, 80, 80), text_color=(30, 32, 45),
            )
            draw_button(
                screen, plus, "+", self.small_font,
                color=(235, 235, 235), hover_color=(120, 220, 120), text_color=(30, 32, 45),
            )

    def _card_profile(self, profession):
        """Состояние карточки: HP и MP считаются так же, как сервер при создании персонажа."""
        stats, _ = creation_stats(self.allocation(profession))
        max_hp = calculate_max_hp(1, stats["endurance"])
        max_mp = calculate_max_mana(stats["intellect"])
        return {
            "level": 1,
            "stats": stats,
            "hp": max_hp,
            "max_hp": max_hp,
            "mp": max_mp,
            "max_mp": max_mp,
            "equipment": {},
            "equipment_bonuses": {},
            "carried_weight_kg": 0,
        }

    def _draw_header(self, screen, frame, profession, profile, class_name):
        x = frame.x + 20
        name = self.name.strip()
        name_surface = self.card_name_font.render(
            name or "Имя персонажа",
            True,
            (240, 240, 245) if name else (110, 115, 130),
        )
        name_rect = name_surface.get_rect(topleft=(x + PROFESSION_ICON_SIZE + PROFESSION_ICON_GAP, frame.y + 20))
        icon_box = pygame.Rect(0, 0, PROFESSION_ICON_SIZE, PROFESSION_ICON_SIZE)
        icon_box.midleft = (x, name_rect.centery)
        pygame.draw.rect(screen, (24, 29, 30), icon_box, border_radius=4)
        pygame.draw.rect(screen, (82, 88, 76), icon_box, 1, border_radius=4)
        icon = profession_icon(profession)
        if icon is not None:
            screen.blit(icon, icon_box)
        screen.blit(name_surface, name_rect)

        level_surface = self.card_small_font.render("Уровень 1", True, (210, 215, 225))
        level_rect = level_surface.get_rect(topleft=(x, frame.y + 48))
        screen.blit(level_surface, level_rect)
        class_surface = self.card_small_font.render(class_name, True, (150, 180, 220))
        screen.blit(class_surface, class_surface.get_rect(topleft=(level_rect.right + 15, frame.y + 48)))

        current_hp, max_hp = displayed_hp_values(profile)
        self._draw_resource(screen, x, frame.y + 100, 360, 14, "HP", current_hp, max_hp, (210, 80, 80))
        self._draw_resource(screen, x, frame.y + 140, 360, 14, "MP", profile["mp"], profile["max_mp"], (60, 140, 220))

    def _draw_resource(self, screen, x, y, width, height, name, value, maximum, color):
        """Полоска HP или MP с подписью над ней, как на карточке персонажа."""
        ratio = max(0.0, min(1.0, value / max(1, maximum)))
        label = self.card_small_font.render(f"{name} {int(value)}/{int(maximum)}", True, (210, 215, 225))
        screen.blit(label, (x, y - label.get_height() - 2))
        bar_rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(screen, (40, 10, 10), bar_rect)
        pygame.draw.rect(screen, color, (bar_rect.x, bar_rect.y, int(bar_rect.width * ratio), bar_rect.height))

    def _draw_info_lines(self, screen, frame, profile):
        """Вес, скорость и дальность удара под слотом обуви."""
        carried_kg = float(profile["carried_weight_kg"])
        capacity_kg = character_carry_capacity(profile)
        speeds = combat_speed_values(profile)
        reach = get_attack_reach(SimpleNamespace(**{key: int(value) for key, value in profile["stats"].items()}))
        lines = (
            (f"Грузоподъёмность: {carried_kg:g}/{capacity_kg} кг", load_color(carried_kg, capacity_kg)),
            (f"Скорость атаки: {speeds['attack_seconds']:g} с", (235, 215, 150)),
            (f"Скорость передвижения: {speeds['move_speed']} px/с", (150, 220, 255)),
            (f"Дальность удара: {reach:g} px", (255, 190, 150)),
        )
        top = equipment_slots.slot_rects(frame)["feet"].bottom + 6
        for text, color in lines:
            surface = self.small_font.render(text, True, color)
            back = pygame.Rect(0, top, surface.get_width() + 12, surface.get_height() + 4)
            back.midtop = (frame.centerx, top)
            pygame.draw.rect(screen, (24, 29, 30), back, border_radius=4)
            pygame.draw.rect(screen, (82, 88, 76), back, 1, border_radius=4)
            screen.blit(surface, surface.get_rect(center=back.center))
            top = back.bottom + 2

    def close(self):
        pass
