"""HUD и окно активного (выбранного по ЛКМ) объекта города."""
import pygame
from core import settings
from ui.hud import draw_button


class CityHudMixin:
    """Требует _is_within_one_tile, active_entity/active_window_rect и т.д. из CityScene."""

    def _draw_active_window(self, screen):
        """Отрисовывает окно активного объекта (выбранного по ЛКМ)."""
        if self.active_entity is None or self.castle_menu_open or self.barn_menu_open or self.warehouse_menu_open or self.forge_menu_open or self.workshop_menu_open or self.barracks_menu_open or self.engineering_menu_open or self.university_menu_open or self.academy_menu_open or self.mage_school_menu_open:
            return

        ent = self.active_entity
        rect = self.active_window_rect

        win_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(win_surf, (15, 20, 28, 245), (0, 0, rect.width, rect.height), border_radius=8)
        pygame.draw.rect(win_surf, (220, 185, 60, 255), (0, 0, rect.width, rect.height), width=2, border_radius=8)
        screen.blit(win_surf, rect.topleft)

        icon = ent.get("icon", "📍")
        name = ent.get("name", "Объект")
        title_surf = self.font.render(f"{icon} {name}", True, (255, 225, 120))
        screen.blit(title_surf, (rect.left + 14, rect.top + 12))

        status_surf = self.badge_font.render("● АКТИВЕН", True, (80, 255, 120))
        screen.blit(status_surf, (rect.left + 14, rect.top + 40))

        m_pos = pygame.mouse.get_pos()
        close_hover = self.active_close_button.collidepoint(m_pos)
        c_bg = (180, 50, 50) if close_hover else (45, 30, 35)
        pygame.draw.rect(screen, c_bg, self.active_close_button, border_radius=4)
        pygame.draw.rect(screen, (220, 100, 100), self.active_close_button, width=1, border_radius=4)
        x_surf = self.small_font.render("✕", True, (255, 255, 255))
        screen.blit(x_surf, x_surf.get_rect(center=self.active_close_button.center))

        pygame.draw.line(screen, (50, 65, 80), (rect.left + 14, rect.top + 62), (rect.right - 14, rect.top + 62), 1)

        in_range = self._is_within_one_tile(ent)
        if ent.get("id") == "player":
            range_info = "● Ваш персонаж"
            range_col = (100, 220, 255)
        elif in_range:
            range_info = "● В радиусе действия (<= 1 тайл)"
            range_col = (80, 255, 120)
        else:
            range_info = "○ Слишком далеко"
            range_col = (160, 160, 160)

        r_surf = self.grid_font.render(f"Тип: {ent.get('type', 'Объект')} | {range_info}", True, range_col)
        screen.blit(r_surf, (rect.left + 14, rect.top + 72))

        desc = ent.get("desc", "")
        if len(desc) > 42:
            line1 = desc[:42]
            line2 = desc[42:84]
            d1_surf = self.grid_font.render(line1, True, (210, 215, 220))
            d2_surf = self.grid_font.render(line2, True, (210, 215, 220))
            screen.blit(d1_surf, (rect.left + 14, rect.top + 92))
            screen.blit(d2_surf, (rect.left + 14, rect.top + 108))
        else:
            d_surf = self.grid_font.render(desc, True, (210, 215, 220))
            screen.blit(d_surf, (rect.left + 14, rect.top + 96))

        if self.action_notice:
            not_surf = self.small_font.render(self.action_notice, True, (255, 120, 100))
            not_rect = not_surf.get_rect(center=self.active_action_button.center)
            pygame.draw.rect(screen, (40, 25, 25), self.active_action_button, border_radius=4)
            pygame.draw.rect(screen, (200, 80, 70), self.active_action_button, width=1, border_radius=4)
            screen.blit(not_surf, not_rect)
        else:
            if ent.get("id") == "player":
                action_label = "ФОКУС КАМЕРЫ"
            elif ent.get("id") == "main_castle":
                action_label = "ПОСЕТИТЬ ЗАМОК"
            elif ent.get("id") == "tavern_building":
                action_label = "ВОЙТИ В ТАВЕРНУ"
            elif ent.get("id") == "barn_building":
                action_label = "ОТКРЫТЬ АМБАР"
            elif ent.get("id") == "warehouse_building":
                action_label = "ОТКРЫТЬ СКЛАД"
            elif ent.get("id") == "forge_building":
                action_label = "ОТКРЫТЬ КУЗНИЦУ"
            elif ent.get("id") == "workshop_building":
                action_label = "ОТКРЫТЬ МАСТЕРСКУЮ"
            elif ent.get("id") == "barracks_building":
                action_label = "ВОЙТИ В КАЗАРМЫ"
            elif ent.get("id") == "engineering_building":
                action_label = "ОТКРЫТЬ ПАЛАТУ"
            elif ent.get("id") == "university_building":
                action_label = "ВОЙТИ В УНИВЕРСИТЕТ"
            elif ent.get("id") == "military_academy":
                action_label = "ВОЙТИ В АКАДЕМИЮ"
            elif ent.get("id") == "mage_school_building":
                action_label = "ВОЙТИ В ШКОЛУ СТИХИЙ"
            elif ent.get("id") == "crystal_of_life":
                action_label = "ПРИКОСНУТЬСЯ К КРИСТАЛЛУ"
            else:
                action_label = "ВЗАИМОДЕЙСТВОВАТЬ"

            btn_hover = self.active_action_button.collidepoint(m_pos)
            if ent.get("id") in ("player", "main_castle", "barn_building", "warehouse_building", "forge_building", "workshop_building", "barracks_building", "engineering_building", "university_building", "military_academy", "mage_school_building") or in_range:
                btn_col = (70, 120, 180) if btn_hover else (45, 80, 130)
                text_col = (255, 255, 255)
            else:
                btn_col = (75, 75, 80) if btn_hover else (55, 55, 60)
                text_col = (170, 170, 175)

            draw_button(screen, self.active_action_button, action_label, self.small_font, color=btn_col, text_color=text_col)

    def _draw_hud(self, screen):
        """Отрисовывает информационный HUD. Никаких кнопок телепортации нет — выход только пешком через ворота."""
        mouse_pos = pygame.mouse.get_pos()
        hover_wx, hover_wy = self.screen_to_world(mouse_pos[0], mouse_pos[1])
        hover_gx = int(hover_wx // self.tile_size)
        hover_gy = int(hover_wy // self.tile_size)
        player_gx = int(self.player_x // self.tile_size)
        player_gy = int(self.player_y // self.tile_size)

        # Верхняя панель
        hud_w = settings.WIDTH - 40
        hud_h = 42
        hud_surf = pygame.Surface((hud_w, hud_h), pygame.SRCALPHA)
        pygame.draw.rect(hud_surf, (15, 18, 24, 235), (0, 0, hud_w, hud_h), border_radius=6)
        pygame.draw.rect(hud_surf, (220, 180, 70), (0, 0, hud_w, hud_h), 1, border_radius=6)
        screen.blit(hud_surf, (20, 16))

        # Текст слева: Название города и размер
        title_surf = self.small_font.render("🏛️ ГОРОД РАДБУРГ (СТОЛИЦА СВЕТА)  [100x100 тайлов]", True, (255, 225, 110))
        screen.blit(title_surf, (34, 28))

        # Текст по центру: подсказка управления
        hint_str = "⌨️ [G] Сетка  |  [Пробел] К герою  |  [ПКМ] Идти  |  🚪 ВЫХОД: ТОЛЬКО ЧЕРЕЗ 4 ВОРОТ"
        hint_surf = self.grid_font.render(hint_str, True, (190, 205, 220))
        screen.blit(hint_surf, hint_surf.get_rect(center=(settings.WIDTH // 2, 37)))

        # Текст справа: координаты
        coord_str = f"Герой: [{player_gx}, {player_gy}]  |  Курсор: [{hover_gx}, {hover_gy}]"
        coord_surf = self.grid_font.render(coord_str, True, (255, 215, 120))
        screen.blit(coord_surf, (settings.WIDTH - coord_surf.get_width() - 36, 28))
