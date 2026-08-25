from ui.hud import draw_text, draw_bar, draw_silhouette, draw_button
from ui.sprite_loader import FighterSprite
from core import settings
import pygame

class FighterPanelRenderer:
    def __init__(self, scene, layout):
        self.scene = scene
        self.layout = layout
        self.fighter_sprite = FighterSprite()  # Загрузчик переехал сюда

    def draw(self, screen, x, fighter, color, title):
        # Заголовок
        title_surface = self.scene.big.render(fighter.name, True, color)
        title_rect = title_surface.get_rect(center=(x, self.layout.panel_title_y))
        screen.blit(title_surface, title_rect)

        ox = self.layout.panel_text_x_offset

        # Уровень
        draw_text(
            screen,
            self.scene.font,
            f"Уровень {fighter.level}",
            x - ox,
            self.layout.panel_name_y,
        )

        # HP
        draw_text(
            screen,
            self.scene.font,
            f"HP: {fighter.hp}/{fighter.max_hp}",
            x - ox,
            self.layout.panel_hp_y,
        )
        draw_bar(
            screen,
            x - ox,
            self.layout.panel_hp_bar_y,
            280,
            22,
            fighter.hp,
            fighter.max_hp,
            fg=(210, 80, 80),
        )

        # MP
        draw_text(
            screen,
            self.scene.font,
            f"MP: {fighter.mp}/{fighter.max_mp}",
            x - ox,
            self.layout.panel_mp_y,
        )
        draw_bar(
            screen,
            x - ox,
            self.layout.panel_mp_bar_y,
            280,
            22,
            fighter.mp,
            fighter.max_mp,
            fg=(60, 140, 220),
        )

        # Отрисовка спрайта или силуэта
        sprite_drawn = self.fighter_sprite.draw(
            screen,
            x,
            self.layout.silhouette_y + 270,
            scale=settings.FIGHTER_SPRITE_SCALE,
        )
        if not sprite_drawn:
            draw_silhouette(screen, x, self.layout.silhouette_y, color)

        self.draw_stats(screen, x, fighter, color)

    def draw_stats(self, screen, x, fighter, color):
        side = "player" if fighter is self.scene.player else "enemy"

        # Шрифт и подзаголовок в стиле карточек персонажа
        stat_font = pygame.font.SysFont(
            "arial",
            18,
        )
        draw_text(
            screen,
            self.scene.small_font,
            "ХАРАКТЕРИСТИКИ",
            self.layout.stat_label_x[side],
            self.layout.stat_points_y - 24,
            color,
        )

        draw_text(
            screen,
            stat_font,
            f"Св. очк: {fighter.stat_points}",
            self.layout.stat_points_x[side],
            self.layout.stat_points_y,
            (255, 220, 120),
        )

        stat_order = ["strength", "agility", "intuition", "endurance"]
        stat_short_names = {
            "strength": "Сила",
            "agility": "Ловкость",
            "intuition": "Интуиция",
            "endurance": "Выносливость",
        }
        for stat_name in stat_order:
            y = self.layout.stat_row_y[stat_name]

            draw_text(
                screen,
                stat_font,
                f"{stat_short_names[stat_name]}: {fighter.stats[stat_name]}",
                self.layout.stat_label_x[side],
                y,
                (230, 230, 230),
            )

            if self.scene.phase == "setup":
                can_remove = fighter.stats[stat_name] > 4
                can_add = fighter.stat_points > 0
                draw_button(
                    screen,
                    self.layout.stat_minus_buttons[side][stat_name],
                    "-",
                    stat_font,
                    color=(200, 90, 90) if can_remove else (90, 90, 100),
                )
                draw_button(
                    screen,
                    self.layout.stat_plus_buttons[side][stat_name],
                    "+",
                    stat_font,
                    color=(80, 200, 120) if can_add else (90, 90, 100),
                )
