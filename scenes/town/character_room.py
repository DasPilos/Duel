"""
Сцена комнаты персонажа - место где можно просматривать экипировку, сундуки и колоды
"""

import pygame
from pathlib import Path

from core import settings
from ui.music import play_tavern_music, stop_tavern_music
from ui.character_profile_overlay import CharacterProfileOverlay


class CharacterRoom:
    """Сцена комнаты персонажа в таверне"""

    def __init__(self, session):
        self.session = session
        self.finished = False
        self.cancelled = False

        # Шрифты
        self.font = pygame.font.SysFont(settings.FONT_NAME, 22)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 18)
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 36)
        self.large_font = pygame.font.SysFont(settings.FONT_NAME, 28)

        # Фон
        self.background = None
        background_path = Path(__file__).resolve().parent.parent.parent / "assets" / "town" / "character_room" / "background.png"
        try:
            self.background = pygame.image.load(str(background_path)).convert()
        except (pygame.error, OSError):
            self.background = None

        # Профиль оверлей (для просмотра карточки персонажа)
        self.profile_overlay = CharacterProfileOverlay(
            self.small_font,
            collection_loader=getattr(self.session, "get_card_collection", None),
        )

        # Вкладки (рюкзак убран, он теперь в глобальной панели)
        self.current_tab = "equipment"
        self.tabs = {
            "equipment": {"label": "⚔️ Экипировка", "x": 30, "y": 30, "w": 140, "h": 40},
            "storage": {"label": "📚 Сундуки", "x": 180, "y": 30, "w": 140, "h": 40},
            "decks": {"label": "📃 Колоды", "x": 330, "y": 30, "w": 140, "h": 40},
        }

        # Кнопка инвентаря в верхнем правом углу (рядом с закрытием)
        self.inventory_button = pygame.Rect(settings.WIDTH - 70, 10, 50, 50)

        # Кнопка "Назад" - на двери (масштабируется с экраном)
        # Позиция будет рассчитана в draw() относительно размера экрана
        self.action_buttons = {
            "back": None,  # Инициализируем в draw()
        }

        # Ректы для вкладок
        self.tab_rects = {}
        for key, tab in self.tabs.items():
            self.tab_rects[key] = pygame.Rect(tab["x"], tab["y"], tab["w"], tab["h"])

        # Данные
        self.selected_item = None
        self.equipment_data = {}
        self.storage_data = {}
        self.decks_data = []

        # Музыка - останавливаем таверну, это отдельная сцена
        stop_tavern_music()

    def handle_event(self, event):
        """Обработка событий"""
        if self.profile_overlay.handle_event(event):
            return
        # Сначала обрабатываем profile_overlay
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            action, profile = self.profile_overlay.handle_click(event.pos)
            if action == "stat_change":
                # Сохраняем изменения статистики
                pass
            if action in ("handled", "close"):
                return
        
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.profile_overlay.is_open:
                    self.profile_overlay.close()
                else:
                    self.finished = True
                return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos

            # Клик по кнопке инвентаря
            if self.inventory_button.collidepoint(mouse_pos):
                self.profile_overlay.open(self.session.character, None)
                return

            # Обработка клика по profile_overlay
            action, profile = self.profile_overlay.handle_click(mouse_pos)
            if action == "stat_change":
                # Сохраняем изменения карточки персонажа
                self.session.character.update(profile)
                return
            if action == "backpack":
                # TODO: обработать клик по рюкзаку
                return
            if action in ("handled", "close"):
                return

            # Клик по двери - выход в таверну
            if self.action_buttons["back"].collidepoint(mouse_pos):
                self.finished = True
                return

            # Клик по вкладкам
            for tab_key, rect in self.tab_rects.items():
                if rect.collidepoint(mouse_pos):
                    self.current_tab = tab_key
                    self.selected_item = None
                    return

    def update(self, dt):
        """Обновление логики сцены"""
        # Загружаем данные с сервера (при первом входе)
        if not self.equipment_data and self.current_tab == "equipment":
            self._load_equipment()

        if not self.storage_data and self.current_tab == "storage":
            self._load_storage()

        if not self.decks_data and self.current_tab == "decks":
            self._load_decks()

    def draw(self, screen):
        """Рисование сцены"""
        screen_width, screen_height = screen.get_size()

        # Фон
        if self.background is None:
            screen.fill((38, 27, 24))
        else:
            background = pygame.transform.smoothscale(
                self.background,
                (screen_width, screen_height),
            )
            screen.blit(background, (0, 0))

        # Полупрозрачный оверлей
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 100))
        screen.blit(overlay, (0, 0))

        # Кнопка "Назад" - в нижнем центре экрана (на двери)
        door_y = int(screen_height * 0.75)  # 75% от высоты экрана
        door_x = int(screen_width * 0.5 - 50)  # Центр минус половина ширины
        self.action_buttons["back"] = pygame.Rect(door_x, door_y, 100, 80)

        # Заголовок
        title = self.title_font.render("🏠 КОМНАТА ПЕРСОНАЖА", True, (255, 220, 120))
        screen.blit(title, (50, 50))

        # Информация о персонаже
        char = self.session.character
        char_info = self.small_font.render(
            f"Персонаж: {char['name']} (Уровень {char.get('level', 1)}) | "
            f"Золото: {char.get('gold', 0)}",
            True,
            (200, 200, 200)
        )
        screen.blit(char_info, (50, 100))

        # Вкладки
        self._draw_tabs(screen)

        # Основной контент
        self._draw_content(screen)

        # Кнопка "Назад" на двери (прозрачная, видна как иконка)
        back_rect = self.action_buttons["back"]
        door_button = self.large_font.render("🚪", True, (200, 180, 150))
        door_rect = door_button.get_rect(center=back_rect.center)
        screen.blit(door_button, door_rect)

        # Кнопка инвентаря в верхнем правом углу
        pygame.draw.rect(screen, (100, 100, 120), self.inventory_button)
        pygame.draw.rect(screen, (150, 150, 170), self.inventory_button, 2)
        inv_text = self.font.render("📦", True, (255, 255, 255))
        inv_rect = inv_text.get_rect(center=self.inventory_button.center)
        screen.blit(inv_text, inv_rect)

        # Оверлей профиля
        show_player_only = self.profile_overlay.counterpart is None
        self.profile_overlay.draw(screen, show_player_only=show_player_only)

    def _draw_tabs(self, screen):
        """Рисует вкладки"""
        for key, tab in self.tabs.items():
            rect = self.tab_rects[key]
            is_active = key == self.current_tab

            # Цвет вкладки
            color = (100, 180, 255) if is_active else (80, 100, 140)
            pygame.draw.rect(screen, color, rect, border_radius=4)

            # Текст вкладки
            label_surface = self.font.render(tab["label"], True, (255, 255, 255))
            label_rect = label_surface.get_rect(center=rect.center)
            screen.blit(label_surface, label_rect)

    def _draw_content(self, screen):
        """Рисует содержимое текущей вкладки"""
        if self.current_tab == "equipment":
            self._draw_equipment(screen)
        elif self.current_tab == "storage":
            self._draw_storage(screen)
        elif self.current_tab == "decks":
            self._draw_decks(screen)

    def _draw_equipment(self, screen):
        """Рисует экипировку"""
        title = self.large_font.render("⚔️ ЭКИПИРОВКА", True, (220, 200, 150))
        screen.blit(title, (50, 150))

        if not self.equipment_data:
            empty_text = self.font.render("Экипировка пуста", True, (150, 150, 150))
            screen.blit(empty_text, (50, 220))
            return

        # Показываем надетое
        slots = [
            ("head", "👑 Голова"),
            ("chest", "🛡️ Тело"),
            ("hands", "🤝 Руки"),
            ("legs", "👖 Ноги"),
            ("main_hand", "⚔️ Оружие (основное)"),
            ("ring1", "💍 Кольцо 1"),
        ]

        start_x = 50
        start_y = 220

        for i, (slot_key, slot_label) in enumerate(slots):
            y = start_y + i * 60

            slot_text = self.font.render(slot_label, True, (200, 200, 200))
            screen.blit(slot_text, (start_x, y))

            if slot_key in self.equipment_data:
                equipment = self.equipment_data[slot_key]
                item_text = self.small_font.render(
                    f"{equipment.get('icon', '📦')} {equipment['name']} ({equipment.get('rarity', 'common')})",
                    True,
                    (150, 200, 255)
                )
                screen.blit(item_text, (start_x + 250, y))

                # Бонусы
                bonuses = equipment.get("bonuses", {})
                if bonuses:
                    bonuses_text = ", ".join([f"+{v} {k}" for k, v in bonuses.items()])
                    bonuses_surface = self.small_font.render(bonuses_text, True, (100, 200, 100))
                    screen.blit(bonuses_surface, (start_x + 250, y + 25))
            else:
                empty_slot = self.small_font.render("[Пусто]", True, (100, 100, 100))
                screen.blit(empty_slot, (start_x + 250, y))

    def _draw_storage(self, screen):
        """Рисует сундуки"""
        title = self.large_font.render("📚 СУНДУКИ", True, (220, 200, 150))
        screen.blit(title, (50, 150))

        storage_types = ["chest1", "chest2"]
        for i, storage_type in enumerate(storage_types):
            y = 220 + i * 300

            storage_label = self.font.render(
                f"{'📚 СУНДУК 1 (КАРТЫ)' if storage_type == 'chest1' else '📚 СУНДУК 2 (МАТЕРИАЛЫ)'}",
                True,
                (220, 200, 150)
            )
            screen.blit(storage_label, (50, y))

            if storage_type in self.storage_data:
                items = self.storage_data[storage_type][:10]
                for j, item in enumerate(items):
                    item_y = y + 50 + j * 40
                    item_text = self.small_font.render(
                        f"{item.get('icon', '📦')} {item['name']} ×{item.get('quantity', 1)}",
                        True,
                        (150, 150, 150)
                    )
                    screen.blit(item_text, (50, item_y))

    def _draw_decks(self, screen):
        """Рисует колоды"""
        title = self.large_font.render("📃 КОЛОДЫ", True, (220, 200, 150))
        screen.blit(title, (50, 150))

        if not self.decks_data:
            empty_text = self.font.render("Колоды не найдены", True, (150, 150, 150))
            screen.blit(empty_text, (50, 220))
            return

        for i, deck in enumerate(self.decks_data):
            y = 220 + i * 80

            deck_text = self.font.render(
                f"📃 {deck.get('name', f'Колода {i+1}')}",
                True,
                (220, 200, 150)
            )
            screen.blit(deck_text, (50, y))

            # Информация о картах
            cards_info = self.small_font.render(
                f"Карт: {len(deck.get('cards', {}))} | Последнее обновление: {deck.get('created_at', 'N/A')}",
                True,
                (150, 150, 150)
            )
            screen.blit(cards_info, (50, y + 35))

    # ==================== ЗАГРУЗКА ДАННЫХ ====================

    def _load_equipment(self):
        """Загружает экипировку с сервера"""
        try:
            self.equipment_data = self.session.client.get_equipment(self.session.character["id"])
        except Exception as e:
            print(f"Ошибка загрузки экипировки: {e}")
            self.equipment_data = {}

    def _load_storage(self):
        """Загружает сундуки с сервера"""
        try:
            self.storage_data = self.session.client.get_storage(self.session.character["id"], "chest1")
        except Exception as e:
            print(f"Ошибка загрузки сундука: {e}")
            self.storage_data = {}

    def _load_decks(self):
        """Загружает колоды с сервера"""
        try:
            self.decks_data = self.session.client.get_decks(self.session.character["id"])
        except Exception as e:
            print(f"Ошибка загрузки колод: {e}")
            self.decks_data = []

    def close(self):
        """Закрытие ресурсов сцены"""
        # Восстанавливаем музыку таверны перед выходом
        play_tavern_music()
