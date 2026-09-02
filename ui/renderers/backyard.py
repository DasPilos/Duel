import time

import pygame

from core import settings
from ui.hud import draw_button, draw_text


class BackyardRenderer:
    """Renders the backyard scene while the scene retains state and actions."""

    def __init__(self, scene):
        self.scene = scene

    def draw(self, screen):
        scene = self.scene
        screen.fill((22, 29, 25))
        draw_button(screen, scene.tavern_button, "ТРАКТИР", scene.small_font, color=(110, 75, 50))
        self._draw_applications(screen)
        self._draw_application_menu(screen)
        if scene.error:
            draw_text(screen, scene.small_font, scene.error, 600, 690, (255, 100, 100))
        scene.chat.draw(screen)
        
        # Кнопка инвентаря в верхнем правом углу
        pygame.draw.rect(screen, (100, 100, 120), scene.inventory_button)
        pygame.draw.rect(screen, (150, 150, 170), scene.inventory_button, 2)
        inv_text = scene.font.render("📦", True, (255, 255, 255))
        inv_rect = inv_text.get_rect(center=scene.inventory_button.center)
        screen.blit(inv_text, inv_rect)
        
        # Если открыто через инвентарь (counterpart is None), показываем только левую панель
        show_player_only = scene.profile_overlay.counterpart is None
        scene.profile_overlay.draw(screen, opponent=scene.session.character, show_player_only=show_player_only)

    def _draw_application_menu(self, screen):
        scene = self.scene
        if scene.application_menu is None:
            return
        height = 280 if scene.application_menu == "duel" else 410
        menu = pygame.Rect(700, 270, 520, height)
        pygame.draw.rect(screen, (30, 32, 45), menu, border_radius=10)
        pygame.draw.rect(screen, (120, 130, 155), menu, width=2, border_radius=10)
        title = "ВРЕМЯ ЗАЯВКИ" if scene.application_menu == "duel" else "ПАРАМЕТРЫ СТЕНКИ НА СТЕНКУ"
        draw_text(screen, scene.font, title, menu.x + 25, menu.y + 20, (255, 220, 120))
        if scene.application_menu == "duel":
            labels = ("2 минуты", "5 минут", "10 минут", "15 минут", "20 минут", "30 минут")
            for index, label in enumerate(labels):
                rect = pygame.Rect(menu.x + 25 + (index % 3) * 160, menu.y + 65 + (index // 3) * 42, 145, 34)
                draw_button(screen, rect, label, scene.small_font, color=(75, 105, 145))
            return
        draw_text(screen, scene.small_font, "Количество участников", menu.x + 25, menu.y + 45, (210, 215, 225))
        for index, label in enumerate(("6 участников", "8 участников", "10 участников")):
            rect = pygame.Rect(menu.x + 25 + index * 160, menu.y + 70, 145, 34)
            color = (70, 170, 100) if scene.group_menu_size == (6, 8, 10)[index] else (75, 105, 145)
            draw_button(screen, rect, label, scene.small_font, color=color)
        draw_text(screen, scene.small_font, "Время сбора", menu.x + 25, menu.y + 130, (210, 215, 225))
        for index, label in enumerate(("2 минуты", "10 минут", "30 минут")):
            rect = pygame.Rect(menu.x + 25 + index * 160, menu.y + 155, 145, 34)
            color = (70, 170, 100) if scene.group_menu_ttl == (120, 600, 1800)[index] else (75, 105, 145)
            draw_button(screen, rect, label, scene.small_font, color=color)
        if scene.group_menu_size is not None and scene.group_menu_ttl is not None:
            confirm = pygame.Rect(menu.x + 160, menu.y + 330, 200, 40)
            draw_button(screen, confirm, "ПОДАТЬ ЗАЯВКУ", scene.small_font, color=(70, 170, 100))

    def _draw_applications(self, screen):
        scene = self.scene
        overlay = pygame.Surface(scene.application_frame.size, pygame.SRCALPHA)
        overlay.fill((45, 56, 48, 190))
        screen.blit(overlay, scene.application_frame.topleft)
        pygame.draw.rect(screen, (100, 125, 95), scene.application_frame, width=2, border_radius=8)
        draw_text(screen, scene.font, "ОДИН НА ОДИН", scene.application_frame.x + 25, scene.application_frame.y + 20, (255, 220, 120))
        offers = scene._application_offers()
        self._draw_duel_offers(screen, offers)
        self._draw_group_offers(screen)
        self._draw_action_buttons(screen)
        if scene.application_popup is not None:
            self._draw_profile_comparison(screen)

    def _draw_group_offers(self, screen):
        scene = self.scene
        draw_text(screen, scene.small_font, "СТЕНКА НА СТЕНКУ", scene.application_frame.x + 25, scene.application_frame.y + 265, (255, 220, 120))
        self._draw_scrollable_rows(screen, scene.group_list_rect, scene.group_offers, scene.group_scroll, self._draw_group_row)

    def _draw_duel_offers(self, screen, offers):
        scene = self.scene
        self._draw_scrollable_rows(screen, scene.duel_list_rect, offers, scene.duel_scroll, self._draw_duel_row)

    def _draw_scrollable_rows(self, screen, list_rect, offers, scroll, row_drawer):
        scene = self.scene
        visible_rows = max(1, list_rect.height // 42)
        max_scroll = max(0, len(offers) - visible_rows)
        scroll = min(scroll, max_scroll)
        if list_rect == scene.duel_list_rect:
            scene.duel_scroll = scroll
        else:
            scene.group_scroll = scroll
        previous_clip = screen.get_clip()
        screen.set_clip(list_rect)
        if not offers:
            draw_text(screen, scene.small_font, "Активных заявок пока нет", list_rect.x, list_rect.y + 8, (190, 195, 185))
        for index, offer in enumerate(offers):
            row = pygame.Rect(list_rect.x, list_rect.y + (index - scroll) * 42, list_rect.width, 34)
            row_drawer(screen, row, offer)
        screen.set_clip(previous_clip)
        self._draw_scrollbar(screen, list_rect, len(offers), visible_rows, scroll)

    def _draw_duel_row(self, screen, row, offer):
        scene = self.scene
        pygame.draw.rect(screen, (35, 42, 38), row, border_radius=5)
        is_own_offer = str(offer.get("sender_id")) == str(scene.session.character.get("id"))
        is_new_offer = time.time() - float(offer.get("created_at", 0)) <= 30
        sender_label = offer["sender"]
        if is_own_offer:
            sender_label += " (ваша заявка)"
        elif is_new_offer:
            sender_label += " (новая)"
        sender_color = (255, 235, 150) if is_own_offer or is_new_offer else (230, 235, 225)
        draw_text(screen, scene.small_font, sender_label, row.x + 12, row.y + 8, sender_color)
        draw_text(screen, scene.small_font, "Нажмите для просмотра", row.right - 190, row.y + 8, (175, 190, 170))

    def _draw_group_row(self, screen, row, offer):
        scene = self.scene
        pygame.draw.rect(screen, (40, 45, 55), row, border_radius=5)
        participants = len(offer.get("participants", []))
        draw_text(screen, scene.small_font, f"{offer.get('sender', 'Группа')} ({participants}/10)", row.x + 12, row.y + 8, (230, 235, 225))
        draw_text(screen, scene.small_font, "Нажмите для участия", row.right - 190, row.y + 8, (175, 190, 170))

    def _draw_scrollbar(self, screen, list_rect, item_count, visible_rows, scroll):
        if item_count <= visible_rows:
            return
        track = pygame.Rect(list_rect.right - 6, list_rect.y, 4, list_rect.height)
        pygame.draw.rect(screen, (50, 55, 66), track, border_radius=3)
        thumb_height = max(20, int(track.height * visible_rows / item_count))
        thumb_y = track.y + int((track.height - thumb_height) * scroll / max(1, item_count - visible_rows))
        pygame.draw.rect(screen, (170, 180, 210), pygame.Rect(track.x, thumb_y, track.width, thumb_height), border_radius=3)

    def _draw_action_buttons(self, screen):
        scene = self.scene
        button_text = "ОТОЗВАТЬ ЗАЯВКУ" if scene.chat.my_application is not None else "ОДИН НА ОДИН"
        button_color = (130, 70, 65) if scene.chat.my_application is not None else (150, 95, 55)
        draw_button(screen, scene.application_button, button_text, scene.small_font, color=button_color)
        group_button_text = "ОТМЕНИТЬ СБОР" if scene.group_application_id is not None else "СТЕНКА НА СТЕНКУ"
        group_button_color = (130, 70, 65) if scene.group_application_id is not None else (75, 95, 135)
        draw_button(screen, scene.group_battle_button, group_button_text, scene.small_font, color=group_button_color)
        if scene.has_incoming_application():
            draw_button(screen, scene.accept_application_button, "ПРИНЯТЬ ЗАЯВКУ", scene.small_font, color=(70, 145, 95))
        self._draw_timers(screen)

    def _draw_timers(self, screen):
        scene = self.scene
        if scene.chat.my_application is not None:
            seconds_left = max(0, int(float(scene.chat.my_application.get("created_at", time.time())) + float(scene.chat.my_application.get("ttl", scene.application_ttl or settings.DUEL_APPLICATION_TTL_SECONDS)) - time.time()))
            timer = scene.small_font.render(f"Заявка активна: {seconds_left // 60}:{seconds_left % 60:02d}", True, (255, 100, 100))
            screen.blit(timer, timer.get_rect(midtop=(scene.application_button.centerx, scene.application_button.bottom + 5)))
        if scene.group_application_id is not None:
            group_application = scene.group_application or {}
            seconds_left = max(0, int(float(group_application.get("created_at", time.time())) + float(group_application.get("ttl", 120)) - time.time()))
            timer = scene.small_font.render(f"Сбор активен: {seconds_left // 60}:{seconds_left % 60:02d}", True, (255, 100, 100))
            screen.blit(timer, timer.get_rect(midtop=(scene.group_battle_button.centerx, scene.group_battle_button.bottom + 5)))

    def _draw_profile_comparison(self, screen):
        scene = self.scene
        scene.profile_comparison.draw(
            screen,
            scene.session.character,
            scene.application_popup,
        )
