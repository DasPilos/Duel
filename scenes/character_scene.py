import pygame

from client.network import ServerError
from core import settings
from ui.hud import draw_button, draw_text


class CharacterScene:
    def __init__(self, session):
        self.session = session
        self.characters = []
        self.finished = False
        self.cancelled = False
        self.error = ""
        self.font = pygame.font.SysFont(settings.FONT_NAME, 22)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 18)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 36)
        
        # UI for character list
        self.character_list_rect = pygame.Rect(60, 310, 400, 500)
        self.character_rects = []
        self.character_scroll = 0
        self.max_visible_characters = 5
        self.selected_character = None
        
        # Buttons
        self.continue_button = pygame.Rect(760, 920, 400, 50)
        self.delete_button = pygame.Rect(760, 990, 400, 50)
        self.create_new_button = pygame.Rect(60, 850, 400, 50)
        
        # Password confirmation dialog
        self.show_delete_confirmation = False
        self.delete_password = ""
        self.delete_error = ""
        self.password_input_rect = pygame.Rect(550, 600, 700, 46)
        self.confirm_delete_button = pygame.Rect(600, 680, 250, 50)
        self.cancel_delete_button = pygame.Rect(900, 680, 250, 50)
        
        # Flag to transition to character creation screen
        self.create_new_character = False
        
        self.refresh()
        from ui.character_card import CharacterCard
        self.card = CharacterCard()

    def refresh(self):
        try:
            self.characters = self.session.list_characters()
            self.error = ""
        except ServerError as error:
            self.error = str(error)

    def handle_event(self, event):
        # Handle delete confirmation dialog
        if self.show_delete_confirmation:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.show_delete_confirmation = False
                    self.delete_password = ""
                    self.delete_error = ""
                elif event.key == pygame.K_BACKSPACE:
                    self.delete_password = self.delete_password[:-1]
                elif event.key == pygame.K_RETURN:
                    self._confirm_delete()
                    return
            elif event.type == pygame.TEXTINPUT:
                if len(self.delete_password) < 128:
                    self.delete_password += event.text
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.confirm_delete_button.collidepoint(event.pos):
                    self._confirm_delete()
                    return
                elif self.cancel_delete_button.collidepoint(event.pos):
                    self.show_delete_confirmation = False
                    self.delete_password = ""
                    self.delete_error = ""
                    return
            return
        
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.selected_character = None
                self.cancelled = True
                self.finished = True
            elif event.key == pygame.K_RETURN:
                if self.selected_character is not None:
                    self.session.select_character(self.selected_character)
                    self.finished = True
        elif event.type == pygame.MOUSEWHEEL:
            if self.character_list_rect.collidepoint(pygame.mouse.get_pos()):
                max_scroll = max(0, len(self.characters) - self.max_visible_characters)
                self.character_scroll = max(0, min(max_scroll, self.character_scroll - event.y * 1))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Continue button
            if self.selected_character is not None:
                if self.continue_button.collidepoint(event.pos):
                    self.session.select_character(self.selected_character)
                    self.finished = True
                    return
                # Delete button
                if self.delete_button.collidepoint(event.pos):
                    self.show_delete_confirmation = True
                    self.delete_password = ""
                    self.delete_error = ""
                    return
            
            # Create new character button
            if self.create_new_button.collidepoint(event.pos):
                self.create_new_character = True
                self.finished = True
                return
            
            # Click on character in list
            for visible_index, rect in enumerate(self.character_rects):
                if rect.collidepoint(event.pos):
                    actual_index = visible_index + self.character_scroll
                    if 0 <= actual_index < len(self.characters):
                        self.selected_character = self.characters[actual_index]
                        self.card.sync(self.selected_character, title=None, kind="player")
                    return

    def _confirm_delete(self):
        """Confirm deletion with password"""
        if not self.delete_password:
            self.delete_error = "Введите пароль"
            return
        
        try:
            self.session.delete_character_with_password(self.selected_character["id"], self.delete_password)
            self.show_delete_confirmation = False
            self.delete_password = ""
            self.delete_error = ""
            self.selected_character = None
            self.refresh()
        except ServerError as error:
            self.delete_error = str(error)

    def update(self, dt):
        pass

    def draw(self, screen):
        screen.fill((16, 18, 28))
        
        # Draw character list on the left
        max_scroll = max(0, len(self.characters) - self.max_visible_characters)
        self.character_scroll = min(self.character_scroll, max_scroll)
        visible_characters = self.characters[self.character_scroll:self.character_scroll + self.max_visible_characters]
        self.character_rects = []
        for visible_index, character in enumerate(visible_characters):
            rect = pygame.Rect(60, 310 + visible_index * 82, 400, 62)
            self.character_rects.append(rect)
            
            is_selected = self.selected_character and self.selected_character["id"] == character["id"]
            border_color = (100, 200, 100) if is_selected else (70, 140, 220)
            
            pygame.draw.rect(screen, (30, 34, 48), rect, border_radius=6)
            pygame.draw.rect(screen, border_color, rect, width=2, border_radius=6)
            draw_text(screen, self.font, character["name"], rect.x + 18, rect.y + 8, (240, 240, 245))
            draw_text(screen, self.small_font, f"Уровень {character['level']}   HP {character['hp']}/{character['max_hp']}", rect.x + 18, rect.y + 34, (180, 185, 200))

        if len(self.characters) > self.max_visible_characters:
            bar_height = 360
            bar_x = 475
            bar_y = 310
            pygame.draw.rect(screen, (30, 34, 48), pygame.Rect(bar_x, bar_y, 8, bar_height), border_radius=6)
            track = max(0, bar_height - 36)
            thumb_height = max(24, int(track * (self.max_visible_characters / max(1, len(self.characters)))))
            thumb_top = bar_y + 18 + int((track - thumb_height) * (self.character_scroll / max(1, max_scroll)))
            pygame.draw.rect(screen, (110, 150, 220), pygame.Rect(bar_x, thumb_top, 8, thumb_height), border_radius=6)

        # Draw character card on the right if selected
        if self.selected_character is not None:
            card_frame = pygame.Rect(550, 100, 700, 800)
            
            self.card.draw(
                screen,
                card_frame,
                profile=self.selected_character,
                border_color=(70, 140, 220),
                title=None,
                editable=False
            )
            
            draw_button(screen, self.continue_button, "ПРОДОЛЖИТЬ ИГРУ", self.font, color=(70, 140, 220))
            draw_button(screen, self.delete_button, "УДАЛИТЬ ПЕРСОНАЖА", self.font, color=(220, 100, 100))
        
        # Button to create new character
        draw_button(screen, self.create_new_button, "СОЗДАТЬ ПЕРСОНАЖА", self.font, color=(70, 140, 220))
        
        if self.error:
            draw_text(screen, self.small_font, self.error, 60, 920, (255, 100, 100))
        
        # Draw delete confirmation dialog
        if self.show_delete_confirmation:
            overlay = pygame.Surface((1920, 1080))
            overlay.set_alpha(200)
            overlay.fill((0, 0, 0))
            screen.blit(overlay, (0, 0))
            
            dialog_rect = pygame.Rect(400, 400, 1120, 280)
            pygame.draw.rect(screen, (30, 34, 48), dialog_rect, border_radius=10)
            pygame.draw.rect(screen, (220, 100, 100), dialog_rect, width=3, border_radius=10)
            
            title_text = self.font.render("Подтверждение удаления персонажа", True, (240, 240, 255))
            screen.blit(title_text, (dialog_rect.x + 40, dialog_rect.y + 20))
            
            instr_text = self.small_font.render("Введите пароль для подтверждения удаления:", True, (200, 200, 200))
            screen.blit(instr_text, (dialog_rect.x + 40, dialog_rect.y + 70))
            
            pygame.draw.rect(screen, (28, 30, 43), self.password_input_rect, border_radius=6)
            pygame.draw.rect(screen, (220, 100, 100), self.password_input_rect, width=2, border_radius=6)
            password_display = "*" * len(self.delete_password)
            draw_text(screen, self.font, password_display, self.password_input_rect.x + 12, self.password_input_rect.y + 10, (240, 240, 245))
            
            if self.delete_error:
                draw_text(screen, self.small_font, self.delete_error, dialog_rect.x + 40, dialog_rect.y + 160, (255, 100, 100))
            
            draw_button(screen, self.confirm_delete_button, "УДАЛИТЬ", self.font, color=(220, 100, 100))
            draw_button(screen, self.cancel_delete_button, "ОТМЕНИТЬ", self.font, color=(70, 140, 220))

    def close(self):
        pass
