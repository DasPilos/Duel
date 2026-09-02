"""
Панель экипировки
"""

import pygame
from typing import Dict, Optional


class EquipmentPanel:
    """Панель для управления экипировкой персонажа"""

    def __init__(self, font, small_font):
        self.font = font
        self.small_font = small_font

        # Параметры отображения
        self.start_x = 50
        self.start_y = 220

        # Слоты экипировки
        self.slots = [
            ("head", "👑 Голова", "armor"),
            ("body", "🛡️ Тело", "armor"),
            ("hands", "🤝 Руки", "armor"),
            ("legs", "👖 Ноги", "armor"),
            ("feet", "👞 Ноги", "armor"),
            ("weapon_main", "⚔️ Основное оружие", "weapon"),
            ("weapon_off", "🗡️ Второе оружие", "weapon"),
            ("ring_1", "💍 Кольцо 1", "accessory"),
            ("ring_2", "💍 Кольцо 2", "accessory"),
            ("amulet", "⭐ Амулет", "accessory"),
        ]

        # Данные
        self.equipment: Dict[str, Dict] = {}
        self.selected_slot: Optional[str] = None
        self.slot_rects: Dict[str, pygame.Rect] = {}

    def set_equipment(self, equipment: Dict[str, Dict]):
        """Устанавливает экипировку"""
        self.equipment = equipment
        self._update_rects()

    def _update_rects(self):
        """Обновляет прямоугольники для отображения"""
        self.slot_rects = {}
        for i, (slot_key, slot_label, _) in enumerate(self.slots):
            x = self.start_x
            y = self.start_y + i * 70

            rect = pygame.Rect(x, y, 1800, 60)
            self.slot_rects[slot_key] = rect

    def handle_event(self, event) -> bool:
        """Обрабатывает события"""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos
            for slot_key, rect in self.slot_rects.items():
                if rect.collidepoint(mouse_pos):
                    self.selected_slot = slot_key
                    return True

        return False

    def draw(self, screen):
        """Рисует панель экипировки"""
        # Заголовок
        title = pygame.font.SysFont("arial", 28).render("⚔️ ЭКИПИРОВКА", True, (220, 200, 150))
        screen.blit(title, (self.start_x, self.start_y - 60))

        # Рисуем слоты
        for i, (slot_key, slot_label, slot_type) in enumerate(self.slots):
            y = self.start_y + i * 70
            rect = self.slot_rects[slot_key]

            is_selected = slot_key == self.selected_slot
            color = (150, 200, 255) if is_selected else (70, 90, 120)

            # Фон ячейки
            pygame.draw.rect(screen, color, rect, border_radius=8, width=2)

            # Название слота
            slot_text = self.font.render(slot_label, True, (200, 200, 200))
            screen.blit(slot_text, (self.start_x + 20, y + 10))

            if slot_key in self.equipment:
                equipment = self.equipment[slot_key]

                # Иконка и название надетого предмета
                item_icon = self.small_font.render(equipment["icon"], True, (255, 255, 255))
                screen.blit(item_icon, (self.start_x + 300, y + 10))

                item_name = self.small_font.render(
                    f"{equipment['name']} ({equipment['rarity']})",
                    True,
                    (150, 200, 255)
                )
                screen.blit(item_name, (self.start_x + 330, y + 10))

                # Бонусы
                bonuses_list = [f"+{v} {k}" for k, v in equipment["bonuses"].items()]
                bonuses_text = ", ".join(bonuses_list)
                bonuses_surface = self.small_font.render(bonuses_text, True, (100, 200, 100))
                screen.blit(bonuses_surface, (self.start_x + 330, y + 35))
            else:
                empty_text = self.small_font.render("[Не надета]", True, (100, 100, 100))
                screen.blit(empty_text, (self.start_x + 300, y + 15))

        # Показываем итоговые бонусы в нижней части
        self._draw_total_bonuses(screen)

    def _draw_total_bonuses(self, screen):
        """Рисует итоговые бонусы"""
        # Собираем все бонусы
        total_bonuses = {}
        for slot_data in self.equipment.values():
            for stat, value in slot_data["bonuses"].items():
                total_bonuses[stat] = total_bonuses.get(stat, 0) + value

        # Рисуем итого
        y = self.start_y + len(self.slots) * 70 + 20
        total_text = pygame.font.SysFont("arial", 22).render("ИТОГО БОНУСЫ:", True, (200, 200, 100))
        screen.blit(total_text, (self.start_x, y))

        if total_bonuses:
            bonuses_text = ", ".join([f"+{v} {k.replace('_', ' ')}" for k, v in total_bonuses.items()])
            bonuses_surface = pygame.font.SysFont("arial", 20).render(bonuses_text, True, (100, 200, 100))
            screen.blit(bonuses_surface, (self.start_x, y + 30))

    def get_selected_slot(self) -> Optional[str]:
        """Возвращает выбранный слот"""
        return self.selected_slot

    def clear_selection(self):
        """Очищает выбор"""
        self.selected_slot = None
