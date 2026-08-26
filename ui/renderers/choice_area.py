from ui.hud import draw_text, draw_button
from combat.zones import ZONES

class ChoiceAreaRenderer:
    def __init__(self, scene, layout):
        self.scene = scene
        self.layout = layout

    def draw(self, screen):
        draw_text(
            screen,
            self.scene.font,
            "АТАКА",
            self.layout.attack_title_x,
            self.layout.choice_title_y,
            (255, 110, 110),
        )

        draw_text(
            screen,
            self.scene.font,
            "ЗАЩИТА",
            self.layout.defense_title_x,
            self.layout.choice_title_y,
            (110, 180, 255),
        )

        for zone in self.scene.zone_names:
            name = ZONES[zone]

            # Кнопки атаки
            draw_button(
                screen,
                self.layout.attack_buttons[zone],
                name,
                self.scene.font,
                color=(200, 60, 60) if self.scene.attack_zone == zone else (80, 80, 90),
                hover_color=(220, 80, 80),
            )

            # Кнопки защиты
            draw_button(
                screen,
                self.layout.defense_buttons[zone],
                name,
                self.scene.font,
                color=(60, 120, 200) if zone in self.scene.defense_zones else (80, 80, 90),
                hover_color=(80, 140, 220),
            )

        ready = (
            self.scene.attack_zone is not None
            and len(self.scene.defense_zones) == 2
        )

        draw_button(
            screen,
            self.layout.confirm_button,
            "ПОДТВЕРДИТЬ ХОД",
            self.scene.font,
            color=(80, 200, 120) if ready else (100, 100, 110),
        )
