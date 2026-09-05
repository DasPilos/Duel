import pygame
from pathlib import Path

from core import settings
from ui.chat import ChatPanel
from ui.character_profile_overlay import CharacterProfileOverlay
from ui.tavern_shop import TavernShop
from ui.hud import draw_button
from ui.music import play_tavern_music, stop_tavern_music, update_tavern_music


class TavernScene:
    def __init__(self, session):
        self.session = session
        self.finished = False
        self.cancelled = False
        self.font = pygame.font.SysFont(settings.FONT_NAME, 22)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 18)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 36)
        self.battle_button = pygame.Rect(780, 850, 360, 55)
        self.inventory_button = pygame.Rect(settings.WIDTH - 70, 10, 50, 50)
        self.profile_overlay = CharacterProfileOverlay(
            self.small_font,
            collection_loader=getattr(self.session, "get_card_collection", None),
        )
        self.chat = ChatPanel(session, "tavern", profile_overlay=self.profile_overlay)
        self.tavern_shop = TavernShop(self.font, self.small_font)
        
        # Кнопки магазина слева (напитки и скупка) - снаружи панели магазина, вверху
        # Панель магазина начинается на x = ENEMY_CARD_RECT[0], y = ENEMY_CARD_RECT[1] + 60
        self.shop_drinks_button = pygame.Rect(
            settings.ENEMY_CARD_RECT[0] - 105,  # Слева от панели, с отступом 5
            settings.ENEMY_CARD_RECT[1] + 60,   # На верху панели
            100,
            40,
        )
        self.shop_sell_button = pygame.Rect(
            settings.ENEMY_CARD_RECT[0] - 105,  # Слева от панели, с отступом 5
            settings.ENEMY_CARD_RECT[1] + 60 + 50,  # Ниже первой кнопки
            100,
            40,
        )
        
        self.navigate = None
        # Горячие зоны привязаны к фону таверны, а не к размерам чата.
        self.tavern_hotspots = (
            ("Выход на улицу", 160, 400, 130, 300, None),
            ("Главный зал", 944, 373, 126, 141, None),
            ("Комната отдыха", 1160, 443, 69, 85, "character_room"),
            ("Задний двор", 1560, 390, 55, 153, "backyard"),
            ("Хозяин трактира", 1560, 590, 85, 108, None),
            ("Искатели приключений", 260, 779, 167, 121, None),
        )
        self.background = None
        background_path = Path(__file__).resolve().parent.parent / "assets" / "tavern" / "background_original.png"
        try:
            self.background = pygame.image.load(str(background_path)).convert()
        except (pygame.error, OSError):
            self.background = None
        play_tavern_music()
        
        # Перезагружаем персонажа чтобы получить свежие данные с сервера
        self.session.refresh_character()
        
        # Загружаем напитки с сервера
        self._load_drinks_from_server()

    def _hotspot_rect(self, x, y, width, height):
        return pygame.Rect(x, y, width, height)

    def handle_event(self, event):
        if self.profile_overlay.handle_event(event):
            return
        if self.chat.handle_event(event):
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Обработка магазина (приоритет выше всех)
            if self.tavern_shop.is_open:
                if self.shop_drinks_button.collidepoint(event.pos):
                    self.tavern_shop.current_tab = "drinks"
                    return
                if self.shop_sell_button.collidepoint(event.pos):
                    self.tavern_shop.current_tab = "sell"
                    return
                
                # Обработка магазина
                shop_action = self.tavern_shop.handle_click(event.pos)
                if shop_action is not None:
                    # Обработка действий магазина (покупка напитков)
                    if isinstance(shop_action, str) and shop_action.startswith("buy_drink_"):
                        drink_index = int(shop_action.split("_")[-1])
                        if drink_index < len(self.tavern_shop.drinks):
                            self._buy_drink(drink_index)
                    return
            
            # Обработка клика по кнопке инвентаря
            if self.inventory_button.collidepoint(event.pos):
                self.profile_overlay.open(self.session.character, None)
                return
            
            action, profile = self.profile_overlay.handle_click(event.pos)
            if action == "stat_change":
                self._save_profile_card(profile)
                return
            if action == "backpack":
                # TODO: обработать клик по рюкзаку
                return
            if action in ("handled", "close"):
                return
            for name, x, y, width, height, action in self.tavern_hotspots:
                if self._hotspot_rect(x, y, width, height).collidepoint(event.pos):
                    # Обработка горячей зоны "Хозяин трактира"
                    if name == "Хозяин трактира":
                        self.tavern_shop.open()
                        return
                    # Другие горячие зоны - навигация
                    if action is not None:
                        self.navigate = action
                        self.finished = True
                        return
            if self.battle_button.collidepoint(event.pos):
                self.finished = True
                return
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_b):
                self.finished = True
            elif event.key == pygame.K_ESCAPE:
                self.cancelled = True
                self.finished = True

    def update(self, dt):
        self.chat.update(dt)
        self.tavern_shop.update()  # Обновляем таймер ошибок
        update_tavern_music()

    def draw(self, screen):
        if self.background is None:
            screen.fill((38, 27, 24))
        else:
            screen_width, screen_height = screen.get_size()
            background = pygame.transform.smoothscale(
                self.background,
                (screen_width, screen_height),
            )
            screen.blit(background, (0, 0))

        # Скрываем встроенную в картинку декоративную область чата.
        # Настоящий ChatPanel рисуется поверх и остается полностью функциональным.
        if not self.chat.collapsed:
            chat_cover = self.chat.panel_rect.inflate(6, 6)
            pygame.draw.rect(screen, (22, 24, 34), chat_cover, border_radius=10)

        mouse_pos = pygame.mouse.get_pos()
        
        # Обновляем наведение на товары магазина
        self.tavern_shop.update_hover(mouse_pos)
        
        for label, x, y, width, height, action in self.tavern_hotspots:
            rect = self._hotspot_rect(x, y, width, height)
            if not rect.collidepoint(mouse_pos):
                continue
            pygame.draw.rect(screen, (255, 220, 120), rect, width=2, border_radius=6)
            label_surface = self.small_font.render(label, True, (255, 230, 160))
            label_rect = label_surface.get_rect(midbottom=(rect.centerx, rect.top - 6))
            pygame.draw.rect(screen, (20, 18, 15), label_rect.inflate(12, 8))
            screen.blit(label_surface, label_rect)

        self.chat.draw(screen)
        
        # Кнопка инвентаря в верхнем правом углу
        pygame.draw.rect(screen, (100, 100, 120), self.inventory_button)
        pygame.draw.rect(screen, (150, 150, 170), self.inventory_button, 2)
        inv_text = self.font.render("📦", True, (255, 255, 255))
        inv_rect = inv_text.get_rect(center=self.inventory_button.center)
        screen.blit(inv_text, inv_rect)
        
        # Если открыто через инвентарь (counterpart is None), показываем только левую панель
        show_player_only = self.profile_overlay.counterpart is None
        self.profile_overlay.draw(screen, opponent=self.session.character, show_player_only=show_player_only)
        
        # Кнопки магазина (рисуются только когда магазин открыт)
        if self.tavern_shop.is_open:
            draw_button(screen, self.shop_drinks_button, "НАПИТКИ", self.small_font, color=(100, 150, 200))
            draw_button(screen, self.shop_sell_button, "СКУПКА", self.small_font, color=(200, 100, 100))
        
        # Магазин (рисуется поверх всего)
        self.tavern_shop.draw(screen)

    def _buy_drink(self, drink_index):
        """Покупка напитка через API сервера"""
        if drink_index >= len(self.tavern_shop.drinks):
            return
        
        drink = self.tavern_shop.drinks[drink_index]
        character = self.session.character
        
        # Проверяем хватает ли средств локально
        from core.currency import Currency
        currency = Currency(
            copper=int(character.get("copper", 0)),
            silver=int(character.get("silver", 0)),
            gold=int(character.get("gold", 0))
        )
        
        if not currency.has_enough(copper=drink["price"]):
            self.tavern_shop.show_error("ХАЛЯВЫ НЕТ! хочешь выпить иди на задний двор!")
            return
        
        # Вызываем API для покупки на сервере
        try:
            result = self.session.client._request(
                "POST",
                "/api/character/buy_drink",
                {
                    "character_id": character["id"],
                    "drink_id": drink["id"]
                },
                authenticated=True
            )
            
            # Обновляем локальный персонаж с ответом сервера
            self.session.character = result.get("character", character)
            
            # Обновляем оба профиля в overlay
            self.profile_overlay.update_profile(self.session.character)
            self.profile_overlay.update_counterpart(self.session.character)
        except Exception as e:
            error_msg = str(e)
            # Скрываем внутреннее имя ошибки - сообщение уже в чате от бармена
            if "БАРМАН_ПОЛНОЕ_ЗДОРОВЬЕ" in error_msg:
                # Не показываем ошибку - сообщение уже отправлено в чат
                return
            self.tavern_shop.show_error(f"Ошибка покупки: {error_msg}")

    def _save_profile_card(self, profile):
        saved_profile = self.session.save_character_profile(profile)
        if saved_profile is not None:
            self.profile_overlay.update_counterpart(saved_profile)

    
    def _load_drinks_from_server(self):
        """Загружает список напитков с сервера"""
        try:
            result = self.session.client._request(
                "GET",
                "/api/drinks",
                authenticated=True
            )
            drinks = result.get("drinks", [])
            print(f"Загруженные напитки: {drinks}")
            # Преобразуем для UI: берем только нужные поля
            self.tavern_shop.drinks = [
                {
                    "id": drink.get("id", 1),
                    "name": drink.get("name", "Неизвестный напиток"),
                    "price": drink.get("price_copper", 0),
                    "effect": drink.get("effect", "recovery"),
                    "description": drink.get("description", "")
                }
                for drink in drinks
            ]
            print(f"Преобразованные напитки: {self.tavern_shop.drinks}")
        except Exception as e:
            print(f"Ошибка загрузки напитков: {e}")
            # Используем fallback drinks
            print("Используем fallback drinks...")
    
    def close(self):
        stop_tavern_music()
        self.chat.close()
