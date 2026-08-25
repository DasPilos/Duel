from ui.hud import draw_button

class SetupAreaRenderer:
    def __init__(self, scene, layout):
        self.scene = scene
        self.layout = layout

    def draw(self, screen):
        ready = self.scene.player.is_ready()
        draw_button(
            screen,
            self.layout.stat_confirm_button,
            "НАЧАТЬ БОЙ",
            self.scene.font,
            color=(80, 200, 120) if ready else (100, 100, 110),
        )
