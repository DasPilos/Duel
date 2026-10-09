"""Модальные окна-заглушки зданий города (кнопка 'Вернуться в город')."""
import time
import pygame
from core import settings
from core.forge_recipes import (
    FORGE_RECIPES,
    RECIPE_DETAILS,
    MATERIAL_NAMES,
    format_forge_time,
    FORGE_QUEUE_LIMIT,
)
from core.cart_progress import CART_GRADES, cart_stats
from ui.catalog_icons import draw_building_icon, draw_item_icon
from ui.hud import draw_button
from ui.map_travel import draw_transport_cart_icon

WORKSHOP_TABS = (
    ("helmets", "ШЛЕМЫ"),
    ("armor", "ДОСПЕХИ"),
    ("gloves", "ПЕРЧАТКИ"),
    ("plates", "ЛАТЫ"),
    ("shoes", "ОБУВЬ"),
    ("leatherworker", "КОЖЕВНИК"),
    ("carts", "ПОВОЗКИ"),
    ("upgrades", "УЛУЧШЕНИЯ"),
    ("storage", "СКЛАД"),
)


FORGE_ITEM_ICONS = {
    "Старый серп": "tool_sickle",
    "Топор лесоруба": "tool_axe",
    "Кирка": "tool_pickaxe",
    "Разделочный нож": "tool_butcher_knife",
    "Дубина": "weapon_club",
    "Простой лук": "weapon_bow",
    "Деревянный посох": "weapon_staff",
    "Деревянный щит": "shield_wooden",
    "Деревяный шит": "shield_wooden",
    "Железный шлем": "head_iron_helmet",
    "Кожаный доспех": "body_steel_breastplate",
    "Стальные рукавицы": "hands_steel_gauntlets",
    "Боевой доспех": "body_steel_breastplate",
    "Железные сапоги": "feet_iron_boots",
    "Железо": "material_iron",
    "Сталь": "material_steel",
}


class CityModalsMixin:
    """Требует rect/button-атрибуты, созданные в CityScene.__init__ для каждого здания."""

    def _draw_building_title(self, screen, rect, building_id, text, color):
        draw_building_icon(screen, building_id, (rect.left + 24, rect.top + 19), 32)
        title = self.large_font.render(text, True, color)
        screen.blit(title, (rect.left + 64, rect.top + 24))

    def _draw_castle_modal(self, screen):
        self.castle_window.draw(screen)

    def _draw_forge_modal(self, screen):
        """Интерактивное меню кузницы: карточки рецептов (8 на страницу 4х2 со скроллом), процесс работы и склад."""
        if not hasattr(self, "forge_scroll"):
            self.forge_scroll = 0
        if not hasattr(self, "forge_action_buttons"):
            self.forge_action_buttons = []
        if not hasattr(self, "forge_info_popup_item"):
            self.forge_info_popup_item = None
        if not hasattr(self, "forge_state") or self.forge_state is None:
            self.forge_state = {"queue": [], "queue_count": 0, "queue_limit": FORGE_QUEUE_LIMIT, "queue_total_seconds": 0, "warehouse": []}
        if not hasattr(self, "forge_player_materials"):
            self.forge_player_materials = {}

        self.forge_action_buttons = []

        overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 18, 220))
        screen.blit(overlay, (0, 0))

        rect = self.forge_modal_rect
        modal_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(modal_surf, (24, 20, 20, 252), (0, 0, rect.width, rect.height), border_radius=12)
        pygame.draw.rect(modal_surf, (255, 140, 50), (0, 0, rect.width, rect.height), width=2, border_radius=12)
        screen.blit(modal_surf, rect.topleft)

        m_pos = pygame.mouse.get_pos()
        c_hover = self.forge_close_button.collidepoint(m_pos)
        pygame.draw.rect(screen, (160, 45, 45) if c_hover else (45, 30, 35), self.forge_close_button, border_radius=4)
        pygame.draw.rect(screen, (220, 100, 100), self.forge_close_button, 1, border_radius=4)
        x_surf = self.small_font.render("✕", True, (255, 255, 255))
        screen.blit(x_surf, x_surf.get_rect(center=self.forge_close_button.center))

        # ==================== ЧИСТАЯ ШАПКА КУЗНИЦЫ ====================
        # Кузница
        # уровень 1
        # закладки
        # __________________________________________________
        draw_building_icon(screen, "forge_building", (rect.left + 24, rect.top + 18), 32)
        title_surf = self.large_font.render("Кузница", True, (255, 220, 100))
        screen.blit(title_surf, (rect.left + 66, rect.top + 14))

        sub_surf = self.badge_font.render("ОРУЖЕЙНАЯ КУЗНИЦА • УРОВЕНЬ 1", True, (220, 185, 140))
        screen.blit(sub_surf, (rect.left + 66, rect.top + 42))

        # Всплывающее сообщение обратной связи
        if getattr(self, "forge_message", None) and time.time() < self.forge_message[2]:
            msg_text, msg_color, _ = self.forge_message
            msg_surf = self.small_font.render(msg_text, True, msg_color)
            screen.blit(msg_surf, (rect.left + 380, rect.top + 22))

        # Закладки (вкладки)
        for tab, button in self.forge_tabs.items():
            label = self.forge_tab_labels.get(tab, tab.upper())
            badge_extra = ""
            if tab == "storage":
                ready_count = len(self.forge_state.get("warehouse", []))
                if ready_count > 0:
                    badge_extra = f" ({ready_count})"
            is_active = self.forge_tab == tab
            draw_button(
                screen, button, f"{label}{badge_extra}", self.small_font,
                color=(140, 75, 35) if is_active else (49, 44, 39),
                text_color=(255, 225, 175) if is_active else (190, 177, 157),
            )

        # Разделительная линия под закладками
        pygame.draw.line(screen, (90, 60, 50), (rect.left + 24, rect.top + 116), (rect.right - 24, rect.top + 116), 1)

        # ==================== ЦЕНТРАЛЬНАЯ ЧАСТЬ (ПО 8 ПРЕДМЕТОВ 4х2 СО СКРОЛЛОМ) ====================
        viewport_rect = pygame.Rect(rect.left + 24, rect.top + 124, rect.width - 48, 490)
        card_w = 374
        card_h = 236
        gap_x = 18
        gap_y = 14

        screen.set_clip(viewport_rect)

        if self.forge_tab in ("weapons", "shields", "smelting"):
            recipe_ids = [r["item_id"] for r in FORGE_RECIPES.get(self.forge_tab, ()) if r["item_id"] in RECIPE_DETAILS]
            total_rows = (len(recipe_ids) + 3) // 4
            max_scroll = max(0, total_rows * (card_h + gap_y) - viewport_rect.height)
            self.forge_scroll = max(0, min(self.forge_scroll, max_scroll))

            for idx, item_id in enumerate(recipe_ids):
                item = RECIPE_DETAILS[item_id]
                col = idx % 4
                row = idx // 4
                cx = viewport_rect.left + col * (card_w + gap_x)
                cy = viewport_rect.top + row * (card_h + gap_y) - self.forge_scroll
                card_rect = pygame.Rect(cx, cy, card_w, card_h)

                if card_rect.bottom < viewport_rect.top or card_rect.top > viewport_rect.bottom:
                    continue

                is_hover = card_rect.collidepoint(m_pos) and viewport_rect.collidepoint(m_pos) and (self.forge_info_popup_item is None)
                pygame.draw.rect(screen, (40, 32, 30) if is_hover else (33, 27, 26), card_rect, border_radius=8)
                pygame.draw.rect(screen, (235, 140, 50) if is_hover else (82, 65, 58), card_rect, 2 if is_hover else 1, border_radius=8)

                # Шапка карточки: Иконка + Название
                draw_item_icon(screen, item["icon"], (cx + 12, cy + 16), 32)
                name_surf = self.font.render(item["name"], True, (255, 230, 150))
                screen.blit(name_surf, (cx + 52, cy + 14))

                pygame.draw.line(screen, (75, 58, 52), (cx + 12, cy + 68), (cx + card_w - 12, cy + 68), 1)

                # Только 4 параметра на титульной карточке: Требование, Урон, Характеристики, Бафы
                line_y = cy + 78
                req_text = f"Требование: {item['req']}"
                screen.blit(self.small_font.render(req_text, True, (255, 215, 120)), (cx + 16, line_y))
                line_y += 26

                dmg_text = f"Урон: {item['damage']}"
                screen.blit(self.small_font.render(dmg_text, True, (255, 205, 110)), (cx + 16, line_y))
                line_y += 26

                stat_val = item["stats"] if item["stats"] != "" else "-"
                stat_text = f"Характеристики: {stat_val}"
                stat_color = (120, 235, 130) if stat_val != "-" else (175, 170, 165)
                screen.blit(self.small_font.render(stat_text, True, stat_color), (cx + 16, line_y))
                line_y += 26

                buff_val = item["buffs"] if item["buffs"] != "" else "-"
                buff_text = f"Бафы: {buff_val}"
                buff_color = (110, 215, 255) if buff_val != "-" else (175, 170, 165)
                screen.blit(self.small_font.render(buff_text, True, buff_color), (cx + 16, line_y))

                # Проверка наличия материалов и денег для ковки
                can_craft = True
                cost_copper = int(item.get("cost_copper", 0))
                if cost_copper > 0:
                    player_money = getattr(self, "forge_player_copper", 0)
                    if player_money < cost_copper:
                        can_craft = False
                for mat_id, need in item["materials"].items():
                    have = self.forge_player_materials.get(mat_id, 0)
                    if have < need:
                        can_craft = False
                        break

                # Кнопки внизу карточки
                info_btn_rect = pygame.Rect(cx + 14, cy + card_h - 44, 105, 36)
                craft_btn_rect = pygame.Rect(cx + 128, cy + card_h - 44, card_w - 142, 36)

                queue_count = self.forge_state.get("queue_count", len(self.forge_state.get("queue", [])))
                queue_limit = self.forge_state.get("queue_limit", FORGE_QUEUE_LIMIT)
                queue_full = queue_count >= queue_limit

                # Кнопка [ИНФО]
                i_hover = info_btn_rect.collidepoint(m_pos) and viewport_rect.collidepoint(m_pos) and (self.forge_info_popup_item is None)
                draw_button(screen, info_btn_rect, "ИНФО", self.small_font,
                            color=(75, 65, 60) if i_hover else (55, 48, 44),
                            text_color=(255, 230, 180) if i_hover else (220, 210, 190))

                # Кнопка [ВЫКОВАТЬ]
                if can_craft and not queue_full:
                    c_hover = craft_btn_rect.collidepoint(m_pos) and viewport_rect.collidepoint(m_pos) and (self.forge_info_popup_item is None)
                    btn_color = (195, 100, 40) if c_hover else (150, 75, 30)
                    draw_button(screen, craft_btn_rect, "ВЫКОВАТЬ", self.small_font, color=btn_color, text_color=(255, 255, 255))
                    self.forge_action_buttons.append(("craft", item["item_id"], craft_btn_rect, True))
                elif queue_full:
                    draw_button(screen, craft_btn_rect, "ОЧЕРЕДЬ (5/5)", self.small_font, color=(55, 45, 45), text_color=(170, 140, 140))
                    self.forge_action_buttons.append(("craft", item["item_id"], craft_btn_rect, False))
                else:
                    draw_button(screen, craft_btn_rect, "НЕТ МАТЕРИАЛОВ", self.small_font, color=(50, 40, 40), text_color=(190, 110, 110))
                    self.forge_action_buttons.append(("craft", item["item_id"], craft_btn_rect, False))

                self.forge_action_buttons.append(("info_btn", item["item_id"], info_btn_rect, True))
                # Клик по телу карточки также открывает всплывающую информацию
                self.forge_action_buttons.append(("card", item["item_id"], card_rect, True))

        elif self.forge_tab == "storage":
            warehouse = self.forge_state.get("warehouse", [])
            if not warehouse:
                box = pygame.Rect(viewport_rect.left + 220, viewport_rect.top + 70, viewport_rect.width - 440, 230)
                pygame.draw.rect(screen, (34, 28, 28), box, border_radius=10)
                pygame.draw.rect(screen, (100, 75, 65), box, 1, border_radius=10)
                title = self.font.render("СКЛАД ГОТОВОЙ ПРОДУКЦИИ ПУСТ", True, (255, 215, 120))
                screen.blit(title, title.get_rect(center=(box.centerx, box.top + 36)))

                lines = [
                    "Здесь будут храниться выкованные предметы вашего персонажа.",
                    "Вам не обязательно ждать окончания ковки в кузнице — вы можете",
                    "спокойно покинуть кузницу и вернуться забрать свой заказ в любое время.",
                    "С этого склада можно забрать только свои заказы, чужие предметы недоступны.",
                ]
                cur_y = box.top + 75
                for line in lines:
                    surf = self.small_font.render(line, True, (215, 210, 200))
                    screen.blit(surf, surf.get_rect(center=(box.centerx, cur_y)))
                    cur_y += 26
            else:
                total_rows = (len(warehouse) + 3) // 4
                max_scroll = max(0, total_rows * (card_h + gap_y) - viewport_rect.height)
                self.forge_scroll = max(0, min(self.forge_scroll, max_scroll))

                for idx, order in enumerate(warehouse):
                    col = idx % 4
                    row = idx // 4
                    cx = viewport_rect.left + col * (card_w + gap_x)
                    cy = viewport_rect.top + row * (card_h + gap_y) - self.forge_scroll
                    card_rect = pygame.Rect(cx, cy, card_w, card_h)

                    if card_rect.bottom < viewport_rect.top or card_rect.top > viewport_rect.bottom:
                        continue

                    is_hover = card_rect.collidepoint(m_pos) and viewport_rect.collidepoint(m_pos) and (self.forge_info_popup_item is None)
                    pygame.draw.rect(screen, (32, 42, 34) if is_hover else (26, 35, 28), card_rect, border_radius=8)
                    pygame.draw.rect(screen, (90, 190, 110) if is_hover else (60, 140, 80), card_rect, 2 if is_hover else 1, border_radius=8)

                    draw_item_icon(screen, order.get("icon", "tool_axe"), (cx + 12, cy + 16), 32)
                    screen.blit(self.font.render(order["item_name"], True, (255, 230, 150)), (cx + 52, cy + 14))
                    screen.blit(self.badge_font.render("ГОТОВО К ВЫДАЧЕ", True, (110, 230, 130)), (cx + 52, cy + 38))

                    pygame.draw.line(screen, (60, 95, 70), (cx + 12, cy + 68), (cx + card_w - 12, cy + 68), 1)

                    desc_text = order.get("description", "Готовый выкованный предмет")
                    screen.blit(self.small_font.render(desc_text[:38], True, (210, 225, 210)), (cx + 14, cy + 82))
                    screen.blit(self.small_font.render(f"Вес: {order.get('weight', 1)} кг", True, (180, 200, 180)), (cx + 14, cy + 112))
                    screen.blit(self.small_font.render("Заказ ожидает на вашем складе кузницы", True, (150, 220, 170)), (cx + 14, cy + 142))

                    btn_rect = pygame.Rect(cx + 14, cy + card_h - 44, card_w - 28, 36)
                    b_hover = btn_rect.collidepoint(m_pos) and viewport_rect.collidepoint(m_pos) and (self.forge_info_popup_item is None)
                    btn_color = (65, 160, 85) if b_hover else (45, 125, 65)
                    draw_button(screen, btn_rect, "ЗАБРАТЬ В РЮКЗАК", self.small_font, color=btn_color, text_color=(255, 255, 255))
                    self.forge_action_buttons.append(("collect", order["order_id"], btn_rect, True))

        elif self.forge_tab in ("helmets", "armor", "gloves", "plates", "shoes"):
            box = pygame.Rect(viewport_rect.left + 220, viewport_rect.top + 80, viewport_rect.width - 440, 180)
            pygame.draw.rect(screen, (34, 28, 28), box, border_radius=10)
            pygame.draw.rect(screen, (100, 75, 65), box, 1, border_radius=10)
            t_label = self.forge_tab_labels.get(self.forge_tab, self.forge_tab.upper())
            title = self.font.render(f"РАЗДЕЛ «{t_label}» ЗАКРЫТ", True, (255, 200, 120))
            screen.blit(title, title.get_rect(center=(box.centerx, box.top + 45)))
            desc = self.small_font.render("Ковка элементов брони и защитной экипировки открывается на 2-м уровне кузницы.", True, (220, 210, 200))
            screen.blit(desc, desc.get_rect(center=(box.centerx, box.top + 95)))
            hint = self.small_font.render("Развивайте город и улучшайте здания во вкладке «УЛУЧШЕНИЯ».", True, (170, 160, 150))
            screen.blit(hint, hint.get_rect(center=(box.centerx, box.top + 130)))

        elif self.forge_tab == "upgrades":
            box = pygame.Rect(viewport_rect.left + 220, viewport_rect.top + 80, viewport_rect.width - 440, 180)
            pygame.draw.rect(screen, (34, 28, 28), box, border_radius=10)
            pygame.draw.rect(screen, (100, 75, 65), box, 1, border_radius=10)
            title = self.font.render("УЛУЧШЕНИЕ КУЗНИЦЫ: УРОВЕНЬ 1 -> 2", True, (255, 200, 120))
            screen.blit(title, title.get_rect(center=(box.centerx, box.top + 45)))
            desc = self.small_font.render("Улучшение кузницы откроет рецепты защитных доспехов, шлемов и лат.", True, (220, 210, 200))
            screen.blit(desc, desc.get_rect(center=(box.centerx, box.top + 95)))
            hint = self.small_font.render("Для улучшения потребуются доски, каменные блоки и ресурсы города.", True, (170, 160, 150))
            screen.blit(hint, hint.get_rect(center=(box.centerx, box.top + 130)))

        screen.set_clip(None)

        # ==================== НИЖНЯЯ ЧАСТЬ (ПРОЦЕСС РАБОТЫ КУЗНИЦЫ И ОЧЕРЕДЬ) ====================
        panel_rect = pygame.Rect(rect.left + 24, rect.bottom - 264, rect.width - 48, 244)
        pygame.draw.rect(screen, (28, 22, 22), panel_rect, border_radius=10)
        pygame.draw.rect(screen, (215, 115, 45), panel_rect, width=2, border_radius=10)

        # Шапка нижней панели
        hdr_rect = pygame.Rect(panel_rect.left, panel_rect.top, panel_rect.width, 36)
        pygame.draw.rect(screen, (48, 32, 28), hdr_rect, border_top_left_radius=10, border_top_right_radius=10)

        queue = self.forge_state.get("queue", [])
        queue_count = self.forge_state.get("queue_count", len(queue))
        queue_limit = self.forge_state.get("queue_limit", FORGE_QUEUE_LIMIT)
        queue_total_sec = self.forge_state.get("queue_total_seconds", 0)

        left_hdr_txt = f"ПРОЦЕСС РАБОТЫ КУЗНИЦЫ • ОЧЕРЕДЬ: {queue_count} / {queue_limit} (МАКС. 5 ЗАКАЗОВ)"
        screen.blit(self.font.render(left_hdr_txt, True, (255, 215, 130)), (panel_rect.left + 16, panel_rect.top + 7))

        right_hdr_txt = f"ОБЩЕЕ ВРЕМЯ ЗАГРУЗКИ: {format_forge_time(queue_total_sec)}"
        r_surf = self.font.render(right_hdr_txt, True, (255, 230, 160))
        screen.blit(r_surf, (panel_rect.right - r_surf.get_width() - 16, panel_rect.top + 7))

        # Левый блок: ДЕЙСТВУЮЩИЙ ПРЕДМЕТ В РАБОТЕ (увеличен)
        work_rect = pygame.Rect(panel_rect.left + 14, panel_rect.top + 46, 440, 186)
        pygame.draw.rect(screen, (38, 29, 27), work_rect, border_radius=8)
        pygame.draw.rect(screen, (120, 80, 65), work_rect, 1, border_radius=8)

        if queue and queue[0].get("status") in ("working", "queued"):
            curr = queue[0]
            draw_item_icon(screen, curr.get("icon", "tool_axe"), (work_rect.left + 16, work_rect.top + 24), 32)

            w_title = self.font.render(f"В РАБОТЕ: {curr['item_name']}", True, (255, 225, 120))
            screen.blit(w_title, (work_rect.left + 58, work_rect.top + 16))

            owner_txt = self.small_font.render(f"Заказчик: {curr['owner_name']}", True, (160, 205, 245))
            screen.blit(owner_txt, (work_rect.left + 58, work_rect.top + 48))

            t_left_txt = self.font.render(f"До готовности: {format_forge_time(curr['seconds_left'])}", True, (255, 195, 100))
            screen.blit(t_left_txt, (work_rect.left + 82, work_rect.top + 78))

            # Полоса прогресса (крупная)
            pbar_rect = pygame.Rect(work_rect.left + 16, work_rect.top + 124, work_rect.width - 32, 28)
            pygame.draw.rect(screen, (18, 14, 14), pbar_rect, border_radius=6)
            tot = max(1, curr.get("duration_seconds", 1))
            elapsed = max(0, tot - curr.get("seconds_left", 0))
            pct = min(1.0, max(0.0, elapsed / tot))
            fill_w = int(pbar_rect.width * pct)
            if fill_w > 0:
                pygame.draw.rect(screen, (245, 135, 45), (pbar_rect.left, pbar_rect.top, fill_w, pbar_rect.height), border_radius=6)
            pygame.draw.rect(screen, (160, 100, 70), pbar_rect, 1, border_radius=6)
            pct_text = f"{int(pct * 100)}% ({format_forge_time(curr['seconds_left'])})"
            p_surf = self.badge_font.render(pct_text, True, (255, 255, 255))
            screen.blit(p_surf, p_surf.get_rect(center=pbar_rect.center))
        else:
            idle_h = self.font.render("Горн свободен. Кузнец ждет заказов", True, (225, 210, 190))
            screen.blit(idle_h, (work_rect.left + 20, work_rect.top + 45))
            idle_d = self.small_font.render("Выберите рецепт в верхнем меню и нажмите «ВЫКОВАТЬ».", True, (180, 170, 160))
            screen.blit(idle_d, (work_rect.left + 20, work_rect.top + 85))

        # Правый блок: ОЧЕРЕДЬ ЗАКАЗОВ (5 слотов, крупные просторные ячейки)
        slot_w = 210
        slot_h = 186
        for slot_i in range(5):
            slot_x = panel_rect.left + 466 + slot_i * (slot_w + 10)
            slot_y = panel_rect.top + 46
            slot_box = pygame.Rect(slot_x, slot_y, slot_w, slot_h)

            if slot_i < len(queue):
                order = queue[slot_i]
                is_working = (slot_i == 0 and order.get("status") == "working")
                box_bg = (52, 35, 30) if is_working else (40, 32, 30)
                box_border = (245, 130, 50) if is_working else (115, 90, 80)
                pygame.draw.rect(screen, box_bg, slot_box, border_radius=8)
                pygame.draw.rect(screen, box_border, slot_box, 2 if is_working else 1, border_radius=8)

                badge = f"[{slot_i + 1}] В РАБОТЕ" if is_working else f"[{slot_i + 1}] В ОЧЕРЕДИ"
                badge_col = (255, 185, 85) if is_working else (190, 180, 170)
                screen.blit(self.badge_font.render(badge, True, badge_col), (slot_x + 12, slot_y + 12))

                draw_item_icon(screen, order.get("icon", "tool_axe"), (slot_x + 12, slot_y + 44), 32)
                screen.blit(self.font.render(order["item_name"][:13], True, (245, 235, 215)), (slot_x + 52, slot_y + 40))
                screen.blit(self.small_font.render(f"Игрок: {order['owner_name'][:11]}", True, (160, 205, 245)), (slot_x + 52, slot_y + 68))

                pygame.draw.line(screen, (85, 68, 62), (slot_x + 12, slot_y + 104), (slot_x + slot_w - 12, slot_y + 104), 1)

                screen.blit(self.small_font.render("Время до готовности:", True, (180, 170, 160)), (slot_x + 12, slot_y + 116))
                timer_txt = format_forge_time(order["seconds_left"])
                screen.blit(self.font.render(timer_txt, True, (255, 205, 110)), (slot_x + 12, slot_y + 142))
            else:
                pygame.draw.rect(screen, (32, 27, 27), slot_box, border_radius=8)
                pygame.draw.rect(screen, (75, 64, 62), slot_box, 1, border_radius=8)
                screen.blit(self.badge_font.render(f"[{slot_i + 1}] СВОБОДНЫЙ СЛОТ", True, (135, 125, 120)), (slot_x + 12, slot_y + 12))
                screen.blit(self.small_font.render("Свободно для заказа", True, (160, 150, 145)), (slot_x + 12, slot_y + 60))
                screen.blit(self.small_font.render("до 5 заказов кузнецу", True, (140, 130, 125)), (slot_x + 12, slot_y + 90))

        # ==================== ВСПЛЫВАЮЩАЯ ПОЛНАЯ ИНФОРМАЦИЯ О ПРЕДМЕТЕ ====================
        if self.forge_info_popup_item is not None and self.forge_info_popup_item in RECIPE_DETAILS:
            p_item = RECIPE_DETAILS[self.forge_info_popup_item]

            # Затемнение под всплывающим окном
            pop_overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
            pop_overlay.fill((0, 0, 0, 190))
            screen.blit(pop_overlay, (0, 0))

            pop_w = 580
            pop_h = 560
            pop_x = (settings.WIDTH - pop_w) // 2
            pop_y = (settings.HEIGHT - pop_h) // 2
            self.forge_popup_rect = pygame.Rect(pop_x, pop_y, pop_w, pop_h)

            pop_surf = pygame.Surface((pop_w, pop_h), pygame.SRCALPHA)
            pygame.draw.rect(pop_surf, (26, 20, 20, 254), (0, 0, pop_w, pop_h), border_radius=12)
            pygame.draw.rect(pop_surf, (255, 150, 60), (0, 0, pop_w, pop_h), width=2, border_radius=12)
            screen.blit(pop_surf, (pop_x, pop_y))

            # Крестик закрытия
            self.forge_popup_close_btn = pygame.Rect(pop_x + pop_w - 40, pop_y + 14, 26, 26)
            pc_hover = self.forge_popup_close_btn.collidepoint(m_pos)
            pygame.draw.rect(screen, (170, 45, 45) if pc_hover else (50, 32, 35), self.forge_popup_close_btn, border_radius=4)
            pygame.draw.rect(screen, (230, 100, 100), self.forge_popup_close_btn, 1, border_radius=4)
            px_surf = self.small_font.render("✕", True, (255, 255, 255))
            screen.blit(px_surf, px_surf.get_rect(center=self.forge_popup_close_btn.center))

            # Иконка и заголовок
            draw_item_icon(screen, p_item["icon"], (pop_x + 22, pop_y + 24), 32)
            p_title = self.large_font.render(p_item["name"], True, (255, 225, 120))
            screen.blit(p_title, (pop_x + 62, pop_y + 16))
            p_sub = self.small_font.render("Информация о предмете кузницы", True, (200, 185, 170))
            screen.blit(p_sub, (pop_x + 62, pop_y + 46))

            pygame.draw.line(screen, (90, 65, 55), (pop_x + 20, pop_y + 78), (pop_x + pop_w - 20, pop_y + 78), 1)

            # Таблица параметров
            fields = [
                ("Слот", p_item["slot"]),
                ("Требование:", p_item["req"]),
                ("Урон:", p_item["damage"]),
                ("Рецепт:", p_item["recipe_str"]),
                ("Вес (кг)", p_item["weight_str"]),
                ("Бафы", p_item["buffs"]),
                ("Характеристика", p_item["stats"]),
                ("Колода", p_item["deck"]),
                ("Изготовления:", p_item["duration_str"]),
                ("Цена:", p_item["price_str"]),
            ]

            row_y = pop_y + 88
            row_h = 36
            for idx, (label, val) in enumerate(fields):
                bg_col = (34, 27, 26) if idx % 2 == 0 else (42, 33, 31)
                r_rect = pygame.Rect(pop_x + 20, row_y, pop_w - 40, row_h)
                pygame.draw.rect(screen, bg_col, r_rect, border_radius=4)

                lbl_surf = self.small_font.render(label, True, (205, 195, 185))
                screen.blit(lbl_surf, (r_rect.left + 14, r_rect.top + 9))

                val_col = (255, 230, 160)
                if label == "Бафы" and val != "-":
                    val_col = (110, 215, 255)
                elif label == "Характеристика" and val != "-":
                    val_col = (120, 235, 130)
                elif label == "Урон:":
                    val_col = (255, 210, 110)

                if label == "Рецепт:":
                    cur_x = r_rect.left + 220
                    for mat_id, amount in p_item.get("materials", {}).items():
                        draw_item_icon(screen, mat_id, (cur_x, r_rect.top + 2), 32)
                        cur_x += 36
                        mat_name = MATERIAL_NAMES.get(mat_id, "Материал")
                        t_surf = self.small_font.render(f"{mat_name} ×{amount}   ", True, (255, 230, 160))
                        screen.blit(t_surf, (cur_x, r_rect.top + 9))
                        cur_x += t_surf.get_width()
                    cost = int(p_item.get("cost_copper", 0))
                    if cost > 0:
                        if cost % 100 == 0:
                            silv = cost // 100
                            draw_item_icon(screen, "silver", (cur_x, r_rect.top + 2), 32)
                            cur_x += 36
                            t_surf = self.small_font.render(f"Серебра ×{silv}", True, (255, 230, 160))
                            screen.blit(t_surf, (cur_x, r_rect.top + 9))
                        else:
                            draw_item_icon(screen, "copper", (cur_x, r_rect.top + 2), 32)
                            cur_x += 36
                            t_surf = self.small_font.render(f"Медь ×{cost}", True, (255, 230, 160))
                            screen.blit(t_surf, (cur_x, r_rect.top + 9))
                elif label == "Цена:":
                    cur_x = r_rect.left + 220
                    coin_type = "gold" if "золот" in val.lower() else ("copper" if "мед" in val.lower() else "silver")
                    draw_item_icon(screen, coin_type, (cur_x, r_rect.top + 2), 32)
                    cur_x += 36
                    v_surf = self.small_font.render(val, True, (255, 230, 160))
                    screen.blit(v_surf, (cur_x, r_rect.top + 9))
                else:
                    v_surf = self.small_font.render(val, True, val_col)
                    screen.blit(v_surf, (r_rect.left + 230, r_rect.top + 9))
                row_y += row_h + 3

            # Кнопки действия всплывающего окна
            can_p_craft = True
            cost_p_copper = int(p_item.get("cost_copper", 0))
            if cost_p_copper > 0:
                player_money = getattr(self, "forge_player_copper", 0)
                if player_money < cost_p_copper:
                    can_p_craft = False
            for m_id, n_need in p_item["materials"].items():
                if self.forge_player_materials.get(m_id, 0) < n_need:
                    can_p_craft = False
                    break
            q_full = self.forge_state.get("queue_count", len(queue)) >= self.forge_state.get("queue_limit", FORGE_QUEUE_LIMIT)

            self.forge_popup_craft_btn = pygame.Rect(pop_x + 30, pop_y + pop_h - 54, 260, 38)
            self.forge_popup_cancel_btn = pygame.Rect(pop_x + 310, pop_y + pop_h - 54, 240, 38)

            if can_p_craft and not q_full:
                b_craft_col = (195, 100, 40) if self.forge_popup_craft_btn.collidepoint(m_pos) else (150, 75, 30)
                draw_button(screen, self.forge_popup_craft_btn, "ВЫКОВАТЬ ПРЕДМЕТ", self.small_font, color=b_craft_col, text_color=(255, 255, 255))
            elif q_full:
                draw_button(screen, self.forge_popup_craft_btn, "ОЧЕРЕДЬ ЗАПОЛНЕНА (5/5)", self.small_font, color=(55, 45, 45), text_color=(170, 140, 140))
            else:
                draw_button(screen, self.forge_popup_craft_btn, "НЕДОСТАТОЧНО МАТЕРИАЛОВ", self.small_font, color=(50, 40, 40), text_color=(190, 110, 110))

            b_cancel_col = (75, 65, 60) if self.forge_popup_cancel_btn.collidepoint(m_pos) else (55, 48, 44)
            draw_button(screen, self.forge_popup_cancel_btn, "ЗАКРЫТЬ", self.small_font, color=b_cancel_col, text_color=(255, 255, 255))

    def _draw_workshop_modal(self, screen):
        """Tabbed armor workshop with a ready-goods warehouse and work queue."""
        overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 18, 220))
        screen.blit(overlay, (0, 0))

        rect = self.workshop_modal_rect
        modal_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(modal_surf, (23, 25, 25, 252), (0, 0, rect.width, rect.height), border_radius=10)
        pygame.draw.rect(modal_surf, (111, 144, 159), (0, 0, rect.width, rect.height), width=2, border_radius=10)
        screen.blit(modal_surf, rect.topleft)

        m_pos = pygame.mouse.get_pos()
        c_hover = self.workshop_close_button.collidepoint(m_pos)
        pygame.draw.rect(screen, (160, 45, 45) if c_hover else (45, 30, 35),
                         self.workshop_close_button, border_radius=4)
        pygame.draw.rect(screen, (220, 100, 100), self.workshop_close_button, width=1, border_radius=4)
        x_surf = self.small_font.render("✕", True, (255, 255, 255))
        screen.blit(x_surf, x_surf.get_rect(center=self.workshop_close_button.center))

        draw_building_icon(screen, "workshop_building", (rect.left + 24, rect.top + 17), 32)
        title = self.large_font.render("Городская мастерская", True, (220, 229, 231))
        screen.blit(title, (rect.left + 66, rect.top + 16))
        subtitle = self.badge_font.render(
            "БРОННАЯ МАСТЕРСКАЯ РАДБУРГА • УРОВЕНЬ 1", True, (155, 191, 204)
        )
        screen.blit(subtitle, (rect.left + 66, rect.top + 48))

        tab_gap = 8
        tab_width = (rect.width - 48 - tab_gap * (len(WORKSHOP_TABS) - 1)) // len(WORKSHOP_TABS)
        self.workshop_tabs = {}
        for index, (key, label) in enumerate(WORKSHOP_TABS):
            left = rect.left + 24 + index * (tab_width + tab_gap)
            width = rect.right - 24 - left if index == len(WORKSHOP_TABS) - 1 else tab_width
            button = pygame.Rect(left, rect.top + 70, width, 34)
            self.workshop_tabs[key] = button
            active = getattr(self, "workshop_tab", "helmets") == key
            draw_button(screen, button, label, self.small_font,
                        color=(80, 111, 126) if active else (47, 51, 51),
                        hover_color=(105, 138, 153),
                        text_color=(230, 237, 235) if active else (178, 184, 181))

        pygame.draw.line(screen, (72, 88, 92), (rect.left + 24, rect.top + 116),
                         (rect.right - 24, rect.top + 116), 1)
        viewport = pygame.Rect(rect.left + 24, rect.top + 124, rect.width - 48, 490)
        selected_tab = getattr(self, "workshop_tab", "helmets")
        labels = dict(WORKSHOP_TABS)
        self.workshop_cart_button = None
        self.workshop_cart_buttons = {}
        self.workshop_cart_lot_rects = {}
        pygame.draw.rect(screen, (29, 32, 32), viewport, border_radius=6)
        pygame.draw.rect(screen, (62, 72, 73), viewport, 1, border_radius=6)

        if selected_tab == "storage":
            orders = getattr(self, "workshop_state", {}).get("warehouse", [])
            if not orders:
                empty = pygame.Rect(viewport.left + 220, viewport.top + 78,
                                    viewport.width - 440, 220)
                pygame.draw.rect(screen, (34, 37, 36), empty, border_radius=8)
                pygame.draw.rect(screen, (86, 103, 104), empty, 1, border_radius=8)
                title = self.font.render("СКЛАД ГОТОВОЙ ПРОДУКЦИИ ПУСТ", True, (222, 207, 168))
                screen.blit(title, title.get_rect(center=(empty.centerx, empty.top + 46)))
                message = self.small_font.render(
                    "Готовые изделия мастерской будут храниться здесь.", True, (184, 191, 187)
                )
                screen.blit(message, message.get_rect(center=(empty.centerx, empty.top + 92)))
            else:
                self._draw_workshop_finished_goods(screen, viewport, orders)
        elif selected_tab == "carts":
            cart_state = getattr(self, "workshop_state", {})
            cart_progress = cart_state.get("cart_progress", {})
            grade_states = cart_progress.get("grades", {})
            catalog = [
                (int(grade), config) for grade, config in CART_GRADES.items()
                if config.get("researched") and config.get("production_seconds")
            ]
            row_height, row_gap, column_gap = 184, 10, 10
            cell_width = (viewport.width - 20 - column_gap) // 2
            total_rows = (len(catalog) + 1) // 2
            total_height = total_rows * (row_height + row_gap)
            max_scroll = max(0, total_height - viewport.height)
            self.workshop_cart_scroll = max(
                0, min(getattr(self, "workshop_cart_scroll", 0), max_scroll)
            )
            screen.set_clip(viewport)
            for index, (grade, config) in enumerate(catalog):
                row = pygame.Rect(
                    viewport.left + 10 + (index % 2) * (cell_width + column_gap),
                    viewport.top + 10 + (index // 2) * (row_height + row_gap) - self.workshop_cart_scroll,
                    cell_width,
                    row_height,
                )
                if row.bottom < viewport.top or row.top > viewport.bottom:
                    continue
                self.workshop_cart_lot_rects[grade] = row
                grade_state = grade_states.get(str(grade), {})
                stats = cart_stats(grade_state.get("upgrades", {}))
                hovered = row.collidepoint(m_pos)
                pygame.draw.rect(screen, (34, 42, 37) if hovered else (31, 37, 34), row, border_radius=7)
                pygame.draw.rect(screen, (103, 145, 108) if hovered else (68, 88, 76), row, 1, border_radius=7)
                draw_transport_cart_icon(
                    screen, config.get("sprite_key", "light"), (row.left + 12, row.top + 12), 32
                )
                title = self.font.render(config["name"], True, (226, 218, 193))
                screen.blit(title, (row.left + 54, row.top + 15))
                production_orders = grade_state.get("production_orders", [])
                if production_orders:
                    queued_label = self.small_font.render(
                        f"В очереди: {len(production_orders)}", True, (221, 187, 120)
                    )
                    screen.blit(queued_label, queued_label.get_rect(
                        midright=(row.right - 16, row.top + 26)
                    ))
                pygame.draw.line(screen, (62, 78, 68),
                                 (row.left + 54, row.top + 46),
                                 (row.right - 16, row.top + 46), 1)

                specs = (
                    (0, 0, "Грузоподъёмность", f"{stats['capacity_kg']} кг"),
                    (1, 0, "Кучер", str(config["villagers_required"])),
                    (0, 1, "Слот для товаров", str(config["resource_slots"])),
                    (1, 1, "Упряжка", str(config["horse_count"])),
                    (0, 2, "Погрузка", f"{config['load_kg_per_minute']} кг/мин"),
                    (1, 2, "Разгрузка", f"{config['unload_kg_per_minute']} кг/мин"),
                    (0, 3, "Скорость без груза", f"{stats['empty_tiles_per_hour']} тайлов/час"),
                    (1, 3, "Полная загрузка", f"штраф -{stats['full_load_speed_penalty_percent']}%"),
                )
                spec_column_width = (row.width - 24) // 2
                for column, spec_row, label, value in specs:
                    x = row.left + 12 + column * spec_column_width
                    y = row.top + 52 + spec_row * 22
                    text = f"{label}: {value}"
                    screen.blit(self.small_font.render(text, True, (200, 207, 198)), (x, y))

                price_y = row.bottom - 30
                screen.blit(self.small_font.render("Цена:", True, (225, 195, 135)),
                            (row.left + 12, price_y + 2))
                warehouse = cart_state.get("warehouse_storage", {})
                wood_available = int(warehouse.get("wood", 0))
                silver_available = int(cart_state.get("treasury_silver_available", 0))
                draw_item_icon(screen, "wood", (row.left + 58, price_y - 6), 32)
                screen.blit(self.small_font.render(
                    f"{wood_available}/{config['wood_cost']}", True, (225, 218, 193)),
                    (row.left + 94, price_y + 2))
                draw_item_icon(screen, "silver", (row.left + 158, price_y - 6), 32)
                screen.blit(self.small_font.render(
                    f"{silver_available}/{config['silver_cost']}", True, (225, 218, 193)),
                    (row.left + 194, price_y + 2))
                production_seconds = int(config["production_seconds"])
                duration = (
                    "40 минут" if production_seconds == 40 * 60
                    else format_forge_time(production_seconds)
                )
                production_label = f"Производство: {duration}"
                screen.blit(self.small_font.render(production_label, True, (193, 208, 204)),
                            (row.left + 270, price_y + 2))

                action_rect = pygame.Rect(row.right - 108, price_y - 3, 96, 26)
                queue_count = len(cart_state.get("queue", []))
                can_order = (
                    queue_count < int(cart_state.get("queue_limit", 5))
                    and wood_available >= int(config["wood_cost"])
                    and silver_available >= int(config["silver_cost"])
                )
                draw_button(
                    screen, action_rect, "Заказать", self.small_font,
                    color=(73, 105, 82) if can_order else (56, 61, 57),
                    text_color=(230, 237, 220) if can_order else (150, 157, 151),
                )
                self.workshop_cart_buttons[grade] = action_rect
                if grade == 1:
                    self.workshop_cart_button = action_rect
            screen.set_clip(None)

            workshop_message = getattr(self, "workshop_message", None)
            if workshop_message:
                message = self.small_font.render(str(workshop_message), True, (232, 153, 123))
                screen.blit(message, (viewport.left + 18, viewport.bottom - message.get_height() - 6))
        else:
            messages = {
                "helmets": "Раздел шлемов мастерской.",
                "armor": "Раздел доспехов и брони.",
                "gloves": "Раздел перчаток.",
                "plates": "Раздел латных комплектов.",
                "shoes": "Раздел обуви.",
                "leatherworker": "Кожевник: обработка кожи и кожаные изделия.",
                "upgrades": "Улучшения мастерской будут доступны после настройки требований.",
            }
            title = self.font.render(labels.get(selected_tab, "Мастерская"), True, (226, 218, 193))
            screen.blit(title, (viewport.left + 28, viewport.top + 28))
            message = self.small_font.render(messages.get(selected_tab, "Раздел готовится."),
                                             True, (184, 191, 187))
            screen.blit(message, (viewport.left + 28, viewport.top + 66))

        self._draw_workshop_process(screen, rect)

    def _draw_workshop_finished_goods(self, screen, viewport, orders):
        for index, order in enumerate(orders):
            column, row = index % 4, index // 4
            card = pygame.Rect(viewport.left + 12 + column * 386,
                               viewport.top + 12 + row * 184, 374, 170)
            pygame.draw.rect(screen, (26, 35, 28), card, border_radius=8)
            pygame.draw.rect(screen, (60, 140, 80), card, 1, border_radius=8)
            draw_item_icon(screen, order.get("icon", "armor_light"),
                           (card.left + 12, card.top + 18), 32)
            name = self.font.render(str(order.get("item_name", "Изделие мастерской")),
                                    True, (231, 218, 187))
            screen.blit(name, (card.left + 52, card.top + 14))
            status = self.badge_font.render("ГОТОВО К ВЫДАЧЕ", True, (110, 220, 130))
            screen.blit(status, (card.left + 52, card.top + 42))

    def _draw_workshop_process(self, screen, rect):
        panel = pygame.Rect(rect.left + 24, rect.bottom - 264, rect.width - 48, 244)
        pygame.draw.rect(screen, (28, 31, 31), panel, border_radius=8)
        pygame.draw.rect(screen, (94, 132, 144), panel, 2, border_radius=8)
        header = pygame.Rect(panel.left, panel.top, panel.width, 36)
        pygame.draw.rect(screen, (43, 53, 55), header,
                         border_top_left_radius=8, border_top_right_radius=8)
        queue = getattr(self, "workshop_state", {}).get("queue", [])
        queue_limit = int(getattr(self, "workshop_state", {}).get("queue_limit", 5))
        queue_total_seconds = sum(int(order.get("seconds_left", 0)) for order in queue)
        title = f"ПРОЦЕСС РАБОТЫ МАСТЕРСКОЙ • ОЧЕРЕДЬ: {len(queue)} / {queue_limit} (МАКС. 5 ЗАКАЗОВ)"
        screen.blit(self.small_font.render(title, True, (201, 224, 229)),
                    (panel.left + 16, panel.top + 7))
        total_time = self.font.render(
            f"ОБЩЕЕ ВРЕМЯ: {format_forge_time(queue_total_seconds)}",
            True, (221, 205, 157),
        )
        screen.blit(total_time, total_time.get_rect(
            midright=(panel.right - 16, panel.top + 18)
        ))
        work = pygame.Rect(panel.left + 14, panel.top + 46, 440, 186)
        pygame.draw.rect(screen, (34, 39, 39), work, border_radius=8)
        pygame.draw.rect(screen, (73, 94, 98), work, 1, border_radius=8)
        if queue:
            order = queue[0]
            cart_icon = draw_transport_cart_icon(
                screen, CART_GRADES.get(str(order.get("grade", 1)), {}).get("sprite_key", "light"),
                (work.left + 16, work.top + 16), 32,
            )
            name = self.font.render(f"В ПРОИЗВОДСТВЕ: {order.get('item_name', 'Повозка')}",
                                    True, (224, 217, 194))
            name_x = cart_icon.right + 8 if cart_icon else work.left + 16
            screen.blit(name, (name_x, work.top + 16))
            seconds = int(order.get("seconds_left", 0))
            screen.blit(self.small_font.render(f"До готовности: {format_forge_time(seconds)}",
                                               True, (221, 187, 120)),
                        (name_x, work.top + 48))
            progress_bar = pygame.Rect(work.left + 16, work.top + 124, work.width - 32, 28)
            pygame.draw.rect(screen, (20, 25, 25), progress_bar, border_radius=5)
            duration = max(1, int(order.get("duration_seconds", 40 * 60)))
            elapsed = max(0, min(duration, duration - seconds))
            progress_ratio = elapsed / duration
            if progress_ratio > 0:
                pygame.draw.rect(
                    screen, (77, 163, 103),
                    (progress_bar.left, progress_bar.top,
                     int(progress_bar.width * progress_ratio), progress_bar.height),
                    border_radius=5,
                )
            pygame.draw.rect(screen, (94, 132, 144), progress_bar, 1, border_radius=5)
            progress_text = self.badge_font.render(
                f"{int(progress_ratio * 100)}%", True, (238, 244, 237)
            )
            screen.blit(progress_text, progress_text.get_rect(center=progress_bar.center))
        else:
            screen.blit(self.font.render("Мастерская свободна", True, (218, 213, 197)),
                        (work.left + 18, work.top + 46))
            screen.blit(self.small_font.render("Ожидает заказа на производство.",
                                               True, (174, 181, 178)),
                        (work.left + 18, work.top + 84))
        slot_width, slot_gap = 210, 10
        for slot_index in range(5):
            slot = pygame.Rect(panel.left + 466 + slot_index * (slot_width + slot_gap),
                               panel.top + 46, slot_width, 186)
            if slot_index < len(queue):
                order = queue[slot_index]
                is_current = slot_index == 0
                pygame.draw.rect(screen, (40, 51, 43) if is_current else (34, 42, 37),
                                 slot, border_radius=8)
                pygame.draw.rect(screen, (108, 168, 115) if is_current else (72, 100, 79),
                                 slot, 2 if is_current else 1, border_radius=8)
                badge = f"[{slot_index + 1}] В ПРОИЗВОДСТВЕ"
                screen.blit(self.badge_font.render(badge, True, (159, 219, 164)),
                            (slot.left + 10, slot.top + 10))
                cart_sprite = CART_GRADES.get(
                    str(order.get("grade", 1)), {}
                ).get("sprite_key", "light")
                draw_transport_cart_icon(screen, cart_sprite,
                                         (slot.left + 10, slot.top + 38), 32)
                name = str(order.get("item_name", "Повозка"))
                screen.blit(self.small_font.render(name, True, (223, 214, 190)),
                            (slot.left + 50, slot.top + 44))
                screen.blit(self.small_font.render("До готовности:", True, (166, 177, 170)),
                            (slot.left + 10, slot.top + 92))
                timer = format_forge_time(int(order.get("seconds_left", 0)))
                screen.blit(self.font.render(timer, True, (221, 187, 120)),
                            (slot.left + 10, slot.top + 118))
            else:
                pygame.draw.rect(screen, (34, 38, 38), slot, border_radius=8)
                pygame.draw.rect(screen, (72, 85, 86), slot, 1, border_radius=8)
                label = f"[{slot_index + 1}] СВОБОДНЫЙ СЛОТ"
                screen.blit(self.badge_font.render(label, True, (160, 164, 158)),
                            (slot.left + 10, slot.top + 12))
                screen.blit(self.small_font.render("До 5 заказов мастерской",
                                                   True, (143, 150, 146)),
                            (slot.left + 10, slot.top + 54))

    def _draw_barracks_modal(self, screen):
        """Отрисовывает модальное меню-заглушку Городских Казарм с кнопкой 'Вернуться в город'."""
        overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 18, 215))
        screen.blit(overlay, (0, 0))

        rect = self.barracks_modal_rect
        modal_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(modal_surf, (22, 26, 32, 250), (0, 0, rect.width, rect.height), border_radius=12)
        pygame.draw.rect(modal_surf, (80, 150, 230), (0, 0, rect.width, rect.height), width=2, border_radius=12)
        screen.blit(modal_surf, rect.topleft)

        m_pos = pygame.mouse.get_pos()
        c_hover = self.barracks_close_button.collidepoint(m_pos)
        pygame.draw.rect(screen, (160, 45, 45) if c_hover else (45, 30, 35), self.barracks_close_button, border_radius=4)
        pygame.draw.rect(screen, (220, 100, 100), self.barracks_close_button, 1, border_radius=4)
        x_surf = self.small_font.render("✕", True, (255, 255, 255))
        screen.blit(x_surf, x_surf.get_rect(center=self.barracks_close_button.center))

        # Заголовок
        self._draw_building_title(screen, rect, "barracks_building", "ГОРОДСКИЕ КАЗАРМЫ (УРОВЕНЬ 1)", (255, 220, 100))

        sub_surf = self.badge_font.render("[ ВОЕННЫЙ ГАРНИЗОН РАДБУРГА • 9х13 ТАЙЛОВ • ВХОД: 84/43 ]", True, (130, 200, 255))
        screen.blit(sub_surf, (rect.left + 30, rect.top + 58))

        pygame.draw.line(screen, (60, 80, 105), (rect.left + 24, rect.top + 84), (rect.right - 24, rect.top + 84), 1)

        # Плашка состояния гарнизона
        status_box = pygame.Rect(rect.left + 30, rect.top + 98, rect.width - 60, 40)
        pygame.draw.rect(screen, (24, 34, 46), status_box, border_radius=6)
        pygame.draw.rect(screen, (70, 140, 220), status_box, 1, border_radius=6)
        notice_txt = self.small_font.render("🛡️ Гарнизон на боевом дежурстве: Солдаты содержатся и несут службу на стенах", True, (160, 220, 255))
        screen.blit(notice_txt, notice_txt.get_rect(center=status_box.center))

        # Блок оперативной сводки по войскам
        stats_top = rect.top + 155
        h1 = self.font.render("⚔️ Содержание и численность солдат гарнизона:", True, (255, 230, 140))
        screen.blit(h1, (rect.left + 30, stats_top))

        stat_lines = [
            ("👥 Регулярные солдаты гарнизона:", "120 / 200 бойцов (пехотинцы, мечники, копейщики)"),
            ("🏹 Стрелки и стражи стен:", "60 / 100 лучников на крепостных стенах и башнях"),
            ("🍞 Снабжение провизией из амбара:", "100% суточного довольствия (боеготовность максимальная)"),
            ("⚔️ Оснащение оружием и броней:", "Кузница и мастерская обеспечивают +20% к боевой мощи"),
            ("🎖️ Назначение казарм:", "Оборона ворот города, отражение штурмов и марш армий Света"),
            ("📈 Улучшение казарм (Ур. 2):", "Увеличит вместимость до 500 бойцов и откроет наём тяжелых рыцарей"),
        ]

        curr_y = stats_top + 34
        for title_line, text_line in stat_lines:
            f_title = self.small_font.render(title_line, True, (100, 220, 255))
            screen.blit(f_title, (rect.left + 40, curr_y))
            curr_y += 20
            f_desc = self.grid_font.render(text_line, True, (215, 225, 235))
            screen.blit(f_desc, (rect.left + 50, curr_y))
            curr_y += 24

        # Кнопка: [ ВЕРНУТЬСЯ В ГОРОД ]
        btn_hover = self.barracks_back_button.collidepoint(m_pos)
        btn_col = (70, 130, 200) if btn_hover else (45, 85, 140)
        draw_button(screen, self.barracks_back_button, "ВЕРНУТЬСЯ В ГОРОД", self.font, color=btn_col, text_color=(255, 255, 255))

    def _draw_engineering_modal(self, screen):
        """Отрисовывает модальное меню-заглушку Инженерной палаты с кнопкой 'Вернуться в город'."""
        overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 18, 215))
        screen.blit(overlay, (0, 0))

        rect = self.engineering_modal_rect
        modal_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(modal_surf, (20, 26, 28, 250), (0, 0, rect.width, rect.height), border_radius=12)
        pygame.draw.rect(modal_surf, (100, 210, 190), (0, 0, rect.width, rect.height), width=2, border_radius=12)
        screen.blit(modal_surf, rect.topleft)

        m_pos = pygame.mouse.get_pos()
        c_hover = self.engineering_close_button.collidepoint(m_pos)
        pygame.draw.rect(screen, (160, 45, 45) if c_hover else (45, 30, 35), self.engineering_close_button, border_radius=4)
        pygame.draw.rect(screen, (220, 100, 100), self.engineering_close_button, 1, border_radius=4)
        x_surf = self.small_font.render("✕", True, (255, 255, 255))
        screen.blit(x_surf, x_surf.get_rect(center=self.engineering_close_button.center))

        # Заголовок
        self._draw_building_title(screen, rect, "engineering_building", "ИНЖЕНЕРНАЯ ПАЛАТА (УРОВЕНЬ 1)", (255, 220, 100))

        sub_surf = self.badge_font.render("[ ЦЕХ ОБОРОННЫХ СООРУЖЕНИЙ И ОСАДНЫХ МАШИН • 10х8 ТАЙЛОВ • ВХОД: 44/15 ]", True, (130, 200, 255))
        screen.blit(sub_surf, (rect.left + 30, rect.top + 58))

        pygame.draw.line(screen, (60, 90, 85), (rect.left + 24, rect.top + 84), (rect.right - 24, rect.top + 84), 1)

        # Плашка состояния цеха
        status_box = pygame.Rect(rect.left + 30, rect.top + 98, rect.width - 60, 40)
        pygame.draw.rect(screen, (22, 36, 36), status_box, border_radius=6)
        pygame.draw.rect(screen, (80, 200, 170), status_box, 1, border_radius=6)
        notice_txt = self.small_font.render("🔨 Цех инженеров активен: Чертежи и станки подготовлены к сборке боевых машин", True, (150, 235, 215))
        screen.blit(notice_txt, notice_txt.get_rect(center=status_box.center))

        # Блок описания возможностей
        stats_top = rect.top + 155
        h1 = self.font.render("🎯 Производство боевых машин и осадной техники:", True, (255, 230, 140))
        screen.blit(h1, (rect.left + 30, stats_top))

        stat_lines = [
            ("🎯 Катапульта полевая:", "Метание зажигательных снарядов и камней по вражеским укреплениям"),
            ("🪵 Осадный таран:", "Пробитие ворот и укреплений противника в наступлении армий Света"),
            ("🏹 Тяжелый требушет:", "Сверхдальнобойная артиллерия для сокрушения цитаделей Тьмы"),
            ("🧱 Оборонные турели и баллисты:", "Усиление гарнизона и огневой мощи крепостных стен города"),
            ("📦 Требуемые ресурсы со склада:", "Древесина, камень, обработанное железо и канаты"),
            ("📈 Улучшение палаты (Ур. 2):", "Откроет автоматические многозарядные баллисты и бронированные башни"),
        ]

        curr_y = stats_top + 34
        for title_line, text_line in stat_lines:
            f_title = self.small_font.render(title_line, True, (120, 225, 210))
            screen.blit(f_title, (rect.left + 40, curr_y))
            curr_y += 20
            f_desc = self.grid_font.render(text_line, True, (215, 225, 235))
            screen.blit(f_desc, (rect.left + 50, curr_y))
            curr_y += 24

        # Кнопка: [ ВЕРНУТЬСЯ В ГОРОД ]
        btn_hover = self.engineering_back_button.collidepoint(m_pos)
        btn_col = (70, 130, 200) if btn_hover else (45, 85, 140)
        draw_button(screen, self.engineering_back_button, "ВЕРНУТЬСЯ В ГОРОД", self.font, color=btn_col, text_color=(255, 255, 255))

    def _draw_university_modal(self, screen):
        """Отрисовывает модальное меню-заглушку Городского Университета с кнопкой 'Вернуться в город'."""
        overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 18, 215))
        screen.blit(overlay, (0, 0))

        rect = self.university_modal_rect
        modal_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(modal_surf, (20, 26, 36, 250), (0, 0, rect.width, rect.height), border_radius=12)
        pygame.draw.rect(modal_surf, (120, 190, 255), (0, 0, rect.width, rect.height), width=2, border_radius=12)
        screen.blit(modal_surf, rect.topleft)

        m_pos = pygame.mouse.get_pos()
        c_hover = self.university_close_button.collidepoint(m_pos)
        pygame.draw.rect(screen, (160, 45, 45) if c_hover else (45, 30, 35), self.university_close_button, border_radius=4)
        pygame.draw.rect(screen, (220, 100, 100), self.university_close_button, 1, border_radius=4)
        x_surf = self.small_font.render("✕", True, (255, 255, 255))
        screen.blit(x_surf, x_surf.get_rect(center=self.university_close_button.center))

        # Заголовок
        self._draw_building_title(screen, rect, "university_building", "ГОРОДСКОЙ УНИВЕРСИТЕТ (УРОВЕНЬ 1)", (255, 220, 100))

        sub_surf = self.badge_font.render("[ АКАДЕМИЯ ТЕХНОЛОГИЙ И НАУК РАДБУРГА • 15х11 ТАЙЛОВ • ВХОД: 23/84 ]", True, (130, 200, 255))
        screen.blit(sub_surf, (rect.left + 30, rect.top + 58))

        pygame.draw.line(screen, (60, 80, 110), (rect.left + 24, rect.top + 84), (rect.right - 24, rect.top + 84), 1)

        # Плашка состояния исследований
        status_box = pygame.Rect(rect.left + 30, rect.top + 98, rect.width - 60, 40)
        pygame.draw.rect(screen, (20, 32, 48), status_box, border_radius=6)
        pygame.draw.rect(screen, (80, 160, 240), status_box, 1, border_radius=6)
        notice_txt = self.small_font.render("📖 Академия активна: Учёные и архимаги исследуют новые технологии города", True, (160, 225, 255))
        screen.blit(notice_txt, notice_txt.get_rect(center=status_box.center))

        # Блок описания возможностей
        stats_top = rect.top + 155
        h1 = self.font.render("🔬 Изучение новых технологий и научных открытий:", True, (255, 230, 140))
        screen.blit(h1, (rect.left + 30, stats_top))

        stat_lines = [
            ("⛏️ Горное дело и металлургия:", "+15% к добыче железной руды и качеству выплавки слитков"),
            ("🧱 Фортификация и зодчество:", "+20% к прочности крепостных стен, башен и ворот города"),
            ("🌾 Селекция и агрономия:", "Повышение урожайности пшеничных полей и вместимости амбаров"),
            ("⚔️ Военное искусство и тактика:", "Увеличение атаки и защиты гарнизона регулярной армии"),
            ("📜 Свитки древних знаний:", "Открытие редких рецептов крафта, чар и рунических печатей"),
            ("📈 Улучшение университета (Ур. 2):", "Откроет высшую алхимию, зачарование экипировки и магические башни"),
        ]

        curr_y = stats_top + 34
        for title_line, text_line in stat_lines:
            f_title = self.small_font.render(title_line, True, (130, 210, 255))
            screen.blit(f_title, (rect.left + 40, curr_y))
            curr_y += 20
            f_desc = self.grid_font.render(text_line, True, (215, 225, 235))
            screen.blit(f_desc, (rect.left + 50, curr_y))
            curr_y += 24

        # Кнопка: [ ВЕРНУТЬСЯ В ГОРОД ]
        btn_hover = self.university_back_button.collidepoint(m_pos)
        btn_col = (70, 130, 200) if btn_hover else (45, 85, 140)
        draw_button(screen, self.university_back_button, "ВЕРНУТЬСЯ В ГОРОД", self.font, color=btn_col, text_color=(255, 255, 255))

    def _draw_academy_modal(self, screen):
        """Отрисовывает модальное меню-заглушку Военной академии с кнопкой 'Вернуться в город'."""
        overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 18, 215))
        screen.blit(overlay, (0, 0))

        rect = self.academy_modal_rect
        modal_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(modal_surf, (26, 20, 22, 250), (0, 0, rect.width, rect.height), border_radius=12)
        pygame.draw.rect(modal_surf, (220, 90, 70), (0, 0, rect.width, rect.height), width=2, border_radius=12)
        screen.blit(modal_surf, rect.topleft)

        m_pos = pygame.mouse.get_pos()
        c_hover = self.academy_close_button.collidepoint(m_pos)
        pygame.draw.rect(screen, (160, 45, 45) if c_hover else (45, 30, 35), self.academy_close_button, border_radius=4)
        pygame.draw.rect(screen, (220, 100, 100), self.academy_close_button, 1, border_radius=4)
        x_surf = self.small_font.render("✕", True, (255, 255, 255))
        screen.blit(x_surf, x_surf.get_rect(center=self.academy_close_button.center))

        # Заголовок
        self._draw_building_title(screen, rect, "military_academy", "ВОЕННАЯ АКАДЕМИЯ (УРОВЕНЬ 1)", (255, 220, 100))

        sub_surf = self.badge_font.render("[ ЦЕНТР ОБУЧЕНИЯ ВОИНОВ И ПРОКАЧКИ КАРТ • 10х7 ТАЙЛОВ • ВХОД: 19/73 ]", True, (255, 180, 150))
        screen.blit(sub_surf, (rect.left + 30, rect.top + 58))

        pygame.draw.line(screen, (90, 60, 65), (rect.left + 24, rect.top + 84), (rect.right - 24, rect.top + 84), 1)

        # Плашка состояния академии
        status_box = pygame.Rect(rect.left + 30, rect.top + 98, rect.width - 60, 40)
        pygame.draw.rect(screen, (42, 24, 28), status_box, border_radius=6)
        pygame.draw.rect(screen, (220, 80, 70), status_box, 1, border_radius=6)
        notice_txt = self.small_font.render("⚔️ Академия открыта: Место тренировки бойцов, развития талантов и усиления карт", True, (255, 190, 180))
        screen.blit(notice_txt, notice_txt.get_rect(center=status_box.center))

        # Блок описания возможностей
        stats_top = rect.top + 155
        h1 = self.font.render("🥋 Обучение воинов и прокачка карт силовой линии:", True, (255, 230, 140))
        screen.blit(h1, (rect.left + 30, stats_top))

        stat_lines = [
            ("⚔️ Прокачка карт силовой линии:", "Повышение урона, снижение стоимости и открытие комбо-эффектов боевых карт"),
            ("🌲 Ветви талантов бойца:", "Развитие направлений: Несокрушимый защитник, Берсерк ярости, Мастер клинка"),
            ("🎴 Открытие новых боевых карт:", "Изучение приёмов: Сокрушительный удар, Парирование, Боевой клич, Раскол брони"),
            ("🥊 Тренировочные спарринги:", "Отработка тактики боя на полигоне с инструкторами академии"),
            ("🛡️ Подготовка элитных командиров:", "Повышение выучки офицеров гарнизона (+15% к дисциплине отрядов)"),
            ("📈 Улучшение академии (Ур. 2):", "Откроет доступ к легендарным картам стоек и ультимативным приёмам"),
        ]

        curr_y = stats_top + 34
        for title_line, text_line in stat_lines:
            f_title = self.small_font.render(title_line, True, (255, 160, 140))
            screen.blit(f_title, (rect.left + 40, curr_y))
            curr_y += 20
            f_desc = self.grid_font.render(text_line, True, (225, 225, 235))
            screen.blit(f_desc, (rect.left + 50, curr_y))
            curr_y += 24

        # Кнопка: [ ВЕРНУТЬСЯ В ГОРОД ]
        btn_hover = self.academy_back_button.collidepoint(m_pos)
        btn_col = (70, 130, 200) if btn_hover else (45, 85, 140)
        draw_button(screen, self.academy_back_button, "ВЕРНУТЬСЯ В ГОРОД", self.font, color=btn_col, text_color=(255, 255, 255))

    def _draw_mage_school_modal(self, screen):
        """Отрисовывает модальное меню-заглушку Школы стихий с кнопкой 'Вернуться в город'."""
        overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 18, 215))
        screen.blit(overlay, (0, 0))

        rect = self.mage_school_modal_rect
        modal_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(modal_surf, (22, 18, 34, 250), (0, 0, rect.width, rect.height), border_radius=12)
        pygame.draw.rect(modal_surf, (180, 110, 255), (0, 0, rect.width, rect.height), width=2, border_radius=12)
        screen.blit(modal_surf, rect.topleft)

        m_pos = pygame.mouse.get_pos()
        c_hover = self.mage_school_close_button.collidepoint(m_pos)
        pygame.draw.rect(screen, (160, 45, 45) if c_hover else (45, 30, 35), self.mage_school_close_button, border_radius=4)
        pygame.draw.rect(screen, (220, 100, 100), self.mage_school_close_button, 1, border_radius=4)
        x_surf = self.small_font.render("✕", True, (255, 255, 255))
        screen.blit(x_surf, x_surf.get_rect(center=self.mage_school_close_button.center))

        # Заголовок
        self._draw_building_title(screen, rect, "mage_school_building", "ШКОЛА СТИХИЙ (УРОВЕНЬ 1)", (255, 220, 100))

        sub_surf = self.badge_font.render("[ ЦЕНТР ОБУЧЕНИЯ МАГИИ И ПРОКАЧКИ МАГИЧЕСКИХ КАРТ • 15х9 ТАЙЛОВ • ВХОД: 44/66 ]", True, (210, 175, 255))
        screen.blit(sub_surf, (rect.left + 30, rect.top + 58))

        pygame.draw.line(screen, (85, 60, 110), (rect.left + 24, rect.top + 84), (rect.right - 24, rect.top + 84), 1)

        # Плашка состояния школы
        status_box = pygame.Rect(rect.left + 30, rect.top + 98, rect.width - 60, 40)
        pygame.draw.rect(screen, (34, 24, 52), status_box, border_radius=6)
        pygame.draw.rect(screen, (180, 100, 255), status_box, 1, border_radius=6)
        notice_txt = self.small_font.render("✨ Школа стихий открыта: Постижение тайных знаний, концентрация маны и усиление заклинаний", True, (225, 195, 255))
        screen.blit(notice_txt, notice_txt.get_rect(center=status_box.center))

        # Блок описания возможностей
        stats_top = rect.top + 155
        h1 = self.font.render("⚡ Обучение магии и развитие стихийных карт:", True, (255, 230, 140))
        screen.blit(h1, (rect.left + 30, stats_top))

        stat_lines = [
            ("🔥 Стихия Огня:", "Прокачка атакующих карт пламени, взрывов, ожогов и огненного шара"),
            ("💧 Стихия Воды:", "Изучение исцеляющих потоков, ледяных оков и очищения разума"),
            ("🌪️ Стихия Воздуха:", "Увеличение скорости каста, молнии, цепные разряды и уклонение"),
            ("🌿 Стихия Земли:", "Каменная кожа, шипы, защитные барьеры и землетрясения"),
            ("✨ Стихия Света:", "Божественные благословения, экзорцизм и рассеивание чар Тьмы"),
            ("🎴 Прокачка магических карт:", "Снижение расхода маны карт заклинаний, увеличение урона и длительности эффектов"),
            ("📈 Улучшение школы (Ур. 2):", "Откроет создание комбинированных стихийных заклинаний и ритуальные круги"),
        ]

        curr_y = stats_top + 34
        for title_line, text_line in stat_lines:
            f_title = self.small_font.render(title_line, True, (200, 160, 255))
            screen.blit(f_title, (rect.left + 40, curr_y))
            curr_y += 19
            f_desc = self.grid_font.render(text_line, True, (225, 225, 235))
            screen.blit(f_desc, (rect.left + 50, curr_y))
            curr_y += 22

        # Кнопка: [ ВЕРНУТЬСЯ В ГОРОД ]
        btn_hover = self.mage_school_back_button.collidepoint(m_pos)
        btn_col = (70, 130, 200) if btn_hover else (45, 85, 140)
        draw_button(screen, self.mage_school_back_button, "ВЕРНУТЬСЯ В ГОРОД", self.font, color=btn_col, text_color=(255, 255, 255))
