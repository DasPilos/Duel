from ui.hud import draw_text, draw_button

class SetupAreaRenderer:
    def __init__(self, scene, layout):
        self.scene = scene
        self.layout = layout

    def draw(self, screen):
        draw_text(
            screen,
            self.scene.big,
            "РАСПРЕДЕЛЕНИЕ ХАРАКТЕРИСТИК",
            self.layout.stat_setup_title_x,
            self.layout.stat_setup_title_y,
            (100, 200, 120),
        )

        draw_text(
            screen,
            self.scene.font,
            f"Свободных очков: {self.scene.player.stat_points}",
            self.layout.stat_points_x,
            self.layout.stat_points_y,
            (255, 220, 120),
        )

        stat_order = ["strength", "agility", "intuition", "endurance"]

        for stat_name in stat_order:
            y = self.layout.stat_row_y[stat_name]
            label = self.scene.player.STAT_NAMES[stat_name]
            value = self.scene.player.stats[stat_name]

            draw_text(screen, self.scene.font, label, self.layout.stat_label_x, y + 15, (230, 230, 230))
            draw_text(screen, self.scene.font, str(value), self.layout.stat_value_x, y + 15, (255, 255, 255))

            can_remove = value > 4
            draw_button(
                screen,
                self.layout.stat_minus_buttons[stat_name],
                "-",
                self.scene.font,
                color=(200, 90, 90) if can_remove else (90, 90, 100),
            )

            can_add = self.scene.player.stat_points > 0
            draw_button(
                screen,
                self.layout.stat_plus_buttons[stat_name],
                "+",
                self.scene.font,
                color=(80, 200, 120) if can_add else (90, 90, 100),
            )

        ready = self.scene.player.is_ready()
        draw_button(
            screen,
            self.layout.stat_confirm_button,
            "НАЧАТЬ БОЙ",
            self.scene.font,
            color=(80, 200, 120) if ready else (100, 100, 110),
        )
