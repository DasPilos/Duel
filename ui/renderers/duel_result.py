from core import settings
from ui.hud import draw_button, draw_text


class DuelResultRenderer:
    """Draws the battle outcome without owning battle state."""

    def __init__(self, scene, layout):
        self.scene = scene
        self.layout = layout

    def draw(self, screen):
        battle = self.scene.battle
        self._draw_stats(
            screen,
            settings.CHAT_PANEL_X,
            360,
            "СТАТИСТИКА ИГРОКА",
            battle.stats["player"],
            (120, 240, 170),
        )
        self._draw_stats(
            screen,
            self.layout.battle_enemy_card.left - 180,
            360,
            "СТАТИСТИКА ВРАГА",
            battle.stats["enemy"],
            (240, 130, 130),
        )
        draw_text(screen, self.scene.font, "БОЙ ЗАВЕРШЁН", 820, 325, (255, 220, 120))
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
            "ВЕРНУТЬСЯ В ТРАКТИР (R)"
            if self.scene.online_session is not None
            else "НОВЫЙ БОЙ (R)",
            self.scene.font,
            color=(70, 140, 220),
        )

    def _draw_stats(self, screen, x, y, title, stats, title_color):
        draw_text(screen, self.scene.small_font, title, x, y, title_color)
        values = [
            f"Попаданий: {stats['hits']}",
            f"Урон: {stats['damage']}",
            f"Критов: {stats['critical']}",
            f"Уворотов: {stats['dodges']}",
            f"Блоков: {stats['blocks']}",
            f"Комбо: {stats['combo_sessions']}",
            f"Макс. комбо: {stats['max_combo']}",
        ]
        if title == "СТАТИСТИКА ИГРОКА":
            values.append(f"Получено опыта: {self.scene.battle.xp_awarded} XP")
        for index, value in enumerate(values):
            draw_text(screen, self.scene.small_font, value, x, y + 22 + index * 18, (205, 205, 215))
