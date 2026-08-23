from ui.hud import draw_text, draw_bar, draw_silhouette
from ui.sprite_loader import FighterSprite

class FighterPanelRenderer:
    def __init__(self, scene, layout):
        self.scene = scene
        self.layout = layout
        self.fighter_sprite = FighterSprite()  # Загрузчик переехал сюда

    def draw(self, screen, x, fighter, color, title):
        # Заголовок
        title_surface = self.scene.big.render(title, True, color)
        title_rect = title_surface.get_rect(center=(x, self.layout.panel_title_y))
        screen.blit(title_surface, title_rect)

        ox = self.layout.panel_text_x_offset

        # Имя и уровень
        draw_text(
            screen,
            self.scene.font,
            f"{fighter.name}, уровень {fighter.level}",
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
            fg=color,
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
        sprite_drawn = self.fighter_sprite.draw(screen, x, self.layout.silhouette_y + 270)
        if not sprite_drawn:
            draw_silhouette(screen, x, self.layout.silhouette_y, color)
