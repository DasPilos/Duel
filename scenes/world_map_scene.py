import pygame
from core import settings
from ui.hud import draw_button


class WorldMapScene:
    """
    Сцена глобальной карты 6000x4000.
    Центр мира: (0, 0).
    Размер сетки: 50x50 пикселей.
    Координаты тайлов отображаются от центра: 1/1, -1/1, 1/-1, -1/-1 и т.д.
    """

    def __init__(self, session):
        self.session = session
        self.finished = False
        self.cancelled = False
        self.navigate = None

        # Размеры мира
        self.world_w = 6000
        self.world_h = 4000
        self.tile_size = 50

        # Границы мира в координатах от центра
        self.min_world_x = -self.world_w // 2  # -3000
        self.max_world_x = self.world_w // 2   # 3000
        self.min_world_y = -self.world_h // 2  # -2000
        self.max_world_y = self.world_h // 2   # 2000

        # Камера (координаты центра экрана в мировых координатах)
        # Стартуем с видом на Замок Света (-2000, -1000)
        self.camera_x = -1975.0
        self.camera_y = -975.0

        # Перетаскивание карты мышью
        self.dragging = False
        self.drag_start_mouse = (0, 0)
        self.drag_start_camera = (0.0, 0.0)

        # Шрифты
        self.font = pygame.font.SysFont(settings.FONT_NAME, 20)
        self.grid_font = pygame.font.SysFont(settings.FONT_NAME, 11)
        self.large_font = pygame.font.SysFont(settings.FONT_NAME, 24, bold=True)

        # UI элементы
        self.back_button = pygame.Rect(20, 20, 180, 45)
        self.center_button = pygame.Rect(210, 20, 160, 45)
        self.light_castle_button = pygame.Rect(380, 20, 160, 45)
        self.dark_castle_button = pygame.Rect(550, 20, 160, 45)

    def world_to_screen(self, wx, wy):
        """Преобразование мировых координат (относительно центра 0,0) в экранные пиксели."""
        sx = int(wx - self.camera_x + settings.WIDTH / 2)
        sy = int(wy - self.camera_y + settings.HEIGHT / 2)
        return sx, sy

    def screen_to_world(self, sx, sy):
        """Преобразование экранных пикселей в мировые координаты."""
        wx = (sx - settings.WIDTH / 2) + self.camera_x
        wy = (sy - settings.HEIGHT / 2) + self.camera_y
        return wx, wy

    def _clamp_camera(self):
        """Удержание камеры в пределах мира."""
        half_screen_w = settings.WIDTH / 2
        half_screen_h = settings.HEIGHT / 2
        self.camera_x = max(self.min_world_x + half_screen_w, min(self.max_world_x - half_screen_w, self.camera_x))
        self.camera_y = max(self.min_world_y + half_screen_h, min(self.max_world_y - half_screen_h, self.camera_y))

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.cancelled = True
                self.finished = True
                return

        # Нажатие мыши
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                # Кнопки верхнего меню
                if self.back_button.collidepoint(event.pos):
                    self.finished = True
                    return
                if self.center_button.collidepoint(event.pos):
                    self.camera_x = 0.0
                    self.camera_y = 0.0
                    return
                if self.light_castle_button.collidepoint(event.pos):
                    self.camera_x = -1975.0
                    self.camera_y = -975.0
                    return
                if self.dark_castle_button.collidepoint(event.pos):
                    self.camera_x = 1975.0
                    self.camera_y = 975.0
                    return

                # Захват карты для драга
                self.dragging = True
                self.drag_start_mouse = event.pos
                self.drag_start_camera = (self.camera_x, self.camera_y)

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.dragging = False

        elif event.type == pygame.MOUSEMOTION:
            if self.dragging:
                dx = event.pos[0] - self.drag_start_mouse[0]
                dy = event.pos[1] - self.drag_start_mouse[1]
                self.camera_x = self.drag_start_camera[0] - dx
                self.camera_y = self.drag_start_camera[1] - dy
                self._clamp_camera()

    def update(self, dt):
        # Передвижение стрелками / WASD
        keys = pygame.key.get_pressed()
        speed = 800.0 * dt
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
            speed *= 2.0

        moved = False
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            self.camera_x -= speed
            moved = True
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            self.camera_x += speed
            moved = True
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            self.camera_y -= speed
            moved = True
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            self.camera_y += speed
            moved = True

        if moved:
            self._clamp_camera()

    def draw(self, screen):
        screen.fill((20, 24, 28))

        # Вычисляем видимый диапазон мира
        top_left_wx, top_left_wy = self.screen_to_world(0, 0)
        bot_right_wx, bot_right_wy = self.screen_to_world(settings.WIDTH, settings.HEIGHT)

        # Выравниваем границы видимых тайлов по сетке 50x50
        start_gx = int(top_left_wx // self.tile_size) - 1
        end_gx = int(bot_right_wx // self.tile_size) + 1
        start_gy = int(top_left_wy // self.tile_size) - 1
        end_gy = int(bot_right_wy // self.tile_size) + 1

        # Ограничиваем пределами мира
        min_gx = self.min_world_x // self.tile_size
        max_gx = self.max_world_x // self.tile_size
        min_gy = self.min_world_y // self.tile_size
        max_gy = self.max_world_y // self.tile_size

        start_gx = max(min_gx, start_gx)
        end_gx = min(max_gx, end_gx)
        start_gy = max(min_gy, start_gy)
        end_gy = min(max_gy, end_gy)

        mouse_pos = pygame.mouse.get_pos()
        hover_wx, hover_wy = self.screen_to_world(mouse_pos[0], mouse_pos[1])

        # Отрисовка ячеек сетки
        for gy in range(start_gy, end_gy):
            for gx in range(start_gx, end_gx):
                tile_wx = gx * self.tile_size
                tile_wy = gy * self.tile_size
                sx, sy = self.world_to_screen(tile_wx, tile_wy)

                rect = pygame.Rect(sx, sy, self.tile_size, self.tile_size)

                # Вычисляем координаты ячейки от центра 0,0:
                # Вправо от 0 -> 1, 2, 3; Влево от 0 -> -1, -2, -3
                coord_x = gx + 1 if gx >= 0 else gx
                # Вниз от 0 -> 1, 2, 3; Вверх от 0 -> -1, -2, -3
                coord_y = gy + 1 if gy >= 0 else gy

                # Фоновая подложка клетки
                cell_color = (25, 30, 35) if (gx + gy) % 2 == 0 else (28, 34, 40)
                
                # Подсветка зоны Замка Света (5x5 клеток вокруг центра -40/-20)
                if -42 <= gx < -37 and -22 <= gy < -17:
                    cell_color = (35, 55, 75)
                # Подсветка зоны Цитадели Тьмы (5x5 клеток вокруг центра +40/+20)
                elif 37 <= gx < 42 and 17 <= gy < 22:
                    cell_color = (75, 35, 45)

                pygame.draw.rect(screen, cell_color, rect)
                pygame.draw.rect(screen, (45, 52, 60), rect, 1)

                # Координатная надпись формата: 1/1, -1/1, 1/-1, -1/-1
                coord_text = f"{coord_x}/{coord_y}"
                text_surf = self.grid_font.render(coord_text, True, (120, 135, 150))
                text_rect = text_surf.get_rect(center=rect.center)
                screen.blit(text_surf, text_rect)

        # Выделение центральных осей (X = 0 и Y = 0)
        axis_x, _ = self.world_to_screen(0, 0)
        _, axis_y = self.world_to_screen(0, 0)

        # Ось Y (по центру X=0)
        if 0 <= axis_x <= settings.WIDTH:
            pygame.draw.line(screen, (220, 200, 80), (axis_x, 0), (axis_x, settings.HEIGHT), 2)
        # Ось X (по центру Y=0)
        if 0 <= axis_y <= settings.HEIGHT:
            pygame.draw.line(screen, (220, 200, 80), (0, axis_y), (settings.WIDTH, axis_y), 2)

        # Отрисовка маркеров ключевых объектов (5x5 тайлов = 250x250 px)
        self._draw_marker(screen, -1975, -975, "ЗАМОК СВЕТА 5x5 (-2000, -1000)", (80, 180, 255), 5 * self.tile_size)
        self._draw_marker(screen, 1975, 975, "ЦИТАДЕЛЬ ТЬМЫ 5x5 (+2000, +1000)", (255, 80, 80), 5 * self.tile_size)
        self._draw_marker(screen, 0, 0, "ЦЕНТР МИРА (0, 0)", (255, 220, 50), 50)

        # Верхняя панель управления и подсказок
        hud_bg = pygame.Rect(0, 0, settings.WIDTH, 75)
        pygame.draw.rect(screen, (15, 18, 22), hud_bg)
        pygame.draw.line(screen, (60, 70, 85), (0, 75), (settings.WIDTH, 75), 2)

        draw_button(screen, self.back_button, "В ТАВЕРНУ", self.font, color=(160, 70, 70))
        draw_button(screen, self.center_button, "ЦЕНТР (0, 0)", self.font, color=(70, 110, 150))
        draw_button(screen, self.light_castle_button, "ЗАМОК СВЕТА", self.font, color=(60, 120, 180))
        draw_button(screen, self.dark_castle_button, "ЦИТАДЕЛЬ ТЬМЫ", self.font, color=(180, 60, 60))

        # Индикатор позиции камеры и курсора
        hover_gx = int(hover_wx // self.tile_size)
        hover_gy = int(hover_wy // self.tile_size)
        hover_cx = hover_gx + 1 if hover_gx >= 0 else hover_gx
        hover_cy = hover_gy + 1 if hover_gy >= 0 else hover_gy

        info_str = f"Камера: X={int(self.camera_x)}, Y={int(self.camera_y)} | Курсор: WX={int(hover_wx)}, WY={int(hover_wy)} | Квадрат: {hover_cx}/{hover_cy}"
        info_surf = self.font.render(info_str, True, (240, 240, 240))
        screen.blit(info_surf, (730, 27))

        hint_str = "Управление: Перетаскивание мышью (ЛКМ) | Стрелки / WASD (+Shift для ускорения)"
        hint_surf = self.grid_font.render(hint_str, True, (160, 170, 180))
        screen.blit(hint_surf, (20, settings.HEIGHT - 25))

    def _draw_marker(self, screen, wx, wy, title, color, size_px):
        """Отрисовывает рамку объекта и подпись."""
        sx, sy = self.world_to_screen(wx - size_px // 2, wy - size_px // 2)
        obj_rect = pygame.Rect(sx, sy, size_px, size_px)
        
        # Рисуем рамку
        pygame.draw.rect(screen, color, obj_rect, 3, border_radius=4)
        
        # Подпись
        title_surf = self.font.render(title, True, color)
        t_rect = title_surf.get_rect(midbottom=(obj_rect.centerx, obj_rect.top - 6))
        bg_rect = t_rect.inflate(12, 6)
        pygame.draw.rect(screen, (10, 12, 16), bg_rect, border_radius=4)
        pygame.draw.rect(screen, color, bg_rect, 1, border_radius=4)
        screen.blit(title_surf, t_rect)

    def close(self):
        pass
