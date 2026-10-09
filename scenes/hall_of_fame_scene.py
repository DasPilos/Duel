import json
import time

import pygame

from client.network import ServerError
from core import settings
from ui.hud import draw_button, draw_text

OUTCOME_LABELS = {"win": "Победа", "draw": "Ничья", "loss": "Поражение"}


class HallOfFameScene:
    PAGE_SIZE = 12

    def __init__(self, session):
        self.session = session
        self.finished = False
        self.error = ""
        self.offset = 0
        self.total = 0
        self.records = []
        self.selected = None
        self.history_index = 0
        self.history_scroll = 0
        self.font = pygame.font.SysFont(settings.FONT_NAME, 20)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 16)
        self.tiny_font = pygame.font.SysFont(settings.FONT_NAME, 14)
        self.back_button = pygame.Rect(50, 30, 190, 42)
        self.previous_page_button = pygame.Rect(405, 935, 64, 42)
        self.next_page_button = pygame.Rect(478, 935, 64, 42)
        self.previous_turn_button = pygame.Rect(1510, 935, 96, 42)
        self.next_turn_button = pygame.Rect(1615, 935, 96, 42)
        self.list_rect = pygame.Rect(50, 100, 700, 890)
        self.detail_rect = pygame.Rect(775, 100, 1095, 890)
        self.row_rects = []
        self.load_page()

    def load_page(self):
        try:
            result = self.session.list_battle_archive(self.PAGE_SIZE, self.offset)
            self.records = result.get("battles", [])
            self.total = int(result.get("total", 0))
            visible_ids = {int(row["id"]) for row in self.records}
            if self.selected is not None and int(self.selected["id"]) not in visible_ids:
                self.selected = None
            self.error = ""
        except (ServerError, AttributeError, KeyError, OSError) as error:
            self.records = []
            self.total = 0
            self.error = str(error)

    def select_record(self, record_id):
        try:
            self.selected = self.session.get_battle_archive_record(record_id)
            self.history_index = 0
            self.history_scroll = 0
            self.error = ""
        except (ServerError, AttributeError, KeyError, OSError) as error:
            self.selected = None
            self.error = str(error)

    def _change_page(self, delta):
        next_offset = self.offset + int(delta) * self.PAGE_SIZE
        if next_offset < 0 or next_offset >= self.total:
            return
        self.offset = next_offset
        self.selected = None
        self.load_page()

    @staticmethod
    def _fit(text, font, width):
        text = str(text)
        while text and font.size(text)[0] > width:
            text = text[:-4] + "..." if len(text) > 4 else text[:-1]
        return text

    @staticmethod
    def _event_text(event, player_name, opponent_name):
        if not isinstance(event, dict):
            return str(event)
        side = {"player": player_name, "enemy": opponent_name}.get(event.get("side"), event.get("side", ""))
        parts = [str(side)] if side else []
        for key in ("card", "action", "effect", "text", "target", "damage", "healed", "critical", "dodged"):
            value = event.get(key)
            if value is not None and value != "":
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                parts.append(f"{key}: {value}")
        return " · ".join(parts) if parts else json.dumps(event, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _wrap(text, font, width):
        words = str(text).split()
        if not words:
            return [""]
        lines = []
        line = words[0]
        for word in words[1:]:
            candidate = f"{line} {word}"
            if font.size(candidate)[0] <= width:
                line = candidate
            else:
                lines.append(line)
                line = word
        lines.append(line)
        return lines

    def _history_events(self):
        replay = (self.selected or {}).get("replay_json", {})
        history = replay.get("history") or []
        if not history:
            return [], 0
        self.history_index = max(0, min(self.history_index, len(history) - 1))
        entry = history[self.history_index]
        events = entry.get("events", []) if isinstance(entry, dict) else []
        player_name = replay.get("player", {}).get("name", "Игрок")
        opponent_name = replay.get("enemy", {}).get("name", "Соперник")
        lines = []
        for event in events:
            lines.extend(self._wrap(self._event_text(event, player_name, opponent_name), self.small_font,
                                    self.detail_rect.width - 70))
        return lines, len(history)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.finished = True
            return
        if event.type == pygame.MOUSEWHEEL:
            if self.detail_rect.collidepoint(pygame.mouse.get_pos()):
                lines, _ = self._history_events()
                self.history_scroll = max(0, min(max(0, len(lines) - 18), self.history_scroll - event.y * 3))
            return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if self.back_button.collidepoint(event.pos):
            self.finished = True
        elif self.previous_page_button.collidepoint(event.pos):
            self._change_page(-1)
        elif self.next_page_button.collidepoint(event.pos):
            self._change_page(1)
        elif self.previous_turn_button.collidepoint(event.pos) and self.selected is not None:
            self.history_index = max(0, self.history_index - 1)
            self.history_scroll = 0
        elif self.next_turn_button.collidepoint(event.pos) and self.selected is not None:
            history = (self.selected.get("replay_json") or {}).get("history", [])
            self.history_index = min(max(0, len(history) - 1), self.history_index + 1)
            self.history_scroll = 0
        else:
            for record, rect in zip(self.records, self.row_rects):
                if rect.collidepoint(event.pos):
                    self.select_record(record["id"])
                    return

    def update(self, _dt):
        pass

    def draw(self, screen):
        screen.fill((16, 18, 28))
        pygame.draw.rect(screen, (27, 30, 41), self.list_rect, border_radius=8)
        pygame.draw.rect(screen, (73, 81, 102), self.list_rect, 1, border_radius=8)
        pygame.draw.rect(screen, (27, 30, 41), self.detail_rect, border_radius=8)
        pygame.draw.rect(screen, (73, 81, 102), self.detail_rect, 1, border_radius=8)
        draw_button(screen, self.back_button, "НАЗАД", self.small_font, color=(67, 73, 87))
        title = self.font.render("ЗАЛ СЛАВЫ", True, (238, 210, 146))
        screen.blit(title, title.get_rect(center=(settings.WIDTH // 2, 50)))
        draw_text(screen, self.small_font, f"Всего боёв: {self.total}", 75, 125, (200, 204, 214))

        self.row_rects = []
        row_top = 165
        row_height = 62
        for index, record in enumerate(self.records):
            rect = pygame.Rect(68, row_top + index * row_height, 664, 54)
            self.row_rects.append(rect)
            is_selected = self.selected is not None and int(self.selected["id"]) == int(record["id"])
            pygame.draw.rect(screen, (57, 62, 76) if is_selected else (36, 40, 51), rect, border_radius=5)
            name_line = f"{record['player_name']}  vs  {record['opponent_name']}"
            draw_text(screen, self.small_font, self._fit(name_line, self.small_font, rect.width - 20),
                      rect.x + 10, rect.y + 5, (235, 235, 239))
            result_color = (112, 207, 132) if record.get("outcome") == "win" else (222, 150, 110)
            timestamp = time.strftime("%d.%m.%Y %H:%M", time.localtime(float(record["created_at"])))
            outcome_label = OUTCOME_LABELS.get(record.get("outcome"), "Бой")
            result_line = f"{timestamp} · ур. {record['player_level']}:{record['opponent_level']} · {outcome_label} · ходов {record['turns']}"
            draw_text(screen, self.tiny_font, result_line, rect.x + 10, rect.y + 31, result_color)

        page_count = max(1, (self.total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        current_page = self.offset // self.PAGE_SIZE + 1
        draw_button(screen, self.previous_page_button, "<", self.font,
                    color=(57, 63, 76) if self.offset else (37, 40, 48))
        draw_button(screen, self.next_page_button, ">", self.font,
                    color=(57, 63, 76) if self.offset + self.PAGE_SIZE < self.total else (37, 40, 48))
        page_label = self.small_font.render(f"Страница {current_page}/{page_count}", True, (190, 195, 207))
        screen.blit(page_label, page_label.get_rect(center=(625, 956)))

        if self.error:
            draw_text(screen, self.small_font, self.error, 75, 900, (248, 121, 105))
        if self.selected is None:
            text = "Выберите бой слева" if self.records else "Завершённых боёв пока нет"
            label = self.font.render(text, True, (194, 199, 211))
            screen.blit(label, label.get_rect(center=self.detail_rect.center))
            return

        record = self.selected
        replay = record.get("replay_json", {})
        player = replay.get("player", {})
        enemy = replay.get("enemy", {})
        draw_text(screen, self.font,
                  f"{record['player_name']}  vs  {record['opponent_name']}",
                  self.detail_rect.x + 28, self.detail_rect.y + 24, (241, 222, 174))
        summary = (f"{time.strftime('%d.%m.%Y %H:%M:%S', time.localtime(float(record['created_at'])))}  ·  "
                   f"уровни {record['player_level']}:{record['opponent_level']}  ·  "
                   f"победитель: {record['winner_name'] or 'ничья'}  ·  ходов: {record['turns']}")
        draw_text(screen, self.small_font, summary, self.detail_rect.x + 28,
                  self.detail_rect.y + 64, (197, 202, 213))
        stats = replay.get("stats", {})
        player_stats = stats.get("player", {}) if isinstance(stats, dict) else {}
        enemy_stats = stats.get("enemy", {}) if isinstance(stats, dict) else {}
        stats_text = (f"Урон: {record['player_name']} {player_stats.get('damage', 0)}  ·  "
                      f"{record['opponent_name']} {enemy_stats.get('damage', 0)}  ·  "
                      f"HP в конце: {player.get('hp', '?')}:{enemy.get('hp', '?')}")
        draw_text(screen, self.small_font, stats_text, self.detail_rect.x + 28,
                  self.detail_rect.y + 98, (168, 196, 218))
        pygame.draw.line(screen, (70, 76, 91), (self.detail_rect.x + 24, 260),
                         (self.detail_rect.right - 24, 260), 1)

        events, history_count = self._history_events()
        if not history_count:
            draw_text(screen, self.small_font, "Подробная история ходов в этой записи отсутствует.",
                      self.detail_rect.x + 28, self.detail_rect.y + 190, (196, 198, 205))
        else:
            turn_value = replay.get("history", [])[self.history_index].get("turn", self.history_index + 1)
            draw_text(screen, self.small_font, f"Ход {turn_value} из {history_count}",
                      self.detail_rect.x + 28, self.detail_rect.y + 180, (238, 210, 146))
            visible = events[self.history_scroll:self.history_scroll + 18]
            for line_index, line in enumerate(visible):
                draw_text(screen, self.tiny_font, line,
                          self.detail_rect.x + 32, self.detail_rect.y + 218 + line_index * 28,
                          (216, 220, 228))
            draw_button(screen, self.previous_turn_button, "ХОД <", self.small_font,
                        color=(58, 64, 77) if self.history_index else (38, 41, 49))
            draw_button(screen, self.next_turn_button, "> ХОД", self.small_font,
                        color=(58, 64, 77) if self.history_index + 1 < history_count else (38, 41, 49))

    def close(self):
        pass