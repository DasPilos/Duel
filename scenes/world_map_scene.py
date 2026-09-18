import math
import random
import pygame
from core import settings
from ui.hud import draw_button


def catmull_rom_spline(p0, p1, p2, p3, num_points=12):
    """
    Генерирует сглаженные точки Catmull-Rom сплайна между p1 и p2.
    """
    points = []
    for i in range(num_points):
        t = i / float(num_points)
        t2 = t * t
        t3 = t2 * t

        x = 0.5 * (
            (2.0 * p1[0])
            + (-p0[0] + p2[0]) * t
            + (2.0 * p0[0] - 5.0 * p1[0] + 4.0 * p2[0] - p3[0]) * t2
            + (-p0[0] + 3.0 * p1[0] - 3.0 * p2[0] + p3[0]) * t3
        )
        y = 0.5 * (
            (2.0 * p1[1])
            + (-p0[1] + p2[1]) * t
            + (2.0 * p0[1] - 5.0 * p1[1] + 4.0 * p2[1] - p3[1]) * t2
            + (-p0[1] + 3.0 * p1[1] - 3.0 * p2[1] + p3[1]) * t3
        )
        points.append((x, y))
    return points


def build_spline_path(waypoints, samples_per_segment=18):
    """
    Создает плавную плотную цепочку точек вдоль массива контрольных путевых точек.
    """
    if len(waypoints) < 2:
        return list(waypoints)

    extended = [waypoints[0]] + list(waypoints) + [waypoints[-1]]
    full_path = []

    for i in range(len(extended) - 3):
        p0 = extended[i]
        p1 = extended[i + 1]
        p2 = extended[i + 2]
        p3 = extended[i + 3]
        pts = catmull_rom_spline(p0, p1, p2, p3, samples_per_segment)
        full_path.extend(pts)

    full_path.append(waypoints[-1])
    return full_path


class WorldMapScene:
    """
    Сцена глобальной карты 6000x4000.
    Центр мира: (0, 0).
    Размер сетки: 50x50 пикселей.
    Главный Тракт связывает Замок Света и Цитадель Тьмы по извилистой S-образной дуге.
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
        self.camera_x = -1975.0
        self.camera_y = -975.0

        # Перетаскивание карты мышью
        self.dragging = False
        self.drag_start_mouse = (0, 0)
        self.drag_start_camera = (0.0, 0.0)

        # Шрифты
        self.font = pygame.font.SysFont(settings.FONT_NAME, 20)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 16)
        self.grid_font = pygame.font.SysFont(settings.FONT_NAME, 11)
        self.badge_font = pygame.font.SysFont(settings.FONT_NAME, 13, bold=True)
        self.large_font = pygame.font.SysFont(settings.FONT_NAME, 24, bold=True)

        # UI элементы
        self.back_button = pygame.Rect(20, 20, 160, 45)
        self.center_button = pygame.Rect(190, 20, 140, 45)
        self.light_castle_button = pygame.Rect(340, 20, 150, 45)
        self.dark_castle_button = pygame.Rect(500, 20, 150, 45)

        # --- 1. Опорные путевые точки Главного Тракта (S-образная дуга) ---
        self.road_waypoints = [
            (-1975, -975),   # 1. Замок Света (выход из ворот)
            (-1600, -960),   # Вышка 5 Света
            (-1200, -930),   # Вышка 4 Света
            (-800,  -900),   # Каменный Гарнизон 2 Света (до 12 солдат)
            (-400,  -870),   # Вышка 3 Света
            (0,     -850),   # Вышка 2 Света
            (700,   -820),   # Деревянный Гарнизон 1 Света (до 6 солдат)
            (1450,  -800),   # Плавный вход в петлю
            (1520,  -550),   # Поворот вниз вдоль нейтрального холма
            (1150,  -250),   # Вышка 1 Света (300 px до центра)
            (450,   -90),    # Спуск к ничейной земле
            (0,      0),     # ⚔️ ЦЕНТР МИРА (перекресток и застава)
            (-450,   90),    # Выход в земли Тьмы
            (-1150,  250),   # Вышка 1 Тьмы (300 px от центра)
            (-1520,  550),   # Петля Тьмы
            (-1450,  800),   # Плавный разворот
            (-700,   820),   # Деревянный Гарнизон 1 Тьмы (до 6 солдат)
            (0,      850),   # Вышка 2 Тьмы
            (400,    870),   # Вышка 3 Тьмы
            (800,    900),   # Каменный Гарнизон 2 Тьмы (до 12 солдат)
            (1200,   930),   # Вышка 4 Тьмы
            (1600,   960),   # Вышка 5 Тьмы
            (1975,   975),   # 2. Цитадель Тьмы (ворота)
        ]

        # Рассчитываем сглаженный путь сплайна (высокая плотность точек)
        self.spline_path = build_spline_path(self.road_waypoints, samples_per_segment=18)

        # --- 2. Гарнизоны и Сторожевые Вышки вдоль Тракта ---
        self.military_structures = [
            # Сторона Света:
            {"type": "tower", "name": "Вышка 5 (Свет)", "pos": (-1600, -960), "faction": "light"},
            {"type": "tower", "name": "Вышка 4 (Свет)", "pos": (-1200, -930), "faction": "light"},
            {"type": "stone_garrison", "name": "Каменный форпост (12 солдат)", "pos": (-800, -900), "faction": "light"},
            {"type": "tower", "name": "Вышка 3 (Свет)", "pos": (-400, -870), "faction": "light"},
            {"type": "tower", "name": "Вышка 2 (Свет)", "pos": (0, -850), "faction": "light"},
            {"type": "wood_garrison", "name": "Частокольный форпост (6 солдат)", "pos": (700, -820), "faction": "light"},
            {"type": "tower", "name": "Вышка 1 (Свет, 300px)", "pos": (1150, -250), "faction": "light"},

            # Сторона Тьмы:
            {"type": "tower", "name": "Вышка 1 (Тьма, 300px)", "pos": (-1150, 250), "faction": "dark"},
            {"type": "wood_garrison", "name": "Частокольный форпост (6 солдат)", "pos": (-700, 820), "faction": "dark"},
            {"type": "tower", "name": "Вышка 2 (Тьма)", "pos": (0, 850), "faction": "dark"},
            {"type": "tower", "name": "Вышка 3 (Тьма)", "pos": (400, 870), "faction": "dark"},
            {"type": "stone_garrison", "name": "Каменный форпост (12 солдат)", "pos": (800, 900), "faction": "dark"},
            {"type": "tower", "name": "Вышка 4 (Тьма)", "pos": (1200, 930), "faction": "dark"},
            {"type": "tower", "name": "Вышка 5 (Тьма)", "pos": (1600, 960), "faction": "dark"},
        ]

        # --- 3. Генерация декоративных заплаток травы, камней и указателей вдоль тракта ---
        self._init_roadside_decorations()

    def _init_roadside_decorations(self):
        """
        Создает атмосферные заплатки травы, дорожные камни, фонари и указатели
        по обеим обочинам тракта (детерминированно, чтобы не прыгали между кадрами).
        """
        rng = random.Random(42)  # Фиксированное зерно для стабильности мира
        self.grass_patches = []
        self.roadside_props = []

        step = 6  # с каким шагом по точкам сплайна спавнить обочину
        for i in range(2, len(self.spline_path) - 2, step):
            curr_pt = self.spline_path[i]
            prev_pt = self.spline_path[i - 1]
            next_pt = self.spline_path[i + 1]

            # Нормаль к касательной дороги (влево и вправо от полотна)
            dx = next_pt[0] - prev_pt[0]
            dy = next_pt[1] - prev_pt[1]
            dist = math.hypot(dx, dy)
            if dist == 0:
                continue
            nx = -dy / dist
            ny = dx / dist

            # Обе стороны обочины: левая (+), правая (-)
            for side in (1, -1):
                offset_dist = rng.uniform(55, 120) * side
                px = curr_pt[0] + nx * offset_dist
                py = curr_pt[1] + ny * offset_dist

                # Заплатка травы (цвета зависят от зоны: пышная зеленая у Света, выжженная темная у Тьмы)
                if py < 0:
                    base_green = rng.randint(45, 75)
                    color = (rng.randint(25, 40), base_green, rng.randint(20, 35))
                else:
                    base_dark = rng.randint(20, 38)
                    color = (rng.randint(35, 55), base_dark, rng.randint(25, 35))

                radius = rng.randint(18, 42)
                self.grass_patches.append({"x": px, "y": py, "r": radius, "color": color})

                # Случайный предмет на обочине (камни, фонари, деревянные указатели, бочки)
                prop_roll = rng.random()
                if prop_roll < 0.22:
                    if prop_roll < 0.10:
                        prop_type = "boulder"      # придорожный валун / камень
                        prop_color = (95, 105, 115)
                        prop_size = rng.randint(8, 14)
                    elif prop_roll < 0.16:
                        prop_type = "lantern"      # путевой столб / фонарь
                        prop_color = (220, 180, 70) if py < 0 else (180, 60, 60)
                        prop_size = 6
                    else:
                        prop_type = "signpost"     # дорожный указатель
                        prop_color = (139, 90, 43)
                        prop_size = 9

                    self.roadside_props.append({
                        "x": px,
                        "y": py,
                        "type": prop_type,
                        "color": prop_color,
                        "size": prop_size
                    })

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

        # 1. Отрисовка ячеек сетки
        for gy in range(start_gy, end_gy):
            for gx in range(start_gx, end_gx):
                tile_wx = gx * self.tile_size
                tile_wy = gy * self.tile_size
                sx, sy = self.world_to_screen(tile_wx, tile_wy)

                rect = pygame.Rect(sx, sy, self.tile_size, self.tile_size)

                coord_x = gx + 1 if gx >= 0 else gx
                coord_y = gy + 1 if gy >= 0 else gy

                cell_color = (24, 28, 33) if (gx + gy) % 2 == 0 else (27, 32, 38)
                
                # Подсветка зоны Замка Света (5x5 клеток вокруг центра -40/-20)
                if -42 <= gx < -37 and -22 <= gy < -17:
                    cell_color = (35, 55, 75)
                # Подсветка зоны Цитадели Тьмы (5x5 клеток вокруг центра +40/+20)
                elif 37 <= gx < 42 and 17 <= gy < 22:
                    cell_color = (75, 35, 45)

                pygame.draw.rect(screen, cell_color, rect)
                pygame.draw.rect(screen, (40, 47, 55), rect, 1)

                coord_text = f"{coord_x}/{coord_y}"
                text_surf = self.grid_font.render(coord_text, True, (100, 115, 130))
                text_rect = text_surf.get_rect(center=rect.center)
                screen.blit(text_surf, text_rect)

        # 2. Отрисовка заплаток травы на обочинах
        self._draw_grass_patches(screen)

        # 3. Отрисовка полотна Главного Тракта (обочина + мощение + осевая разметка)
        self._draw_road_ribbon(screen)

        # 4. Отрисовка декоративных придорожных объектов (камни, указатели, фонари)
        self._draw_roadside_props(screen)

        # 5. Отрисовка военных укреплений (Гарнизоны 1 и 2, Вышки 1-5)
        self._draw_military_structures(screen)

        # 6. Отрисовка осей X/Y и ключевых замков
        self._draw_axes_and_castles(screen)

        # 7. Верхний HUD и подсказки
        self._draw_hud(screen, hover_wx, hover_wy)

    def _draw_grass_patches(self, screen):
        """Отрисовывает органичные пятна травы вдоль обочины."""
        for patch in self.grass_patches:
            sx, sy = self.world_to_screen(patch["x"], patch["y"])
            r = patch["r"]
            if -r <= sx <= settings.WIDTH + r and -r <= sy <= settings.HEIGHT + r:
                pygame.draw.circle(screen, patch["color"], (sx, sy), r)

    def _draw_road_ribbon(self, screen):
        """
        Рисует широкую фэнтезийную мощеную дорогу:
        - Внешний слой грунта/обочины (ширина 84px)
        - Каменное мощение (ширина 56px)
        - Внутренняя плиточная колея (ширина 32px)
        - Поперечные штрихи брусчатки
        """
        screen_points = [self.world_to_screen(pt[0], pt[1]) for pt in self.spline_path]
        if len(screen_points) < 2:
            return

        # 1. Обочина (земляная насыпь)
        pygame.draw.lines(screen, (55, 46, 38), False, screen_points, 84)

        # 2. Каменное полотно (булыжник)
        pygame.draw.lines(screen, (85, 82, 80), False, screen_points, 56)

        # 3. Внутренняя плиточная колея (чуть светлее)
        pygame.draw.lines(screen, (108, 104, 100), False, screen_points, 32)

        # 4. Поперечные швы брусчатки (рисуются через равные интервалы)
        for i in range(1, len(self.spline_path) - 1, 2):
            pt = self.spline_path[i]
            sx, sy = self.world_to_screen(pt[0], pt[1])
            if 0 <= sx <= settings.WIDTH and 0 <= sy <= settings.HEIGHT:
                prev_p = self.spline_path[i - 1]
                next_p = self.spline_path[i + 1]
                dx = next_p[0] - prev_p[0]
                dy = next_p[1] - prev_p[1]
                dist = math.hypot(dx, dy)
                if dist > 0:
                    nx = -dy / dist * 14
                    ny = dx / dist * 14
                    p_start = (int(sx - nx), int(sy - ny))
                    p_end = (int(sx + nx), int(sy + ny))
                    pygame.draw.line(screen, (70, 67, 65), p_start, p_end, 2)

    def _draw_roadside_props(self, screen):
        """Отрисовывает придорожные объекты (валуны, указатели, фонари)."""
        for prop in self.roadside_props:
            sx, sy = self.world_to_screen(prop["x"], prop["y"])
            sz = prop["size"]
            if -sz <= sx <= settings.WIDTH + sz and -sz <= sy <= settings.HEIGHT + sz:
                ptype = prop["type"]
                if ptype == "boulder":
                    pygame.draw.circle(screen, prop["color"], (sx, sy), sz)
                    pygame.draw.circle(screen, (40, 45, 50), (sx, sy), sz, 1)
                elif ptype == "lantern":
                    # Столб с фонарем
                    pygame.draw.rect(screen, (70, 50, 30), (sx - 2, sy - 8, 4, 16))
                    pygame.draw.circle(screen, prop["color"], (sx, sy - 9), 5)
                elif ptype == "signpost":
                    # Деревянный указатель
                    pygame.draw.rect(screen, prop["color"], (sx - 2, sy - 6, 4, 14))
                    pygame.draw.polygon(screen, (160, 110, 60), [(sx - 6, sy - 8), (sx + 8, sy - 8), (sx + 12, sy - 4), (sx + 8, sy), (sx - 6, sy)])

    def _draw_military_structures(self, screen):
        """Отрисовывает вышки и гарнизоны вдоль тракта."""
        for item in self.military_structures:
            wx, wy = item["pos"]
            sx, sy = self.world_to_screen(wx, wy)
            stype = item["type"]
            name = item["name"]
            is_light = item["faction"] == "light"

            f_color = (80, 190, 255) if is_light else (255, 90, 90)

            if stype == "tower":
                # Сторожевая вышка (квадрат 34x34)
                rect = pygame.Rect(sx - 17, sy - 17, 34, 34)
                pygame.draw.rect(screen, (30, 35, 42), rect, border_radius=4)
                pygame.draw.rect(screen, (139, 90, 43), rect, 3, border_radius=4)
                roof = [(rect.centerx, rect.top - 8), (rect.left - 2, rect.top + 3), (rect.right + 2, rect.top + 3)]
                pygame.draw.polygon(screen, f_color, roof)
                self._draw_badge(screen, rect.centerx, rect.top - 12, name, f_color)

            elif stype == "wood_garrison":
                # Частокольный гарнизон 1 (до 6 солдат) - размер 50x50
                rect = pygame.Rect(sx - 25, sy - 25, 50, 50)
                pygame.draw.rect(screen, (45, 34, 25), rect, border_radius=6)
                pygame.draw.rect(screen, (160, 110, 60), rect, 3, border_radius=6)
                gate_rect = pygame.Rect(rect.centerx - 8, rect.bottom - 6, 16, 6)
                pygame.draw.rect(screen, (190, 140, 70), gate_rect)
                self._draw_badge(screen, rect.centerx, rect.top - 10, f"🪵 {name}", (230, 190, 110))

            elif stype == "stone_garrison":
                # Каменный гарнизон 2 (до 12 солдат) - размер 65x65
                rect = pygame.Rect(sx - 32, sy - 32, 65, 65)
                pygame.draw.rect(screen, (40, 45, 52), rect, border_radius=8)
                pygame.draw.rect(screen, (160, 175, 190), rect, 4, border_radius=8)
                gate_rect = pygame.Rect(rect.centerx - 10, rect.bottom - 7, 20, 7)
                pygame.draw.rect(screen, (180, 200, 220), gate_rect)
                self._draw_badge(screen, rect.centerx, rect.top - 10, f"🛡️ {name}", (200, 220, 255) if is_light else (255, 180, 180))

    def _draw_badge(self, screen, cx, bottom_y, text, border_color):
        """Вспомогательный метод для аккуратной плашки с текстом."""
        surf = self.badge_font.render(text, True, (240, 240, 240))
        bg = surf.get_rect(midbottom=(cx, bottom_y)).inflate(10, 4)
        if -50 <= bg.centerx <= settings.WIDTH + 50 and -50 <= bg.centery <= settings.HEIGHT + 50:
            pygame.draw.rect(screen, (12, 14, 18), bg, border_radius=3)
            pygame.draw.rect(screen, border_color, bg, 1, border_radius=3)
            screen.blit(surf, surf.get_rect(center=bg.center))

    def _draw_axes_and_castles(self, screen):
        """Отрисовывает центральные оси мира, перекресток и Главные Замки."""
        axis_x, _ = self.world_to_screen(0, 0)
        _, axis_y = self.world_to_screen(0, 0)

        if 0 <= axis_x <= settings.WIDTH:
            pygame.draw.line(screen, (180, 160, 60), (axis_x, 0), (axis_x, settings.HEIGHT), 1)
        if 0 <= axis_y <= settings.HEIGHT:
            pygame.draw.line(screen, (180, 160, 60), (0, axis_y), (settings.WIDTH, axis_y), 1)

        self._draw_marker(screen, -1975, -975, "🏰 ЗАМОК СВЕТА (5x5 тайлов)", (80, 180, 255), 5 * self.tile_size)
        self._draw_marker(screen, 1975, 975, "🏰 ЦИТАДЕЛЬ ТЬМЫ (5x5 тайлов)", (255, 80, 80), 5 * self.tile_size)

        cx, cy = self.world_to_screen(0, 0)
        center_rect = pygame.Rect(cx - 25, cy - 25, 50, 50)
        pygame.draw.rect(screen, (220, 180, 40), center_rect, 2, border_radius=5)
        self._draw_badge(screen, cx, cy - 28, "⚔️ ЦЕНТР МИРА (0, 0)", (255, 215, 0))

    def _draw_marker(self, screen, wx, wy, title, color, size_px):
        """Отрисовывает рамку объекта и подпись."""
        sx, sy = self.world_to_screen(wx - size_px // 2, wy - size_px // 2)
        obj_rect = pygame.Rect(sx, sy, size_px, size_px)
        
        pygame.draw.rect(screen, color, obj_rect, 3, border_radius=4)
        
        title_surf = self.font.render(title, True, color)
        t_rect = title_surf.get_rect(midbottom=(obj_rect.centerx, obj_rect.top - 6))
        bg_rect = t_rect.inflate(12, 6)
        pygame.draw.rect(screen, (10, 12, 16), bg_rect, border_radius=4)
        pygame.draw.rect(screen, color, bg_rect, 1, border_radius=4)
        screen.blit(title_surf, t_rect)

    def _draw_hud(self, screen, hover_wx, hover_wy):
        """Верхняя панель управления и подсказок."""
        hud_bg = pygame.Rect(0, 0, settings.WIDTH, 75)
        pygame.draw.rect(screen, (15, 18, 22), hud_bg)
        pygame.draw.line(screen, (60, 70, 85), (0, 75), (settings.WIDTH, 75), 2)

        draw_button(screen, self.back_button, "В ТАВЕРНУ", self.font, color=(160, 70, 70))
        draw_button(screen, self.center_button, "ЦЕНТР (0, 0)", self.font, color=(70, 110, 150))
        draw_button(screen, self.light_castle_button, "ЗАМОК СВЕТА", self.font, color=(60, 120, 180))
        draw_button(screen, self.dark_castle_button, "ЦИТАДЕЛЬ ТЬМЫ", self.font, color=(180, 60, 60))

        hover_gx = int(hover_wx // self.tile_size)
        hover_gy = int(hover_wy // self.tile_size)
        hover_cx = hover_gx + 1 if hover_gx >= 0 else hover_gx
        hover_cy = hover_gy + 1 if hover_gy >= 0 else hover_gy

        info_str = f"Камера: X={int(self.camera_x)}, Y={int(self.camera_y)} | Курсор: WX={int(hover_wx)}, WY={int(hover_wy)} | Квадрат: {hover_cx}/{hover_cy}"
        info_surf = self.font.render(info_str, True, (240, 240, 240))
        screen.blit(info_surf, (680, 27))

        hint_str = "Управление: Перетаскивание мышью (ЛКМ) | Стрелки / WASD (+Shift для ускорения)"
        hint_surf = self.small_font.render(hint_str, True, (160, 170, 180))
        screen.blit(hint_surf, (20, settings.HEIGHT - 25))
