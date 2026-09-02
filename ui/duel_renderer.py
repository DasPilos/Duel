from pathlib import Path
import time

import pygame

from core import settings
from ui.hud import draw_text, draw_button, update_and_draw_floating_texts

from ui.character_card import CharacterCard
from ui.renderers.card_area import CardAreaRenderer


class DuelRenderer:
    def __init__(self, scene):
        self.scene = scene
        self.layout = scene.layout

        self.player_card = CharacterCard()
        self.enemy_card = CharacterCard()

        self.card_renderer = CardAreaRenderer(
            scene,
            self.layout,
        )
        self.background = None
        background_path = Path(__file__).resolve().parent.parent / "assets" / "combat" / "background.png"
        try:
            source = pygame.image.load(str(background_path)).convert()
            self.background = pygame.transform.smoothscale(source, (settings.WIDTH, settings.HEIGHT))
        except (pygame.error, OSError):
            self.background = None
        self.hit_placeholder = None
        placeholder_path = Path(__file__).resolve().parent.parent / "assets" / "combat" / "hit_placeholder.png"
        try:
            self.hit_placeholder = pygame.image.load(str(placeholder_path)).convert_alpha()
        except (pygame.error, OSError):
            self.hit_placeholder = None

    def draw(self, screen):
        if self.background is None or screen.get_size() != self.background.get_size():
            screen.fill((16, 18, 28))
        else:
            screen.blit(self.background, (0, 0))

        if self.scene.phase == "result":
            self.draw_result(screen)
            return
        
        if self.scene.phase in ("result_transition", "battle_start_transition"):
            if self.scene.phase_transition.draw(screen):
                return

        self.draw_header(screen)

        if self.scene.phase in ("intro_table", "intro_deck", "draft_reveal", "draft", "draft_transfer", "enemy_transfer", "strength_transfer", "draft_cleanup", "planning", "waiting_enemy", "clash", "damage", "deck_shuffle", "card_draw", "card_return"):
            self.card_renderer.draw(screen)

        elif self.scene.phase == "resolve":
            self.draw_resolve_overlay(screen)


        if self.scene.chat is not None:
            self.scene.chat.draw(screen)

        # Рисуем статические характеристики в углах вместо всплывающих карточек
        self.draw_battle_stats(screen)

        update_and_draw_floating_texts(
            screen,
            self.scene.active_floating_texts,
        )

        # Кнопка инвентаря в верхнем правом углу
        pygame.draw.rect(screen, (100, 100, 120), self.scene.inventory_button)
        pygame.draw.rect(screen, (150, 150, 170), self.scene.inventory_button, 2)
        inv_text = self.scene.font.render("📦", True, (255, 255, 255))
        inv_rect = inv_text.get_rect(center=self.scene.inventory_button.center)
        screen.blit(inv_text, inv_rect)

        # Если открыто через инвентарь (counterpart is None), показываем только левую панель
        show_player_only = self.scene.profile_overlay.counterpart is None
        self.scene.profile_overlay.draw(
            screen,
            opponent=self.scene.player,
            show_counterpart=False,
            show_player_only=show_player_only,
        )

    def draw_result(self, screen):
        scene = self.scene
        screen_width, screen_height = screen.get_size()
        
        # Фон панели
        pygame.draw.rect(screen, (25, 27, 38), pygame.Rect(0, 0, screen_width, screen_height))
        
        # Заголовок результата (в центре вверху)
        outcome = scene.battle.outcome()
        title = {"win": "ПОБЕДА", "loss": "ПОРАЖЕНИЕ", "draw": "НИЧЬЯ"}.get(outcome, "БОЙ ОКОНЧЕН")
        title_color = (110, 235, 120) if outcome == "win" else (235, 110, 100) if outcome == "loss" else (255, 220, 120)
        title_surface = scene.big.render(title, True, title_color)
        screen.blit(title_surface, title_surface.get_rect(center=(screen_width // 2, 40)))
        
        # Информация о победителе
        winner_text = f"Победитель: {scene.battle.winner_name() or 'Ничья'}"
        draw_text(screen, scene.small_font, winner_text, screen_width // 2 - 100, 100, (220, 220, 225))
        
        # Параметры панелей с информацией о игроке и противнике
        left_margin = 50
        right_margin = 50
        usable_width = screen_width - left_margin - right_margin
        half_width = usable_width // 2 - 25  # 25px gap между панелями
        
        player_x = left_margin
        enemy_x = left_margin + half_width + 50
        y_start = 150
        
        for index, side in enumerate(("player", "enemy")):
            stats = scene.battle.stats[side]
            fighter = scene.player if side == "player" else scene.enemy
            
            if side == "player":
                x, side_color = player_x, (80, 180, 120)
            else:
                x, side_color = enemy_x, (210, 100, 90)
            
            # Имя и статистика
            draw_text(screen, scene.font, fighter.name, x, y_start, (255, 220, 120))
            
            stats_lines = (
                f"Критов: {stats['critical']}",
                f"Уворотов: {stats['dodges']}",
                f"Ударов прошло: {stats['hits']}",
                f"Урона нанесено: {stats['damage']}",
                f"Восстановлено: {stats['healed']} HP",
                f"Карт использовано: {stats['cards_played']}",
            )
            
            for line_idx, line in enumerate(stats_lines):
                draw_text(screen, scene.small_font, line, x, y_start + 35 + line_idx * 25, (215, 220, 230))
            
            # Рисуем карты в столбик
            cards_y = y_start + 35 + len(stats_lines) * 25 + 20
            draw_text(screen, scene.small_font, "Карты:", x, cards_y, side_color)
            
            # Скролл для карт
            cards_panel_height = screen_height - cards_y - 110
            card_height = 24
            max_visible_cards = max(1, cards_panel_height // card_height)
            
            # Получаем уникальные карты (без дубликатов)
            unique_cards = []
            seen = set()
            for card_name in stats["cards"]:
                if card_name not in seen:
                    unique_cards.append(card_name)
                    seen.add(card_name)
            
            # Скролл для карт (сохраняем в scene если его еще нет)
            scroll_key = f"cards_scroll_{side}"
            if not hasattr(scene, scroll_key):
                setattr(scene, scroll_key, 0)
            
            scroll_offset = getattr(scene, scroll_key)
            max_scroll = max(0, len(unique_cards) * card_height - cards_panel_height)
            scroll_offset = min(scroll_offset, max_scroll)
            setattr(scene, scroll_key, scroll_offset)
            
            # Рисуем карты с уроном
            for card_idx, card_name in enumerate(unique_cards):
                card_y = cards_y + 30 + card_idx * card_height - scroll_offset
                
                # Проверяем видимость карты
                if card_y + card_height < cards_y + 30 or card_y > screen_height - 110:
                    continue
                
                # Урон нанесен этой картой (если есть)
                damage = stats["card_damage"].get(card_name, 0)
                card_text = f"{card_name}" + (f" ({damage} урон)" if damage > 0 else "")
                
                draw_text(screen, scene.small_font, card_text, x, card_y, (215, 220, 230))
        
        # Кнопка "В ТАВЕРНУ"
        scene.result_button = pygame.Rect(screen_width // 2 - 160, screen_height - 75, 320, 45)
        draw_button(screen, scene.result_button, "В ТАВЕРНУ", scene.font, color=(75, 105, 155))

    def draw_header(self, screen):
        self.draw_turn_timer(screen)

    def draw_resolve_overlay(self, screen):
        if self.hit_placeholder is None:
            return
        image = pygame.transform.smoothscale(self.hit_placeholder, (128, 128))
        image_rect = image.get_rect(center=(960, 520))
        screen.blit(image, image_rect)

    def draw_turn_timer(self, screen):
        if self.scene.turn_deadline is None:
            return
        remaining = max(0, int(self.scene.turn_deadline - time.monotonic()))
        if remaining <= settings.TURN_WARNING_RED_SECONDS:
            color = (220, 70, 70)
        elif remaining <= settings.TURN_WARNING_YELLOW_SECONDS:
            color = (230, 190, 70)
        else:
            color = (80, 200, 120)
        bar = self.layout.turn_bar
        pygame.draw.rect(screen, (55, 58, 68), bar, border_radius=5)
        fill = bar.copy()
        fill.height = int(bar.height * remaining / settings.TURN_DECISION_SECONDS)
        fill.top = bar.bottom - fill.height
        pygame.draw.rect(screen, color, fill, border_radius=5)
        label = self.scene.small_font.render(f"Ход {remaining // 60}:{remaining % 60:02d}", True, color)
        label = pygame.transform.rotate(label, 90)
        screen.blit(label, label.get_rect(midright=(bar.left - 8, bar.centery)))

    def draw_battle_stats(self, screen):
        """Рисует статистику боцов как в карточке персонажа - в верхних углах и характеристики внизу."""
        from ui.character_profile import normalize_character_profile, derived_values
        screen_width, screen_height = screen.get_size()
        
        # Левый верхний угол - Игрок (зелёный)
        player_profile = normalize_character_profile(self.scene.player)
        enemy_profile = normalize_character_profile(self.scene.enemy)
        player_derived = derived_values(player_profile, enemy_profile)
        
        self._draw_corner_fighter_card(
            screen,
            fighter=self.scene.player,
            profile=player_profile,
            derived=player_derived,
            x=10,
            y=10,
            border_color=(80, 180, 120),
            align="left"
        )
        
        # Правый верхний угол - Противник (красный)
        enemy_derived = derived_values(enemy_profile, player_profile)
        
        self._draw_corner_fighter_card(
            screen,
            fighter=self.scene.enemy,
            profile=enemy_profile,
            derived=enemy_derived,
            x=screen_width - 320,
            y=10,
            border_color=(210, 80, 80),
            align="right"
        )
        
        # Левый нижний угол - Характеристики Игрока
        self._draw_corner_stats(
            screen,
            profile=player_profile,
            derived=player_derived,
            x=10,
            y=screen_height - 130,
            border_color=(80, 180, 120)
        )
        
        # Правый нижний угол - Характеристики Противника
        self._draw_corner_stats(
            screen,
            profile=enemy_profile,
            derived=enemy_derived,
            x=screen_width - 320,
            y=screen_height - 130,
            border_color=(210, 80, 80)
        )

    def _draw_corner_fighter_card(self, screen, fighter, profile, derived, x, y, border_color, align):
        """Рисует укороченную карточку боца в углу (Имя, Уровень, HP/MP бары)."""
        width = 310
        height = 170
        
        # Фон с полупрозрачностью
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((30, 32, 45, 200))
        screen.blit(overlay, (x, y))
        
        # Рамка
        pygame.draw.rect(screen, border_color, pygame.Rect(x, y, width, height), width=2, border_radius=8)
        
        inner_x = x + 12
        
        # Имя (большой шрифт как на карточке)
        name_surface = self.scene.small_font.render(fighter.name, True, (240, 240, 245))
        name_rect = name_surface.get_rect(topleft=(inner_x, y + 8))
        screen.blit(name_surface, name_rect)
        
        # ID рядом с именем
        id_text = f"ID: {fighter.character_id or 'N/A'}"
        draw_text(screen, self.scene.small_font, id_text, name_rect.right + 15, y + 10, (170, 175, 185))
        
        # Уровень
        level_text = f"Уровень {fighter.level}"
        draw_text(screen, self.scene.small_font, level_text, inner_x, y + 28, (210, 215, 225))
        
        # HP шкала (опущена вниз чтобы не наплывать на текст)
        hp_y = y + 65
        bar_width = 280
        bar_height = 11
        self._draw_resource_bar(
            screen,
            inner_x,
            hp_y,
            bar_width,
            bar_height,
            "HP",
            profile["hp"],
            profile["max_hp"],
            (210, 80, 80)
        )
        
        # MP шкала ниже HP
        mp_y = y + 105
        self._draw_resource_bar(
            screen,
            inner_x,
            mp_y,
            bar_width,
            bar_height,
            "MP",
            profile["mp"],
            profile["max_mp"],
            (60, 140, 220)
        )

    def _draw_corner_stats(self, screen, profile, derived, x, y, border_color):
        """Рисует характеристики боца в углу (Урон, Уворот, Крит, HP) как на карточке."""
        width = 310
        height = 100
        
        # Фон с полупрозрачностью
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((30, 32, 45, 200))
        screen.blit(overlay, (x, y))
        
        # Рамка
        pygame.draw.rect(screen, border_color, pygame.Rect(x, y, width, height), width=2, border_radius=8)
        
        inner_x = x + 12
        header_y = y + 8
        
        # Заголовок "ХАРАКТЕРИСТИКИ"
        draw_text(screen, self.scene.small_font, "ХАРАКТЕРИСТИКИ", inner_x, header_y, border_color)
        
        # Характеристики как на карточке (в 2 колонки)
        stats = profile.get("stats", {})
        stat_names = (
            ("strength", "Сила", "Урон"),
            ("agility", "Ловкость", "Уворот"),
            ("intuition", "Интуиция", "Крит"),
            ("endurance", "Выносливость", "HP"),
        )
        
        stat_value_colors = {
            "Урон": (255, 255, 255),
            "Уворот": (150, 220, 255),
            "Крит": (255, 90, 90),
            "HP": (110, 235, 120),
        }
        
        # Левая колонка (имена статов)
        col1_x = inner_x
        # Правая колонка (производные значения)
        col2_x = inner_x + 150
        
        for index, (key, label, derived_key) in enumerate(stat_names):
            row_y = header_y + 22 + index * 16
            
            # Левая: название стата и значение
            stat_text = f"{label}: {stats.get(key, 0)}"
            draw_text(screen, self.scene.small_font, stat_text, col1_x, row_y, (215, 220, 225))
            
            # Правая: производное значение (Урон, Уворот, Крит, HP)
            derived_text = f"{derived_key}: {derived[derived_key]}"
            color = stat_value_colors.get(derived_key, (220, 70, 70))
            draw_text(screen, self.scene.small_font, derived_text, col2_x, row_y, color)

    def _draw_resource_bar(self, screen, x, y, bar_width, bar_height, label, current, maximum, color):
        """Рисует полосу ресурса (HP/MP) как на карточке."""
        # Текст выше бара (как на карточке)
        text = f"{label}: {int(current)}/{int(maximum)}"
        draw_text(screen, self.scene.small_font, text, x, y - 15, (220, 225, 235))
        
        # Бары опущены на 4px вниз (y + 4)
        bar_y = y + 4
        
        # Фон шкалы
        pygame.draw.rect(screen, (50, 50, 50), pygame.Rect(x, bar_y, bar_width, bar_height), border_radius=2)
        
        # Полоска ресурса
        if maximum > 0:
            ratio = max(0, min(1.0, current / maximum))
            filled_width = int(bar_width * ratio)
            pygame.draw.rect(screen, color, pygame.Rect(x, bar_y, filled_width, bar_height), border_radius=2)


