from pathlib import Path
import math
import random
import pygame
from core import settings
from ui.hud import draw_button


# Фразы при попытке взаимодействия с расстояния больше 1 тайла
TOO_FAR_PHRASES = [
    "Слишком далеко",
    "Мне не достать",
    "Нужно подойти ближе",
    "Это далеко",
    "Не дотянуться",
    "Сначала надо подойти",
    "Слишком большое расстояние",
    "Я не достаю отсюда",
    "Надо подойти вплотную",
    "Туда отсюда не достать",
]


# Направления в виде битовых флагов для автотайлинга дороги (классика HoMM3)
DIR_N = 1
DIR_E = 2
DIR_S = 4
DIR_W = 8

NEIGHBOR_OFFSETS = {
    DIR_N: (0, -1),
    DIR_E: (1, 0),
    DIR_S: (0, 1),
    DIR_W: (-1, 0),
}


def walk_grid_line(gx1, gy1, gx2, gy2):
    """
    Ортогональный обход клеток сетки (supercover line): каждый шаг двигается
    только по ОДНОЙ оси за раз, поэтому соседние клетки всегда соединены гранью
    (N/E/S/W), а не углом. Это обязательное условие для автотайлинга по битовой маске.
    """
    cells = [(gx1, gy1)]
    x, y = gx1, gy1
    dx = gx2 - gx1
    dy = gy2 - gy1
    sx = 1 if dx > 0 else -1 if dx < 0 else 0
    sy = 1 if dy > 0 else -1 if dy < 0 else 0
    adx, ady = abs(dx), abs(dy)
    err = adx - ady

    while x != gx2 or y != gy2:
        e2 = err * 2
        moved = False
        if e2 > -ady and x != gx2:
            err -= ady
            x += sx
            cells.append((x, y))
            moved = True
        if e2 < adx and y != gy2:
            err += adx
            y += sy
            cells.append((x, y))
            moved = True
        if not moved:
            break

    return cells


class WorldMapScene:
    """
    Сцена глобальной карты.
    Тайл: 32x32 пикселя.
    Размер карты: 512 тайлов по ширине (16384 px) x 256 тайлов по высоте (8192 px).
    Координатная сетка начинается с левого верхнего угла: (0, 0) = [0, 0].
    """

    def __init__(self, session):
        self.session = session
        self.finished = False
        self.cancelled = False
        self.navigate = None

        # Размеры сетки: 512 по X, 256 по Y
        self.grid_w = 512
        self.grid_h = 256
        self.tile_size = 32
        self.world_w = self.grid_w * self.tile_size  # 16384 px
        self.world_h = self.grid_h * self.tile_size  # 8192 px

        # Фиксированный масштаб (1.0x)
        self.zoom = 1.0

        # Границы мира: левый верхний угол (0, 0), правый нижний (world_w, world_h)
        self.min_world_x = 0
        self.max_world_x = self.world_w
        self.min_world_y = 0
        self.max_world_y = self.world_h

        # Базовый старт игрока (по центру карты или в свободной точке)
        self.player_x = float(self.world_w // 2)
        self.player_y = float(self.world_h // 2)
        self.player_target = None
        self.player_speed = 220.0
        self.player_state = "idle"
        self.player_direction = "s"  # Текущее направление (8 сторон: n, ne, e, se, s, sw, w, nw)
        self.player_anim_timer = 0.0
        self.click_effect = None

        # Камера центрируется на игроке
        self.camera_x = self.player_x
        self.camera_y = self.player_y
        self.camera_follow_player = True

        # Скролл карты перетаскиванием (drag)
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
        self.back_button = pygame.Rect(20, 20, 150, 45)
        self.center_button = pygame.Rect(180, 20, 150, 45)
        self.player_pos_button = pygame.Rect(340, 20, 160, 45)

        # Переключатель отображения тонкой сетки (клавиша G)
        self.show_grid = False

        # Интерактивные сущности, наведение (hover) и активное состояние (ЛКМ)
        self.hovered_entity = None
        self.active_entity = None
        self.drag_moved = False
        self.active_window_rect = pygame.Rect(settings.WIDTH - 390, settings.HEIGHT - 255, 365, 215)
        self.active_close_button = pygame.Rect(self.active_window_rect.right - 36, self.active_window_rect.top + 10, 26, 26)
        self.active_action_button = pygame.Rect(self.active_window_rect.left + 16, self.active_window_rect.bottom - 48, self.active_window_rect.width - 32, 34)
        self.action_notice = None
        self.action_notice_timer = 0.0

        # Всплывающие сообщения в игровом мире
        self.floating_messages = []
        self.last_too_far_phrase = None

        # Начальные тестовые интерактивные объекты:
        # 1. Походный военный лагерь: размер 4х4 тайла (128х128 px), вход — средний нижний тайл
        camp_gx, camp_gy = 260, 124
        camp_px = camp_gx * self.tile_size
        camp_py = camp_gy * self.tile_size

        # 2. Древний сундук: размер 1х1 тайл (32х32 px)
        chest_gx, chest_gy = 252, 128
        chest_px = chest_gx * self.tile_size
        chest_py = chest_gy * self.tile_size

        self.objects = [
            {
                "id": "camp_1",
                "name": "Походный лагерь",
                "type": "Строение 4х4",
                "tile_x": camp_gx,
                "tile_y": camp_gy,
                "tile_w": 4,
                "tile_h": 4,
                "x": camp_px + 64,
                "y": camp_py + 64,
                "radius": 56,
                "entrance_tile": (camp_gx + 1, camp_gy + 3),
                "approach_pos": (camp_px + 48, camp_py + 128 + 14),
                "desc": "Военный лагерь 4х4 тайла. Вход расположен по центру снизу. Непроходим для сквозного прохода.",
                "icon": "⛺",
                "solid_rects": [
                    pygame.Rect(camp_px, camp_py, 128, 96),          # верхние 3 ряда палатки
                    pygame.Rect(camp_px, camp_py + 96, 32, 32),      # левый нижний угол
                    pygame.Rect(camp_px + 64, camp_py + 96, 64, 32), # правые нижние тайлы
                ],
            },
            {
                "id": "chest_1",
                "name": "Древний сундук",
                "type": "Трофей 1х1",
                "tile_x": chest_gx,
                "tile_y": chest_gy,
                "tile_w": 1,
                "tile_h": 1,
                "x": chest_px + 16,
                "y": chest_py + 16,
                "radius": 18,
                "approach_pos": (chest_px + 16, chest_py + 44),
                "desc": "Древний кованый сундук 1х1 тайл. Заперт на крепкий замок.",
                "icon": "📦",
                "opened": False,
                "solid_rects": [
                    pygame.Rect(chest_px + 2, chest_py + 4, 28, 24)
                ],
            },
        ]

        # Загрузка 8-направленных спрайтов idle (из assets/2Idle/) и бега (из assets/3run/)
        self.player_directional_frames = {}
        self.player_run_directional_frames = {}
        self._load_player_directional_sprites()

    def _load_player_directional_sprites(self):
        """
        Загружает 8-направленные спрайты:
        1. Idle (assets/2Idle/) - по 4 кадра стойки на месте
        2. Run (assets/3run/) - по 6 кадров полноценного бега
        """
        target_h = 56
        directions = ["n", "ne", "e", "se", "s", "sw", "w", "nw"]

        # 1. Idle спрайты
        idle_dir = Path(__file__).resolve().parent.parent / "assets" / "2Idle"
        if idle_dir.is_dir():
            for d in directions:
                d_folder = idle_dir / d
                if not d_folder.is_dir():
                    continue
                frame_files = sorted([
                    f for f in d_folder.glob("*.png")
                    if not f.name.endswith("apng.png") and not f.name.endswith("spritesheet.png")
                ])
                if not frame_files:
                    continue
                sample = pygame.image.load(str(frame_files[0])).convert_alpha()
                crop_rect = sample.get_bounding_rect()
                if crop_rect.height <= 0:
                    continue
                ratio = target_h / float(crop_rect.height)
                target_w = max(1, int(crop_rect.width * ratio))
                frames = []
                for ff in frame_files:
                    try:
                        raw = pygame.image.load(str(ff)).convert_alpha()
                        cropped = raw.subsurface(crop_rect).copy()
                        scaled = pygame.transform.smoothscale(cropped, (target_w, target_h))
                        frames.append(scaled)
                    except Exception as e:
                        print(f"[WorldMapScene] Error loading idle {ff}: {e}")
                if frames:
                    self.player_directional_frames[d] = frames

        # 2. Run спрайты (бег)
        run_dir = Path(__file__).resolve().parent.parent / "assets" / "3run"
        if run_dir.is_dir():
            for d in directions:
                d_folder = run_dir / d
                if not d_folder.is_dir():
                    continue
                frame_files = sorted([
                    f for f in d_folder.glob("*.png")
                    if not f.name.endswith("apng.png") and not f.name.endswith("spritesheet.png")
                ])
                if not frame_files:
                    continue
                sample = pygame.image.load(str(frame_files[0])).convert_alpha()
                crop_rect = sample.get_bounding_rect()
                if crop_rect.height <= 0:
                    continue
                ratio = target_h / float(crop_rect.height)
                target_w = max(1, int(crop_rect.width * ratio))
                frames = []
                for ff in frame_files:
                    try:
                        raw = pygame.image.load(str(ff)).convert_alpha()
                        cropped = raw.subsurface(crop_rect).copy()
                        scaled = pygame.transform.smoothscale(cropped, (target_w, target_h))
                        frames.append(scaled)
                    except Exception as e:
                        print(f"[WorldMapScene] Error loading run {ff}: {e}")
                if frames:
                    self.player_run_directional_frames[d] = frames

    @staticmethod
    def _vector_to_direction(dx, dy):
        """Определяет одно из 8 направлений (n, ne, e, se, s, sw, w, nw) по вектору движения."""
        angle = math.degrees(math.atan2(dy, dx))  # 0 вправо (E), 90 вниз (S), -90 вверх (N)
        if -22.5 <= angle < 22.5:
            return "e"
        elif 22.5 <= angle < 67.5:
            return "se"
        elif 67.5 <= angle < 112.5:
            return "s"
        elif 112.5 <= angle < 157.5:
            return "sw"
        elif angle >= 157.5 or angle < -157.5:
            return "w"
        elif -157.5 <= angle < -112.5:
            return "nw"
        elif -112.5 <= angle < -67.5:
            return "n"
        else:
            return "ne"

    # ------------------------------------------------------------------
    # Камера: строго плоская top-down проекция
    # ------------------------------------------------------------------

    def world_to_screen(self, wx, wy, z=0):
        """
        Преобразование мировых координат в экранные пиксели.
        Плоскость земли строго плоская (как в оригинальных Героях 3).
        Параметр z поднимает объект вертикально вверх по экрану (для стен/крыш зданий).
        """
        sx = int((wx - self.camera_x) * self.zoom + settings.WIDTH / 2)
        sy = int((wy - self.camera_y - z) * self.zoom + settings.HEIGHT / 2)
        return sx, sy

    def screen_to_world(self, sx, sy):
        """Преобразование экранных пикселей в мировые координаты."""
        wx = (sx - settings.WIDTH / 2) / self.zoom + self.camera_x
        wy = (sy - settings.HEIGHT / 2) / self.zoom + self.camera_y
        return wx, wy

    def _clamp_camera(self):
        """Удержание камеры в пределах мира с учетом текущего зума."""
        half_screen_w = (settings.WIDTH / 2) / self.zoom
        half_screen_h = (settings.HEIGHT / 2) / self.zoom
        self.camera_x = max(self.min_world_x + half_screen_w, min(self.max_world_x - half_screen_w, self.camera_x))
        self.camera_y = max(self.min_world_y + half_screen_h, min(self.max_world_y - half_screen_h, self.camera_y))

    def _find_entity_at(self, screen_pos):
        """Находит интерактивную сущность (персонажа или объект карты) под экранными координатами курсора."""
        # 1. Проверяем персонажа игрока
        psx, psy = self.world_to_screen(self.player_x, self.player_y)
        player_rect = pygame.Rect(psx - 22, psy - 58, 44, 62)
        if player_rect.collidepoint(screen_pos):
            char_name = getattr(self.session, "character", {}).get("name", "Герой") if hasattr(self.session, "character") else "Герой"
            status_str = "Бежит" if self.player_state == "walk" else "В покое"
            return {
                "id": "player",
                "name": char_name,
                "type": "Игровой персонаж",
                "x": self.player_x,
                "y": self.player_y,
                "radius": 22,
                "desc": f"Ваш главный герой. Статус: {status_str}. Управляется кликом ПКМ.",
                "icon": "👤",
            }

        # 2. Проверяем объекты из self.objects (сверху вниз)
        for obj in reversed(self.objects):
            if obj.get("tile_w", 1) > 1:
                # Многоклеточный объект (например, лагерь 4х4)
                top_left_x = obj["tile_x"] * self.tile_size
                top_left_y = obj["tile_y"] * self.tile_size
                tw = obj["tile_w"] * self.tile_size
                th = obj["tile_h"] * self.tile_size
                sx, sy = self.world_to_screen(top_left_x, top_left_y)
                # Расширяем вверх на 22px для учета крыши/флага
                obj_rect = pygame.Rect(sx, sy - 22, tw, th + 22)
                if obj_rect.collidepoint(screen_pos):
                    return obj
            else:
                # Одноклеточный объект (например, сундук 1х1)
                ox, oy = obj["x"], obj["y"]
                sx, sy = self.world_to_screen(ox, oy)
                r = obj.get("radius", 20)
                if math.hypot(screen_pos[0] - sx, screen_pos[1] - sy) <= r + 6:
                    return obj

        return None

    def _is_within_one_tile(self, entity):
        """
        Проверяет, находится ли персонаж не дальше 1 тайла от места взаимодействия объекта.
        Для сундука (1x1) - соседние 8 тайлов вокруг сундука (max(|dx|, |dy|) <= 1).
        Для лагеря (4x4) - не дальше 1 тайла от входа (средний нижний тайл).
        """
        if not entity:
            return False
        if entity.get("id") == "player":
            return True

        pgx = int(self.player_x // self.tile_size)
        pgy = int(self.player_y // self.tile_size)

        entrance = entity.get("entrance_tile")
        if entrance:
            egx, egy = entrance
            # Игрок может стоять на тайле прямо перед входом (egy + 1) или на тайле входа / рядом с ним
            d1 = max(abs(pgx - egx), abs(pgy - (egy + 1)))
            d2 = max(abs(pgx - egx), abs(pgy - egy))
            return min(d1, d2) <= 1
        else:
            # Для объектов 1x1 или занимающих область
            tgx = entity.get("tile_x", int(entity.get("x", 0) // self.tile_size))
            tgy = entity.get("tile_y", int(entity.get("y", 0) // self.tile_size))
            tw = entity.get("tile_w", 1)
            th = entity.get("tile_h", 1)

            dx = 0
            if pgx < tgx:
                dx = tgx - pgx
            elif pgx >= tgx + tw:
                dx = pgx - (tgx + tw - 1)

            dy = 0
            if pgy < tgy:
                dy = tgy - pgy
            elif pgy >= tgy + th:
                dy = pgy - (tgy + th - 1)

            return max(dx, dy) <= 1

    def _on_too_far(self, entity):
        """Срабатывает при попытке взаимодействия с расстояния больше 1 тайла."""
        available = [p for p in TOO_FAR_PHRASES if p != self.last_too_far_phrase]
        phrase = random.choice(available) if available else TOO_FAR_PHRASES[0]
        self.last_too_far_phrase = phrase

        # Всплывающее диалоговое сообщение над персонажем в игровом мире
        self._add_floating_message(phrase, self.player_x, self.player_y - 34, (255, 110, 90))
        self.action_notice = phrase
        self.action_notice_timer = 2.2

    def _get_entity_approach_target(self, entity):
        """Возвращает точку входа/подхода к объекту, в которую персонаж может подойти вплотную."""
        if entity.get("approach_pos"):
            return entity["approach_pos"]

        ex = entity.get("x", self.player_x)
        ey = entity.get("y", self.player_y)
        dx = ex - self.player_x
        dy = ey - self.player_y
        dist = math.hypot(dx, dy)
        if dist > 0:
            stop_dist = entity.get("radius", 24) + 12
            return (ex - (dx / dist) * stop_dist, ey - (dy / dist) * stop_dist)
        return (ex, ey)

    def _trigger_active_action(self):
        """Обрабатывает нажатие кнопки действия в активном окне объекта."""
        if not self.active_entity:
            return

        eid = self.active_entity.get("id")
        if eid == "player":
            self.camera_x = self.player_x
            self.camera_y = self.player_y
            self.camera_follow_player = True
            self._clamp_camera()
            self._add_floating_message("Камера сфокусирована", self.player_x, self.player_y - 30, (100, 220, 255))
            self.action_notice = "Камера сфокусирована!"
            self.action_notice_timer = 2.0
            return

        # 1. Слишком далеко -> фраза и отказ во взаимодействии (персонаж не бежит сам)
        if not self._is_within_one_tile(self.active_entity):
            self._on_too_far(self.active_entity)
            return

        if eid == "camp_1":
            self._add_floating_message("Привал совершен! Силы восстановлены", self.player_x, self.player_y - 30, (100, 255, 140))
            self.action_notice = "Привал совершен! Силы восстановлены."
            self.action_notice_timer = 2.5
        elif eid == "chest_1":
            if not self.active_entity.get("opened"):
                self.active_entity["opened"] = True
                self.active_entity["desc"] = "Кованый сундук распахнут. Внутри мерцают золотые монеты и самоцветы."
                self._add_floating_message("Сундук открыт! +15 монет", self.active_entity["x"], self.active_entity["y"] - 24, (255, 220, 60))
                self.action_notice = "Сундук открыт! Получено 15 монет."
                self.action_notice_timer = 3.0
            else:
                self._add_floating_message("Сундук уже пуст", self.active_entity["x"], self.active_entity["y"] - 24, (200, 200, 200))
                self.action_notice = "Сундук уже пуст."
                self.action_notice_timer = 2.0
        else:
            self.action_notice = "Взаимодействие выполнено!"
            self.action_notice_timer = 2.0

    def _add_floating_message(self, text, wx, wy, color=(255, 220, 80)):
        """Добавляет всплывающее сообщение в игровом мире над объектом/персонажем."""
        self.floating_messages.append({
            "text": text,
            "world_x": float(wx),
            "world_y": float(wy),
            "timer": 1.9,
            "max_timer": 1.9,
            "color": color,
        })

    def _check_collision(self, px, py):
        """
        Проверяет коллизию ног персонажа с границами карты и твердыми препятствиями (зданиями, сундуками).
        Персонаж не может проходить сквозь твердые объекты.
        """
        if px - 10 < self.min_world_x or px + 10 > self.max_world_x:
            return True
        if py - 6 < self.min_world_y or py + 6 > self.max_world_y:
            return True

        feet_rect = pygame.Rect(int(px - 10), int(py - 6), 20, 10)
        for obj in self.objects:
            for s_rect in obj.get("solid_rects", []):
                if feet_rect.colliderect(s_rect):
                    return True
        return False

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.active_entity is not None:
                    self.active_entity = None
                    return
                self.cancelled = True
                self.finished = True
                return
            if event.key == pygame.K_g:
                self.show_grid = not self.show_grid
                return
            if event.key == pygame.K_SPACE:
                # Центрировать камеру на персонаже
                self.camera_x = self.player_x
                self.camera_y = self.player_y
                self.camera_follow_player = True
                self._clamp_camera()
                return

        # Нажатие кнопок мыши
        if event.type == pygame.MOUSEBUTTONDOWN:
            # ЛКМ: клик по кнопкам HUD, выбор/активация объекта или перетаскивание карты
            if event.button == 1:
                # 1. Верхний HUD
                if self.back_button.collidepoint(event.pos):
                    self.finished = True
                    return
                if self.center_button.collidepoint(event.pos):
                    self.camera_x = float(self.world_w // 2)
                    self.camera_y = float(self.world_h // 2)
                    self.camera_follow_player = False
                    self._clamp_camera()
                    return
                if self.player_pos_button.collidepoint(event.pos):
                    self.camera_x = self.player_x
                    self.camera_y = self.player_y
                    self.camera_follow_player = True
                    self._clamp_camera()
                    return

                # 2. Клик внутри активного окна (если открыто)
                if self.active_entity is not None and self.active_window_rect.collidepoint(event.pos):
                    if self.active_close_button.collidepoint(event.pos):
                        self.active_entity = None
                        return
                    if self.active_action_button.collidepoint(event.pos):
                        self._trigger_active_action()
                        return
                    return  # Поглощаем клик по телу окна

                # 3. Клик по интерактивному объекту или персонажу -> ДЕЛАЕМ АКТИВНЫМ (персонаж НЕ бежит)
                clicked_entity = self._find_entity_at(event.pos)
                if clicked_entity is not None:
                    self.active_entity = clicked_entity
                    self.action_notice = None
                    self.dragging = False
                    return

                # 4. Клик по пустой земле -> подготовка к драгу
                self.dragging = True
                self.drag_start_mouse = event.pos
                self.drag_start_camera = (self.camera_x, self.camera_y)
                self.drag_moved = False
                self.camera_follow_player = False

            # ПКМ (как в Dota/RTS/Diablo): отправить персонажа в точку клика
            elif event.button == 3:
                clicked_entity = self._find_entity_at(event.pos)
                if clicked_entity is not None and clicked_entity.get("id") != "player":
                    # Клик ПКМ по объекту -> подойти к объекту и упереться перед ним
                    target = self._get_entity_approach_target(clicked_entity)
                    tx, ty = target
                else:
                    wx, wy = self.screen_to_world(event.pos[0], event.pos[1])
                    tx = max(self.min_world_x + 16, min(self.max_world_x - 16, wx))
                    ty = max(self.min_world_y + 16, min(self.max_world_y - 16, wy))

                self.player_target = (tx, ty)
                self.player_state = "walk"
                dx = tx - self.player_x
                dy = ty - self.player_y
                if dx != 0 or dy != 0:
                    self.player_direction = self._vector_to_direction(dx, dy)
                self.player_facing_right = (dx >= 0)
                self.camera_follow_player = True
                self.click_effect = {"x": tx, "y": ty, "timer": 0.35}

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                if self.dragging and not self.drag_moved:
                    # Короткий клик на пустое место без движения мыши -> сбросить активность
                    self.active_entity = None
                self.dragging = False

        elif event.type == pygame.MOUSEMOTION:
            if self.dragging:
                dx = event.pos[0] - self.drag_start_mouse[0]
                dy = event.pos[1] - self.drag_start_mouse[1]
                if abs(dx) > 4 or abs(dy) > 4:
                    self.drag_moved = True
                    self.camera_x = self.drag_start_camera[0] - (dx / self.zoom)
                    self.camera_y = self.drag_start_camera[1] - (dy / self.zoom)
                    self.camera_follow_player = False
                    self._clamp_camera()

    def update(self, dt):
        # 1. Движение персонажа к целевой точке (Dota-стиль) с проверкой коллизий
        if self.player_target is not None:
            tx, ty = self.player_target
            dx = tx - self.player_x
            dy = ty - self.player_y
            dist = math.hypot(dx, dy)
            step = self.player_speed * dt

            if dist <= step or dist < 2.0:
                self.player_x = tx
                self.player_y = ty
                self.player_target = None
                self.player_state = "idle"
            else:
                vx = (dx / dist) * step
                vy = (dy / dist) * step

                moved_x = False
                moved_y = False

                if vx != 0:
                    new_x = self.player_x + vx
                    if not self._check_collision(new_x, self.player_y):
                        self.player_x = new_x
                        moved_x = True

                if vy != 0:
                    new_y = self.player_y + vy
                    if not self._check_collision(self.player_x, new_y):
                        self.player_y = new_y
                        moved_y = True

                if not moved_x and not moved_y:
                    # Персонаж уперся в объект и остановился перед ним
                    self.player_target = None
                    self.player_state = "idle"
                else:
                    self.player_state = "walk"
                    self.player_direction = self._vector_to_direction(dx, dy)
                    self.player_facing_right = (dx >= 0)

            # Плавное следование камеры за персонажем (если включено)
            if self.camera_follow_player:
                self.camera_x += (self.player_x - self.camera_x) * min(1.0, 8.0 * dt)
                self.camera_y += (self.player_y - self.camera_y) * min(1.0, 8.0 * dt)

        # 2. Анимационный таймер персонажа
        self.player_anim_timer += dt

        # 3. Эффект клика ПКМ (расходящийся круг)
        if self.click_effect is not None:
            self.click_effect["timer"] -= dt
            if self.click_effect["timer"] <= 0:
                self.click_effect = None

        # 4. Обновление плавающих сообщений
        for msg in self.floating_messages[:]:
            msg["timer"] -= dt
            msg["world_y"] -= 20.0 * dt
            if msg["timer"] <= 0:
                self.floating_messages.remove(msg)

        # 5. Определение сущности под курсором мыши (hover)
        m_pos = pygame.mouse.get_pos()
        if m_pos[1] <= 75 or (self.active_entity and self.active_window_rect.collidepoint(m_pos)):
            self.hovered_entity = None
        else:
            self.hovered_entity = self._find_entity_at(m_pos)

        # 6. Таймер уведомления о действии
        if self.action_notice_timer > 0:
            self.action_notice_timer -= dt
            if self.action_notice_timer <= 0:
                self.action_notice = None

        # 7. Скролл карты стрелками / WASD
        keys = pygame.key.get_pressed()
        speed = 850.0 * dt
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
            speed *= 2.2

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
            self.camera_follow_player = False
            self._clamp_camera()
        elif self.camera_follow_player:
            self._clamp_camera()

    # ------------------------------------------------------------------
    # Отрисовка
    # ------------------------------------------------------------------

    def draw(self, screen):
        screen.fill((20, 24, 28))

        top_left_wx, top_left_wy = self.screen_to_world(0, 0)
        bot_right_wx, bot_right_wy = self.screen_to_world(settings.WIDTH, settings.HEIGHT)

        start_gx = int(top_left_wx // self.tile_size) - 1
        end_gx = int(bot_right_wx // self.tile_size) + 2
        start_gy = int(top_left_wy // self.tile_size) - 1
        end_gy = int(bot_right_wy // self.tile_size) + 2

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

        # 1. Базовая земля (чистая плоская заливка top-down, без искажений)
        half_gy = self.grid_h // 2
        for gy in range(start_gy, end_gy):
            for gx in range(start_gx, end_gx):
                tile_wx = gx * self.tile_size
                tile_wy = gy * self.tile_size
                sx, sy = self.world_to_screen(tile_wx, tile_wy)
                sx2, sy2 = self.world_to_screen(tile_wx + self.tile_size, tile_wy + self.tile_size)

                rect = pygame.Rect(sx, sy, sx2 - sx + 1, sy2 - sy + 1)

                if gy < half_gy:
                    # Северная половина карты (Свет) - приглушенная зеленая трава
                    cell_color = (28, 42, 32) if (gx + gy) % 2 == 0 else (31, 46, 35)
                else:
                    # Южная половина карты (Тьма) - каменистая пустошь
                    cell_color = (36, 32, 34) if (gx + gy) % 2 == 0 else (40, 35, 38)

                pygame.draw.rect(screen, cell_color, rect)

                if self.show_grid:
                    pygame.draw.rect(screen, (45, 52, 60), rect, 1)

        # 2. Интерактивные объекты карты
        self._draw_objects(screen)

        # 3. Игровой персонаж и эффекты клика (Dota-стиль)
        self._draw_click_effect(screen)
        self._draw_player_character(screen)

        # 4. Всплывающие сообщения в мире ("Слишком далеко" и т.д.)
        self._draw_floating_messages(screen)

        # 5. Всплывающее окно активного объекта (ЛКМ)
        self._draw_active_window(screen)

        # 6. Всплывающее окно при наведении курсора (hover tooltip)
        self._draw_hover_popup(screen, mouse_pos)

        # 7. Верхний HUD и подсказки
        self._draw_hud(screen, hover_wx, hover_wy)

    def _draw_badge(self, screen, cx, bottom_y, text, border_color):
        """Вспомогательный метод для аккуратной плашки с текстом над объектом."""
        surf = self.badge_font.render(text, True, (240, 240, 240))
        bg = surf.get_rect(midbottom=(cx, bottom_y)).inflate(10, 4)
        if -50 <= bg.centerx <= settings.WIDTH + 50 and -50 <= bg.centery <= settings.HEIGHT + 50:
            pygame.draw.rect(screen, (12, 14, 18, 220), bg, border_radius=3)
            pygame.draw.rect(screen, border_color, bg, 1, border_radius=3)
            screen.blit(surf, surf.get_rect(center=bg.center))

    def _draw_objects(self, screen):
        """Отрисовывает интерактивные объекты карты из self.objects."""
        pulse = 1.0 + 0.12 * math.sin(self.player_anim_timer * 6.0)

        for obj in self.objects:
            if obj.get("id") == "camp_1":
                # Военный походный лагерь 4х4 тайла (128х128 px)
                top_left_x = obj["tile_x"] * self.tile_size
                top_left_y = obj["tile_y"] * self.tile_size
                sx, sy = self.world_to_screen(top_left_x, top_left_y)
                camp_rect = pygame.Rect(sx, sy, 128, 128)

                if not (-140 <= sx <= settings.WIDTH + 140 and -140 <= sy <= settings.HEIGHT + 140):
                    continue

                is_active = self.active_entity and self.active_entity.get("id") == obj["id"]
                is_hovered = self.hovered_entity and self.hovered_entity.get("id") == obj["id"]

                # Тень и расчищенная площадка лагеря
                pygame.draw.ellipse(screen, (35, 30, 22, 210), camp_rect.inflate(18, 12))
                pygame.draw.rect(screen, (55, 46, 32), camp_rect, border_radius=8)
                pygame.draw.rect(screen, (80, 68, 48), camp_rect, 2, border_radius=8)

                # Шатер лагеря (тяжелое военное полотно)
                tent_rect = pygame.Rect(camp_rect.left + 10, camp_rect.top + 8, camp_rect.width - 20, camp_rect.height - 24)
                tent_peak = (camp_rect.centerx, camp_rect.top - 18)

                roof_poly = [
                    tent_peak,
                    (tent_rect.right, tent_rect.top + 24),
                    (tent_rect.right, tent_rect.bottom - 10),
                    (tent_rect.left, tent_rect.bottom - 10),
                    (tent_rect.left, tent_rect.top + 24),
                ]
                pygame.draw.polygon(screen, (185, 145, 95), roof_poly)
                pygame.draw.polygon(screen, (140, 105, 65), roof_poly, 2)
                pygame.draw.line(screen, (140, 105, 65), tent_peak, (tent_rect.centerx, tent_rect.bottom - 10), 2)

                # Флагшток и знамя на вершине
                pygame.draw.line(screen, (60, 45, 30), tent_peak, (tent_peak[0], tent_peak[1] - 16), 2)
                pygame.draw.polygon(screen, (220, 60, 60), [
                    (tent_peak[0], tent_peak[1] - 16),
                    (tent_peak[0] + 16, tent_peak[1] - 11),
                    (tent_peak[0], tent_peak[1] - 6),
                ])

                # Вход в шатер на среднем нижнем тайле (ширина 28, высота 34)
                entry_left = camp_rect.left + 34
                entry_top = camp_rect.bottom - 36
                entry_rect = pygame.Rect(entry_left, entry_top, 28, 34)
                pygame.draw.polygon(screen, (30, 20, 15), [
                    (entry_rect.centerx, entry_rect.top),
                    (entry_rect.left, entry_rect.bottom),
                    (entry_rect.right, entry_rect.bottom),
                ])
                # Теплый свет фонаря внутри входа
                pygame.draw.circle(screen, (255, 170, 50, 180), (entry_rect.centerx, entry_rect.bottom - 10), 8)
                pygame.draw.circle(screen, (255, 230, 100), (entry_rect.centerx, entry_rect.bottom - 10), 3)

                # Маркер ВХОД
                entry_badge = self.grid_font.render("ВХОД", True, (255, 220, 100))
                eb_rect = entry_badge.get_rect(midtop=(entry_rect.centerx, entry_rect.bottom + 2))
                pygame.draw.rect(screen, (15, 18, 24, 210), eb_rect.inflate(6, 2), border_radius=2)
                screen.blit(entry_badge, eb_rect)

                # Костер рядом с шатром
                fire_x = camp_rect.right - 24
                fire_y = camp_rect.bottom - 20
                pygame.draw.circle(screen, (35, 30, 25), (fire_x, fire_y), 9)
                pygame.draw.circle(screen, (255, 120, 30), (fire_x, fire_y - 2), 5)
                pygame.draw.circle(screen, (255, 230, 80), (fire_x, fire_y - 3), 3)

                # Подсветка активного / наведенного
                if is_active:
                    ring_r = int(66 * pulse)
                    ring_surf = pygame.Surface((ring_r * 2 + 6, ring_r * 2 + 6), pygame.SRCALPHA)
                    pygame.draw.circle(ring_surf, (255, 215, 60, 220), (ring_r + 3, ring_r + 3), ring_r, 2)
                    screen.blit(ring_surf, (camp_rect.centerx - ring_r - 3, camp_rect.centery - ring_r - 3))
                elif is_hovered:
                    pygame.draw.rect(screen, (80, 200, 255), camp_rect.inflate(8, 8), 2, border_radius=10)

                # Бейдж названия над лагерем
                badge_color = (255, 215, 60) if is_active else (100, 200, 255) if is_hovered else (200, 190, 160)
                self._draw_badge(screen, camp_rect.centerx, tent_peak[1] - 22, f"⛺ {obj['name']} [4x4]", badge_color)

            elif obj.get("id") == "chest_1":
                # Сундук 1х1 тайл (32х32 px)
                top_left_x = obj["tile_x"] * self.tile_size
                top_left_y = obj["tile_y"] * self.tile_size
                sx, sy = self.world_to_screen(top_left_x + 16, top_left_y + 16)
                chest_rect = pygame.Rect(sx - 14, sy - 10, 28, 20)

                if not (-50 <= sx <= settings.WIDTH + 50 and -50 <= sy <= settings.HEIGHT + 50):
                    continue

                is_active = self.active_entity and self.active_entity.get("id") == obj["id"]
                is_hovered = self.hovered_entity and self.hovered_entity.get("id") == obj["id"]

                # Тень
                pygame.draw.ellipse(screen, (10, 14, 18, 170), (sx - 15, sy + 7, 30, 8))

                # Тело сундука
                pygame.draw.rect(screen, (120, 80, 45), chest_rect, border_radius=3)
                pygame.draw.rect(screen, (60, 40, 20), chest_rect, 2, border_radius=3)
                pygame.draw.line(screen, (180, 170, 160), (chest_rect.left + 6, chest_rect.top), (chest_rect.left + 6, chest_rect.bottom), 2)
                pygame.draw.line(screen, (180, 170, 160), (chest_rect.right - 7, chest_rect.top), (chest_rect.right - 7, chest_rect.bottom), 2)

                if obj.get("opened"):
                    # Откинутая назад крышка
                    lid_poly = [
                        (chest_rect.left - 2, chest_rect.top - 8),
                        (chest_rect.right + 2, chest_rect.top - 8),
                        (chest_rect.right, chest_rect.top + 2),
                        (chest_rect.left, chest_rect.top + 2),
                    ]
                    pygame.draw.polygon(screen, (90, 60, 35), lid_poly)
                    pygame.draw.polygon(screen, (60, 40, 20), lid_poly, 1)
                    # Сияние сокровищ внутри (золото и рубин)
                    pygame.draw.circle(screen, (255, 215, 0), (sx - 4, sy - 3), 3)
                    pygame.draw.circle(screen, (255, 230, 80), (sx + 3, sy - 4), 3)
                    pygame.draw.polygon(screen, (230, 40, 60), [(sx, sy - 6), (sx - 3, sy - 2), (sx, sy), (sx + 3, sy - 2)])
                else:
                    # Запертый замок
                    pygame.draw.circle(screen, (240, 200, 70), (sx, sy - 1), 3)
                    pygame.draw.line(screen, (240, 200, 70), (sx, sy - 1), (sx, sy + 3), 2)

                # Подсветка
                if is_active:
                    pygame.draw.circle(screen, (255, 215, 60), (sx, sy), 22, 2)
                elif is_hovered:
                    pygame.draw.circle(screen, (80, 200, 255), (sx, sy), 22, 2)

                badge_status = " [Открыт]" if obj.get("opened") else " [Заперт]"
                badge_color = (255, 215, 60) if is_active else (100, 200, 255) if is_hovered else (200, 190, 160)
                self._draw_badge(screen, sx, sy - 22, f"📦 {obj['name']}{badge_status}", badge_color)

    def _draw_floating_messages(self, screen):
        """Отрисовывает всплывающие сообщения в мире ('Слишком далеко' и т.д.)."""
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

    def _draw_hover_popup(self, screen, mouse_pos):
        """Отрисовывает всплывающее окно (tooltip) при наведении курсора на объект."""
        if self.hovered_entity is None:
            return

        if self.active_entity and self.active_entity.get("id") == self.hovered_entity.get("id"):
            return

        ent = self.hovered_entity
        mx, my = mouse_pos

        box_w = 300
        box_h = 115
        box_x = mx + 16
        box_y = my + 16

        if box_x + box_w > settings.WIDTH - 12:
            box_x = mx - box_w - 12
        if box_y + box_h > settings.HEIGHT - 12:
            box_y = my - box_h - 12
        if box_y < 80:
            box_y = 80

        popup_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        pygame.draw.rect(popup_surf, (18, 24, 32, 235), (0, 0, box_w, box_h), border_radius=6)
        pygame.draw.rect(popup_surf, (80, 190, 255, 255), (0, 0, box_w, box_h), width=2, border_radius=6)
        screen.blit(popup_surf, (box_x, box_y))

        icon = ent.get("icon", "📍")
        name = ent.get("name", "Объект")
        title_surf = self.small_font.render(f"{icon} {name}", True, (255, 230, 140))
        screen.blit(title_surf, (box_x + 12, box_y + 10))

        type_str = ent.get("type", "Объект")
        type_surf = self.grid_font.render(f"[{type_str}]", True, (130, 200, 255))
        screen.blit(type_surf, (box_x + 12, box_y + 32))

        gx = int(ent.get("x", 0) // self.tile_size)
        gy = int(ent.get("y", 0) // self.tile_size)
        coord_surf = self.grid_font.render(f"Тайл: [{gx}, {gy}]", True, (170, 180, 190))
        screen.blit(coord_surf, (box_x + box_w - coord_surf.get_width() - 12, box_y + 32))

        desc = ent.get("desc", "")
        if len(desc) > 44:
            desc = desc[:41] + "..."
        desc_surf = self.grid_font.render(desc, True, (200, 210, 220))
        screen.blit(desc_surf, (box_x + 12, box_y + 54))

        # Статус дистанции
        in_range = self._is_within_one_tile(ent)
        if ent.get("id") == "player":
            status_text = "● Персонаж готов к управлению"
            status_col = (100, 220, 255)
        elif in_range:
            status_text = "● Рядом (дистанция <= 1 тайл)"
            status_col = (80, 255, 120)
        else:
            status_text = "○ Слишком далеко (кликните, чтобы подойти)"
            status_col = (255, 160, 90)
        range_surf = self.grid_font.render(status_text, True, status_col)
        screen.blit(range_surf, (box_x + 12, box_y + 74))

        hint_surf = self.grid_font.render("🖱️ ЛКМ - сделать активным", True, (140, 255, 180))
        screen.blit(hint_surf, (box_x + 12, box_y + 92))

    def _draw_active_window(self, screen):
        """Отрисовывает окно активного объекта (выбранного по ЛКМ)."""
        if self.active_entity is None:
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

        gx = int(ent.get("x", 0) // self.tile_size)
        gy = int(ent.get("y", 0) // self.tile_size)

        # Статус дистанции до объекта в активном окне
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
            elif ent.get("id") == "chest_1":
                action_label = "ОСМОТРЕТЬ" if ent.get("opened") else "ОТКРЫТЬ СУНДУК"
            elif ent.get("id") == "camp_1":
                action_label = "СДЕЛАТЬ ПРИВАЛ"
            else:
                action_label = "ВЗАИМОДЕЙСТВОВАТЬ"

            btn_hover = self.active_action_button.collidepoint(m_pos)
            if ent.get("id") == "player" or in_range:
                # В зоне действия - активная синяя кнопка
                btn_col = (70, 120, 180) if btn_hover else (45, 80, 130)
                text_col = (255, 255, 255)
            else:
                # Вне зоны действия - серая неактивная кнопка
                btn_col = (75, 75, 80) if btn_hover else (55, 55, 60)
                text_col = (170, 170, 175)

            draw_button(screen, self.active_action_button, action_label, self.small_font, color=btn_col, text_color=text_col)

    def _draw_click_effect(self, screen):
        """Отрисовывает расходящийся маркер клика ПКМ (Dota-стиль)."""
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
        """
        Отрисовывает персонажа:
        - В движении (walk): 8-направленный бег (assets/3run/), 6 кадров по направлению движения.
        - В покое (idle): 8-направленная стойка с дыханием (assets/2Idle/), 4 кадра.
        - Процедурный чиби-воин как фолбэк при отсутствии файлов.
        """
        sx, sy = self.world_to_screen(self.player_x, self.player_y)

        # Тень под ногами
        pygame.draw.ellipse(screen, (10, 12, 16, 170), (sx - 14, sy - 4, 28, 10))

        # Подсветка персонажа если активен или под курсором
        is_player_active = self.active_entity and self.active_entity.get("id") == "player"
        is_player_hovered = self.hovered_entity and self.hovered_entity.get("id") == "player"
        if is_player_active:
            pulse = 1.0 + 0.12 * math.sin(self.player_anim_timer * 6.0)
            p_ring_r = int(22 * pulse)
            p_ring_surf = pygame.Surface((p_ring_r * 2 + 6, p_ring_r * 2 + 6), pygame.SRCALPHA)
            pygame.draw.circle(p_ring_surf, (255, 215, 60, 220), (p_ring_r + 3, p_ring_r + 3), p_ring_r, 2)
            screen.blit(p_ring_surf, (sx - p_ring_r - 3, sy - p_ring_r - 3))
        elif is_player_hovered:
            pygame.draw.circle(screen, (80, 200, 255), (sx, sy), 22, 2)

        # Выбираем активный набор кадров (бег или покой)
        if self.player_state == "walk" and self.player_run_directional_frames:
            frames_dict = self.player_run_directional_frames
            anim_fps = 10.0  # Энергичный бег (10 кадров/сек)
        else:
            frames_dict = self.player_directional_frames
            anim_fps = 4.0   # Спокойное дыхание на месте (4 кадра/сек)

        direction_frames = frames_dict.get(self.player_direction)
        if not direction_frames and frames_dict:
            direction_frames = next(iter(frames_dict.values()))

        if direction_frames:
            frame_idx = int(self.player_anim_timer * anim_fps) % len(direction_frames)
            frame_surf = direction_frames[frame_idx]

            # Ноги персонажа касаются земли в точке (sx, sy)
            frame_rect = frame_surf.get_rect(midbottom=(sx, sy))
            screen.blit(frame_surf, frame_rect)
            name_y = frame_rect.top - 4
        else:
            # Процедурный чиби-воин (фолбэк)
            bob_y = int(math.sin(self.player_anim_timer * 14.0) * 2.5) if self.player_state == "walk" else int(math.sin(self.player_anim_timer * 4.0))
            cy = sy + bob_y
            facing = 1 if self.player_facing_right else -1

            cape_points = [(sx - 5 * facing, cy - 4), (sx - 12 * facing, cy + 8), (sx - 4 * facing, cy + 9)]
            pygame.draw.polygon(screen, (34, 110, 55), cape_points)

            body_rect = pygame.Rect(sx - 6, cy - 6, 12, 13)
            pygame.draw.rect(screen, (85, 115, 145), body_rect, border_radius=2)
            pygame.draw.rect(screen, (40, 60, 80), body_rect, 1, border_radius=2)

            leg_offset = int(math.sin(self.player_anim_timer * 14.0) * 2) if self.player_state == "walk" else 0
            pygame.draw.rect(screen, (50, 65, 80), (sx - 5, cy + 7 - leg_offset, 4, 5))
            pygame.draw.rect(screen, (50, 65, 80), (sx + 1, cy + 7 + leg_offset, 4, 5))

            pygame.draw.circle(screen, (220, 195, 160), (sx, cy - 11), 6)
            pygame.draw.rect(screen, (215, 180, 75), (sx - 6, cy - 17, 12, 7), border_radius=2)
            pygame.draw.line(screen, (40, 160, 70), (sx - 2 * facing, cy - 17), (sx - 6 * facing, cy - 22), 2)
            name_y = cy - 23

        # Маркер имени игрока над головой
        char_name = getattr(self.session, "character", {}).get("name", "Герой") if hasattr(self.session, "character") else "Герой"
        name_surf = self.grid_font.render(char_name, True, (255, 235, 150))
        n_rect = name_surf.get_rect(midbottom=(sx, name_y))
        bg = n_rect.inflate(8, 2)
        pygame.draw.rect(screen, (15, 18, 24, 210), bg, border_radius=3)
        pygame.draw.rect(screen, (180, 150, 60), bg, 1, border_radius=3)
        screen.blit(name_surf, n_rect)

    def _draw_hud(self, screen, hover_wx, hover_wy):
        """Верхняя панель управления и подсказок."""
        hud_bg = pygame.Rect(0, 0, settings.WIDTH, 75)
        pygame.draw.rect(screen, (15, 18, 22), hud_bg)
        pygame.draw.line(screen, (60, 70, 85), (0, 75), (settings.WIDTH, 75), 2)

        draw_button(screen, self.back_button, "В ТАВЕРНУ", self.font, color=(160, 70, 70))
        draw_button(screen, self.center_button, "ЦЕНТР КАРТЫ", self.font, color=(70, 110, 150))
        draw_button(screen, self.player_pos_button, "К ГЕРОЮ", self.font, color=(60, 120, 180))

        hover_gx = int(hover_wx // self.tile_size)
        hover_gy = int(hover_wy // self.tile_size)

        info_str = f"Карта: 512x256 (32px) | Персонаж: X={int(self.player_x)}, Y={int(self.player_y)} | Тайл: [{hover_gx}, {hover_gy}]"
        info_surf = self.font.render(info_str, True, (240, 240, 240))
        screen.blit(info_surf, (640, 27))

        hint_str = "ЛКМ - активировать объект | Наведение - всплывающее окно | ПКМ - бежать | Drag ЛКМ - скролл | G - Сетка"
        hint_surf = self.small_font.render(hint_str, True, (160, 170, 180))
        screen.blit(hint_surf, (20, settings.HEIGHT - 25))

    def close(self):
        pass

