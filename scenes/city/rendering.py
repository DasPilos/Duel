"""Отрисовка зданий, стен/ворот, персонажа и эффектов сцены города."""
import math
import pygame
from core import settings


class CityRenderMixin:
    """Требует атрибуты CityScene: tile_size, world_to_screen, objects, шрифты и т.д."""

    def _draw_badge(self, screen, cx, bottom_y, text, border_color):
        """Вспомогательный метод для аккуратной плашки с текстом над объектом."""
        surf = self.badge_font.render(text, True, (240, 240, 240))
        bg = surf.get_rect(midbottom=(cx, bottom_y)).inflate(10, 4)
        if -50 <= bg.centerx <= settings.WIDTH + 50 and -50 <= bg.centery <= settings.HEIGHT + 50:
            pygame.draw.rect(screen, (12, 14, 18, 220), bg, border_radius=3)
            pygame.draw.rect(screen, border_color, bg, 1, border_radius=3)
            screen.blit(surf, surf.get_rect(center=bg.center))

    def _draw_city_objects(self, screen):
        """Отрисовывает интерактивные строения города (Кристалл Жизни, Главный замок, Таверна, Амбар, Склад)."""
        pulse = 1.0 + 0.08 * math.sin(self.player_anim_timer * 4.0)

        # 1. Главный Замок 15х15 тайлов (центр 75/70, X: 68..82, Y: 63..77)
        castle = self.objects[1]
        cx_px = castle["tile_x"] * self.tile_size
        cy_px = castle["tile_y"] * self.tile_size
        cw_px = castle["tile_w"] * self.tile_size
        ch_px = castle["tile_h"] * self.tile_size
        csx, csy = self.world_to_screen(cx_px, cy_px)

        if -cw_px <= csx <= settings.WIDTH + cw_px and -ch_px <= csy <= settings.HEIGHT + ch_px:
            castle_rect = pygame.Rect(csx, csy, cw_px, ch_px)
            is_active = self.active_entity and self.active_entity.get("id") == castle["id"]
            is_hovered = self.hovered_entity and self.hovered_entity.get("id") == castle["id"]

            # Тень замка
            pygame.draw.ellipse(screen, (15, 18, 24, 200), (csx + 20, csy + ch_px - 70, cw_px - 40, 90))

            # Поверхность заглушки замка
            c_surf = pygame.Surface((cw_px, ch_px), pygame.SRCALPHA)
            pygame.draw.rect(c_surf, (36, 44, 56, 235), (0, 0, cw_px, ch_px), border_radius=8)

            # Внутренняя сетка тайлов замка
            for gx in range(castle["tile_w"] + 1):
                xl = gx * self.tile_size
                col = (75, 95, 120, 160) if gx % 5 == 0 else (48, 62, 78, 100)
                pygame.draw.line(c_surf, col, (xl, 0), (xl, ch_px), 2 if gx % 5 == 0 else 1)
            for gy in range(castle["tile_h"] + 1):
                yl = gy * self.tile_size
                col = (75, 95, 120, 160) if gy % 5 == 0 else (48, 62, 78, 100)
                pygame.draw.line(c_surf, col, (0, yl), (cw_px, yl), 2 if gy % 5 == 0 else 1)

            # 4 угловые башни (3х3 тайла = 96х96 px)
            ts = 3 * self.tile_size
            for tx, ty in [(0, 0), (cw_px - ts, 0), (0, ch_px - ts), (cw_px - ts, ch_px - ts)]:
                t_r = pygame.Rect(tx, ty, ts, ts)
                pygame.draw.rect(c_surf, (48, 58, 72, 245), t_r, border_radius=4)
                pygame.draw.rect(c_surf, (90, 115, 145), t_r, 2, border_radius=4)
                for bx in range(tx + 4, tx + ts - 8, 16):
                    pygame.draw.rect(c_surf, (24, 30, 38), (bx, ty + 2, 8, 6))

            # Центральный донжон (5х5 тайлов = 160х160 px)
            ks = 5 * self.tile_size
            kx = (cw_px - ks) // 2
            ky = (ch_px - ks) // 2
            k_r = pygame.Rect(kx, ky, ks, ks)
            pygame.draw.rect(c_surf, (42, 52, 66, 250), k_r, border_radius=6)
            pygame.draw.rect(c_surf, (120, 145, 180), k_r, 2, border_radius=6)

            # Южные королевские ворота замка (3 тайла = 96 px)
            gw = 3 * self.tile_size
            gh = int(1.5 * self.tile_size)
            gx = (cw_px - gw) // 2
            gy = ch_px - gh
            g_r = pygame.Rect(gx, gy, gw, gh)
            pygame.draw.rect(c_surf, (20, 24, 32), g_r, border_radius=4)
            pygame.draw.rect(c_surf, (220, 180, 80), g_r, 2, border_radius=4)
            lbl = self.grid_font.render("ВОРОТА ЗАМКА", True, (255, 220, 100))
            c_surf.blit(lbl, lbl.get_rect(center=g_r.center))

            # Факелы у ворот замка
            pygame.draw.circle(c_surf, (255, 160, 30), (gx - 6, gy + 16), 5)
            pygame.draw.circle(c_surf, (255, 230, 100), (gx - 6, gy + 16), 2)
            pygame.draw.circle(c_surf, (255, 160, 30), (gx + gw + 6, gy + 16), 5)
            pygame.draw.circle(c_surf, (255, 230, 100), (gx + gw + 6, gy + 16), 2)

            # Надписи внутри донжона
            t_surf = self.large_font.render("ГЛАВНЫЙ ЗАМОК", True, (255, 220, 100))
            c_surf.blit(t_surf, t_surf.get_rect(center=(cw_px // 2, ky + 34)))
            sub_surf = self.badge_font.render("[ КОРОЛЕВСКАЯ ЦИТАДЕЛЬ • 15х15 ]", True, (130, 200, 255))
            c_surf.blit(sub_surf, sub_surf.get_rect(center=(cw_px // 2, ky + 58)))
            coord_lbl = self.grid_font.render("Центр: [75, 70] | Сетка: X[68..82], Y[63..77]", True, (210, 220, 230))
            c_surf.blit(coord_lbl, coord_lbl.get_rect(center=(cw_px // 2, ky + 80)))
            hint_lbl = self.grid_font.render("👑 Премиум-квесты и сводка города", True, (255, 230, 140))
            c_surf.blit(hint_lbl, hint_lbl.get_rect(center=(cw_px // 2, ky + 104)))
            stat_lbl = self.grid_font.render("[ КЛИКНИТЕ ДЛЯ АУДИЕНЦИИ ]", True, (200, 170, 120))
            c_surf.blit(stat_lbl, stat_lbl.get_rect(center=(cw_px // 2, ky + 126)))

            screen.blit(c_surf, (csx, csy))

            # Подсветка
            if is_active:
                pygame.draw.rect(screen, (255, 215, 60), castle_rect, 3, border_radius=10)
            elif is_hovered:
                pygame.draw.rect(screen, (80, 200, 255), castle_rect.inflate(8, 8), 2, border_radius=10)
            else:
                pygame.draw.rect(screen, (100, 125, 155), castle_rect, 2, border_radius=8)

            badge_col = (255, 215, 60) if is_active else (100, 200, 255) if is_hovered else (220, 200, 160)
            self._draw_badge(screen, castle_rect.centerx, csy - 12, "🏰 Главный замок [15x15]", badge_col)

        # 2. Кристалл Жизни (в центре площади, 3х3 тайла = 9 тайлов, 96х96 px)
        crystal = self.objects[0]
        kx_px = crystal["tile_x"] * self.tile_size
        ky_px = crystal["tile_y"] * self.tile_size
        kw_px = crystal["tile_w"] * self.tile_size
        kh_px = crystal["tile_h"] * self.tile_size
        ksx, ksy = self.world_to_screen(kx_px, ky_px)

        if -kw_px <= ksx <= settings.WIDTH + kw_px and -kh_px <= ksy <= settings.HEIGHT + kh_px:
            cr_rect = pygame.Rect(ksx, ksy, kw_px, kh_px)
            is_c_active = self.active_entity and self.active_entity.get("id") == crystal["id"]
            is_c_hover = self.hovered_entity and self.hovered_entity.get("id") == crystal["id"]

            # Пьедестал алтаря 3х3 тайла (96х96 px) с рунами
            pygame.draw.ellipse(screen, (10, 30, 40, 200), (ksx - 10, ksy + kh_px - 20, kw_px + 20, 32))
            pygame.draw.rect(screen, (26, 36, 48), cr_rect, border_radius=6)
            pygame.draw.rect(screen, (60, 180, 220), cr_rect, 2, border_radius=6)

            # Внутренний мраморный круг
            pygame.draw.circle(screen, (34, 52, 68), cr_rect.center, 40)
            pygame.draw.circle(screen, (80, 220, 255), cr_rect.center, 38, 1)

            # Светящиеся рунические символы по углам
            for rx, ry in [(ksx + 12, ksy + 12), (ksx + kw_px - 12, ksy + 12), (ksx + 12, ksy + kh_px - 12), (ksx + kw_px - 12, ksy + kh_px - 12)]:
                pygame.draw.circle(screen, (80, 240, 255), (rx, ry), 4)

            # Парящий светящийся Кристалл Жизни
            hover_offset = int(math.sin(self.player_anim_timer * 4.0) * 8.0)
            cry_cx = cr_rect.centerx
            cry_cy = cr_rect.centery - 12 + hover_offset

            # Аура и лучи света
            aura_r = int(32 * pulse)
            aura_surf = pygame.Surface((aura_r * 2 + 4, aura_r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(aura_surf, (80, 220, 255, 70), (aura_r + 2, aura_r + 2), aura_r)
            pygame.draw.circle(aura_surf, (150, 255, 255, 120), (aura_r + 2, aura_r + 2), int(aura_r * 0.7))
            screen.blit(aura_surf, (cry_cx - aura_r - 2, cry_cy - aura_r - 2))

            # Октаэдрический граненый кристалл
            pts_crystal = [
                (cry_cx, cry_cy - 24),       # верх
                (cry_cx + 18, cry_cy - 4),   # право-верх
                (cry_cx + 12, cry_cy + 18),  # право-низ
                (cry_cx, cry_cy + 26),       # низ
                (cry_cx - 12, cry_cy + 18),  # лево-низ
                (cry_cx - 18, cry_cy - 4),   # лево-верх
            ]
            # Грани кристалла
            pygame.draw.polygon(screen, (60, 200, 240), pts_crystal)
            pygame.draw.polygon(screen, (160, 250, 255), [pts_crystal[0], pts_crystal[1], (cry_cx, cry_cy)])
            pygame.draw.polygon(screen, (100, 230, 255), [pts_crystal[0], (cry_cx, cry_cy), pts_crystal[5]])
            pygame.draw.polygon(screen, (40, 160, 210), [pts_crystal[1], pts_crystal[2], (cry_cx, cry_cy)])
            pygame.draw.polygon(screen, (30, 130, 180), [pts_crystal[2], pts_crystal[3], (cry_cx, cry_cy)])
            pygame.draw.polygon(screen, (50, 170, 220), [pts_crystal[3], pts_crystal[4], (cry_cx, cry_cy)])
            pygame.draw.polygon(screen, (80, 210, 250), [pts_crystal[4], pts_crystal[5], (cry_cx, cry_cy)])
            pygame.draw.polygon(screen, (255, 255, 255), pts_crystal, 1)

            # Ядро кристалла
            pygame.draw.circle(screen, (255, 255, 255), (cry_cx, cry_cy), 5)

            # Подсветка
            if is_c_active:
                pygame.draw.rect(screen, (255, 215, 60), cr_rect, 2, border_radius=6)
            elif is_c_hover:
                pygame.draw.rect(screen, (80, 240, 255), cr_rect.inflate(6, 6), 2, border_radius=8)

            badge_col = (255, 215, 60) if is_c_active else (80, 240, 255) if is_c_hover else (160, 230, 255)
            self._draw_badge(screen, cry_cx, ksy - 10, "💎 Кристалл Жизни [3x3]", badge_col)

        # 3. Городская Таверна 7х10 тайлов (X: 55..61, Y: 15..24, вход на тайле 55/15)
        tavern = self.objects[2]
        tx_px = tavern["tile_x"] * self.tile_size
        ty_px = tavern["tile_y"] * self.tile_size
        tw_px = tavern["tile_w"] * self.tile_size
        th_px = tavern["tile_h"] * self.tile_size
        tsx, tsy = self.world_to_screen(tx_px, ty_px)

        if -tw_px <= tsx <= settings.WIDTH + tw_px and -th_px <= tsy <= settings.HEIGHT + th_px:
            tav_rect = pygame.Rect(tsx, tsy, tw_px, th_px)
            is_t_active = self.active_entity and self.active_entity.get("id") == tavern["id"]
            is_t_hover = self.hovered_entity and self.hovered_entity.get("id") == tavern["id"]

            # Тень таверны
            pygame.draw.ellipse(screen, (18, 14, 12, 190), (tsx + 10, tsy + th_px - 40, tw_px - 20, 50))

            # Поверхность заглушки двухэтажной таверны
            t_surf = pygame.Surface((tw_px, th_px), pygame.SRCALPHA)

            # Первый этаж (каменный)
            floor1_rect = pygame.Rect(0, th_px // 2, tw_px, th_px // 2)
            pygame.draw.rect(t_surf, (54, 44, 38, 240), floor1_rect, border_radius=4)
            pygame.draw.rect(t_surf, (90, 75, 62), floor1_rect, 2, border_radius=4)

            # Второй этаж (деревянный фахверк)
            floor2_rect = pygame.Rect(0, 0, tw_px, th_px // 2)
            pygame.draw.rect(t_surf, (72, 54, 38, 240), floor2_rect, border_radius=4)
            pygame.draw.rect(t_surf, (115, 90, 65), floor2_rect, 2, border_radius=4)

            # Двускатная крыша с черепицей
            roof_poly = [
                (tw_px // 2, 4),
                (tw_px - 6, 24),
                (6, 24),
            ]
            pygame.draw.polygon(t_surf, (135, 60, 45), roof_poly)
            pygame.draw.polygon(t_surf, (175, 85, 65), roof_poly, 2)

            # Окна второго этажа
            for wx in range(16, tw_px - 24, 48):
                w_rect = pygame.Rect(wx, 36, 24, 28)
                pygame.draw.rect(t_surf, (255, 220, 110), w_rect, border_radius=3)
                pygame.draw.rect(t_surf, (50, 35, 25), w_rect, 2, border_radius=3)
                pygame.draw.line(t_surf, (50, 35, 25), (wx + 12, 36), (wx + 12, 64), 2)
                pygame.draw.line(t_surf, (50, 35, 25), (wx, 50), (wx + 24, 50), 2)

            # Дверь в таверну на тайле 55/15 (локально: X: 0..32, Y: (15 - 12)*32 = 96..128 на западной стене)
            door_gx, door_gy = tavern.get("entrance_tile", (55, 15))
            door_y = (door_gy - tavern["tile_y"]) * self.tile_size
            door_rect = pygame.Rect(2, door_y + 2, 28, 28)
            pygame.draw.rect(t_surf, (30, 20, 15), door_rect, border_radius=3)
            pygame.draw.rect(t_surf, (255, 215, 80), door_rect, 2, border_radius=3)
            door_lbl = self.grid_font.render("ВХОД", True, (255, 225, 100))
            t_surf.blit(door_lbl, door_lbl.get_rect(center=door_rect.center))

            # Теплый фонарь над дверью
            pygame.draw.circle(t_surf, (255, 180, 40), (16, door_y - 6), 5)
            pygame.draw.circle(t_surf, (255, 240, 120), (16, door_y - 6), 2)

            # Вывеска кружки пива
            sign_rect = pygame.Rect(tw_px // 2 - 40, th_px // 2 - 16, 80, 30)
            pygame.draw.rect(t_surf, (25, 18, 14), sign_rect, border_radius=4)
            pygame.draw.rect(t_surf, (220, 170, 70), sign_rect, 2, border_radius=4)
            sign_lbl = self.small_font.render("🍺 ТАВЕРНА", True, (255, 220, 120))
            t_surf.blit(sign_lbl, sign_lbl.get_rect(center=sign_rect.center))

            # Текстовые метки
            t1 = self.badge_font.render("[ 2 ЭТАЖА • 10х7 ТАЙЛОВ ]", True, (255, 230, 160))
            t_surf.blit(t1, t1.get_rect(center=(tw_px // 2, th_px - 44)))
            t2 = self.grid_font.render("Вход: [55, 15] (со стороны площади)", True, (220, 200, 180))
            t_surf.blit(t2, t2.get_rect(center=(tw_px // 2, th_px - 24)))

            screen.blit(t_surf, (tsx, tsy))

            # Подсветка
            if is_t_active:
                pygame.draw.rect(screen, (255, 215, 60), tav_rect, 2, border_radius=8)
            elif is_t_hover:
                pygame.draw.rect(screen, (255, 200, 100), tav_rect.inflate(6, 6), 2, border_radius=8)

            badge_col = (255, 215, 60) if is_t_active else (255, 200, 100) if is_t_hover else (230, 190, 140)
            self._draw_badge(screen, tav_rect.centerx, tsy - 10, "🍺 Таверна [10х7, 2 этажа]", badge_col)

        # 4. Городской Амбар 12х10 тайлов (X: 5..16, Y: 35..44, вход на 16/40)
        barn = self.objects[3]
        bx_px = barn["tile_x"] * self.tile_size
        by_px = barn["tile_y"] * self.tile_size
        bw_px = barn["tile_w"] * self.tile_size
        bh_px = barn["tile_h"] * self.tile_size
        bsx, bsy = self.world_to_screen(bx_px, by_px)

        if -bw_px <= bsx <= settings.WIDTH + bw_px and -bh_px <= bsy <= settings.HEIGHT + bh_px:
            barn_rect = pygame.Rect(bsx, bsy, bw_px, bh_px)
            is_b_active = self.active_entity and self.active_entity.get("id") == barn["id"]
            is_b_hover = self.hovered_entity and self.hovered_entity.get("id") == barn["id"]

            # Тень амбара
            pygame.draw.ellipse(screen, (16, 14, 10, 190), (bsx + 16, bsy + bh_px - 45, bw_px - 32, 55))

            # Поверхность заглушки амбара
            b_surf = pygame.Surface((bw_px, bh_px), pygame.SRCALPHA)

            # Каменное основание амбара (цоколь)
            base_rect = pygame.Rect(0, bh_px - 40, bw_px, 40)
            pygame.draw.rect(b_surf, (44, 48, 54, 240), base_rect, border_radius=4)
            pygame.draw.rect(b_surf, (70, 78, 88), base_rect, 2, border_radius=4)

            # Деревянный сруб/стены амбара
            body_rect = pygame.Rect(0, 36, bw_px, bh_px - 50)
            pygame.draw.rect(b_surf, (82, 60, 40, 245), body_rect, border_radius=4)
            pygame.draw.rect(b_surf, (55, 38, 24), body_rect, 2, border_radius=4)

            # Горизонтальные и вертикальные балки каркаса
            for gy_line in range(36, bh_px - 40, 32):
                pygame.draw.line(b_surf, (55, 38, 24), (0, gy_line), (bw_px, gy_line), 2)
            for gx_line in range(48, bw_px - 30, 48):
                pygame.draw.line(b_surf, (55, 38, 24), (gx_line, 36), (gx_line, bh_px - 14), 2)

            # Большая амбарная двухскатная крыша (соломенно-черепичная)
            roof_poly = [
                (bw_px // 2, 4),
                (bw_px - 8, 48),
                (8, 48),
            ]
            pygame.draw.polygon(b_surf, (155, 95, 45), roof_poly)
            pygame.draw.polygon(b_surf, (190, 120, 60), roof_poly, 2)
            # Чердачный люк для подъёма мешков
            loft_rect = pygame.Rect(bw_px // 2 - 18, 16, 36, 26)
            pygame.draw.rect(b_surf, (36, 24, 16), loft_rect, border_radius=2)
            pygame.draw.rect(b_surf, (220, 160, 70), loft_rect, 1, border_radius=2)
            # Балка блока / лебёдки
            pygame.draw.line(b_surf, (110, 80, 50), (bw_px // 2, 4), (bw_px // 2, 16), 3)

            # Ворота входа на тайле 16/40 (локально: правая / восточная стена: X = bw_px - 30, Y = (40 - 35) * 32 = 160)
            door_y = (barn["entrance_tile"][1] - barn["tile_y"]) * self.tile_size
            door_rect = pygame.Rect(bw_px - 30, door_y + 2, 28, 28)
            pygame.draw.rect(b_surf, (28, 20, 14), door_rect, border_radius=3)
            pygame.draw.rect(b_surf, (240, 190, 60), door_rect, 2, border_radius=3)
            door_lbl = self.grid_font.render("ВХОД", True, (255, 220, 90))
            b_surf.blit(door_lbl, door_lbl.get_rect(center=door_rect.center))

            # Фонарь у входа в амбар
            pygame.draw.circle(b_surf, (255, 170, 30), (bw_px - 16, door_y - 6), 5)
            pygame.draw.circle(b_surf, (255, 235, 110), (bw_px - 16, door_y - 6), 2)

            # Мешки с зерном у ворот
            pygame.draw.ellipse(b_surf, (185, 155, 105), (bw_px - 44, door_y + 12, 12, 16))
            pygame.draw.ellipse(b_surf, (165, 135, 90), (bw_px - 48, door_y + 16, 12, 12))

            # Вывеска амбара
            sign_rect = pygame.Rect(bw_px // 2 - 75, bh_px // 2 - 18, 150, 36)
            pygame.draw.rect(b_surf, (25, 20, 15), sign_rect, border_radius=4)
            pygame.draw.rect(b_surf, (215, 175, 75), sign_rect, 2, border_radius=4)
            sign_title = self.small_font.render("🌾 АМБАР ГОРОДА", True, (255, 225, 120))
            sign_sub = self.grid_font.render("[ ХРАНИЛИЩЕ ПРОВИЗИИ ]", True, (210, 190, 150))
            b_surf.blit(sign_title, sign_title.get_rect(center=(sign_rect.centerx, sign_rect.centery - 7)))
            b_surf.blit(sign_sub, sign_sub.get_rect(center=(sign_rect.centerx, sign_rect.centery + 8)))

            # Информационные метки на амбаре
            l1 = self.badge_font.render("[ УРОВЕНЬ 1 • 12х10 ТАЙЛОВ ]", True, (255, 225, 140))
            b_surf.blit(l1, l1.get_rect(center=(bw_px // 2, bh_px - 36)))
            l2 = self.grid_font.render("Вход: [16, 40] (с востока)", True, (215, 205, 190))
            b_surf.blit(l2, l2.get_rect(center=(bw_px // 2, bh_px - 18)))

            screen.blit(b_surf, (bsx, bsy))

            # Подсветка
            if is_b_active:
                pygame.draw.rect(screen, (255, 215, 60), barn_rect, 2, border_radius=8)
            elif is_b_hover:
                pygame.draw.rect(screen, (240, 190, 80), barn_rect.inflate(6, 6), 2, border_radius=8)

            badge_col = (255, 215, 60) if is_b_active else (240, 190, 80) if is_b_hover else (225, 185, 130)
            self._draw_badge(screen, barn_rect.centerx, bsy - 10, "🌾 Городской Амбар [Ур. 1 • 12х10]", badge_col)

        # 5. Городской Склад материалов 12х10 тайлов (X: 5..16, Y: 18..27, вход на 16/23)
        warehouse = self.objects[4]
        wx_px = warehouse["tile_x"] * self.tile_size
        wy_px = warehouse["tile_y"] * self.tile_size
        ww_px = warehouse["tile_w"] * self.tile_size
        wh_px = warehouse["tile_h"] * self.tile_size
        wsx, wsy = self.world_to_screen(wx_px, wy_px)

        if -ww_px <= wsx <= settings.WIDTH + ww_px and -wh_px <= wsy <= settings.HEIGHT + wh_px:
            wh_rect = pygame.Rect(wsx, wsy, ww_px, wh_px)
            is_w_active = self.active_entity and self.active_entity.get("id") == warehouse["id"]
            is_w_hover = self.hovered_entity and self.hovered_entity.get("id") == warehouse["id"]

            # Тень склада
            pygame.draw.ellipse(screen, (14, 16, 20, 190), (wsx + 16, wsy + wh_px - 45, ww_px - 32, 55))

            # Поверхность заглушки склада
            w_surf = pygame.Surface((ww_px, wh_px), pygame.SRCALPHA)

            # Массивное каменное основание склада
            base_rect = pygame.Rect(0, wh_px - 42, ww_px, 42)
            pygame.draw.rect(w_surf, (38, 44, 52, 245), base_rect, border_radius=4)
            pygame.draw.rect(w_surf, (65, 75, 90), base_rect, 2, border_radius=4)

            # Стены склада (крепкий тесаный камень и армированные деревянные балки)
            body_rect = pygame.Rect(0, 36, ww_px, wh_px - 52)
            pygame.draw.rect(w_surf, (52, 58, 68, 245), body_rect, border_radius=4)
            pygame.draw.rect(w_surf, (34, 40, 48), body_rect, 2, border_radius=4)

            # Вертикальные и диагональные металлические стяжки
            for gx_line in range(48, ww_px - 30, 48):
                pygame.draw.line(w_surf, (30, 35, 42), (gx_line, 36), (gx_line, wh_px - 14), 2)
            for gy_line in range(40, wh_px - 42, 36):
                pygame.draw.line(w_surf, (30, 35, 42), (0, gy_line), (ww_px, gy_line), 2)

            # Двускатная крыша с защитным навесом
            roof_poly = [
                (ww_px // 2, 4),
                (ww_px - 8, 46),
                (8, 46),
            ]
            pygame.draw.polygon(w_surf, (70, 80, 95), roof_poly)
            pygame.draw.polygon(w_surf, (100, 115, 135), roof_poly, 2)

            # Лебёдка и балка для перемещения тяжёлых грузов (брёвен и руды)
            loft_rect = pygame.Rect(ww_px // 2 - 20, 14, 40, 26)
            pygame.draw.rect(w_surf, (26, 30, 38), loft_rect, border_radius=2)
            pygame.draw.rect(w_surf, (140, 160, 185), loft_rect, 1, border_radius=2)
            pygame.draw.line(w_surf, (80, 95, 115), (ww_px // 2, 4), (ww_px // 2, 16), 3)

            # Укрепленные железные ворота входа на тайле 16/23 (локально: правая стена)
            door_y = (warehouse["entrance_tile"][1] - warehouse["tile_y"]) * self.tile_size
            door_rect = pygame.Rect(ww_px - 30, door_y + 2, 28, 28)
            pygame.draw.rect(w_surf, (24, 28, 34), door_rect, border_radius=3)
            pygame.draw.rect(w_surf, (255, 215, 80), door_rect, 2, border_radius=3)
            door_lbl = self.grid_font.render("ВХОД", True, (255, 220, 90))
            w_surf.blit(door_lbl, door_lbl.get_rect(center=door_rect.center))

            # Фонарь у ворот склада
            pygame.draw.circle(w_surf, (255, 170, 30), (ww_px - 16, door_y - 6), 5)
            pygame.draw.circle(w_surf, (255, 235, 110), (ww_px - 16, door_y - 6), 2)

            # Декорации у ворот: брёвна, каменный блок и ящик с рудой
            # Штабель брёвен
            pygame.draw.rect(w_surf, (110, 75, 45), (ww_px - 54, door_y + 8, 18, 6), border_radius=2)
            pygame.draw.rect(w_surf, (130, 90, 55), (ww_px - 52, door_y + 15, 16, 6), border_radius=2)
            # Каменный блок
            pygame.draw.rect(w_surf, (140, 145, 155), (ww_px - 48, door_y + 22, 12, 10), border_radius=1)
            pygame.draw.rect(w_surf, (80, 85, 95), (ww_px - 48, door_y + 22, 12, 10), 1, border_radius=1)

            # Вывеска склада
            sign_rect = pygame.Rect(ww_px // 2 - 80, wh_px // 2 - 18, 160, 36)
            pygame.draw.rect(w_surf, (20, 24, 30), sign_rect, border_radius=4)
            pygame.draw.rect(w_surf, (215, 180, 85), sign_rect, 2, border_radius=4)
            sign_title = self.small_font.render("📦 СКЛАД МАТЕРИАЛОВ", True, (255, 225, 120))
            sign_sub = self.grid_font.render("[ РЕСУРСЫ ГОРОДА ]", True, (160, 210, 255))
            w_surf.blit(sign_title, sign_title.get_rect(center=(sign_rect.centerx, sign_rect.centery - 7)))
            w_surf.blit(sign_sub, sign_sub.get_rect(center=(sign_rect.centerx, sign_rect.centery + 8)))

            # Информационные метки на складе
            l1 = self.badge_font.render("[ УРОВЕНЬ 1 • 12х10 ТАЙЛОВ ]", True, (255, 225, 140))
            w_surf.blit(l1, l1.get_rect(center=(ww_px // 2, wh_px - 36)))
            l2 = self.grid_font.render("Вход: [16, 23] (с востока)", True, (200, 215, 230))
            w_surf.blit(l2, l2.get_rect(center=(ww_px // 2, wh_px - 18)))

            screen.blit(w_surf, (wsx, wsy))

            # Подсветка
            if is_w_active:
                pygame.draw.rect(screen, (255, 215, 60), wh_rect, 2, border_radius=8)
            elif is_w_hover:
                pygame.draw.rect(screen, (100, 200, 255), wh_rect.inflate(6, 6), 2, border_radius=8)

            badge_col = (255, 215, 60) if is_w_active else (100, 200, 255) if is_w_hover else (190, 210, 235)
            self._draw_badge(screen, wh_rect.centerx, wsy - 10, "📦 Городской Склад [Ур. 1 • 12х10]", badge_col)

        # 6. Городская Кузница 9х7 тайлов (X: 23..31, Y: 25..31, вход на 23/28)
        forge = self.objects[5]
        fx_px = forge["tile_x"] * self.tile_size
        fy_px = forge["tile_y"] * self.tile_size
        fw_px = forge["tile_w"] * self.tile_size
        fh_px = forge["tile_h"] * self.tile_size
        fsx, fsy = self.world_to_screen(fx_px, fy_px)

        if -fw_px <= fsx <= settings.WIDTH + fw_px and -fh_px <= fsy <= settings.HEIGHT + fh_px:
            f_rect = pygame.Rect(fsx, fsy, fw_px, fh_px)
            is_f_active = self.active_entity and self.active_entity.get("id") == forge["id"]
            is_f_hover = self.hovered_entity and self.hovered_entity.get("id") == forge["id"]

            # Тень кузницы
            pygame.draw.ellipse(screen, (18, 12, 10, 190), (fsx + 12, fsy + fh_px - 38, fw_px - 24, 46))

            # Поверхность заглушки кузницы
            f_surf = pygame.Surface((fw_px, fh_px), pygame.SRCALPHA)

            # Основание и каменные стены (обожженный булыжник)
            body_rect = pygame.Rect(0, 28, fw_px, fh_px - 34)
            pygame.draw.rect(f_surf, (50, 44, 42, 245), body_rect, border_radius=4)
            pygame.draw.rect(f_surf, (80, 50, 40), body_rect, 2, border_radius=4)

            # Двускатная крыша кузницы цвета окалины
            roof_poly = [
                (fw_px // 2, 4),
                (fw_px - 6, 36),
                (6, 36),
            ]
            pygame.draw.polygon(f_surf, (68, 54, 52), roof_poly)
            pygame.draw.polygon(f_surf, (110, 75, 60), roof_poly, 2)

            # Высокая каменная труба горна справа вверху
            chimney_rect = pygame.Rect(fw_px - 44, 2, 26, 36)
            pygame.draw.rect(f_surf, (36, 30, 30), chimney_rect, border_radius=2)
            pygame.draw.rect(f_surf, (140, 70, 40), chimney_rect, 1, border_radius=2)
            # Искры и дым из трубы горна
            pygame.draw.circle(f_surf, (255, 140, 30), (fw_px - 31, 0), 4)
            pygame.draw.circle(f_surf, (255, 220, 80), (fw_px - 29, -4), 2)

            # Окно с пылающим пламенем горна внутри
            furnace_rect = pygame.Rect(fw_px // 2 + 10, fh_px // 2 - 10, 34, 28)
            pygame.draw.rect(f_surf, (255, 90, 20), furnace_rect, border_radius=3)
            pygame.draw.circle(f_surf, (255, 210, 60), furnace_rect.center, 8)

            # Дверь входа на западной стене (тайл 23/28)
            door_y = (forge["entrance_tile"][1] - forge["tile_y"]) * self.tile_size
            door_rect = pygame.Rect(2, door_y + 2, 28, 28)
            pygame.draw.rect(f_surf, (28, 20, 16), door_rect, border_radius=3)
            pygame.draw.rect(f_surf, (255, 160, 50), door_rect, 2, border_radius=3)
            door_lbl = self.grid_font.render("ВХОД", True, (255, 210, 90))
            f_surf.blit(door_lbl, door_lbl.get_rect(center=door_rect.center))

            # Фонарь у входа
            pygame.draw.circle(f_surf, (255, 170, 30), (16, door_y - 6), 5)
            pygame.draw.circle(f_surf, (255, 235, 110), (16, door_y - 6), 2)

            # Наковальня у входа
            anvil_x = 42
            anvil_y = door_y + 8
            pygame.draw.rect(f_surf, (70, 75, 85), (anvil_x, anvil_y, 16, 12), border_radius=2)
            pygame.draw.rect(f_surf, (160, 170, 185), (anvil_x - 3, anvil_y - 2, 22, 5), border_radius=1)

            # Вывеска кузницы
            sign_rect = pygame.Rect(fw_px // 2 - 70, fh_px // 2 - 16, 140, 32)
            pygame.draw.rect(f_surf, (24, 20, 18), sign_rect, border_radius=4)
            pygame.draw.rect(f_surf, (230, 130, 50), sign_rect, 2, border_radius=4)
            sign_lbl = self.small_font.render("⚒️ КУЗНИЦА", True, (255, 210, 110))
            f_surf.blit(sign_lbl, sign_lbl.get_rect(center=sign_rect.center))

            # Текстовые метки
            l1 = self.badge_font.render("[ УРОВЕНЬ 1 • 9х7 ТАЙЛОВ ]", True, (255, 215, 130))
            f_surf.blit(l1, l1.get_rect(center=(fw_px // 2, fh_px - 36)))
            l2 = self.grid_font.render("Вход: [23, 28] (с запада)", True, (220, 200, 180))
            f_surf.blit(l2, l2.get_rect(center=(fw_px // 2, fh_px - 18)))

            screen.blit(f_surf, (fsx, fsy))

            # Подсветка
            if is_f_active:
                pygame.draw.rect(screen, (255, 215, 60), f_rect, 2, border_radius=8)
            elif is_f_hover:
                pygame.draw.rect(screen, (255, 140, 50), f_rect.inflate(6, 6), 2, border_radius=8)

            badge_col = (255, 215, 60) if is_f_active else (255, 140, 50) if is_f_hover else (235, 175, 120)
            self._draw_badge(screen, f_rect.centerx, fsy - 10, "⚒️ Городская Кузница [Ур. 1 • 9х7]", badge_col)

        # 7. Городская Мастерская 9х7 тайлов (X: 23..31, Y: 13..19, вход на 23/16)
        workshop = self.objects[6]
        wk_px = workshop["tile_x"] * self.tile_size
        wk_py = workshop["tile_y"] * self.tile_size
        wk_w_px = workshop["tile_w"] * self.tile_size
        wk_h_px = workshop["tile_h"] * self.tile_size
        wksx, wksy = self.world_to_screen(wk_px, wk_py)

        if -wk_w_px <= wksx <= settings.WIDTH + wk_w_px and -wk_h_px <= wksy <= settings.HEIGHT + wk_h_px:
            wk_rect = pygame.Rect(wksx, wksy, wk_w_px, wk_h_px)
            is_wk_active = self.active_entity and self.active_entity.get("id") == workshop["id"]
            is_wk_hover = self.hovered_entity and self.hovered_entity.get("id") == workshop["id"]

            # Тень мастерской
            pygame.draw.ellipse(screen, (14, 16, 20, 190), (wksx + 12, wksy + wk_h_px - 38, wk_w_px - 24, 46))

            # Поверхность заглушки мастерской
            wk_surf = pygame.Surface((wk_w_px, wk_h_px), pygame.SRCALPHA)

            # Основание и стены (крепкий дуб и армированные стальные балки)
            body_rect = pygame.Rect(0, 28, wk_w_px, wk_h_px - 34)
            pygame.draw.rect(wk_surf, (48, 54, 62, 245), body_rect, border_radius=4)
            pygame.draw.rect(wk_surf, (80, 100, 125), body_rect, 2, border_radius=4)

            # Двускатная крыша мастерской со сланцевой черепицей
            roof_poly = [
                (wk_w_px // 2, 4),
                (wk_w_px - 6, 36),
                (6, 36),
            ]
            pygame.draw.polygon(wk_surf, (55, 68, 80), roof_poly)
            pygame.draw.polygon(wk_surf, (90, 115, 140), roof_poly, 2)

            # Дверь входа на западной стене (тайл 23/16)
            door_y = (workshop["entrance_tile"][1] - workshop["tile_y"]) * self.tile_size
            door_rect = pygame.Rect(2, door_y + 2, 28, 28)
            pygame.draw.rect(wk_surf, (24, 28, 32), door_rect, border_radius=3)
            pygame.draw.rect(wk_surf, (100, 190, 255), door_rect, 2, border_radius=3)
            door_lbl = self.grid_font.render("ВХОД", True, (160, 220, 255))
            wk_surf.blit(door_lbl, door_lbl.get_rect(center=door_rect.center))

            # Фонарь у входа
            pygame.draw.circle(wk_surf, (255, 170, 30), (16, door_y - 6), 5)
            pygame.draw.circle(wk_surf, (255, 235, 110), (16, door_y - 6), 2)

            # Стойка доспехов и щит у фасада
            stand_x = 42
            stand_y = door_y + 4
            pygame.draw.rect(wk_surf, (130, 140, 155), (stand_x, stand_y, 14, 18), border_radius=2)
            pygame.draw.polygon(wk_surf, (180, 195, 215), [(stand_x + 7, stand_y), (stand_x + 14, stand_y + 6), (stand_x + 7, stand_y + 18), (stand_x, stand_y + 6)])

            # Вывеска мастерской
            sign_rect = pygame.Rect(wk_w_px // 2 - 75, wk_h_px // 2 - 16, 150, 32)
            pygame.draw.rect(wk_surf, (20, 25, 32), sign_rect, border_radius=4)
            pygame.draw.rect(wk_surf, (100, 180, 240), sign_rect, 2, border_radius=4)
            sign_lbl = self.small_font.render("🛡️ МАСТЕРСКАЯ", True, (160, 220, 255))
            wk_surf.blit(sign_lbl, sign_lbl.get_rect(center=sign_rect.center))

            # Текстовые метки
            l1 = self.badge_font.render("[ УРОВЕНЬ 1 • 9х7 ТАЙЛОВ ]", True, (180, 225, 255))
            wk_surf.blit(l1, l1.get_rect(center=(wk_w_px // 2, wk_h_px - 36)))
            l2 = self.grid_font.render("Вход: [23, 16] (с запада)", True, (200, 215, 230))
            wk_surf.blit(l2, l2.get_rect(center=(wk_w_px // 2, wk_h_px - 18)))

            screen.blit(wk_surf, (wksx, wksy))

            # Подсветка
            if is_wk_active:
                pygame.draw.rect(screen, (255, 215, 60), wk_rect, 2, border_radius=8)
            elif is_wk_hover:
                pygame.draw.rect(screen, (100, 200, 255), wk_rect.inflate(6, 6), 2, border_radius=8)

            badge_col = (255, 215, 60) if is_wk_active else (100, 200, 255) if is_wk_hover else (180, 215, 245)
            self._draw_badge(screen, wk_rect.centerx, wksy - 10, "🛡️ Городская Мастерская [Ур. 1 • 9х7]", badge_col)

        # 8. Городские Казармы 29х13 тайлов (X: 60..88, Y: 31..43, вход на 84/43)
        barracks = self.objects[7]
        bk_px = barracks["tile_x"] * self.tile_size
        bk_py = barracks["tile_y"] * self.tile_size
        bk_w_px = barracks["tile_w"] * self.tile_size
        bk_h_px = barracks["tile_h"] * self.tile_size
        bksx, bksy = self.world_to_screen(bk_px, bk_py)

        if -bk_w_px <= bksx <= settings.WIDTH + bk_w_px and -bk_h_px <= bksy <= settings.HEIGHT + bk_h_px:
            bk_rect = pygame.Rect(bksx, bksy, bk_w_px, bk_h_px)
            is_bk_active = self.active_entity and self.active_entity.get("id") == barracks["id"]
            is_bk_hover = self.hovered_entity and self.hovered_entity.get("id") == barracks["id"]

            # Тень казарм
            pygame.draw.ellipse(screen, (12, 14, 18, 200), (bksx + 20, bksy + bk_h_px - 45, bk_w_px - 40, 55))

            # Поверхность заглушки казарм
            bk_surf = pygame.Surface((bk_w_px, bk_h_px), pygame.SRCALPHA)

            # Массивное каменное основание (укрепленный плац и цоколь)
            base_rect = pygame.Rect(0, bk_h_px - 45, bk_w_px, 45)
            pygame.draw.rect(bk_surf, (42, 48, 56, 245), base_rect, border_radius=4)
            pygame.draw.rect(bk_surf, (75, 85, 100), base_rect, 2, border_radius=4)

            # Стены казарм (военный гарнизонный кирпич и камень)
            body_rect = pygame.Rect(0, 36, bk_w_px, bk_h_px - 55)
            pygame.draw.rect(bk_surf, (55, 62, 72, 245), body_rect, border_radius=4)
            pygame.draw.rect(bk_surf, (35, 40, 48), body_rect, 2, border_radius=4)

            # Башни по краям казарм (северо-западная и северо-восточная)
            for bx_pos in [0, bk_w_px - 48]:
                t_rect = pygame.Rect(bx_pos, 16, 48, 40)
                pygame.draw.rect(bk_surf, (40, 45, 54), t_rect, border_radius=3)
                pygame.draw.rect(bk_surf, (90, 105, 125), t_rect, 2, border_radius=3)
                # Флагшток и синее знамя Радбурга
                pygame.draw.line(bk_surf, (160, 170, 185), (bx_pos + 24, 16), (bx_pos + 24, 2), 2)
                pygame.draw.polygon(bk_surf, (60, 140, 220), [(bx_pos + 24, 2), (bx_pos + 40, 7), (bx_pos + 24, 12)])

            # Черепичная двускатная военная крыша казарменных корпусов
            roof_poly = [
                (bk_w_px // 2, 4),
                (bk_w_px - 10, 42),
                (10, 42),
            ]
            pygame.draw.polygon(bk_surf, (80, 92, 108), roof_poly)
            pygame.draw.polygon(bk_surf, (115, 130, 150), roof_poly, 2)

            # Ряд окон жилых отсеков солдат по фасаду
            for wx in range(40, bk_w_px - 40, 48):
                w_rect = pygame.Rect(wx, 54, 20, 26)
                pygame.draw.rect(bk_surf, (255, 215, 110), w_rect, border_radius=2)
                pygame.draw.rect(bk_surf, (30, 35, 45), w_rect, 2, border_radius=2)

            # Южные парадные ворота в казармы (тайл 84/43)
            # Локальные координаты: X = (84 - 80) * 32 = 128 px, Y = (43 - 31) * 32 = 384 px
            door_x = (barracks["entrance_tile"][0] - barracks["tile_x"]) * self.tile_size
            door_y = (barracks["entrance_tile"][1] - barracks["tile_y"]) * self.tile_size
            door_rect = pygame.Rect(door_x + 2, door_y + 2, 28, 28)
            pygame.draw.rect(bk_surf, (25, 28, 35), door_rect, border_radius=4)
            pygame.draw.rect(bk_surf, (255, 215, 80), door_rect, 2, border_radius=4)
            door_lbl = self.grid_font.render("ВХОД", True, (255, 220, 100))
            bk_surf.blit(door_lbl, door_lbl.get_rect(center=door_rect.center))

            # Факелы у ворот казарм
            pygame.draw.circle(bk_surf, (255, 170, 30), (door_x - 8, door_y + 14), 5)
            pygame.draw.circle(bk_surf, (255, 235, 110), (door_x - 8, door_y + 14), 2)
            pygame.draw.circle(bk_surf, (255, 170, 30), (door_x + 36, door_y + 14), 5)
            pygame.draw.circle(bk_surf, (255, 235, 110), (door_x + 36, door_y + 14), 2)

            # Вывеска казарм
            sign_rect = pygame.Rect(bk_w_px // 2 - 90, bk_h_px // 2 - 18, 180, 36)
            pygame.draw.rect(bk_surf, (22, 26, 34), sign_rect, border_radius=4)
            pygame.draw.rect(bk_surf, (220, 180, 80), sign_rect, 2, border_radius=4)
            sign_title = self.small_font.render("⚔️ КАЗАРМЫ", True, (255, 220, 110))
            sign_sub = self.grid_font.render("[ ГАРНИЗОН ГОРОДА ]", True, (160, 210, 255))
            bk_surf.blit(sign_title, sign_title.get_rect(center=(sign_rect.centerx, sign_rect.centery - 7)))
            bk_surf.blit(sign_sub, sign_sub.get_rect(center=(sign_rect.centerx, sign_rect.centery + 8)))

            # Информационные метки на казармах
            l1 = self.badge_font.render("[ УРОВЕНЬ 1 • 9х13 ТАЙЛОВ ]", True, (255, 225, 140))
            bk_surf.blit(l1, l1.get_rect(center=(bk_w_px // 2, bk_h_px - 36)))
            l2 = self.grid_font.render("Вход: [84, 43] (с южной стороны)", True, (200, 215, 230))
            bk_surf.blit(l2, l2.get_rect(center=(bk_w_px // 2, bk_h_px - 18)))

            screen.blit(bk_surf, (bksx, bksy))

            # Подсветка
            if is_bk_active:
                pygame.draw.rect(screen, (255, 215, 60), bk_rect, 2, border_radius=8)
            elif is_bk_hover:
                pygame.draw.rect(screen, (100, 200, 255), bk_rect.inflate(6, 6), 2, border_radius=8)

            badge_col = (255, 215, 60) if is_bk_active else (100, 200, 255) if is_bk_hover else (180, 215, 245)
            self._draw_badge(screen, bk_rect.centerx, bksy - 10, "⚔️ Городские Казармы [Ур. 1 • 9х13]", badge_col)

        # 9. Инженерная палата 10х8 тайлов (X: 35..44, Y: 12..19, вход на 44/15)
        eng = self.objects[8]
        ex_px = eng["tile_x"] * self.tile_size
        ey_px = eng["tile_y"] * self.tile_size
        ew_px = eng["tile_w"] * self.tile_size
        eh_px = eng["tile_h"] * self.tile_size
        esx, esy = self.world_to_screen(ex_px, ey_px)

        if -ew_px <= esx <= settings.WIDTH + ew_px and -eh_px <= esy <= settings.HEIGHT + eh_px:
            eng_rect = pygame.Rect(esx, esy, ew_px, eh_px)
            is_e_active = self.active_entity and self.active_entity.get("id") == eng["id"]
            is_e_hover = self.hovered_entity and self.hovered_entity.get("id") == eng["id"]

            # Тень инженерной палаты
            pygame.draw.ellipse(screen, (14, 18, 16, 190), (esx + 12, esy + eh_px - 40, ew_px - 24, 48))

            # Поверхность заглушки инженерной палаты
            e_surf = pygame.Surface((ew_px, eh_px), pygame.SRCALPHA)

            # Массивное каменное основание (укрепленный конструкторский цех)
            base_rect = pygame.Rect(0, eh_px - 40, ew_px, 40)
            pygame.draw.rect(e_surf, (40, 46, 48, 245), base_rect, border_radius=4)
            pygame.draw.rect(e_surf, (70, 95, 95), base_rect, 2, border_radius=4)

            # Стены цеха (тяжелый брус и кладка)
            body_rect = pygame.Rect(0, 32, ew_px, eh_px - 46)
            pygame.draw.rect(e_surf, (48, 56, 58, 245), body_rect, border_radius=4)
            pygame.draw.rect(e_surf, (60, 80, 85), body_rect, 2, border_radius=4)

            # Двускатная крыша с технологическим окном
            roof_poly = [
                (ew_px // 2, 4),
                (ew_px - 8, 38),
                (8, 38),
            ]
            pygame.draw.polygon(e_surf, (65, 76, 80), roof_poly)
            pygame.draw.polygon(e_surf, (110, 135, 140), roof_poly, 2)

            # Чертежный световой фонарь на крыше
            light_rect = pygame.Rect(ew_px // 2 - 24, 12, 48, 20)
            pygame.draw.rect(e_surf, (120, 200, 220), light_rect, border_radius=2)
            pygame.draw.rect(e_surf, (40, 60, 65), light_rect, 1, border_radius=2)

            # Дверь входа на восточной стене (тайл 44/15)
            # Локальные координаты: X = ew_px - 30, Y = (15 - 12) * 32 = 96 px
            door_y = (eng["entrance_tile"][1] - eng["tile_y"]) * self.tile_size
            door_rect = pygame.Rect(ew_px - 30, door_y + 2, 28, 28)
            pygame.draw.rect(e_surf, (22, 28, 30), door_rect, border_radius=3)
            pygame.draw.rect(e_surf, (120, 220, 200), door_rect, 2, border_radius=3)
            door_lbl = self.grid_font.render("ВХОД", True, (160, 240, 220))
            e_surf.blit(door_lbl, door_lbl.get_rect(center=door_rect.center))

            # Фонарь у входа
            pygame.draw.circle(e_surf, (255, 170, 30), (ew_px - 16, door_y - 6), 5)
            pygame.draw.circle(e_surf, (255, 235, 110), (ew_px - 16, door_y - 6), 2)

            # Осадные колеса и рычаги катапульты у фасада здания
            wheel_x = ew_px - 48
            wheel_y = door_y + 8
            pygame.draw.circle(e_surf, (90, 65, 40), (wheel_x, wheel_y), 10, 2)
            pygame.draw.circle(e_surf, (50, 40, 30), (wheel_x, wheel_y), 3)
            pygame.draw.line(e_surf, (110, 80, 50), (wheel_x - 14, wheel_y - 12), (wheel_x + 8, wheel_y + 8), 3)

            # Шестерня и механизм над вывеской
            gear_cx = ew_px // 2
            gear_cy = 44
            pygame.draw.circle(e_surf, (150, 170, 180), (gear_cx, gear_cy), 10, 2)
            pygame.draw.circle(e_surf, (200, 220, 230), (gear_cx, gear_cy), 4)

            # Вывеска инженерной палаты
            sign_rect = pygame.Rect(ew_px // 2 - 95, eh_px // 2 - 14, 190, 34)
            pygame.draw.rect(e_surf, (20, 26, 28), sign_rect, border_radius=4)
            pygame.draw.rect(e_surf, (100, 200, 190), sign_rect, 2, border_radius=4)
            sign_title = self.small_font.render("⚙️ ИНЖЕНЕРНАЯ ПАЛАТА", True, (180, 240, 230))
            sign_sub = self.grid_font.render("[ ОСАДНЫЕ МАШИНЫ И ОБОРОНА ]", True, (140, 200, 210))
            e_surf.blit(sign_title, sign_title.get_rect(center=(sign_rect.centerx, sign_rect.centery - 7)))
            e_surf.blit(sign_sub, sign_sub.get_rect(center=(sign_rect.centerx, sign_rect.centery + 8)))

            # Информационные метки на здании
            l1 = self.badge_font.render("[ УРОВЕНЬ 1 • 10х8 ТАЙЛОВ ]", True, (170, 235, 220))
            e_surf.blit(l1, l1.get_rect(center=(ew_px // 2, eh_px - 34)))
            l2 = self.grid_font.render("Вход: [44, 15] (с восточной стороны)", True, (190, 215, 215))
            e_surf.blit(l2, l2.get_rect(center=(ew_px // 2, eh_px - 16)))

            screen.blit(e_surf, (esx, esy))

            # Подсветка
            if is_e_active:
                pygame.draw.rect(screen, (255, 215, 60), eng_rect, 2, border_radius=8)
            elif is_e_hover:
                pygame.draw.rect(screen, (100, 220, 200), eng_rect.inflate(6, 6), 2, border_radius=8)

            badge_col = (255, 215, 60) if is_e_active else (100, 220, 200) if is_e_hover else (160, 215, 205)
            self._draw_badge(screen, eng_rect.centerx, esy - 10, "⚙️ Инженерная палата [Ур. 1 • 10х8]", badge_col)

        # 10. Городской Университет 15х11 тайлов (X: 16..30, Y: 84..94, вход на 23/84)
        univ = self.objects[9]
        ux_px = univ["tile_x"] * self.tile_size
        uy_px = univ["tile_y"] * self.tile_size
        uw_px = univ["tile_w"] * self.tile_size
        uh_px = univ["tile_h"] * self.tile_size
        usx, usy = self.world_to_screen(ux_px, uy_px)

        if -uw_px <= usx <= settings.WIDTH + uw_px and -uh_px <= usy <= settings.HEIGHT + uh_px:
            univ_rect = pygame.Rect(usx, usy, uw_px, uh_px)
            is_u_active = self.active_entity and self.active_entity.get("id") == univ["id"]
            is_u_hover = self.hovered_entity and self.hovered_entity.get("id") == univ["id"]

            # Тень университета
            pygame.draw.ellipse(screen, (12, 14, 20, 200), (usx + 18, usy + uh_px - 45, uw_px - 36, 55))

            # Поверхность заглушки университета
            u_surf = pygame.Surface((uw_px, uh_px), pygame.SRCALPHA)

            # Основание и стены (благородный белый и серый мрамор)
            body_rect = pygame.Rect(0, 36, uw_px, uh_px - 48)
            pygame.draw.rect(u_surf, (50, 58, 70, 245), body_rect, border_radius=6)
            pygame.draw.rect(u_surf, (110, 140, 180), body_rect, 2, border_radius=6)

            # Античные колонны по фасаду университета
            for col_x in range(32, uw_px - 32, 40):
                pygame.draw.rect(u_surf, (180, 195, 215), (col_x, 40, 12, uh_px - 56), border_radius=2)
                pygame.draw.rect(u_surf, (220, 230, 245), (col_x - 2, 38, 16, 4))
                pygame.draw.rect(u_surf, (220, 230, 245), (col_x - 2, uh_px - 18, 16, 4))

            # Классический треугольный фронтон / портик над центральным входом
            pediment_poly = [
                (uw_px // 2, 6),
                (uw_px // 2 + 100, 38),
                (uw_px // 2 - 100, 38),
            ]
            pygame.draw.polygon(u_surf, (65, 78, 96), pediment_poly)
            pygame.draw.polygon(u_surf, (180, 210, 240), pediment_poly, 2)

            # Символ раскрытой книги и свитка в тимпане фронтона
            pygame.draw.circle(u_surf, (255, 215, 80), (uw_px // 2, 24), 8, 2)
            pygame.draw.circle(u_surf, (255, 235, 140), (uw_px // 2, 24), 3)

            # Крылья здания с черепичной крышей
            roof_left = [(0, 38), (uw_px // 2 - 100, 38), (uw_px // 2 - 100, 28), (0, 28)]
            roof_right = [(uw_px // 2 + 100, 38), (uw_px, 38), (uw_px, 28), (uw_px // 2 + 100, 28)]
            pygame.draw.polygon(u_surf, (55, 66, 82), roof_left)
            pygame.draw.polygon(u_surf, (55, 66, 82), roof_right)

            # Двери входа на северной стене (тайл 23/84)
            # Локальные координаты: X = (23 - 16) * 32 = 224 px, Y = 0..32 px (северный фасад)
            door_x = (univ["entrance_tile"][0] - univ["tile_x"]) * self.tile_size
            door_y = (univ["entrance_tile"][1] - univ["tile_y"]) * self.tile_size
            door_rect = pygame.Rect(door_x + 2, door_y + 6, 28, 30)
            pygame.draw.rect(u_surf, (20, 26, 36), door_rect, border_radius=4)
            pygame.draw.rect(u_surf, (255, 215, 80), door_rect, 2, border_radius=4)
            door_lbl = self.grid_font.render("ВХОД", True, (255, 220, 100))
            u_surf.blit(door_lbl, door_lbl.get_rect(center=door_rect.center))

            # Теплые факелы/фонари у входа
            pygame.draw.circle(u_surf, (255, 170, 30), (door_x - 8, door_y + 18), 5)
            pygame.draw.circle(u_surf, (255, 235, 110), (door_x - 8, door_y + 18), 2)
            pygame.draw.circle(u_surf, (255, 170, 30), (door_x + 36, door_y + 18), 5)
            pygame.draw.circle(u_surf, (255, 235, 110), (door_x + 36, door_y + 18), 2)

            # Вывеска университета
            sign_rect = pygame.Rect(uw_px // 2 - 105, uh_px // 2 - 18, 210, 36)
            pygame.draw.rect(u_surf, (18, 24, 34), sign_rect, border_radius=4)
            pygame.draw.rect(u_surf, (120, 190, 255), sign_rect, 2, border_radius=4)
            sign_title = self.small_font.render("🏛️ УНИВЕРСИТЕТ", True, (255, 225, 120))
            sign_sub = self.grid_font.render("[ АКАДЕМИЯ ТЕХНОЛОГИЙ И НАУК ]", True, (160, 215, 255))
            u_surf.blit(sign_title, sign_title.get_rect(center=(sign_rect.centerx, sign_rect.centery - 7)))
            u_surf.blit(sign_sub, sign_sub.get_rect(center=(sign_rect.centerx, sign_rect.centery + 8)))

            # Информационные метки на здании
            l1 = self.badge_font.render("[ УРОВЕНЬ 1 • 15х11 ТАЙЛОВ ]", True, (180, 225, 255))
            u_surf.blit(l1, l1.get_rect(center=(uw_px // 2, uh_px - 34)))
            l2 = self.grid_font.render("Вход: [23, 84] (с северной стороны)", True, (200, 215, 235))
            u_surf.blit(l2, l2.get_rect(center=(uw_px // 2, uh_px - 16)))

            screen.blit(u_surf, (usx, usy))

            # Подсветка
            if is_u_active:
                pygame.draw.rect(screen, (255, 215, 60), univ_rect, 2, border_radius=8)
            elif is_u_hover:
                pygame.draw.rect(screen, (120, 200, 255), univ_rect.inflate(6, 6), 2, border_radius=8)

            badge_col = (255, 215, 60) if is_u_active else (120, 200, 255) if is_u_hover else (180, 215, 245)
            self._draw_badge(screen, univ_rect.centerx, usy - 10, "🏛️ Университет [Ур. 1 • 15х11]", badge_col)

        # 11. Военная академия 10х7 тайлов (X: 10..19, Y: 70..76, вход на 19/73)
        academy = self.objects[10]
        ax_px = academy["tile_x"] * self.tile_size
        ay_px = academy["tile_y"] * self.tile_size
        aw_px = academy["tile_w"] * self.tile_size
        ah_px = academy["tile_h"] * self.tile_size
        asx, asy = self.world_to_screen(ax_px, ay_px)

        if -aw_px <= asx <= settings.WIDTH + aw_px and -ah_px <= asy <= settings.HEIGHT + ah_px:
            acad_rect = pygame.Rect(asx, asy, aw_px, ah_px)
            is_a_active = self.active_entity and self.active_entity.get("id") == academy["id"]
            is_a_hover = self.hovered_entity and self.hovered_entity.get("id") == academy["id"]

            # Тень военной академии
            pygame.draw.ellipse(screen, (16, 12, 14, 190), (asx + 12, asy + ah_px - 38, aw_px - 24, 46))

            # Поверхность заглушки военной академии
            a_surf = pygame.Surface((aw_px, ah_px), pygame.SRCALPHA)

            # Основание и стены (мощный тёмный гранит и дубовые балки)
            body_rect = pygame.Rect(0, 28, aw_px, ah_px - 34)
            pygame.draw.rect(a_surf, (52, 44, 48, 245), body_rect, border_radius=4)
            pygame.draw.rect(a_surf, (140, 70, 70), body_rect, 2, border_radius=4)

            # Двускатная крыша с геральдическим гребнем
            roof_poly = [
                (aw_px // 2, 4),
                (aw_px - 6, 36),
                (6, 36),
            ]
            pygame.draw.polygon(a_surf, (88, 50, 50), roof_poly)
            pygame.draw.polygon(a_surf, (150, 80, 80), roof_poly, 2)

            # Геральдический герб воинов (скрещенные мечи и золотой щит)
            shield_cx = aw_px // 2
            shield_cy = 22
            pygame.draw.polygon(a_surf, (220, 180, 60), [
                (shield_cx, shield_cy - 10),
                (shield_cx + 10, shield_cy - 4),
                (shield_cx + 6, shield_cy + 8),
                (shield_cx, shield_cy + 12),
                (shield_cx - 6, shield_cy + 8),
                (shield_cx - 10, shield_cy - 4),
            ])
            pygame.draw.line(a_surf, (240, 240, 250), (shield_cx - 14, shield_cy - 8), (shield_cx + 14, shield_cy + 10), 2)
            pygame.draw.line(a_surf, (240, 240, 250), (shield_cx + 14, shield_cy - 8), (shield_cx - 14, shield_cy + 10), 2)

            # Дверь входа на восточной стене (тайл 19/73)
            # Локальные координаты: X = aw_px - 30, Y = (73 - 70) * 32 = 96 px
            door_y = (academy["entrance_tile"][1] - academy["tile_y"]) * self.tile_size
            door_rect = pygame.Rect(aw_px - 30, door_y + 2, 28, 28)
            pygame.draw.rect(a_surf, (28, 18, 20), door_rect, border_radius=3)
            pygame.draw.rect(a_surf, (255, 140, 60), door_rect, 2, border_radius=3)
            door_lbl = self.grid_font.render("ВХОД", True, (255, 200, 100))
            a_surf.blit(door_lbl, door_lbl.get_rect(center=door_rect.center))

            # Факелы у входа
            pygame.draw.circle(a_surf, (255, 150, 30), (aw_px - 16, door_y - 6), 5)
            pygame.draw.circle(a_surf, (255, 220, 100), (aw_px - 16, door_y - 6), 2)

            # Тренировочные манекены и стойка с оружием у фасада
            man_x = aw_px - 56
            man_y = door_y + 6
            pygame.draw.rect(a_surf, (160, 120, 80), (man_x, man_y, 10, 16), border_radius=2)
            pygame.draw.circle(a_surf, (190, 150, 100), (man_x + 5, man_y - 4), 5)
            pygame.draw.line(a_surf, (120, 90, 60), (man_x - 4, man_y + 4), (man_x + 14, man_y + 4), 3)

            # Вывеска академии
            sign_rect = pygame.Rect(aw_px // 2 - 85, ah_px // 2 - 16, 170, 32)
            pygame.draw.rect(a_surf, (26, 18, 20), sign_rect, border_radius=4)
            pygame.draw.rect(a_surf, (220, 110, 80), sign_rect, 2, border_radius=4)
            sign_title = self.small_font.render("⚔️ ВОЕННАЯ АКАДЕМИЯ", True, (255, 200, 130))
            a_surf.blit(sign_title, sign_title.get_rect(center=sign_rect.center))

            # Текстовые метки
            l1 = self.badge_font.render("[ УРОВЕНЬ 1 • 10х7 ТАЙЛОВ ]", True, (255, 200, 160))
            a_surf.blit(l1, l1.get_rect(center=(aw_px // 2, ah_px - 36)))
            l2 = self.grid_font.render("Вход: [19, 73] (с востока)", True, (230, 205, 195))
            a_surf.blit(l2, l2.get_rect(center=(aw_px // 2, ah_px - 18)))

            screen.blit(a_surf, (asx, asy))

            # Подсветка
            if is_a_active:
                pygame.draw.rect(screen, (255, 215, 60), acad_rect, 2, border_radius=8)
            elif is_a_hover:
                pygame.draw.rect(screen, (255, 120, 90), acad_rect.inflate(6, 6), 2, border_radius=8)

            badge_col = (255, 215, 60) if is_a_active else (255, 120, 90) if is_a_hover else (230, 170, 150)
            self._draw_badge(screen, acad_rect.centerx, asy - 10, "⚔️ Военная академия [Ур. 1 • 10х7]", badge_col)

        # 12. Школа стихий 15х9 тайлов (X: 30..44, Y: 62..70, вход на 44/66)
        mage_school = self.objects[11]
        msx_px = mage_school["tile_x"] * self.tile_size
        msy_px = mage_school["tile_y"] * self.tile_size
        msw_px = mage_school["tile_w"] * self.tile_size
        msh_px = mage_school["tile_h"] * self.tile_size
        mssx, mssy = self.world_to_screen(msx_px, msy_px)

        if -msw_px <= mssx <= settings.WIDTH + msw_px and -msh_px <= mssy <= settings.HEIGHT + msh_px:
            school_rect = pygame.Rect(mssx, mssy, msw_px, msh_px)
            is_m_active = self.active_entity and self.active_entity.get("id") == mage_school["id"]
            is_m_hover = self.hovered_entity and self.hovered_entity.get("id") == mage_school["id"]

            # Магическая мерцающая тень святилища стихий
            pygame.draw.ellipse(screen, (15, 10, 25, 200), (mssx + 16, mssy + msh_px - 44, msw_px - 32, 54))

            # Поверхность заглушки Школы стихий
            m_surf = pygame.Surface((msw_px, msh_px), pygame.SRCALPHA)

            # Основание и стены (мистический обсидиан и фиолетово-синий мрамор)
            body_rect = pygame.Rect(0, 32, msw_px, msh_px - 42)
            pygame.draw.rect(m_surf, (36, 30, 56, 245), body_rect, border_radius=6)
            pygame.draw.rect(m_surf, (150, 90, 220), body_rect, 2, border_radius=6)

            # Башни и мистические шпили по углам
            # Левая башня
            pygame.draw.rect(m_surf, (45, 38, 70), (4, 16, 28, msh_px - 26), border_radius=3)
            pygame.draw.polygon(m_surf, (110, 60, 180), [(18, 2), (32, 16), (4, 16)])
            # Центральный купол с магическим шпилем
            dome_poly = [
                (msw_px // 2, 4),
                (msw_px // 2 + 50, 32),
                (msw_px // 2 - 50, 32),
            ]
            pygame.draw.polygon(m_surf, (75, 45, 125), dome_poly)
            pygame.draw.polygon(m_surf, (180, 110, 255), dome_poly, 2)

            # Сферы 5 стихий над куполом (Огонь, Вода, Воздух, Земля, Свет)
            elem_colors = [
                (255, 90, 40),   # Огонь (красно-оранжевый)
                (50, 160, 255),  # Вода (синий)
                (140, 240, 255), # Воздух (голубой)
                (90, 200, 70),   # Земля (зеленый)
                (255, 240, 140), # Свет (золотой)
            ]
            for i, ecol in enumerate(elem_colors):
                ex = msw_px // 2 - 40 + i * 20
                ey = 24 + int(4 * math.sin(self.player_anim_timer * 3.0 + i))
                pygame.draw.circle(m_surf, ecol, (ex, ey), 5)
                pygame.draw.circle(m_surf, (255, 255, 255), (ex, ey), 2)

            # Дверь входа на восточной стене (тайл 44/66)
            # Локальные координаты: X = msw_px - 30, Y = (66 - 62) * 32 = 128 px
            door_y = (mage_school["entrance_tile"][1] - mage_school["tile_y"]) * self.tile_size
            door_rect = pygame.Rect(msw_px - 30, door_y + 2, 28, 28)
            pygame.draw.rect(m_surf, (22, 16, 38), door_rect, border_radius=3)
            pygame.draw.rect(m_surf, (180, 110, 255), door_rect, 2, border_radius=3)
            door_lbl = self.grid_font.render("ВХОД", True, (220, 170, 255))
            m_surf.blit(door_lbl, door_lbl.get_rect(center=door_rect.center))

            # Магические кристаллы-фонари по бокам от входа
            c_glow = int(180 + 75 * math.sin(self.player_anim_timer * 4.0))
            pygame.draw.circle(m_surf, (180, 100, c_glow), (msw_px - 16, door_y - 6), 5)
            pygame.draw.circle(m_surf, (240, 220, 255), (msw_px - 16, door_y - 6), 2)
            pygame.draw.circle(m_surf, (180, 100, c_glow), (msw_px - 16, door_y + 34), 5)
            pygame.draw.circle(m_surf, (240, 220, 255), (msw_px - 16, door_y + 34), 2)

            # Рунические арки и витражные окна
            for win_x in range(48, msw_px - 60, 48):
                w_rect = pygame.Rect(win_x, 48, 18, 30)
                pygame.draw.rect(m_surf, (20, 16, 34), w_rect, border_radius=8)
                pygame.draw.rect(m_surf, (140, 100, 220), w_rect, 1, border_radius=8)
                pygame.draw.circle(m_surf, (160, 210, 255), (win_x + 9, 63), 4)

            # Вывеска школы стихий
            sign_rect = pygame.Rect(msw_px // 2 - 95, msh_px // 2 - 16, 190, 32)
            pygame.draw.rect(m_surf, (22, 16, 34), sign_rect, border_radius=4)
            pygame.draw.rect(m_surf, (180, 110, 255), sign_rect, 2, border_radius=4)
            sign_title = self.small_font.render("🔮 ШКОЛА СТИХИЙ", True, (230, 180, 255))
            m_surf.blit(sign_title, sign_title.get_rect(center=sign_rect.center))

            # Текстовые метки
            l1 = self.badge_font.render("[ УРОВЕНЬ 1 • 15х9 ТАЙЛОВ ]", True, (210, 175, 255))
            m_surf.blit(l1, l1.get_rect(center=(msw_px // 2, msh_px - 34)))
            l2 = self.grid_font.render("Вход: [44, 66] (с востока)", True, (215, 195, 245))
            m_surf.blit(l2, l2.get_rect(center=(msw_px // 2, msh_px - 16)))

            screen.blit(m_surf, (mssx, mssy))

            # Подсветка
            if is_m_active:
                pygame.draw.rect(screen, (255, 215, 60), school_rect, 2, border_radius=8)
            elif is_m_hover:
                pygame.draw.rect(screen, (180, 110, 255), school_rect.inflate(6, 6), 2, border_radius=8)

            badge_col = (255, 215, 60) if is_m_active else (180, 110, 255) if is_m_hover else (205, 165, 240)
            self._draw_badge(screen, school_rect.centerx, mssy - 10, "🔮 Школа стихий [Ур. 1 • 15х9]", badge_col)

        self._draw_stable(screen)

    def _draw_stable(self, screen):
        """Конюшня 17х6: несколько деревянных сараев со стойлами, лошадьми и сеновалом."""
        stable = next((obj for obj in self.objects if obj.get("id") == "stable_building"), None)
        if stable is None:
            return
        sx_world = stable["tile_x"] * self.tile_size
        sy_world = stable["tile_y"] * self.tile_size
        width = stable["tile_w"] * self.tile_size
        height = stable["tile_h"] * self.tile_size
        sx, sy = self.world_to_screen(sx_world, sy_world)
        if not (-width <= sx <= settings.WIDTH + width and -height <= sy <= settings.HEIGHT + height):
            return

        rect = pygame.Rect(sx, sy, width, height)
        is_active = self.active_entity and self.active_entity.get("id") == stable["id"]
        is_hovered = self.hovered_entity and self.hovered_entity.get("id") == stable["id"]
        pygame.draw.ellipse(screen, (14, 18, 14, 180), (sx + 12, sy + height - 20, width - 24, 30))
        pygame.draw.rect(screen, (116, 91, 58), rect)

        shed_width = 160
        gap = 12
        shed_y = sy + 34
        shed_height = height - 48
        shed_count = 3
        total_width = shed_count * shed_width + (shed_count - 1) * gap
        start_x = rect.centerx - total_width // 2
        for index in range(shed_count):
            left = start_x + index * (shed_width + gap)
            shed = pygame.Rect(left, shed_y, shed_width, shed_height)
            pygame.draw.rect(screen, (115, 75, 42), shed)
            pygame.draw.rect(screen, (66, 48, 32), shed, 3)
            roof = [(left - 8, shed_y + 5), (left + shed_width // 2, sy + 4),
                    (left + shed_width + 8, shed_y + 5)]
            pygame.draw.polygon(screen, (91, 53, 38), roof)
            pygame.draw.lines(screen, (54, 39, 30), True, roof, 3)

            stall_width = shed_width // 2
            for stall in range(2):
                stall_rect = pygame.Rect(left + stall * stall_width + 7, shed_y + 20,
                                         stall_width - 14, shed_height - 27)
                pygame.draw.rect(screen, (79, 57, 39), stall_rect)
                pygame.draw.rect(screen, (157, 119, 75), stall_rect, 2)
                for rail_y in range(stall_rect.top + 12, stall_rect.bottom - 4, 13):
                    pygame.draw.line(screen, (171, 131, 80), (stall_rect.left, rail_y),
                                     (stall_rect.right, rail_y), 2)
                horse_x = stall_rect.centerx
                horse_y = stall_rect.centery + 4
                coat = ((119, 68, 43), (83, 58, 44), (155, 122, 79))[index]
                pygame.draw.ellipse(screen, coat, (horse_x - 23, horse_y - 11, 38, 21))
                pygame.draw.ellipse(screen, coat, (horse_x + 7, horse_y - 18, 17, 18))
                pygame.draw.polygon(screen, (54, 39, 30), [(horse_x + 11, horse_y - 17),
                                  (horse_x + 13, horse_y - 27), (horse_x + 17, horse_y - 17)])
                pygame.draw.circle(screen, (235, 220, 180), (horse_x + 18, horse_y - 11), 2)
                for leg_x in (horse_x - 17, horse_x - 4, horse_x + 5, horse_x + 13):
                    pygame.draw.line(screen, (48, 36, 27), (leg_x, horse_y + 7),
                                     (leg_x - 2, horse_y + 20), 3)

        hay_x = rect.right - 58
        hay_y = rect.top + 12
        for bale in range(3):
            bale_rect = pygame.Rect(hay_x - bale * 13, hay_y + bale * 4, 42, 19)
            pygame.draw.rect(screen, (204, 170, 91), bale_rect, border_radius=4)
            pygame.draw.rect(screen, (126, 94, 49), bale_rect, 2, border_radius=4)
            pygame.draw.line(screen, (231, 202, 127), (bale_rect.left + 8, bale_rect.top + 4),
                             (bale_rect.right - 8, bale_rect.top + 4), 2)

        entrance_x = sx + (stable["entrance_tile"][0] - stable["tile_x"]) * self.tile_size
        pygame.draw.rect(screen, (74, 52, 35), (entrance_x, rect.bottom - 22, self.tile_size, 22))
        pygame.draw.rect(screen, (195, 164, 111), (entrance_x + 3, rect.bottom - 18, self.tile_size - 6, 15), 2)
        if is_active:
            pygame.draw.rect(screen, (255, 215, 60), rect, 3)
        elif is_hovered:
            pygame.draw.rect(screen, (100, 200, 255), rect.inflate(6, 6), 2)
        color = (255, 215, 60) if is_active else (100, 200, 255) if is_hovered else (211, 184, 140)
        self._draw_badge(screen, rect.centerx, sy - 10, "Городская Конюшня [17х6]", color)

    def _draw_walls_and_gates(self, screen):
        """Отрисовывает мощные каменные стены периметра и 4 ворот."""
        pulse = 1.0 + 0.08 * math.sin(self.player_anim_timer * 5.0)

        # 1. Отрисовка непроходимых стен
        for s_rect in self.solid_rects:
            sx, sy = self.world_to_screen(s_rect.x, s_rect.y)
            w = s_rect.width
            h = s_rect.height
            if -w <= sx <= settings.WIDTH + w and -h <= sy <= settings.HEIGHT + h:
                draw_r = pygame.Rect(sx, sy, w, h)
                pygame.draw.rect(screen, (40, 48, 60), draw_r)
                pygame.draw.rect(screen, (65, 80, 100), draw_r, 2)

                # Зубцы стен
                if w > h:
                    for bx in range(draw_r.left + 4, draw_r.right - 8, 20):
                        pygame.draw.rect(screen, (25, 30, 38), (bx, draw_r.top + 2, 10, 6))
                else:
                    for by in range(draw_r.top + 4, draw_r.bottom - 8, 20):
                        pygame.draw.rect(screen, (25, 30, 38), (draw_r.left + 2, by, 6, 10))

        # 2. Главные ворота (Восток, 12 тайлов = 384 px, Y: 44..55)
        gw_e_x = 98 * self.tile_size
        gw_e_y = 44 * self.tile_size
        gw_e_w = 2 * self.tile_size
        gw_e_h = 12 * self.tile_size
        sx, sy = self.world_to_screen(gw_e_x, gw_e_y)
        if -100 <= sx <= settings.WIDTH + 100 and -450 <= sy <= settings.HEIGHT + 450:
            # Зона перехода / выхода (пульсирующая арка)
            exit_rect = pygame.Rect(sx, sy, gw_e_w, gw_e_h)
            pygame.draw.rect(screen, (25, 45, 35, 180), exit_rect, border_radius=4)
            pygame.draw.rect(screen, (255, 215, 60), exit_rect, 3, border_radius=4)

            # Башни по краям ворот
            pygame.draw.rect(screen, (55, 68, 85), (sx - 24, sy - 32, 48, 32), border_radius=4)
            pygame.draw.rect(screen, (55, 68, 85), (sx - 24, sy + gw_e_h, 48, 32), border_radius=4)

            # Факелы у главных ворот
            for fy in (sy + 16, sy + gw_e_h // 2, sy + gw_e_h - 16):
                pygame.draw.circle(screen, (255, 150, 30), (sx + 8, fy), 6)
                pygame.draw.circle(screen, (255, 230, 100), (sx + 8, fy), 3)

            # Вывеска
            lbl = self.badge_font.render("⚜️ ГЛАВНЫЕ ВОРОТА [12 ТАЙЛОВ] ⚜️", True, (255, 225, 100))
            sub_lbl = self.grid_font.render("➜ ШАГНИТЕ ДЛЯ ВЫХОДА НА КАРТУ МИРА", True, (140, 255, 180))
            self._draw_gate_badge(screen, sx - 20, sy + gw_e_h // 2 - 12, lbl, (255, 215, 60))
            self._draw_gate_badge(screen, sx - 20, sy + gw_e_h // 2 + 12, sub_lbl, (100, 220, 160))

        # 3. Северные ворота (Север, 6 тайлов = 192 px, X: 47..52)
        gw_n_x = 47 * self.tile_size
        gw_n_y = 0
        gw_n_w = 6 * self.tile_size
        gw_n_h = 2 * self.tile_size
        sx, sy = self.world_to_screen(gw_n_x, gw_n_y)
        if -250 <= sx <= settings.WIDTH + 250 and -100 <= sy <= settings.HEIGHT + 100:
            exit_rect = pygame.Rect(sx, sy, gw_n_w, gw_n_h)
            pygame.draw.rect(screen, (25, 45, 35, 180), exit_rect, border_radius=4)
            pygame.draw.rect(screen, (100, 200, 255), exit_rect, 2, border_radius=4)
            lbl = self.badge_font.render("СЕВЕРНЫЕ ВОРОТА [6 ТАЙЛОВ]", True, (180, 230, 255))
            sub_lbl = self.grid_font.render("➜ ВЫХОД НА КАРТУ МИРА", True, (140, 255, 180))
            self._draw_gate_badge(screen, sx + gw_n_w // 2, sy + gw_n_h + 16, lbl, (100, 200, 255))
            self._draw_gate_badge(screen, sx + gw_n_w // 2, sy + gw_n_h + 36, sub_lbl, (100, 220, 160))

        # 4. Южные ворота (Юг, 6 тайлов = 192 px, X: 47..52)
        gw_s_x = 47 * self.tile_size
        gw_s_y = 98 * self.tile_size
        gw_s_w = 6 * self.tile_size
        gw_s_h = 2 * self.tile_size
        sx, sy = self.world_to_screen(gw_s_x, gw_s_y)
        if -250 <= sx <= settings.WIDTH + 250 and -100 <= sy <= settings.HEIGHT + 100:
            exit_rect = pygame.Rect(sx, sy, gw_s_w, gw_s_h)
            pygame.draw.rect(screen, (25, 45, 35, 180), exit_rect, border_radius=4)
            pygame.draw.rect(screen, (100, 200, 255), exit_rect, 2, border_radius=4)
            lbl = self.badge_font.render("ЮЖНЫЕ ВОРОТА [6 ТАЙЛОВ]", True, (180, 230, 255))
            sub_lbl = self.grid_font.render("➜ ВЫХОД НА КАРТУ МИРА", True, (140, 255, 180))
            self._draw_gate_badge(screen, sx + gw_s_w // 2, sy - 36, lbl, (100, 200, 255))
            self._draw_gate_badge(screen, sx + gw_s_w // 2, sy - 16, sub_lbl, (100, 220, 160))

        # 5. Западные ворота (Запад, 6 тайлов = 192 px, Y: 47..52)
        gw_w_x = 0
        gw_w_y = 47 * self.tile_size
        gw_w_w = 2 * self.tile_size
        gw_w_h = 6 * self.tile_size
        sx, sy = self.world_to_screen(gw_w_x, gw_w_y)
        if -100 <= sx <= settings.WIDTH + 100 and -250 <= sy <= settings.HEIGHT + 250:
            exit_rect = pygame.Rect(sx, sy, gw_w_w, gw_w_h)
            pygame.draw.rect(screen, (25, 45, 35, 180), exit_rect, border_radius=4)
            pygame.draw.rect(screen, (100, 200, 255), exit_rect, 2, border_radius=4)
            lbl = self.badge_font.render("ЗАПАДНЫЕ ВОРОТА [6 ТАЙЛОВ]", True, (180, 230, 255))
            sub_lbl = self.grid_font.render("➜ ВЫХОД НА КАРТУ МИРА", True, (140, 255, 180))
            self._draw_gate_badge(screen, sx + gw_w_w + 120, sy + gw_w_h // 2 - 12, lbl, (100, 200, 255))
            self._draw_gate_badge(screen, sx + gw_w_w + 120, sy + gw_w_h // 2 + 12, sub_lbl, (100, 220, 160))

    def _draw_gate_badge(self, screen, cx, cy, surf, border_color):
        """Вспомогательная плашка с надписью над воротами."""
        bg = surf.get_rect(center=(cx, cy)).inflate(12, 6)
        pygame.draw.rect(screen, (12, 16, 22, 225), bg, border_radius=4)
        pygame.draw.rect(screen, border_color, bg, 1, border_radius=4)
        screen.blit(surf, surf.get_rect(center=bg.center))

    def _draw_click_effect(self, screen):
        """Отрисовывает расходящийся маркер клика ПКМ."""
        if self.click_effect is None:
            return

        cx, cy = self.world_to_screen(self.click_effect["x"], self.click_effect["y"])
        progress = 1.0 - (self.click_effect["timer"] / 0.35)
        radius = int(8 + progress * 16)
        alpha_val = max(0, int(255 * (1.0 - progress)))

        ring = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(ring, (80, 255, 120, alpha_val), (radius + 2, radius + 2), radius, 2)
        screen.blit(ring, (cx - radius - 2, cy - radius - 2))

    def _draw_player_character(self, screen):
        """Отрисовывает персонажа игрока с 8-направленной анимацией."""
        psx, psy = self.world_to_screen(self.player_x, self.player_y)

        # Тень
        shadow_rect = pygame.Rect(psx - 14, psy - 4, 28, 10)
        shadow_surf = pygame.Surface((32, 14), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (10, 12, 16, 170), (0, 0, 32, 14))
        screen.blit(shadow_surf, (psx - 16, psy - 5))

        direction = getattr(self, "player_direction", "s")
        current_frame = None

        if self.player_state == "walk":
            run_frames = self.player_run_directional_frames.get(direction)
            if run_frames:
                idx = int(self.player_anim_timer * 10.0) % len(run_frames)
                current_frame = run_frames[idx]
        else:
            idle_frames = self.player_directional_frames.get(direction)
            if idle_frames:
                idx = int(self.player_anim_timer * 4.0) % len(idle_frames)
                current_frame = idle_frames[idx]

        if current_frame is not None:
            frame_rect = current_frame.get_rect(midbottom=(psx, psy + 2))
            screen.blit(current_frame, frame_rect)
        else:
            # Запасной рендер
            pygame.draw.circle(screen, (220, 180, 80), (psx, psy - 24), 14)
            pygame.draw.rect(screen, (60, 100, 180), (psx - 10, psy - 12, 20, 16), border_radius=3)

        # Никнейм над головой
        char_name = getattr(self.session, "character", {}).get("name", "Герой") if hasattr(self.session, "character") else "Герой"
        name_surf = self.grid_font.render(char_name, True, (240, 240, 240))
        name_bg = name_surf.get_rect(midbottom=(psx, psy - 42)).inflate(8, 4)
        pygame.draw.rect(screen, (15, 18, 24, 210), name_bg, border_radius=3)
        pygame.draw.rect(screen, (220, 180, 60), name_bg, 1, border_radius=3)
        screen.blit(name_surf, name_surf.get_rect(center=name_bg.center))

    def _draw_floating_messages(self, screen):
        """Отрисовывает всплывающие сообщения в игровом мире."""
        for msg in self.floating_messages:
            sx, sy = self.world_to_screen(msg["world_x"], msg["world_y"])
            if not (-120 <= sx <= settings.WIDTH + 120 and -60 <= sy <= settings.HEIGHT + 60):
                continue
            progress = max(0.0, min(1.0, msg["timer"] / msg["max_timer"]))
            alpha = int(255 * min(1.0, progress * 2.0))

            text_surf = self.small_font.render(msg["text"], True, msg["color"])
            bg_rect = text_surf.get_rect(center=(sx, sy)).inflate(16, 8)

            popup = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            pygame.draw.rect(popup, (15, 18, 24, int(220 * (alpha / 255.0))), (0, 0, bg_rect.width, bg_rect.height), border_radius=5)
            r, g, b = msg["color"][:3]
            pygame.draw.rect(popup, (r, g, b, alpha), (0, 0, bg_rect.width, bg_rect.height), 1, border_radius=5)
            popup.blit(text_surf, (8, 4))
            screen.blit(popup, bg_rect.topleft)
