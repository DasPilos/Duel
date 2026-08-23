from ui.hud import (
    draw_text,
    draw_button,
    update_and_draw_floating_texts,
)

from ui.renderers.fighter_panel import FighterPanelRenderer
from ui.renderers.setup_area import SetupAreaRenderer
from ui.renderers.choice_area import ChoiceAreaRenderer
from ui.renderers.log_area import LogRenderer


class DuelRenderer:
    def __init__(self, scene):
        self.scene = scene
        self.layout = scene.layout

        self.fighter_renderer = FighterPanelRenderer(
            scene,
            self.layout,
        )

        self.setup_renderer = SetupAreaRenderer(
            scene,
            self.layout,
        )

        self.choice_renderer = ChoiceAreaRenderer(
            scene,
            self.layout,
        )

        self.log_renderer = LogRenderer(
            scene,
            self.layout,
        )

    def draw(self, screen):
        screen.fill((16, 18, 28))

        self.draw_header(screen)

        self.fighter_renderer.draw(
            screen,
            self.layout.player_panel_x,
            self.scene.player,
            (80, 180, 120),
            "ИГРОК",
        )

        self.fighter_renderer.draw(
            screen,
            self.layout.enemy_panel_x,
            self.scene.enemy,
            (210, 80, 80),
            "ПРОТИВНИК",
        )

        if self.scene.phase == "setup":
            self.setup_renderer.draw(screen)

        elif self.scene.phase == "choose":
            self.choice_renderer.draw(screen)

        elif self.scene.phase == "resolve":
            self.draw_resolve_overlay(screen)

        elif self.scene.phase == "result":
            self.draw_result_screen(screen)

        # Лог теперь отображается на всех фазах (кроме "setup",
        # это уже проверяется внутри самого LogRenderer),
        # включая экран результата боя.
        self.log_renderer.draw(screen)

        update_and_draw_floating_texts(
            screen,
            self.scene.active_floating_texts,
        )

    def draw_header(self, screen):
        draw_text(
            screen,
            self.scene.big,
            "МИНИ-ДУЭЛЬ",
            self.layout.header_x,
            self.layout.header_y,
            (240, 240, 255),
        )

    def draw_resolve_overlay(self, screen):
        titles = {
            "CALC": "РАСЧЁТ ХОДА...",
            "COMMENTS": "ОБНОВЛЯЕМ ЛОГ...",
            "END": "ПРОДОЛЖЕНИЕ...",
        }

        draw_text(
            screen,
            self.scene.big,
            titles.get(
                self.scene.resolve_state,
                "ХОД",
            ),
            self.layout.overlay_x,
            self.layout.overlay_title_y,
            (255, 220, 120),
        )

        draw_text(
            screen,
            self.scene.font,
            "Клики по зонам заблокированы",
            self.layout.overlay_description_x,
            self.layout.overlay_description_y,
            (170, 170, 170),
        )

    def draw_result_screen(self, screen):
        battle = self.scene.battle

        player_stats_x = (
            self.layout.player_panel_x + 180
        )

        enemy_stats_x = (
            self.layout.enemy_panel_x - 400
        )

        stats_y = 360

        self.draw_result_stats(
            screen,
            player_stats_x,
            stats_y,
            "СТАТИСТИКА ИГРОКА",
            battle.stats["player"],
            (120, 240, 170),
        )

        self.draw_result_stats(
            screen,
            enemy_stats_x,
            stats_y,
            "СТАТИСТИКА ВРАГА",
            battle.stats["enemy"],
            (240, 130, 130),
        )

        draw_text(
            screen,
            self.scene.font,
            "БОЙ ЗАВЕРШЁН",
            820,
            325,
            (255, 220, 120),
        )

        draw_text(
            screen,
            self.scene.small_font,
            f"ПОБЕДИТЕЛЬ: {battle.winner_name()}",
            800,
            350,
            (120, 240, 150),
        )

        draw_button(
            screen,
            self.layout.new_button,
            "НОВЫЙ БОЙ (R)",
            self.scene.font,
            color=(70, 140, 220),
        )

    def draw_result_stats(
        self,
        screen,
        x,
        y,
        title,
        stats,
        title_color,
    ):
        draw_text(
            screen,
            self.scene.small_font,
            title,
            x,
            y,
            title_color,
        )

        y += 22

        values = [
            f"Атак: {stats['attacks']}",
            f"Попаданий: {stats['hits']}",
            f"Урон: {stats['damage']}",
            f"Критов: {stats['critical']}",
            f"Уворотов: {stats['dodges']}",
            f"Блоков: {stats['blocks']}",
            f"Комбо: {stats['combo_sessions']}",
            f"Макс. комбо: {stats['max_combo']}",
        ]

        for value in values:
            draw_text(
                screen,
                self.scene.small_font,
                value,
                x,
                y,
                (205, 205, 215),
            )

            y += 18
