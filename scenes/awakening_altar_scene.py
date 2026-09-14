# Ритуальный Алтарь Пробуждения - локация для магов
import pygame
import time

from client.network import ServerError
from core import settings
from ui.chat import ChatPanel
from ui.character_comparison import CharacterComparison
from ui.character_profile_overlay import CharacterProfileOverlay
from ui.renderers.awakening_altar import AwakeningAltarRenderer


class AwakeningAltarScene:
    """
    Ритуальный Алтарь Пробуждения - локация для персонажей-магов.
    
    Это аналог BackyardScene для магов, где они могут:
    - Встречаться с другими магами
    - Смотреть список доступных дуэлей
    - Вступать в боевые группы
    - Общаться через чат (единый для всей игры)
    """
    
    def __init__(self, session):
        self.session = session
        self.finished = False
        self.cancelled = False
        self.error = ""
        self.font = pygame.font.SysFont(settings.FONT_NAME, 22)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 18)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 36)
        self.profile_overlay = CharacterProfileOverlay(
            self.small_font,
            collection_loader=getattr(session, "get_card_collection", None),
            deck_loader=getattr(session, "get_decks", None),
        )
        
        # Единый чат для всей игры
        self.chat = ChatPanel(session, "awakening_altar", profile_overlay=self.profile_overlay)
        
        self.navigate = None
        self.inventory_button = pygame.Rect(settings.WIDTH - 70, 10, 50, 50)
        
        # Кнопка навигации обратно в город
        self.navigation_buttons = [
            {"rect": pygame.Rect(1640, 35, 220, 45), "label": "В ГОРОД", "target": "tavern"},
        ]
        self.altar_button = pygame.Rect(1395, 35, 220, 45)
        self.tavern_button = self.navigation_buttons[0]["rect"]
        
        # Область приложений (дуэли от других магов)
        self.application_frame = pygame.Rect(560, 40, 800, 560)
        self.duel_list_rect = pygame.Rect(585, 115, 750, 145)
        self.group_list_rect = pygame.Rect(585, 365, 750, 200)
        self.duel_scroll = 0
        self.group_scroll = 0
        
        # Кнопки действий
        self.application_button = pygame.Rect(560, 620, 220, 40)
        self.group_battle_button = pygame.Rect(800, 620, 220, 40)
        self.accept_application_button = pygame.Rect(1040, 620, 220, 40)
        
        # Данные боевых групп
        self.group_offers = []
        self.group_elapsed = 0.0
        self.group_application_id = None
        self.group_application = None
        self.application_menu = None
        self.application_ttl = None
        self.group_menu_size = None
        self.group_menu_ttl = None
        self.application_popup = None
        self.selected_application_id = None
        
        # Профилирование и сравнение персонажей
        self.profile_comparison = CharacterComparison(self.small_font)
        
        # Рендерер сцены
        self.renderer = AwakeningAltarRenderer(self)

    def handle_event(self, event):
        """Обработка событий в сцене"""
        self.profile_overlay.handle_event(event)
        deck_name = self.profile_overlay.take_create_deck_request()
        if deck_name:
            try:
                name, cards = deck_name
                self.session.create_deck(name, cards)
                self.profile_overlay.deck_panel.open(self.session.get_decks())
            except ServerError as error:
                self.error = str(error)
            return
        if self.profile_overlay.deck_panel.is_open and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            action, profile = self.profile_overlay.handle_click(event.pos)
            if action == "delete_deck":
                try:
                    self.session.delete_deck(profile.get("id"))
                    self.profile_overlay.deck_panel.open(self.session.get_decks())
                except ServerError as error:
                    self.error = str(error)
            return
        # Приоритет 1: Чат
        if self.chat.handle_event(event):
            if self.profile_overlay.is_open:
                self.application_popup = None
            return
        
        # Приоритет 2: Прокрутка списков
        if event.type == pygame.MOUSEWHEEL:
            if self.duel_list_rect.collidepoint(pygame.mouse.get_pos()):
                self.duel_scroll = max(0, self.duel_scroll - event.y)
                return
            if self.group_list_rect.collidepoint(pygame.mouse.get_pos()):
                self.group_scroll = max(0, self.group_scroll - event.y)
                return
        
        # Приоритет 3: Клики по интерфейсу
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Инвентарь
            if self.inventory_button.collidepoint(event.pos):
                self.profile_overlay.open(self.session.character, None)
                return
            
            # Профиль персонажа
            action, profile = self.profile_overlay.handle_click(event.pos)
            if action == "delete_deck":
                try:
                    self.session.delete_deck(profile.get("id"))
                    self.profile_overlay.deck_panel.open(self.session.get_decks())
                except ServerError as error:
                    self.error = str(error)
                return
            if action == "deck_selected":
                self.session.selected_deck = profile
                return
            if action == "stat_change":
                self._save_profile_card(profile)
                return
            if action == "backpack":
                # TODO: обработать клик по рюкзаку
                return
            if action in ("handled", "close"):
                return
            
            # Навигация
            if self.altar_button.collidepoint(event.pos):
                self.navigate = None
                return
            for index, offer in enumerate(self._application_offers()):
                row = pygame.Rect(
                    self.duel_list_rect.x,
                    self.duel_list_rect.y + 35 + index * 42,
                    self.duel_list_rect.width,
                    34,
                )
                if row.collidepoint(event.pos):
                    self._accept_mage_offer(offer)
                    return
            for button in self.navigation_buttons:
                if button["rect"].collidepoint(event.pos):
                    self.navigate = button["target"]
                    self.finished = True
                    return

    def update(self, dt):
        """Обновление логики сцены"""
        self.session.passive_regenerate(dt, full_regen_seconds=settings.ALTAR_FULL_REGEN_SECONDS)
        self.chat.update(dt)
        self.renderer.update(dt)

    def draw(self, screen):
        """Рисование сцены"""
        screen.fill(settings.BACKGROUND_COLOR)
        
        # Рисуем основной интерфейс
        self.renderer.draw(screen)
        
        # Рисуем навигационные кнопки
        self._draw_navigation_buttons(screen)
        
        # Рисуем кнопку инвентаря
        self._draw_inventory_button(screen)
        
        # Рисуем чат поверх всего
        self.chat.draw(screen)
        
        # Рисуем профиль если открыт
        self.profile_overlay.draw(screen)

    def _draw_navigation_buttons(self, screen):
        """Рисует кнопки навигации"""
        from ui.hud import draw_button
        
        for button in self.navigation_buttons:
            draw_button(
                screen,
                button["rect"],
                button["label"],
                self.small_font,
                color=(80, 180, 120),
                hover_color=(100, 200, 140),
                text_color=(30, 32, 45)
            )
        draw_button(
            screen,
            self.altar_button,
            "АЛТАРЬ",
            self.small_font,
            color=(120, 80, 170),
            hover_color=(150, 100, 210),
            text_color=(240, 230, 255),
        )

    def _draw_inventory_button(self, screen):
        """Рисует кнопку инвентаря"""
        from ui.hud import draw_button
        
        draw_button(
            screen,
            self.inventory_button,
            "📦",
            self.small_font,
            color=(80, 100, 120),
            hover_color=(100, 120, 140),
            text_color=(230, 230, 230)
        )

    def _save_profile_card(self, profile):
        """Сохраняет изменения профиля персонажа"""
        try:
            saved_profile = self.session.save_character_profile(profile)
            if saved_profile is not None:
                self.session.character = saved_profile
                self.profile_overlay.update_profile(saved_profile)
        except ServerError as error:
            self.error = str(error)

    def _application_offers(self):
        return [offer for offer in self.chat.offers if offer.get("location") == "awakening_altar"]

    def _accept_mage_offer(self, offer):
        try:
            self.session.respond_duel_offer(offer["id"], True)
            self.opponent = next(
                (item for item in self.chat.occupants if str(item.get("character_id")) == str(offer.get("sender_id"))),
                None,
            )
            if self.opponent is None:
                self.error = "Маг больше не находится у алтаря"
                return
            self.finished = True
        except ServerError as error:
            self.error = str(error)

    def close(self):
        """Закрыть сцену"""
        self.chat.close()
        if self.profile_overlay:
            self.profile_overlay.close()
