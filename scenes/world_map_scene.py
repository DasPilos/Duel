from pathlib import Path
import math
import random
import time
import pygame
from core import settings
from core.carry_weight import character_movement_speed_multiplier
from core.production_buildings import plot_slot_ranges
from client.network import ServerError
from client.structures import hydrate_structures
from ui.hud import draw_button
from ui.character_profile_overlay import CharacterProfileOverlay
from ui.chat import ChatPanel
from ui.afk_presence import draw_afk_players
from ui.catalog_icons import draw_building_icon
from ui.production_building_window import VIEWS, ProductionBuildingWindow, object_building, point_in_polygon


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

    def __init__(self, session, spawn_gate=None, spawn_pos=None):
        self.session = session
        refresh_carrying_state = getattr(session, "refresh_carrying_state", None)
        if refresh_carrying_state is not None:
            try:
                refresh_carrying_state()
            except Exception:
                pass
        self.finished = False
        self.cancelled = False
        self.navigate = None
        self.city_gate = None

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

        # Точки появления при выходе из ворот города Радбург:
        gate_spawns = {
            "east": (75 * self.tile_size + 16, 53 * self.tile_size + 16, "e"),
            "main": (75 * self.tile_size + 16, 53 * self.tile_size + 16, "e"),
            "north": (67 * self.tile_size + 16, 45 * self.tile_size + 16, "n"),
            "south": (67 * self.tile_size + 16, 61 * self.tile_size + 16, "s"),
            "west": (59 * self.tile_size + 16, 53 * self.tile_size + 16, "w"),
        }

        if spawn_pos is not None:
            self.player_x = float(spawn_pos[0])
            self.player_y = float(spawn_pos[1])
            self.player_direction = spawn_pos[2] if len(spawn_pos) > 2 else "s"
        elif spawn_gate in gate_spawns:
            sp = gate_spawns[spawn_gate]
            self.player_x = float(sp[0])
            self.player_y = float(sp[1])
            self.player_direction = sp[2]
        else:
            # Базовый старт игрока (по центру карты или в свободной точке)
            self.player_x = float(self.world_w // 2)
            self.player_y = float(self.world_h // 2)
            self.player_direction = "s"

        self.player_target = None
        self.player_speed = 220.0
        self.player_state = "idle"
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
        self.profile_overlay = CharacterProfileOverlay(
            self.small_font,
            collection_loader=getattr(self.session, "get_card_collection", None),
            deck_loader=getattr(self.session, "get_decks", None),
            deck_creator=getattr(self.session, "create_deck", None),
        )
        self.chat = (ChatPanel(session, "world_map", profile_overlay=self.profile_overlay)
                     if hasattr(session, "social_snapshot") else None)

        # UI элементы
        self.player_pos_button = pygame.Rect(20, 20, 160, 45)

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

        # Окна производственных зданий (поселение, лагерь лесорубов); открыто не больше одного
        self.building_windows = {building: ProductionBuildingWindow(self, building) for building in VIEWS}
        self.building_window = None

        # Всплывающие сообщения в игровом мире
        self.floating_messages = []
        self.last_too_far_phrase = None

        # Строения карты живут на сервере и приходят вместе с рельефом (_load_terrain)
        self.objects = []

        self.obstacles = self._load_terrain()

        # Анимация строения лесника 10х10 тайлов (3 кадра анимации дыма из assets/forester's1.png)
        self.forester_frames = []
        self._load_forester_sprite()

        # Загрузка 8-направленных спрайтов idle (из assets/2Idle/) и бега (из assets/3run/)
        self.player_directional_frames = {}
        self.player_run_directional_frames = {}
        self._load_player_directional_sprites()
        self._restore_player_work()

    def _restore_player_work(self):
        client = getattr(self.session, "client", None)
        get_player_work = getattr(client, "get_player_work", None)
        if get_player_work is None:
            return
        try:
            work = get_player_work(self.session.character["id"])
        except (ServerError, KeyError, AttributeError, OSError):
            return
        if not work:
            return

        building = work.get("building")
        window = self.building_windows.get(building)
        if window is None or not window.load():
            return
        slot_index = int(work["slot_index"])
        character_worker_id = f"player:{self.session.character['id']}"
        if not any(
            slot.get("slot_index") == slot_index and slot.get("worker_id") == character_worker_id
            for slot in window._state().get("worker_slots", [])
        ):
            return

        selected_plot = next(
            (index for index, slots in enumerate(plot_slot_ranges(building)) if slot_index in slots),
            None,
        )
        if selected_plot is None:
            return
        window.selected_plot = selected_plot
        window.tab = "production"
        window.is_open = True
        self.building_window = window

    @staticmethod
    def cart_travel_seconds(tile_count):
        """Время в пути повозки по грунтовой дороге для заданного числа тайлов (базовая скорость: 1 тайл = 60 сек)."""
        return tile_count * settings.CART_ROAD_SECONDS_PER_TILE

    def _load_forester_sprite(self):
        """
        Нарезает и масштабирует 3 кадра анимации дыма хижины лесника под размер 10х10 тайлов (320х320 px).
        Спрайтшит содержит 3 фазы дыма из трубы.
        """
        forester_path = Path(__file__).resolve().parent.parent / "assets" / "forester's1.png"
        if forester_path.is_file():
            try:
                sheet = pygame.image.load(str(forester_path)).convert_alpha()
                target_size = (10 * self.tile_size, 10 * self.tile_size)
                # Точные смещения для 3 кадров с идеальным выравниванием домика и трубы
                frame_w, frame_h = 238, 330
                shifts = [-240, 0, 239]
                self.forester_frames = []
                for shift in shifts:
                    frame_surf = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
                    frame_surf.blit(sheet, (0, 0), pygame.Rect(237 + shift, 85, frame_w, frame_h))
                    scaled_frame = pygame.transform.smoothscale(frame_surf, target_size)
                    self.forester_frames.append(scaled_frame)
            except Exception as e:
                print(f"Ошибка загрузки спрайта лесника: {e}")

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
        Для замка с несколькими входами - не дальше 1 тайла от любого из 4 ворот.
        """
        if not entity:
            return False
        if entity.get("id") == "player":
            return True

        pgx = int(self.player_x // self.tile_size)
        pgy = int(self.player_y // self.tile_size)

        # Объект с несколькими входами (например, замок с 4 воротами)

        entrances = entity.get("entrances")
        if entrances:
            for ent_info in entrances:
                for (egx, egy) in ent_info.get("tiles", []):
                    if max(abs(pgx - egx), abs(pgy - egy)) <= 1:
                        return True
            return False

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
        # Для замка с несколькими входами выбираем ближайший вход к текущей позиции персонажа
        if entity.get("entrances"):
            best_pos = None
            min_dist = float("inf")
            for ent_info in entity["entrances"]:
                ap = ent_info.get("approach_pos")
                if ap:
                    d = math.hypot(ap[0] - self.player_x, ap[1] - self.player_y)
                    if d < min_dist:
                        min_dist = d
                        best_pos = ap
            if best_pos:
                return best_pos

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
            self.profile_overlay.open(self.session.character, None)
            self.action_notice = None
            return

        # 1. Слишком далеко -> фраза и отказ во взаимодействии (персонаж не бежит сам)
        if not self._is_within_one_tile(self.active_entity):
            self._on_too_far(self.active_entity)
            return

        building = object_building(eid)
        if building is not None:
            self.building_window = self.building_windows[building]
            self.building_window.open()
            return
        if eid in ("town_radburg", "main_castle"):
            gate = self._get_nearest_gate(self.active_entity)
            self.navigate = "city"
            self.city_gate = gate
            self.finished = True
            return
        else:
            self.action_notice = "Взаимодействие выполнено!"
            self.action_notice_timer = 2.0

    def _get_nearest_gate(self, entity):
        """Определяет ближайшие к персонажу ворота города."""
        best_gate = "east"
        min_dist = float("inf")
        for ent_info in entity.get("entrances", []):
            ap = ent_info.get("approach_pos")
            if ap:
                d = math.hypot(ap[0] - self.player_x, ap[1] - self.player_y)
                if d < min_dist:
                    min_dist = d
                    best_gate = ent_info.get("id", "east")
        return best_gate

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
        for obstacle in self.obstacles:
            if (obstacle["bounds"].collidepoint(px, py) and point_in_polygon((px, py), obstacle["points"])
                    and not any(passage.collidepoint(px, py) for passage in obstacle["passages"])):
                return True
        return False

    def _load_terrain(self):
        """Рельеф, строения и проложенные сервером дороги приходят готовыми для отрисовки."""
        try:
            terrain = self.session.client.get_map_terrain()
        except (ServerError, AttributeError, KeyError, OSError):
            self.road_tiles = set()
            self.road_travel_seconds = 0
            return []
        self.objects = hydrate_structures(terrain.get("objects", []))
        roads = terrain.get("roads", {})
        self.road_tiles = {tuple(tile) for tile in roads.get("tiles", [])}
        self.road_routes = roads.get("routes", [])
        self.road_travel_seconds = roads.get("travel_seconds", 0)
        obstacles = []
        for obstacle in terrain.get("obstacles", []):
            points = [tuple(point) for point in obstacle["points"]]
            xs = [x for x, _ in points]
            ys = [y for _, y in points]
            bounds = pygame.Rect(min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)
            passages = [pygame.Rect(passage) for passage in obstacle.get("passages", [])]
            if obstacle.get("type") == "forest":
                surface, origin = self._render_forest(points, obstacle.get("trees", []))
            elif obstacle.get("type") == "lake":
                water_points = [tuple(point) for point in obstacle["water_points"]]
                surface, origin = self._render_lake(points, water_points, obstacle.get("sandy_shore_sections", []))
            else:
                surface, origin = self._render_mountains(points, obstacle.get("peaks", []), passages)
            obstacles.append({
                **obstacle, "points": points, "bounds": bounds, "passages": passages, "surface": surface, "origin": origin,
            })
        return obstacles

    @staticmethod
    def _render_mountains(points, peaks, passages=()):
        """Один раз рисует массив: каменистое подножие и вершины с светлым/тёмным склоном и снегом."""
        xs = [x for x, _ in points]
        ys = [y for _, y in points]
        top = min([min(ys)] + [peak["y"] - peak["h"] for peak in peaks])
        left, right, bottom = min(xs), max(xs), max(ys)
        surface = pygame.Surface((right - left + 1, bottom - top + 1), pygame.SRCALPHA)
        local = [(x - left, y - top) for x, y in points]
        pygame.draw.polygon(surface, (62, 64, 50), local)
        pygame.draw.polygon(surface, (40, 40, 32), local, 6)
        for peak in peaks:
            x, y, w, h = peak["x"] - left, peak["y"] - top, peak["w"], peak["h"]
            if peak.get("kind") == "hill":
                # Низкий холм: округлый бугор, светлый слева и тёмный справа
                arc = [(x - w / 2 + w * i / 12, y - h * math.sin(math.pi * i / 12)) for i in range(13)]
                pygame.draw.polygon(surface, (96, 102, 70), arc)
                pygame.draw.polygon(surface, (72, 76, 54), arc[6:] + [(x, y)])
                pygame.draw.lines(surface, (48, 50, 38), False, arc[6:], 2)
                continue
            apex = (x, y - h)
            ridge = (x + w * 0.08, y)
            pygame.draw.polygon(surface, (118, 110, 100), [(x - w / 2, y), apex, ridge])
            pygame.draw.polygon(surface, (72, 66, 62), [ridge, apex, (x + w / 2, y)])
            # Снег только на высоких вершинах, у самых больших шапка больше
            if h >= 160:
                snow = 0.22 if h < 300 else 0.32
                pygame.draw.polygon(surface, (235, 238, 242), [
                    (apex[0] - w / 2 * snow, apex[1] + h * snow), apex, (apex[0] + w / 2 * snow, apex[1] + h * snow),
                ])
            pygame.draw.line(surface, (40, 36, 34), apex, (x + w / 2, y), 2)
        # Прорубленный проход: земля видна, по краям тёмные скалы
        local_passages = [passage.move(-left, -top) for passage in passages]
        for local_passage in local_passages:
            surface.fill((0, 0, 0, 0), local_passage)

        def rock_side(point):
            # Кромка рисуется только там, где по ту сторону — скала, а не другой проход
            return point_in_polygon(point, local) and not any(other.collidepoint(point) for other in local_passages)

        for local_passage in local_passages:
            for edge_x, out in ((local_passage.left, -3), (local_passage.right, 3)):
                for y in range(local_passage.top, local_passage.bottom, 8):
                    if rock_side((edge_x + out, y + 4)):
                        pygame.draw.line(surface, (30, 27, 25), (edge_x, y), (edge_x, y + 8), 5)
            for edge_y, out in ((local_passage.top, -3), (local_passage.bottom, 3)):
                for x in range(local_passage.left, local_passage.right, 8):
                    if rock_side((x + 4, edge_y + out)):
                        pygame.draw.line(surface, (30, 27, 25), (x, edge_y), (x + 8, edge_y), 5)
        return surface, (left, top)

    @staticmethod
    def _render_forest(points, trees):
        """Густой лес: тёмная подложка по контуру и кроны деревьев с тенью и бликом."""
        margin = 30
        xs = [x for x, _ in points]
        ys = [y for _, y in points]
        left, top = min(xs) - margin, min(ys) - margin
        surface = pygame.Surface((max(xs) - left + margin, max(ys) - top + margin), pygame.SRCALPHA)
        local = [(x - left, y - top) for x, y in points]
        pygame.draw.polygon(surface, (16, 32, 18), local)
        for tree in trees:
            x, y, r = tree["x"] - left, tree["y"] - top, tree["r"]
            shade = (x * 7 + y * 3) % 18
            pygame.draw.circle(surface, (10, 22, 12), (x + 4, y + 6), r)
            pygame.draw.circle(surface, (26 + shade, 66 + shade, 32 + shade // 2), (x, y), r)
            pygame.draw.circle(surface, (44 + shade, 98 + shade, 46), (x - r // 3, y - r // 3), r // 2)
        return surface, (left, top)

    @staticmethod
    def _render_lake(points, water_points, sandy_sections):
        """Плавное фантазийное озеро: бирюзовая вода, камышово-зелёный берег и песчаные участки."""
        xs = [x for x, _ in points]
        ys = [y for _, y in points]
        left, top = min(xs), min(ys)
        surface = pygame.Surface((max(xs) - left + 1, max(ys) - top + 1), pygame.SRCALPHA)
        shore = [(x - left, y - top) for x, y in points]
        water = [(x - left, y - top) for x, y in water_points]
        pygame.draw.polygon(surface, (74, 91, 61), shore)

        count = len(shore)
        for start, finish in sandy_sections:
            first, last = int(start * count), int(finish * count)
            section = shore[first:last + 1]
            if len(section) > 1:
                pygame.draw.lines(surface, (194, 169, 112), False, section, 22)
                pygame.draw.lines(surface, (220, 197, 143), False, section, 12)

        pygame.draw.polygon(surface, (28, 100, 132), water)
        pygame.draw.polygon(surface, (77, 158, 174), water, 3)
        inner = [(x + (sum(p[0] for p in water) / len(water) - x) * 0.08,
                  y + (sum(p[1] for p in water) / len(water) - y) * 0.08) for x, y in water]
        pygame.draw.lines(surface, (112, 189, 190), True, inner, 2)

        for index in range(72):
            x = 22 + (index * 97) % max(24, surface.get_width() - 44)
            y = 18 + (index * 61) % max(24, surface.get_height() - 36)
            if point_in_polygon((x, y), water):
                length = 5 + index % 13
                color = (119, 192, 194, 170) if index % 3 else (18, 73, 104, 180)
                pygame.draw.arc(surface, color, (x, y, length * 2, 7), 0.2, 2.7, 2)

        return surface, (left, top)

    def _draw_terrain(self, screen):
        for obstacle in self.obstacles:
            sx, sy = self.world_to_screen(*obstacle["origin"])
            surface = obstacle["surface"]
            if sx < settings.WIDTH and sy < settings.HEIGHT and sx + surface.get_width() > 0 and sy + surface.get_height() > 0:
                screen.blit(surface, (sx, sy))

    def handle_event(self, event):
        if self.profile_overlay.is_open:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.profile_overlay.close()
                return
            if self.profile_overlay.handle_event(event):
                return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                action, profile = self.profile_overlay.handle_click(event.pos)
                if action == "stat_change":
                    self._save_profile_card(profile)
                elif action == "deck_selected":
                    self.session.selected_deck = profile
                return

        if self.chat is not None and self.chat.handle_event(event):
            return

        # Окно здания поглощает остальные взаимодействия с картой
        if self.building_window is not None:
            self.building_window.handle_event(event)
            if not self.building_window.is_open:
                self.building_window = None
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.active_entity is not None:
                    self.active_entity = None
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

    def _save_profile_card(self, profile):
        try:
            saved_profile = self.session.save_character_profile(profile)
        except ServerError as error:
            self.action_notice = str(error)
            self.action_notice_timer = 2.0
            return
        if saved_profile is not None:
            self.profile_overlay.update_profile(saved_profile)

    def update(self, dt):
        if self.chat is not None:
            self.chat.update(dt)
        # 1. Движение персонажа к целевой точке (Dota-стиль) с проверкой коллизий
        if self.player_target is not None:
            tx, ty = self.player_target
            dx = tx - self.player_x
            dy = ty - self.player_y
            dist = math.hypot(dx, dy)
            step = self.player_speed * character_movement_speed_multiplier(
                getattr(self.session, "character", None)
            ) * dt

            if dist <= step or dist < 2.0:
                if not self._check_collision(tx, ty):
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

        # Проверка наступления персонажа на ворота города Радбург на глобальной карте
        pgx = int(self.player_x // self.tile_size)
        pgy = int(self.player_y // self.tile_size)
        for obj in self.objects:
            if obj.get("id") in ("town_radburg", "main_castle"):
                for ent_info in obj.get("entrances", []):
                    if (pgx, pgy) in ent_info.get("tiles", []):
                        self.navigate = "city"
                        self.city_gate = ent_info.get("id", "east")
                        self.finished = True
                        return

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
        if self.building_window is not None or m_pos[1] <= 75 or (self.active_entity and self.active_window_rect.collidepoint(m_pos)):
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

                if (gx, gy) in self.road_tiles:
                    # Узкая грунтовая дорога (1 тайл): протоптанная земляная колея
                    cell_color = (120, 96, 60) if (gx + gy) % 2 == 0 else (128, 103, 65)

                pygame.draw.rect(screen, cell_color, rect)

                if (gx, gy) in self.road_tiles:
                    pygame.draw.line(screen, (95, 74, 44), rect.topleft, rect.topright, 1)
                    pygame.draw.line(screen, (95, 74, 44), rect.bottomleft, rect.bottomright, 1)

                if self.show_grid:
                    pygame.draw.rect(screen, (45, 52, 60), rect, 1)

        # 2. Рельеф с сервера и интерактивные объекты карты
        self._draw_terrain(screen)
        self._draw_objects(screen)

        # 3. Игровой персонаж и эффекты клика (Dota-стиль)
        self._draw_click_effect(screen)
        self._draw_player_character(screen)
        draw_afk_players(self, screen, "world_map")

        # 4. Всплывающие сообщения в мире ("Слишком далеко" и т.д.)
        self._draw_floating_messages(screen)

        # 5. Всплывающее окно активного объекта (ЛКМ)
        self._draw_active_window(screen)

        # 6. Всплывающее окно при наведении курсора (hover tooltip)
        self._draw_hover_popup(screen, mouse_pos)

        # 7. Верхний HUD и подсказки
        self._draw_hud(screen, hover_wx, hover_wy)

        # 8. Окно производственного здания
        if self.building_window is not None:
            self.building_window.draw(screen)
        if self.chat is not None:
            self.chat.draw(screen)
        self.profile_overlay.draw(screen, opponent=self.session.character, show_player_only=True)

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
            if obj.get("id") == "lumber_camp":
                # Лагерь лесорубов 10х10 тайлов (320х320 px)
                top_left_x = obj["tile_x"] * self.tile_size
                top_left_y = obj["tile_y"] * self.tile_size
                sx, sy = self.world_to_screen(top_left_x, top_left_y)
                obj_w = obj["tile_w"] * self.tile_size
                obj_h = obj["tile_h"] * self.tile_size
                forester_rect = pygame.Rect(sx, sy, obj_w, obj_h)

                if not (-obj_w <= sx <= settings.WIDTH + obj_w and -obj_h <= sy <= settings.HEIGHT + obj_h):
                    continue

                is_active = self.active_entity and self.active_entity.get("id") == obj["id"]
                is_hovered = self.hovered_entity and self.hovered_entity.get("id") == obj["id"]

                # Мягкая тень под строением
                pygame.draw.ellipse(screen, (16, 24, 16, 170), (sx + 20, sy + 180, obj_w - 40, 120))

                # Отрисовка анимированного спрайта хижины лесника (дым из трубы)
                if self.forester_frames:
                    # 3 кадра анимации дыма, смена кадра каждые 0.35 секунды (~3 FPS)
                    frame_idx = int(self.player_anim_timer / 0.35) % len(self.forester_frames)
                    current_frame = self.forester_frames[frame_idx]
                    screen.blit(current_frame, (sx, sy))
                else:
                    pygame.draw.rect(screen, (42, 60, 42), forester_rect, border_radius=6)

                # Подсветка активного / наведенного
                if is_active:
                    pygame.draw.rect(screen, (255, 215, 60), forester_rect, 2, border_radius=6)
                elif is_hovered:
                    pygame.draw.rect(screen, (80, 200, 255), forester_rect, 2, border_radius=6)

                # Бейдж названия над строением
                badge_color = (255, 215, 60) if is_active else (100, 200, 255) if is_hovered else (200, 190, 160)
                self._draw_badge(screen, forester_rect.centerx, sy - 10, f"🌲 {obj['name']} [10x10]", badge_color)

            elif obj.get("id") == "wheat_farm":
                # Крестьянское поселение 12х12 тайлов (384х384 px), вход по центру нижней стороны (тайл 20/30)
                top_left_x = obj["tile_x"] * self.tile_size
                top_left_y = obj["tile_y"] * self.tile_size
                sx, sy = self.world_to_screen(top_left_x, top_left_y)
                obj_w = obj["tile_w"] * self.tile_size
                obj_h = obj["tile_h"] * self.tile_size
                farm_rect = pygame.Rect(sx, sy, obj_w, obj_h)

                if not (-obj_w <= sx <= settings.WIDTH + obj_w and -obj_h <= sy <= settings.HEIGHT + obj_h):
                    continue

                is_active = self.active_entity and self.active_entity.get("id") == obj["id"]
                is_hovered = self.hovered_entity and self.hovered_entity.get("id") == obj["id"]

                # Тень под полем
                pygame.draw.ellipse(screen, (30, 26, 12, 170), (sx + 16, sy + obj_h - 20, obj_w - 32, 34))

                f_surf = pygame.Surface((obj_w, obj_h), pygame.SRCALPHA)

                # Золотое пшеничное поле с бороздами
                pygame.draw.rect(f_surf, (168, 132, 46, 235), (0, 0, obj_w, obj_h), border_radius=6)
                for row_y in range(10, obj_h - 10, 18):
                    pygame.draw.line(f_surf, (140, 106, 34), (10, row_y), (obj_w - 10, row_y), 2)
                for col_x in range(16, obj_w - 10, 24):
                    for row_y in range(6, obj_h - 10, 18):
                        pygame.draw.line(f_surf, (220, 185, 90), (col_x, row_y), (col_x - 4, row_y + 10), 2)

                # Изгородь по периметру поля
                pygame.draw.rect(f_surf, (110, 78, 45), (0, 0, obj_w, obj_h), width=4, border_radius=6)

                # Ворота-проем внизу по центру (тайл 20/30, локально: 6-й столбец от края)
                gate_local_x = (obj["entrance_tile"][0] - obj["tile_x"]) * self.tile_size
                gate_rect = pygame.Rect(gate_local_x, obj_h - 14, self.tile_size, 14)
                pygame.draw.rect(f_surf, (90, 62, 34), gate_rect)
                pygame.draw.line(f_surf, (200, 160, 80), (gate_rect.left, gate_rect.top), (gate_rect.left, gate_rect.bottom), 3)
                pygame.draw.line(f_surf, (200, 160, 80), (gate_rect.right, gate_rect.top), (gate_rect.right, gate_rect.bottom), 3)

                # Пугало в центре поля
                scare_x, scare_y = obj_w // 2 - 30, obj_h // 2
                pygame.draw.line(f_surf, (90, 65, 40), (scare_x, scare_y - 26), (scare_x, scare_y + 6), 3)
                pygame.draw.line(f_surf, (90, 65, 40), (scare_x - 12, scare_y - 14), (scare_x + 12, scare_y - 14), 3)
                pygame.draw.circle(f_surf, (210, 180, 140), (scare_x, scare_y - 32), 6)

                screen.blit(f_surf, (sx, sy))

                door_lbl = self.grid_font.render("ВХОД", True, (255, 225, 130))
                screen.blit(door_lbl, door_lbl.get_rect(midtop=(sx + gate_local_x + self.tile_size // 2, sy + obj_h + 2)))

                # Подсветка активного / наведенного
                if is_active:
                    pygame.draw.rect(screen, (255, 215, 60), farm_rect, 2, border_radius=6)
                elif is_hovered:
                    pygame.draw.rect(screen, (80, 200, 255), farm_rect, 2, border_radius=6)

                badge_color = (255, 215, 60) if is_active else (100, 200, 255) if is_hovered else (220, 195, 140)
                self._draw_badge(screen, farm_rect.centerx, sy - 10, f"🌾 {obj['name']} [12x12]", badge_color)

            elif obj.get("id") == "mountain_rift":
                self._draw_rift_object(screen, obj)

            elif obj.get("id") == "barnyard":
                self._draw_barnyard_object(screen, obj)

            elif obj.get("id") == "black_pit":
                self._draw_black_pit_object(screen, obj)

            elif obj.get("id") in ("town_radburg", "main_castle") or obj.get("is_placeholder"):
                # Заглушка города (например, Город Радбург 15х15 тайлов, 480х480 px)
                top_left_x = obj["tile_x"] * self.tile_size
                top_left_y = obj["tile_y"] * self.tile_size
                sx, sy = self.world_to_screen(top_left_x, top_left_y)
                obj_w = obj["tile_w"] * self.tile_size
                obj_h = obj["tile_h"] * self.tile_size
                castle_rect = pygame.Rect(sx, sy, obj_w, obj_h)

                if not (-obj_w <= sx <= settings.WIDTH + obj_w and -obj_h <= sy <= settings.HEIGHT + obj_h):
                    continue

                is_active = self.active_entity and self.active_entity.get("id") == obj["id"]
                is_hovered = self.hovered_entity and self.hovered_entity.get("id") == obj["id"]

                # Мягкая тень под замком
                pygame.draw.ellipse(screen, (15, 20, 26, 190), (sx + 20, sy + obj_h - 70, obj_w - 40, 90))

                # Поверхность заглушки здания
                ph_surf = pygame.Surface((obj_w, obj_h), pygame.SRCALPHA)

                # 1. Основное каменное основание крепости
                pygame.draw.rect(ph_surf, (35, 42, 52, 225), (0, 0, obj_w, obj_h), border_radius=10)

                # 2. Внутренняя сетка тайлов здания (для наглядной оценки размеров и разметки)
                for gx in range(obj["tile_w"] + 1):
                    x_line = gx * self.tile_size
                    line_col = (75, 95, 120, 160) if gx % 5 == 0 else (50, 65, 80, 100)
                    line_w = 2 if gx % 5 == 0 else 1
                    pygame.draw.line(ph_surf, line_col, (x_line, 0), (x_line, obj_h), line_w)

                for gy in range(obj["tile_h"] + 1):
                    y_line = gy * self.tile_size
                    line_col = (75, 95, 120, 160) if gy % 5 == 0 else (50, 65, 80, 100)
                    line_w = 2 if gy % 5 == 0 else 1
                    pygame.draw.line(ph_surf, line_col, (0, y_line), (obj_w, y_line), line_w)

                # 3. Четыре угловые бастионные башни (каждая по 3х3 тайла = 96х96 px)
                tower_size = 3 * self.tile_size
                towers = [
                    (0, 0),
                    (obj_w - tower_size, 0),
                    (0, obj_h - tower_size),
                    (obj_w - tower_size, obj_h - tower_size),
                ]
                for tx, ty in towers:
                    t_rect = pygame.Rect(tx, ty, tower_size, tower_size)
                    pygame.draw.rect(ph_surf, (45, 55, 68, 245), t_rect, border_radius=4)
                    pygame.draw.rect(ph_surf, (85, 105, 130), t_rect, 2, border_radius=4)
                    for bx in range(tx + 4, tx + tower_size - 8, 16):
                        pygame.draw.rect(ph_surf, (25, 32, 40), (bx, ty + 2, 8, 6))

                # 4. Центральная цитадель / донжон (5х5 тайлов = 160х160 px)
                keep_size = 5 * self.tile_size
                keep_x = (obj_w - keep_size) // 2
                keep_y = (obj_h - keep_size) // 2
                keep_rect = pygame.Rect(keep_x, keep_y, keep_size, keep_size)
                pygame.draw.rect(ph_surf, (40, 50, 62, 245), keep_rect, border_radius=6)
                pygame.draw.rect(ph_surf, (110, 135, 165), keep_rect, 2, border_radius=6)

                # 5. Отрисовка 4 ворот замка (Главные, Южные, Северные, Западные)
                # 1) Главные ворота (Восточные): 74/52, 74/53, 74/54 -> локально: x = 14*32, y = (52-46)*32 = 6*32 = 192, h = 3*32 = 96
                gw_e = self.tile_size
                gh_e = 3 * self.tile_size
                gx_e = 14 * self.tile_size
                gy_e = 6 * self.tile_size
                rect_e = pygame.Rect(gx_e, gy_e, gw_e, gh_e)
                pygame.draw.rect(ph_surf, (22, 26, 34), rect_e, border_radius=3)
                pygame.draw.rect(ph_surf, (255, 215, 80), rect_e, 2, border_radius=3)
                lbl_e = self.grid_font.render("ГЛАВНЫЕ", True, (255, 220, 100))
                lbl_e_sub = self.grid_font.render("ВОРОТА", True, (255, 220, 100))
                ph_surf.blit(lbl_e, lbl_e.get_rect(center=(gx_e + gw_e // 2, gy_e + gh_e // 2 - 8)))
                ph_surf.blit(lbl_e_sub, lbl_e_sub.get_rect(center=(gx_e + gw_e // 2, gy_e + gh_e // 2 + 8)))
                # Факелы у главных ворот
                pygame.draw.circle(ph_surf, (255, 160, 30), (gx_e - 4, gy_e + 10), 4)
                pygame.draw.circle(ph_surf, (255, 160, 30), (gx_e - 4, gy_e + gh_e - 10), 4)

                # 2) Южные ворота: 67/60 -> локально: x = (67-60)*32 = 224, y = 14*32 = 448
                gw_s = self.tile_size
                gh_s = self.tile_size
                gx_s = 7 * self.tile_size
                gy_s = 14 * self.tile_size
                rect_s = pygame.Rect(gx_s, gy_s, gw_s, gh_s)
                pygame.draw.rect(ph_surf, (22, 26, 34), rect_s, border_radius=3)
                pygame.draw.rect(ph_surf, (140, 190, 240), rect_s, 2, border_radius=3)
                lbl_s = self.grid_font.render("ЮЖНЫЕ", True, (160, 210, 255))
                ph_surf.blit(lbl_s, lbl_s.get_rect(center=rect_s.center))

                # 3) Северные ворота: 67/46 -> локально: x = (67-60)*32 = 224, y = 0
                gx_n = 7 * self.tile_size
                gy_n = 0
                rect_n = pygame.Rect(gx_n, gy_n, gw_s, gh_s)
                pygame.draw.rect(ph_surf, (22, 26, 34), rect_n, border_radius=3)
                pygame.draw.rect(ph_surf, (140, 190, 240), rect_n, 2, border_radius=3)
                lbl_n = self.grid_font.render("СЕВЕР", True, (160, 210, 255))
                ph_surf.blit(lbl_n, lbl_n.get_rect(center=rect_n.center))

                # 4) Западные ворота: 60/53 -> локально: x = 0, y = (53-46)*32 = 224
                gx_w = 0
                gy_w = 7 * self.tile_size
                rect_w = pygame.Rect(gx_w, gy_w, gw_s, gh_s)
                pygame.draw.rect(ph_surf, (22, 26, 34), rect_w, border_radius=3)
                pygame.draw.rect(ph_surf, (140, 190, 240), rect_w, 2, border_radius=3)
                lbl_w = self.grid_font.render("ЗАПАД", True, (160, 210, 255))
                ph_surf.blit(lbl_w, lbl_w.get_rect(center=rect_w.center))

                # 6. Информационные надписи внутри цитадели
                title_surf = self.large_font.render("ГОРОД РАДБУРГ", True, (255, 220, 100))
                ph_surf.blit(title_surf, title_surf.get_rect(center=(obj_w // 2, keep_y + 30)))

                sub_surf = self.badge_font.render(f"[ГОРОД СВЕТА • {obj['tile_w']} x {obj['tile_h']} ТАЙЛОВ]", True, (130, 200, 255))
                ph_surf.blit(sub_surf, sub_surf.get_rect(center=(obj_w // 2, keep_y + 54)))

                origin_text = obj.get("origin_desc", f"Левый нижний: [{obj['tile_x']}, {obj['tile_y'] + obj['tile_h'] - 1}]")
                origin_surf = self.small_font.render(origin_text, True, (240, 240, 240))
                ph_surf.blit(origin_surf, origin_surf.get_rect(center=(obj_w // 2, keep_y + 76)))

                coord_surf = self.grid_font.render(f"Сетка: X [{obj['tile_x']}..{obj['tile_x'] + obj['tile_w'] - 1}], Y [{obj['tile_y']}..{obj['tile_y'] + obj['tile_h'] - 1}]", True, (180, 195, 210))
                ph_surf.blit(coord_surf, coord_surf.get_rect(center=(obj_w // 2, keep_y + 96)))

                entrances_lbl = self.grid_font.render("ВХОДЫ: Восток(3т) | Юг(1т) | Север(1т) | Запад(1т)", True, (255, 230, 140))
                ph_surf.blit(entrances_lbl, entrances_lbl.get_rect(center=(obj_w // 2, keep_y + 116)))

                status_surf = self.grid_font.render("[ СТОЛИЦА СВЕТА • ЗАГЛУШКА ]", True, (200, 170, 120))
                ph_surf.blit(status_surf, status_surf.get_rect(center=(obj_w // 2, keep_y + 134)))

                # Рисуем поверхность заглушки на экран
                screen.blit(ph_surf, (sx, sy))

                # Внешняя рамка и подсветка
                if is_active:
                    pulse = 1.0 + 0.04 * math.sin(self.player_anim_timer * 6.0)
                    glow_w = int(obj_w * pulse)
                    glow_h = int(obj_h * pulse)
                    glow_x = castle_rect.centerx - glow_w // 2
                    glow_y = castle_rect.centery - glow_h // 2
                    pygame.draw.rect(screen, (255, 215, 60), (glow_x, glow_y, glow_w, glow_h), 3, border_radius=12)
                elif is_hovered:
                    pygame.draw.rect(screen, (80, 200, 255), castle_rect.inflate(8, 8), 2, border_radius=12)
                else:
                    pygame.draw.rect(screen, (100, 125, 155), castle_rect, 2, border_radius=10)

                # Бейдж названия над замком
                badge_color = (255, 215, 60) if is_active else (100, 200, 255) if is_hovered else (220, 200, 160)
                self._draw_badge(screen, castle_rect.centerx, sy - 12, f"🏛️ {obj['name']} [15x15]", badge_color)

    def _draw_rift_object(self, screen, obj):
        """Разлом на карте: скала, расколотая ущельем снизу-слева вверх-направо, вход снизу."""
        sx, sy = self.world_to_screen(obj["tile_x"] * self.tile_size, obj["tile_y"] * self.tile_size)
        w, h = obj["tile_w"] * self.tile_size, obj["tile_h"] * self.tile_size
        if not (-w <= sx <= settings.WIDTH + w and -h <= sy <= settings.HEIGHT + h):
            return
        rect = pygame.Rect(sx, sy, w, h)
        pygame.draw.polygon(screen, (82, 76, 70), [(sx, sy + h), (sx + 10, sy + 30), (sx + 60, sy), (sx + w - 20, sy + 12), (sx + w, sy + h)])
        canyon = [(sx + 58, sy + h), (sx + w - 46, sy + 18), (sx + w - 26, sy + 30), (sx + 102, sy + h)]
        pygame.draw.polygon(screen, (116, 96, 70), canyon)
        pygame.draw.lines(screen, (36, 32, 30), False, canyon[:2], 3)
        pygame.draw.lines(screen, (36, 32, 30), False, canyon[2:], 3)
        for mx, my, color in ((sx + 34, sy + 150, (200, 120, 90)), (sx + 128, sy + 190, (185, 185, 178)), (sx + 70, sy + 70, (150, 205, 245))):
            pygame.draw.ellipse(screen, (18, 14, 12), (mx - 9, my - 8, 18, 16))
            pygame.draw.line(screen, (130, 90, 50), (mx - 11, my - 8), (mx + 11, my - 8), 3)
            pygame.draw.circle(screen, color, (mx + 12, my + 6), 3)
        is_active = self.active_entity and self.active_entity.get("id") == obj["id"]
        is_hovered = self.hovered_entity and self.hovered_entity.get("id") == obj["id"]
        if is_active:
            pygame.draw.rect(screen, (255, 215, 60), rect, 2, border_radius=6)
        elif is_hovered:
            pygame.draw.rect(screen, (80, 200, 255), rect, 2, border_radius=6)
        door = self.grid_font.render("ВХОД", True, (255, 225, 130))
        screen.blit(door, door.get_rect(midtop=(sx + w // 2, sy + h + 2)))
        badge_color = (255, 215, 60) if is_active else (100, 200, 255) if is_hovered else (210, 200, 180)
        self._draw_badge(screen, rect.centerx, sy - 10, f"{obj['name']} [5x8]", badge_color)

    def _draw_barnyard_object(self, screen, obj):
        """Скотный двор: хлев слева, загон с скотом справа, изгородь с воротами снизу."""
        ts = self.tile_size
        sx, sy = self.world_to_screen(obj["tile_x"] * ts, obj["tile_y"] * ts)
        w, h = obj["tile_w"] * ts, obj["tile_h"] * ts
        if not (-w <= sx <= settings.WIDTH + w and -h <= sy <= settings.HEIGHT + h):
            return
        rect = pygame.Rect(sx, sy, w, h)
        pygame.draw.rect(screen, (88, 110, 52), rect)
        # Вытоптанная земля у ворот и кормуши
        pygame.draw.ellipse(screen, (120, 98, 62), (sx + 7 * ts - 20, sy + h - 70, ts + 40, 60))
        barn = pygame.Rect(sx + 14, sy + 20, 6 * ts, 5 * ts)
        pygame.draw.rect(screen, (150, 52, 40), barn)
        pygame.draw.polygon(screen, (92, 46, 34), [(barn.left - 10, barn.top + 10), (barn.centerx, barn.top - 26), (barn.right + 10, barn.top + 10)])
        door = pygame.Rect(barn.centerx - 26, barn.bottom - 58, 52, 58)
        pygame.draw.rect(screen, (70, 40, 26), door)
        pygame.draw.line(screen, (230, 220, 200), door.topleft, door.bottomright, 3)
        pygame.draw.line(screen, (230, 220, 200), door.topright, door.bottomleft, 3)
        pygame.draw.rect(screen, (230, 220, 200), barn, 3)
        trough = pygame.Rect(sx + 8 * ts, sy + 5 * ts, 3 * ts, 14)
        pygame.draw.rect(screen, (110, 80, 48), trough, border_radius=4)
        pygame.draw.rect(screen, (190, 170, 80), trough.inflate(-8, -8), border_radius=3)
        for cx, cy, spotted in ((9.2, 2.0, True), (11.6, 1.5, False), (13.8, 2.6, True), (10.4, 3.6, False), (13.0, 4.4, True)):
            x, y = int(sx + cx * ts), int(sy + cy * ts)
            body = (240, 238, 230) if spotted else (130, 88, 58)
            pygame.draw.ellipse(screen, body, (x - 16, y - 9, 32, 18))
            pygame.draw.circle(screen, body, (x + 17, y - 4), 7)
            if spotted:
                pygame.draw.circle(screen, (30, 28, 26), (x - 4, y - 2), 5)
        # Изгородь по периметру с проёмом ворот на тайле входа
        gate_left = sx + (obj["entrance_tile"][0] - obj["tile_x"]) * ts
        fence = (138, 100, 58)
        pygame.draw.line(screen, fence, rect.topleft, rect.topright, 4)
        pygame.draw.line(screen, fence, rect.topleft, rect.bottomleft, 4)
        pygame.draw.line(screen, fence, rect.topright, rect.bottomright, 4)
        pygame.draw.line(screen, fence, rect.bottomleft, (gate_left, rect.bottom), 4)
        pygame.draw.line(screen, fence, (gate_left + ts, rect.bottom), rect.bottomright, 4)
        for post_x in range(rect.left, rect.right + 1, ts):
            if not gate_left < post_x < gate_left + ts:
                pygame.draw.rect(screen, (100, 70, 40), (post_x - 3, rect.bottom - 8, 6, 12))
        is_active = self.active_entity and self.active_entity.get("id") == obj["id"]
        is_hovered = self.hovered_entity and self.hovered_entity.get("id") == obj["id"]
        if is_active:
            pygame.draw.rect(screen, (255, 215, 60), rect, 2, border_radius=6)
        elif is_hovered:
            pygame.draw.rect(screen, (80, 200, 255), rect, 2, border_radius=6)
        door_label = self.grid_font.render("ВХОД", True, (255, 225, 130))
        screen.blit(door_label, door_label.get_rect(midtop=(gate_left + ts // 2, rect.bottom + 2)))
        badge_color = (255, 215, 60) if is_active else (100, 200, 255) if is_hovered else (220, 200, 160)
        self._draw_badge(screen, rect.centerx, sy - 10, f"{obj['name']} [16x8]", badge_color)

    def _draw_black_pit_object(self, screen, obj):
        """Чёрная копь: угольный карьер в скалах, устье шахты и рельсы к западному входу со стороны города."""
        ts = self.tile_size
        sx, sy = self.world_to_screen(obj["tile_x"] * ts, obj["tile_y"] * ts)
        w, h = obj["tile_w"] * ts, obj["tile_h"] * ts
        if not (-w <= sx <= settings.WIDTH + w and -h <= sy <= settings.HEIGHT + h):
            return
        rect = pygame.Rect(sx, sy, w, h)
        pygame.draw.rect(screen, (54, 50, 48), rect, border_radius=10)
        for step in range(4):
            ring = rect.inflate(-40 - step * 44, -60 - step * 70)
            shade = 40 - step * 9
            pygame.draw.ellipse(screen, (shade, shade, shade + 2), ring)
            pygame.draw.ellipse(screen, (shade + 26, shade + 24, shade + 20), ring, 2)
        mouth = pygame.Rect(0, 0, 60, 46)
        mouth.center = rect.center
        pygame.draw.ellipse(screen, (4, 4, 6), mouth)
        pygame.draw.line(screen, (130, 92, 50), (mouth.left - 4, mouth.top + 10), (mouth.right + 4, mouth.top + 10), 6)
        rail_y = sy + (obj["entrance_tile"][1] - obj["tile_y"]) * ts + ts // 2
        for offset in (-6, 6):
            pygame.draw.line(screen, (120, 116, 110), (rect.left - ts, rail_y + offset), (mouth.left, rail_y + offset), 2)
        for x in range(rect.left - ts, mouth.left, 12):
            pygame.draw.line(screen, (96, 70, 44), (x, rail_y - 9), (x, rail_y + 9), 3)
        for hx, hy in ((sx + 50, sy + 70), (sx + 220, sy + 330), (sx + 70, sy + 340)):
            pygame.draw.polygon(screen, (16, 16, 18), [(hx - 26, hy + 12), (hx, hy - 16), (hx + 26, hy + 12)])
            pygame.draw.circle(screen, (210, 40, 70), (hx + 6, hy + 2), 3)
        is_active = self.active_entity and self.active_entity.get("id") == obj["id"]
        is_hovered = self.hovered_entity and self.hovered_entity.get("id") == obj["id"]
        if is_active:
            pygame.draw.rect(screen, (255, 215, 60), rect, 2, border_radius=10)
        elif is_hovered:
            pygame.draw.rect(screen, (80, 200, 255), rect, 2, border_radius=10)
        door = self.grid_font.render("ВХОД", True, (255, 225, 130))
        screen.blit(door, door.get_rect(midright=(rect.left - 4, rail_y - 20)))
        badge_color = (255, 215, 60) if is_active else (100, 200, 255) if is_hovered else (210, 200, 180)
        self._draw_badge(screen, rect.centerx, sy - 10, f"{obj['name']} [9x13]", badge_color)

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

        name = ent.get("name", "Объект")
        building_icon = draw_building_icon(screen, ent.get("id"), (box_x + 10, box_y + 5), 26)
        title_x = box_x + 42 if building_icon else box_x + 12
        title = name if building_icon else f"{ent.get('icon', '📍')} {name}"
        title_surf = self.small_font.render(title, True, (255, 230, 140))
        screen.blit(title_surf, (title_x, box_y + 10))

        type_str = ent.get("type", "Объект")
        type_surf = self.grid_font.render(f"[{type_str}]", True, (130, 200, 255))
        screen.blit(type_surf, (box_x + 12, box_y + 32))

        gx = ent.get("tile_x", int(ent.get("x", 0) // self.tile_size))
        gy = ent.get("tile_y", int(ent.get("y", 0) // self.tile_size))
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
        if self.active_entity is None or self.building_window is not None:
            return

        ent = self.active_entity
        rect = self.active_window_rect

        win_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(win_surf, (15, 20, 28, 245), (0, 0, rect.width, rect.height), border_radius=8)
        pygame.draw.rect(win_surf, (220, 185, 60, 255), (0, 0, rect.width, rect.height), width=2, border_radius=8)
        screen.blit(win_surf, rect.topleft)

        name = ent.get("name", "Объект")
        building_icon = draw_building_icon(screen, ent.get("id"), (rect.left + 12, rect.top + 6), 32)
        title_x = rect.left + 52 if building_icon else rect.left + 14
        title = name if building_icon else f"{ent.get('icon', '📍')} {name}"
        title_surf = self.font.render(title, True, (255, 225, 120))
        screen.blit(title_surf, (title_x, rect.top + 12))

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
                action_label = "ИНФОРМАЦИЯ"
            elif ent.get("id") == "lumber_camp":
                action_label = "ОТКРЫТЬ ЛАГЕРЬ"
            elif ent.get("id") == "black_pit":
                action_label = "ОТКРЫТЬ КОПЬ"
            elif ent.get("id") == "barnyard":
                action_label = "ОТКРЫТЬ СКОТНЫЙ ДВОР"
            elif ent.get("id") == "mountain_rift":
                action_label = "ОТКРЫТЬ РАЗЛОМ"
            elif ent.get("id") == "wheat_farm":
                action_label = "ОТКРЫТЬ ПОСЕЛЕНИЕ"
            elif ent.get("id") in ("town_radburg", "main_castle"):
                action_label = "ВОЙТИ В ГОРОД"
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

