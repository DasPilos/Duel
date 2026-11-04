import math
import random
import time
import uuid
import pygame
from kaloda import settings
from kaloda.map_config import (
    ANCIENT_ENT_TILE,
    CARD_SHOP_BOUNDS,
    DUNGEON_ENTRANCE_BOUNDS,
    DUNGEON_ROOM_ORIGIN,
    DUNGEON_ROOM_SIZE,
    GRAVEYARD_BOUNDS,
    GUILD_BOUNDS,
    LIBRARY_BOUNDS,
    KOBOLD_CAMP_SIZE,
    KOBOLD_CAMP_TILE,
    KOBOLD_CAMP2_TILE,
    KOBOLD_RESPAWN_SECONDS,
    KOBOLD_SPAWN_TILE,
    MAP_HEIGHT_TILES,
    MAP_VERSION,
    MAP_WIDTH_TILES,
    RESPAWN_CRYSTAL,
    SHOW_OUTSIDE_CITY_LOCATIONS,
    SUPPLIES_SHOP_BOUNDS,
    TAVERN_BOUNDS,
    TILE_SIZE,
    city_area_payload,
    forest_area_payload,
    is_graveyard_tile,
    is_library_tile,
    is_city_tile,
    is_card_shop_tile,
    is_dungeon_entrance_tile,
    is_forest_tile,
    is_guild_tile,
    is_supplies_shop_tile,
    is_tavern_tile,
    tile_center,
)
from client.network import ServerError
from client.structures import hydrate_structures
from kaloda.quests import quest_log_for
from kaloda.ui.hud import draw_button
from kaloda.ui.arena_overlay import ArenaController, draw_kobold, draw_necromancer, draw_skeleton
from kaloda.ui.guild_window import GuildWindow
from kaloda.ui.library_window import LibraryWindow
from kaloda.ui.talent_tree_window import TalentTreeWindow
from kaloda.ui.supplies_shop_window import SuppliesShopWindow
from kaloda.ui.card_shop_window import CardShopWindow
from kaloda.ui.dungeon_window import DungeonRoomWindow
from kaloda.ui.character_profile_overlay import CharacterProfileOverlay
from kaloda.ui.chat import ChatPanel
from kaloda.ui.player_presence import draw_active_players, draw_afk_players, draw_player_hover_card, player_at
from kaloda.world_map import point_in_polygon


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
    Тайл: 48x48 пикселей (TILE_SIZE).
    Размер карты: 128 тайлов по ширине x 256 тайлов по высоте.
    Координатная сетка начинается с левого верхнего угла: (0, 0) = [0, 0].
    """

    def __init__(self, session, spawn_gate=None, spawn_pos=None):
        self.session = session
        refresh_equipment_state = getattr(session, "refresh_equipment_state", None)
        if refresh_equipment_state is not None:
            try:
                refresh_equipment_state()
            except Exception:
                pass
        self.finished = False
        self.cancelled = False
        self.navigate = None
        self.city_gate = None

        self.grid_w = MAP_WIDTH_TILES
        self.grid_h = MAP_HEIGHT_TILES
        self.tile_size = TILE_SIZE
        self.world_w = self.grid_w * self.tile_size
        self.world_h = self.grid_h * self.tile_size

        # Фиксированный масштаб (1.0x)
        self.zoom = 1.0

        # Границы мира: левый верхний угол (0, 0), правый нижний (world_w, world_h)
        self.min_world_x = 0
        self.max_world_x = self.world_w
        self.min_world_y = 0
        self.max_world_y = self.world_h

        center_x = self.world_w // 2
        center_y = self.world_h // 2
        gate_spawns = {
            "east": (self.world_w - 16, center_y, "e"),
            "main": (center_x, center_y, "s"),
            "north": (center_x, 16, "n"),
            "south": (center_x, self.world_h - 16, "s"),
            "west": (16, center_y, "w"),
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
            # Новые и перенесённые персонажи появляются у кристалла на актуальной карте.
            self.player_x, self.player_y = map(float, RESPAWN_CRYSTAL["approach_pos"])
            self.player_direction = "n"

        self.player_x = max(10.0, min(self.world_w - 10.0, self.player_x))
        self.player_y = max(6.0, min(self.world_h - 6.0, self.player_y))

        self.player_target = None
        self.player_speed = 220.0 * self.tile_size / 32
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
        if self.chat is not None:
            self.chat.presence_provider = lambda: {
                "position_x": self.player_x,
                "position_y": self.player_y,
                "position_direction": self.player_direction,
            }

        # UI элементы
        self.player_pos_button = pygame.Rect(20, 20, 160, 45)

        # Переключатель отображения тонкой сетки (клавиша G)
        self.show_grid = False

        # Интерактивные сущности, наведение (hover) и активное состояние (ЛКМ)
        self.hovered_entity = None
        self.hovered_player = None
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

        # Строения карты живут на сервере и приходят вместе с рельефом (_load_terrain)
        self.objects = []
        self.show_outside_city_locations = SHOW_OUTSIDE_CITY_LOCATIONS
        self._set_city_area(city_area_payload())
        self.forest_bounds = (
            tuple(forest_area_payload()["bounds"])
            if self.show_outside_city_locations else (0, 0, 0, 0)
        )
        self.library_bounds = LIBRARY_BOUNDS
        self.graveyard_bounds = GRAVEYARD_BOUNDS if self.show_outside_city_locations else (0, 0, 0, 0)
        self.dungeon_entrance_bounds = DUNGEON_ENTRANCE_BOUNDS if self.show_outside_city_locations else (0, 0, 0, 0)

        self.obstacles = self._load_terrain()

        # Кобольд на карте и пошаговый бой на гексагональной арене при подходе к нему
        self.arena = None
        self.arena_source = None
        self.ancient_ent_defeated = False
        self.kobold_respawn_at = None
        self.camp_respawn_at = None
        self.camp2_respawn_at = None
        self.graveyard_respawn_at = {}
        self.dungeon_entry_elapsed = None
        self.dungeon_fade_alpha = 0
        self.dungeon_room = None
        self.dungeon_treasure_request_id = None
        self.dungeon_cleared_rooms = set()
        self.dungeon_completed_rooms = set()
        self.dungeon_message = None
        self.arena_reward_request_id = None
        self.dungeon_room_window = DungeonRoomWindow(self)
        self.guild_window = GuildWindow(self)
        self.supplies_shop_window = SuppliesShopWindow(self)
        self.card_shop_window = CardShopWindow(self)
        self.library_window = LibraryWindow(self)
        self.talent_tree_window = TalentTreeWindow(self)
        self._last_player_tile = self._player_tile()
        self._sync_kobold()
        if self.show_outside_city_locations:
            self.objects.append(self._ancient_ent_object())
        self.objects.append(self._library_object())
        self.objects.append(self._talent_tree_object())
        self._sync_graveyard()

        # Анимация строения лесника 10х10 тайлов (3 кадра анимации дыма из assets/forester's1.png)
        self.forester_frames = []
        self._load_forester_sprite()

        # Загрузка 8-направленных спрайтов idle (из assets/2Idle/) и бега (из assets/3run/)
        self.player_directional_frames = {}
        self.player_run_directional_frames = {}
        self._load_player_directional_sprites()

    def _load_forester_sprite(self):
        """
        Нарезает и масштабирует 3 кадра анимации дыма хижины лесника под размер 10х10 тайлов (320х320 px).
        Спрайтшит содержит 3 фазы дыма из трубы.
        """
        forester_path = settings.ASSETS_DIR / "forester's1.png"
        if forester_path.is_file():
            try:
                sheet = pygame.image.load(str(forester_path)).convert_alpha()
                target_size = (10 * self.tile_size, 10 * self.tile_size)
                # Точные смещения для 3 кадров с идеальным выравниванием домика и трубы
                frame_w, frame_h = 238, 330
                shifts = [-240, 0, 239]
                self.forester_frames = []
                camp_rotation = int(next(
                    (obj.get("rotation", 0) for obj in self.objects if obj.get("id") == "lumber_camp"),
                    0,
                )) % 360
                for shift in shifts:
                    frame_surf = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
                    frame_surf.blit(sheet, (0, 0), pygame.Rect(237 + shift, 85, frame_w, frame_h))
                    scaled_frame = pygame.transform.smoothscale(frame_surf, target_size)
                    if camp_rotation:
                        scaled_frame = pygame.transform.rotate(scaled_frame, camp_rotation)
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
        idle_dir = settings.ASSETS_DIR / "2Idle"
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
        run_dir = settings.ASSETS_DIR / "3run"
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
            character = getattr(self.session, "character", None)
            char_name = character.get("name", "Герой") if isinstance(character, dict) else "Герой"
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

        if eid == "kobold":
            self.start_kobold_battle()
            return
        if eid == "ancient_ent":
            self.start_ancient_ent_battle()
            return
        if eid in self.GRAVEYARD_MOBS:
            self.start_graveyard_battle(eid)
            return
        if eid == "library":
            self.library_window.open()
            return
        if eid == "talent_tree":
            self.talent_tree_window.open()
            return
        if eid in ("kobold_camp", "kobold_camp_2"):
            self.start_camp_battle(eid)
            return
        if eid in ("town_radburg", "main_castle"):
            self.action_notice = "Город находится на этой карте"
            self.action_notice_timer = 2.0
            return
        if eid == "crystal_of_life":
            character = getattr(self.session, "character", None)
            if not character:
                self.action_notice = "Персонаж не загружен"
                self.action_notice_timer = 2.0
                return
            character["hp"] = character.get("max_hp", 100)
            try:
                self.session.client.save_character(character)
            except ServerError as error:
                self.action_notice = f"Здоровье восстановлено, но не сохранено: {error}"
                self.action_notice_timer = 3.0
                return
            self._add_floating_message(
                "✨ Кристалл возрождения исцеляет ваши раны!",
                self.player_x,
                self.player_y - 36,
                (100, 240, 255),
            )
            self.action_notice = "Здоровье полностью восстановлено!"
            self.action_notice_timer = 2.5
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
        if self.dungeon_room is not None:
            return self._check_dungeon_collision(px, py)
        if px - 10 < self.min_world_x or px + 10 > self.max_world_x:
            return True
        if py - 6 < self.min_world_y or py + 6 > self.max_world_y:
            return True

        feet_rect = pygame.Rect(int(px - 10), int(py - 6), 20, 10)
        for obj in self.objects:
            for s_rect in obj.get("solid_rects", []):
                if feet_rect.colliderect(s_rect):
                    return True
        if feet_rect.collidelist(self.city_wall_rects) != -1:
            return True
        for obstacle in self.obstacles:
            if (obstacle["bounds"].collidepoint(px, py) and point_in_polygon((px, py), obstacle["points"])
                    and not any(passage.collidepoint(px, py) for passage in obstacle["passages"])):
                return True
        return False

    def _player_tile(self):
        return int(self.player_x // self.tile_size), int(self.player_y // self.tile_size)

    def _kobold_object(self):
        tx, ty = KOBOLD_SPAWN_TILE
        x, y = tile_center(tx, ty)
        return {
            "id": "kobold",
            "name": "Кобольд",
            "type": "Враг • 1 ур.",
            "desc": "Злобный лесной кобольд. Подойдите вплотную, чтобы начать бой на арене.",
            "icon": "👹",
            "tile_x": tx,
            "tile_y": ty,
            "tile_w": 1,
            "tile_h": 1,
            "x": x,
            "y": y,
            "radius": self.tile_size // 2,
            "solid_rects": [],
        }

    def _ancient_ent_object(self):
        tx, ty = ANCIENT_ENT_TILE
        x, y = tile_center(tx, ty)
        return {
            "id": "ancient_ent",
            "name": "ДРЕВНИЙ ЕНТ" if not self.ancient_ent_defeated else "Древнее дерево",
            "type": "Босс леса",
            "desc": ("Древний энт охраняет лес. Подойдите к дереву, чтобы бросить вызов."
                     if not self.ancient_ent_defeated else "Древний энт повержен."),
            "icon": "🌳",
            "tile_x": tx,
            "tile_y": ty,
            "tile_w": 1,
            "tile_h": 1,
            "x": x,
            "y": y,
            "radius": self.tile_size,
            "solid_rects": [[
                tx * self.tile_size + self.tile_size // 3,
                ty * self.tile_size + self.tile_size // 2,
                self.tile_size // 3,
                self.tile_size // 2,
            ]],
        }

    def _library_object(self):
        left, top, width, height = self.library_bounds
        entrance = (left + width // 2, top + height)
        return {
            "id": "library",
            "name": "Библиотека",
            "type": "Справочник мира",
            "desc": "Справочник по существам, предметам, картам, классам, эффектам и местам.",
            "icon": "📚",
            "tile_x": left,
            "tile_y": top,
            "tile_w": width,
            "tile_h": height,
            "x": (left + width / 2) * self.tile_size,
            "y": (top + height / 2) * self.tile_size,
            "radius": self.tile_size * 2,
            "entrance_tile": list(entrance),
            "approach_pos": tile_center(*entrance),
            "solid_rects": [],
        }

    def _talent_tree_object(self):
        tile_x, tile_y = (22, 37)
        return {
            "id": "talent_tree",
            "name": "Древо талантов",
            "type": "Развитие персонажа",
            "desc": "Выбирайте бесплатные улучшения своего класса по мере роста уровня.",
            "icon": "🌳",
            "tile_x": tile_x,
            "tile_y": tile_y,
            "tile_w": 2,
            "tile_h": 2,
            "x": (tile_x + 1) * self.tile_size,
            "y": (tile_y + 1) * self.tile_size,
            "radius": self.tile_size * 2,
            "entrance_tile": [tile_x + 1, tile_y + 2],
            "approach_pos": tile_center(tile_x + 1, tile_y + 2),
            "solid_rects": [],
        }

    def _graveyard_mob_object(self, eid):
        tx, ty = self.GRAVEYARD_MOBS[eid]
        x, y = tile_center(tx, ty)
        is_necromancer = eid == "necromancer"
        name = "Некромансер" if is_necromancer else "Скелет"
        return {
            "id": eid,
            "name": name,
            "type": "Враг кладбища",
            "desc": f"{name}. Подойдите, чтобы вступить в бой.",
            "icon": "☠" if is_necromancer else "💀",
            "tile_x": tx,
            "tile_y": ty,
            "tile_w": 1,
            "tile_h": 1,
            "x": x,
            "y": y,
            "radius": self.tile_size // 2,
            "solid_rects": [],
        }

    def _graveyard_mob_alive(self, eid):
        respawn_at = self.graveyard_respawn_at.get(eid)
        return respawn_at is None or time.time() >= respawn_at

    def _sync_graveyard(self):
        self.objects = [obj for obj in self.objects if obj.get("id") not in self.GRAVEYARD_MOBS]
        if not self.show_outside_city_locations:
            return
        if self.arena is not None:
            return
        for eid in self.GRAVEYARD_MOBS:
            if self._graveyard_mob_alive(eid):
                self.objects.append(self._graveyard_mob_object(eid))

    def _kobold_camp_object(self, eid="kobold_camp"):
        cx, cy = self.CAMP_TILES[eid]
        x, y = tile_center(cx, cy)
        with_ally = eid == "kobold_camp_2"
        return {
            "id": eid,
            "name": "Лесной лагерь кобольдов" if with_ally else "Лагерь кобольдов",
            "type": f"Враги • {KOBOLD_CAMP_SIZE} кобольда",
            "desc": ("Стоянка кобольдов в чаще. В бою вам поможет лучник Ельпачино Фред."
                     if with_ally else
                     "Стоянка кобольдов. Подойдите вплотную — в бой вступят все кобольды лагеря сразу."),
            "icon": "⛺",
            "tile_x": cx - 1,
            "tile_y": cy - 1,
            "tile_w": 3,
            "tile_h": 3,
            "x": x,
            "y": y,
            "radius": self.tile_size * 3 // 2,
            "solid_rects": [],
        }

    CAMP_TILES = {"kobold_camp": KOBOLD_CAMP_TILE, "kobold_camp_2": KOBOLD_CAMP2_TILE}
    CAMP_RESPAWN_ATTRS = {"kobold_camp": "camp_respawn_at", "kobold_camp_2": "camp2_respawn_at"}
    GRAVEYARD_MOBS = {"skeleton": (34, 55), "necromancer": (48, 58)}

    def kobold_alive(self):
        return self.kobold_respawn_at is None or time.time() >= self.kobold_respawn_at

    def camp_alive(self, eid="kobold_camp"):
        respawn_at = getattr(self, self.CAMP_RESPAWN_ATTRS[eid], None)
        return respawn_at is None or time.time() >= respawn_at

    def _sync_enemy_object(self, eid, visible, factory):
        present = any(obj.get("id") == eid for obj in self.objects)
        if visible and not present:
            self.objects.append(factory())
        elif not visible and present:
            self.objects = [obj for obj in self.objects if obj.get("id") != eid]
            if self.active_entity and self.active_entity.get("id") == eid:
                self.active_entity = None

    def _sync_kobold(self):
        """Кобольд и лагерь стоят на карте, пока живы; во время боя на арене их скрываем."""
        if not self.show_outside_city_locations:
            hidden_ids = {"kobold", *self.CAMP_TILES, "ancient_ent"}
            self.objects = [obj for obj in self.objects if obj.get("id") not in hidden_ids]
            return
        in_battle = self.arena is not None
        kobold_visible = not in_battle and self.kobold_alive()
        if kobold_visible:
            self.kobold_respawn_at = None
        self._sync_enemy_object("kobold", kobold_visible, self._kobold_object)
        for eid, attr in self.CAMP_RESPAWN_ATTRS.items():
            camp_visible = not in_battle and self.camp_alive(eid)
            if camp_visible:
                setattr(self, attr, None)
            self._sync_enemy_object(eid, camp_visible, lambda eid=eid: self._kobold_camp_object(eid))

    def _start_arena(self, source, enemy_tile, enemy_count, ally=False, boss=None):
        self.player_target = None
        self.player_state = "idle"
        self.active_entity = None
        self.hovered_entity = None
        self.guild_window.close()
        self.supplies_shop_window.close()
        self.card_shop_window.close()
        self.library_window.close()
        self.talent_tree_window.close()
        self.arena = ArenaController.start(
            self, enemy_tile, enemy_count=enemy_count, ally=ally, boss=boss
        )
        self.arena_source = source
        self.arena_reward_request_id = str(uuid.uuid4())
        self._sync_kobold()
        self._sync_graveyard()
        self.camera_follow_player = False
        self.camera_x, self.camera_y = self.arena.arena_center_world()
        self._clamp_camera()
        return True

    @staticmethod
    def _npc_xp_type(name):
        normalized = str(name).casefold()
        if "кобольд" in normalized:
            return "kobold"
        if "древний ент" in normalized:
            return "ancient_ent"
        if "король скелетов" in normalized:
            return "skeleton_king"
        if "страж" in normalized:
            return "skeleton_guard"
        if "некромансер" in normalized:
            return "necromancer"
        if "скелет" in normalized:
            return "skeleton"
        return None

    def _claim_npc_kill_xp(self, battle, source):
        """Просит сервер начислить опыт за убитых; возвращает текст ошибки, если опыт не начислен."""
        character = getattr(self.session, "character", None)
        if not isinstance(character, dict) or character.get("id") is None:
            return None
        defeated = [
            npc_type
            for enemy_id in battle.enemy_ids
            if battle.fighters[enemy_id].hp <= 0
            and (npc_type := self._npc_xp_type(battle.fighters[enemy_id].name)) is not None
        ]
        if not defeated:
            return None
        encounter_id = (
            f"dungeon_room_{self.dungeon_room}"
            if source == "dungeon"
            else source
        )
        try:
            result = self.session.client.claim_npc_kill_xp(
                character["id"],
                encounter_id,
                defeated,
                self.arena_reward_request_id,
            )
        except (ServerError, AttributeError, KeyError, OSError) as error:
            failure = f"Опыт не начислен: {error}"
            self.action_notice = failure
            self.action_notice_timer = 4.0
            return failure
        character.update(result["character"])
        xp_awarded = int(result["xp"])
        self._add_floating_message(
            f"+{xp_awarded} опыта",
            self.player_x,
            self.player_y - 54,
            (255, 220, 100),
        )
        return None

    def start_kobold_battle(self):
        if self.arena is not None or not self.kobold_alive():
            return False
        return self._start_arena("kobold", KOBOLD_SPAWN_TILE, 1)

    def start_camp_battle(self, eid="kobold_camp"):
        if self.arena is not None or not self.camp_alive(eid):
            return False
        return self._start_arena(eid, self.CAMP_TILES[eid], KOBOLD_CAMP_SIZE, ally=eid == "kobold_camp_2")

    def start_ancient_ent_battle(self):
        if self.arena is not None or self.ancient_ent_defeated:
            return False
        return self._start_arena(
            "ancient_ent", ANCIENT_ENT_TILE, 1, boss="ancient_ent"
        )

    def start_graveyard_battle(self, eid):
        if self.arena is not None or eid not in self.GRAVEYARD_MOBS or not self._graveyard_mob_alive(eid):
            return False
        return self._start_arena(eid, self.GRAVEYARD_MOBS[eid], 1, boss=eid)

    def _check_kobold_encounter(self):
        """Реакция на смену тайла: вход в гильдию и столкновение с врагами."""
        tile = self._player_tile()
        if tile == self._last_player_tile:
            return
        previous, self._last_player_tile = self._last_player_tile, tile
        if self.arena is not None:
            return
        if self.show_outside_city_locations:
            ent_x, ent_y = ANCIENT_ENT_TILE
            if not self.ancient_ent_defeated and max(abs(tile[0] - ent_x), abs(tile[1] - ent_y)) <= 1:
                self.start_ancient_ent_battle()
                return
            kx, ky = KOBOLD_SPAWN_TILE
            if self.kobold_alive() and max(abs(tile[0] - kx), abs(tile[1] - ky)) <= 1:
                self.start_kobold_battle()
                return
            for eid, (cx, cy) in self.CAMP_TILES.items():
                if self.camp_alive(eid) and max(abs(tile[0] - cx), abs(tile[1] - cy)) <= 2:
                    self.start_camp_battle(eid)
                    return
            for eid, (mx, my) in self.GRAVEYARD_MOBS.items():
                if self._graveyard_mob_alive(eid) and max(abs(tile[0] - mx), abs(tile[1] - my)) <= 1:
                    self.start_graveyard_battle(eid)
                    return
        if is_library_tile(*tile) and not (previous and is_library_tile(*previous)):
            self.player_target = None
            self.player_state = "idle"
            self.library_window.open()
        elif is_guild_tile(*tile) and not (previous and is_guild_tile(*previous)):
            self.player_target = None
            self.player_state = "idle"
            self.guild_window.open()
        elif is_supplies_shop_tile(*tile) and not (previous and is_supplies_shop_tile(*previous)):
            self.player_target = None
            self.player_state = "idle"
            self.supplies_shop_window.open()
        elif is_card_shop_tile(*tile) and not (previous and is_card_shop_tile(*previous)):
            self.player_target = None
            self.player_state = "idle"
            self.card_shop_window.open()
        elif is_tavern_tile(*tile) and not (previous and is_tavern_tile(*previous)):
            self.player_target = None
            self.player_state = "idle"
            self.navigate = "tavern"
            self.finished = True

    def save_character_quietly(self):
        character = getattr(self.session, "character", None)
        if not isinstance(character, dict):
            return
        try:
            self.session.client.save_character(character)
        except (ServerError, AttributeError, OSError):
            pass

    def _finish_arena(self):
        arena, self.arena = self.arena, None
        source = getattr(self, "arena_source", "kobold")
        self.arena_source = None
        battle = arena.battle
        result = battle.result
        character = getattr(self.session, "character", None)
        xp_failure = self._claim_npc_kill_xp(battle, source)
        self.arena_reward_request_id = None
        if source == "dungeon":
            if result == "win":
                self.dungeon_cleared_rooms.add(self.dungeon_room)
                if isinstance(character, dict):
                    character["hp"] = max(1, int(battle.player.hp))
                    character["mp"] = int(battle.player.mp)
                    self.save_character_quietly()
                self.player_target = None
                self.player_state = "idle"
                self.camera_follow_player = True
                self.camera_x, self.camera_y = self.player_x, self.player_y
                self._clamp_camera()
            else:
                if result == "loss" and isinstance(character, dict):
                    character["hp"] = int(character.get("max_hp", battle.player.max_hp))
                    character["mp"] = int(battle.player.mp)
                    self.save_character_quietly()
                self.exit_dungeon()
            return
        if result == "win":
            if source == "ancient_ent":
                self.ancient_ent_defeated = True
                message = "ДРЕВНИЙ ЕНТ повержен!"
            elif source in self.GRAVEYARD_MOBS:
                self.graveyard_respawn_at[source] = time.time() + KOBOLD_RESPAWN_SECONDS
                message = f"{'Некромансер' if source == 'necromancer' else 'Скелет'} повержен!"
            elif source in self.CAMP_RESPAWN_ATTRS:
                setattr(self, self.CAMP_RESPAWN_ATTRS[source], time.time() + KOBOLD_RESPAWN_SECONDS)
                message = "Лагерь кобольдов разгромлен!"
            else:
                self.kobold_respawn_at = time.time() + KOBOLD_RESPAWN_SECONDS
                message = "Кобольд повержен!"
            color = (120, 235, 140)
            hp = max(1, int(battle.player.hp))
            if source in self.CAMP_RESPAWN_ATTRS or source == "kobold":
                finished = quest_log_for(self.session).record_progress("kobold", len(battle.enemy_ids))
                for index, quest in enumerate(finished):
                    self._add_floating_message(f"Задание «{quest.title}» выполнено — сдайте в гильдии",
                                               self.player_x, self.player_y - 70 - index * 26, (255, 220, 90))
            elif source == "ancient_ent":
                finished = quest_log_for(self.session).record_progress("ancient_ent")
                for index, quest in enumerate(finished):
                    self._add_floating_message(f"Задание «{quest.title}» выполнено — сдайте в гильдии",
                                               self.player_x, self.player_y - 70 - index * 26, (255, 220, 90))
            elif source in self.GRAVEYARD_MOBS:
                finished = quest_log_for(self.session).record_progress(source)
                for index, quest in enumerate(finished):
                    self._add_floating_message(f"Задание «{quest.title}» выполнено — сдайте в гильдии",
                                               self.player_x, self.player_y - 70 - index * 26, (255, 220, 90))
            self._sync_graveyard()
        else:
            self.player_x, self.player_y = (float(v) for v in RESPAWN_CRYSTAL["approach_pos"])
            self.player_direction = "s"
            if result == "loss":
                message, color = "Вы пали и возродились у кристалла", (255, 120, 100)
                hp = int((character or {}).get("max_hp", battle.player.max_hp))
            else:
                message, color = "Телепорт к кристаллу возрождения", (110, 210, 255)
                hp = max(1, int(battle.player.hp))
        self.player_target = None
        self.player_state = "idle"
        self._last_player_tile = self._player_tile()
        self.camera_follow_player = True
        self.camera_x, self.camera_y = self.player_x, self.player_y
        self._clamp_camera()
        self._sync_kobold()
        self._add_floating_message(message, self.player_x, self.player_y - 40, color)
        self.action_notice = f"{message} {xp_failure}" if xp_failure else message
        self.action_notice_timer = 4.0 if xp_failure else 3.0
        if isinstance(character, dict):
            character["hp"] = hp
            character["mp"] = int(battle.player.mp)
            try:
                self.session.client.save_character(character)
            except (ServerError, AttributeError, OSError):
                pass

    def _update_dungeon_gate(self, dt):
        if not self.show_outside_city_locations:
            self.dungeon_entry_elapsed = None
            self.dungeon_fade_alpha = 0
            return
        if self.arena is not None:
            return
        if is_dungeon_entrance_tile(*self._player_tile(), bounds=self.dungeon_entrance_bounds):
            if self.dungeon_entry_elapsed is None:
                self.dungeon_entry_elapsed = 0.0
            self.dungeon_entry_elapsed = min(5.0, self.dungeon_entry_elapsed + dt)
            self.dungeon_fade_alpha = (
                min(255, int((self.dungeon_entry_elapsed - 2.0) * 85))
                if self.dungeon_entry_elapsed >= 2.0 else 0
            )
            if self.dungeon_entry_elapsed >= 5.0:
                self._enter_dungeon()
        else:
            self.dungeon_entry_elapsed = None
            self.dungeon_fade_alpha = 0

    def _enter_dungeon(self):
        self.dungeon_entry_elapsed = None
        self.dungeon_fade_alpha = 255
        self.player_target = None
        self.player_state = "idle"
        self.active_entity = None
        self.dungeon_treasure_request_id = None
        self.dungeon_cleared_rooms.clear()
        self.dungeon_completed_rooms.clear()
        self.dungeon_message = None
        self.dungeon_room_window.room = None
        self.dungeon_room_window.treasure_opened = False
        self.dungeon_room_window.treasure_request_id = None
        self.dungeon_room_window.treasure_rewards = []
        self._enter_dungeon_room(1)

    def _enter_dungeon_room(self, room):
        self.dungeon_room = int(room)
        if self.dungeon_room not in range(1, 7):
            raise ValueError("Комнаты подземелья идут от 1 до 6")
        ox, oy = DUNGEON_ROOM_ORIGIN
        self.player_x = (ox + 1.5) * self.tile_size
        self.player_y = (oy + DUNGEON_ROOM_SIZE[1] / 2 + 0.5) * self.tile_size
        self.player_target = None
        self.player_state = "idle"
        self.camera_follow_player = True
        self.camera_x, self.camera_y = self.player_x, self.player_y
        self._last_player_tile = self._player_tile()
        self.dungeon_room_window.close()
        self.arena = None
        self.arena_source = None
        self._clamp_camera()

    def advance_dungeon_room(self):
        if self.dungeon_room_window.is_open and self.dungeon_room == 2:
            self.dungeon_completed_rooms.add(2)
            self.dungeon_room_window.close()

    def _dungeon_gate_open(self):
        if self.dungeon_room in (1, 3, 5):
            return self.dungeon_room in self.dungeon_cleared_rooms
        if self.dungeon_room in (2, 4):
            return self.dungeon_room in self.dungeon_completed_rooms
        return False

    def _dungeon_room_world_bounds(self):
        left, top = DUNGEON_ROOM_ORIGIN
        width, height = DUNGEON_ROOM_SIZE
        return (
            left * self.tile_size,
            top * self.tile_size,
            (left + width) * self.tile_size,
            (top + height) * self.tile_size,
        )

    def _check_dungeon_collision(self, px, py):
        left, top, right, bottom = self._dungeon_room_world_bounds()
        if px - 10 < left or px + 10 > right or py - 6 < top or py + 6 > bottom:
            door_y = (DUNGEON_ROOM_ORIGIN[1] + DUNGEON_ROOM_SIZE[1] / 2) * self.tile_size
            can_pass_door = (
                self._dungeon_gate_open()
                and abs(py - door_y) <= self.tile_size / 2
                and self.dungeon_room < 6
            )
            if px + 10 > right and can_pass_door:
                return False
            return True
        if py - 6 <= top or py + 6 >= bottom or px - 10 <= left:
            return True
        if px + 10 >= right:
            door_y = (DUNGEON_ROOM_ORIGIN[1] + DUNGEON_ROOM_SIZE[1] / 2) * self.tile_size
            if not (
                self._dungeon_gate_open()
                and abs(py - door_y) <= self.tile_size / 2
                and self.dungeon_room < 6
            ):
                return True
        return False

    def _try_dungeon_room_transition(self):
        if self.dungeon_room >= 6 or not self._dungeon_gate_open():
            return False
        _, _, right, _ = self._dungeon_room_world_bounds()
        door_y = (DUNGEON_ROOM_ORIGIN[1] + DUNGEON_ROOM_SIZE[1] / 2) * self.tile_size
        if self.player_x + 10 >= right and abs(self.player_y - door_y) <= self.tile_size / 2:
            self._enter_dungeon_room(self.dungeon_room + 1)
            return True
        return False

    def _dungeon_actor_world_position(self):
        left, top = DUNGEON_ROOM_ORIGIN
        return (
            (left + 8.5) * self.tile_size,
            (top + DUNGEON_ROOM_SIZE[1] / 2 + 0.5) * self.tile_size,
        )

    def _interact_dungeon(self):
        if self.dungeon_room_window.is_open or self.arena is not None:
            return
        actor_x, actor_y = self._dungeon_actor_world_position()
        if math.hypot(self.player_x - actor_x, self.player_y - actor_y) > self.tile_size * 1.75:
            self.dungeon_message = "Подойдите ближе к объекту"
            return
        if self.dungeon_room == 2:
            self.dungeon_room_window.open(2)
        elif self.dungeon_room == 4:
            self._use_dungeon_fountain()
        elif self.dungeon_room == 6:
            if self.dungeon_room_window.treasure_opened:
                self.exit_dungeon()
            else:
                self.dungeon_room_window.open(6)

    def _update_dungeon_encounter(self):
        if self.dungeon_room not in (1, 3, 5) or self.dungeon_room in self.dungeon_cleared_rooms:
            return
        enemy_x, enemy_y = self._dungeon_actor_world_position()
        if math.hypot(self.player_x - enemy_x, self.player_y - enemy_y) > self.tile_size * 1.75:
            return
        self.player_target = None
        self.player_state = "idle"
        self.arena = ArenaController.start_dungeon(self, self.dungeon_room)
        self.arena_source = "dungeon"
        self.arena_reward_request_id = str(uuid.uuid4())
        self.camera_follow_player = False
        self.camera_x, self.camera_y = self.arena.arena_center_world()
        self._clamp_camera()

    def checkpoint_position(self):
        """Позиция для сохранения: внутри подземелья герой возвращается к его входу."""
        if self.dungeon_room is not None:
            left, top, _, height = self.dungeon_entrance_bounds
            x, y = tile_center(left - 1, top + height // 2)
            return float(x), float(y), self.player_direction
        return self.player_x, self.player_y, self.player_direction

    def exit_dungeon(self):
        dungeon_cleared = (
            self.dungeon_room == 6 and self.dungeon_room_window.treasure_opened
        )
        finished_quests = (
            quest_log_for(self.session).record_progress("dungeon_clear")
            if dungeon_cleared
            else []
        )
        self.dungeon_room_window.close()
        self.arena = None
        self.arena_source = None
        self.dungeon_room = None
        left, top, _, height = self.dungeon_entrance_bounds
        self.player_x, self.player_y = map(float, tile_center(left - 1, top + height // 2))
        self.player_target = None
        self.player_state = "idle"
        self.dungeon_entry_elapsed = None
        self.dungeon_fade_alpha = 0
        self.dungeon_cleared_rooms.clear()
        self.dungeon_completed_rooms.clear()
        self.dungeon_message = None
        self._last_player_tile = self._player_tile()
        self.camera_follow_player = True
        self.camera_x, self.camera_y = self.player_x, self.player_y
        self._clamp_camera()
        for index, quest in enumerate(finished_quests):
            self._add_floating_message(
                f"Задание «{quest.title}» выполнено — сдайте в гильдии",
                self.player_x,
                self.player_y - 70 - index * 26,
                (255, 220, 90),
            )

    def _use_dungeon_fountain(self):
        if 4 in self.dungeon_completed_rooms:
            self.dungeon_message = "Фонтан уже восстановил здоровье и ману"
            return True
        character = getattr(self.session, "character", None)
        if not isinstance(character, dict):
            return False
        character["hp"] = int(character.get("max_hp", 100))
        character["mp"] = int(character.get("max_mp", character.get("mp", 0)))
        try:
            self.session.client.save_character(character)
        except (ServerError, AttributeError, OSError) as error:
            self.dungeon_message = f"Исцеление не сохранено: {error}"
            return False
        self.dungeon_completed_rooms.add(4)
        self.dungeon_message = "Фонтан восстановил здоровье и ману"
        return True

    def _draw_dungeon_room(self, screen):
        screen.fill((18, 19, 23))
        left, top = DUNGEON_ROOM_ORIGIN
        width, height = DUNGEON_ROOM_SIZE
        door_y = top + height // 2
        gate_open = self._dungeon_gate_open()
        for tile_y in range(top, top + height):
            for tile_x in range(left, left + width):
                sx, sy = self.world_to_screen(tile_x * self.tile_size, tile_y * self.tile_size)
                sx2, sy2 = self.world_to_screen(
                    (tile_x + 1) * self.tile_size,
                    (tile_y + 1) * self.tile_size,
                )
                rect = pygame.Rect(sx, sy, sx2 - sx + 1, sy2 - sy + 1)
                is_wall = (
                    tile_y in (top, top + height - 1)
                    or tile_x == left
                    or (tile_x == left + width - 1 and not (tile_y == door_y and gate_open))
                )
                color = (61, 58, 60) if is_wall else (
                    (47, 45, 48) if (tile_x + tile_y) % 2 else (53, 50, 53)
                )
                pygame.draw.rect(screen, color, rect)
                pygame.draw.rect(screen, (32, 30, 33), rect, 1)
        if self.dungeon_room < 6:
            door_x, door_screen_y = self.world_to_screen(
                (left + width - 0.5) * self.tile_size,
                (door_y + 0.5) * self.tile_size,
            )
            if not gate_open:
                pygame.draw.line(
                    screen, (155, 55, 48), (door_x - 20, door_screen_y - 22),
                    (door_x - 20, door_screen_y + 22), 6,
                )
                pygame.draw.line(
                    screen, (155, 55, 48), (door_x + 20, door_screen_y - 22),
                    (door_x + 20, door_screen_y + 22), 6,
                )
        room_names = {
            1: "Комната I • Скелетный дозор",
            2: "Комната II • Подземный торговец",
            3: "Комната III • Некромант",
            4: "Комната IV • Целебный фонтан",
            5: "Комната V • Король скелетов",
            6: "Комната VI • Сокровищница",
        }
        title = self.large_font.render(room_names[self.dungeon_room], True, (220, 218, 207))
        screen.blit(title, title.get_rect(center=(settings.WIDTH // 2, 42)))
        actor_x, actor_y = self._dungeon_actor_world_position()
        actor_screen = self.world_to_screen(actor_x, actor_y)
        if self.arena is not None:
            self.arena.draw_world(screen)
            self._draw_player_character(screen)
            self.arena.draw_ui(screen)
        else:
            if self.dungeon_room in (1, 3, 5) and self.dungeon_room not in self.dungeon_cleared_rooms:
                enemy_names = {1: "2 СКЕЛЕТА", 3: "СКЕЛЕТЫ • НЕКРОМАНСЕР", 5: "СТРАЖА • КОРОЛЬ"}
                pygame.draw.ellipse(
                    screen, (17, 16, 18),
                    (actor_screen[0] - 56, actor_screen[1] + 8, 112, 26),
                )
                for offset in (-22, 22):
                    pygame.draw.circle(screen, (196, 194, 180), (actor_screen[0] + offset, actor_screen[1] - 22), 10)
                    pygame.draw.line(screen, (196, 194, 180), (actor_screen[0] + offset, actor_screen[1] - 12),
                                     (actor_screen[0] + offset, actor_screen[1] + 10), 4)
                enemy_label = self.small_font.render(enemy_names[self.dungeon_room], True, (235, 190, 155))
                screen.blit(enemy_label, enemy_label.get_rect(center=(actor_screen[0], actor_screen[1] + 34)))
            elif self.dungeon_room in (2, 4, 6):
                object_names = {2: "ТОРГОВЕЦ", 4: "ФОНТАН", 6: "СУНДУК"}
                object_colors = {2: (166, 122, 77), 4: (76, 157, 193), 6: (184, 138, 54)}
                pygame.draw.ellipse(
                    screen, (17, 16, 18),
                    (actor_screen[0] - 54, actor_screen[1] + 18, 108, 24),
                )
                if self.dungeon_room == 4:
                    pygame.draw.circle(screen, object_colors[4], actor_screen, 34)
                    pygame.draw.circle(screen, (147, 217, 230), actor_screen, 22, 4)
                else:
                    pygame.draw.rect(
                        screen, object_colors[self.dungeon_room],
                        (actor_screen[0] - 32, actor_screen[1] - 28, 64, 54),
                        border_radius=8,
                    )
                object_label = self.small_font.render(
                    object_names[self.dungeon_room], True, (245, 232, 195)
                )
                screen.blit(
                    object_label,
                    object_label.get_rect(center=(actor_screen[0], actor_screen[1] + 40)),
                )
            self._draw_player_character(screen)
            hint_text = "ПКМ — идти • E / ЛКМ — взаимодействовать"
            if self.dungeon_room in (1, 3, 5) and not gate_open:
                hint_text = "Враги преграждают проход"
            elif self.dungeon_room == 2 and not gate_open:
                hint_text = "Поговорите с торговцем и закройте магазин, чтобы пройти дальше"
            elif self.dungeon_room == 4 and not gate_open:
                hint_text = "Используйте фонтан, чтобы открыть проход"
            elif self.dungeon_room == 6:
                hint_text = "Откройте сундук и заберите награды"
            hint = self.small_font.render(hint_text, True, (235, 220, 185))
            screen.blit(hint, hint.get_rect(center=(settings.WIDTH // 2, settings.HEIGHT - 36)))
            if self.dungeon_message:
                message = self.small_font.render(self.dungeon_message, True, (255, 220, 150))
                screen.blit(message, message.get_rect(center=(settings.WIDTH // 2, settings.HEIGHT - 62)))
            if self.dungeon_room == 6 and self.dungeon_room_window.treasure_opened:
                exit_hint = self.small_font.render("Подойдите к сундуку и нажмите E, чтобы выйти", True, (200, 230, 200))
                screen.blit(exit_hint, exit_hint.get_rect(center=(settings.WIDTH // 2, settings.HEIGHT - 88)))
            self.dungeon_room_window.draw(screen)
        if self.dungeon_fade_alpha:
            shade = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
            shade.fill((0, 0, 0, self.dungeon_fade_alpha))
            screen.blit(shade, (0, 0))

    def _draw_dungeon_entrance(self, screen):
        left, top, width, height = self.dungeon_entrance_bounds
        x, y = self.world_to_screen((left + width / 2) * self.tile_size,
                                    (top + height / 2) * self.tile_size)
        scale = self.zoom
        arch = pygame.Rect(
            int(x - 24 * scale),
            int(y - 34 * scale),
            max(1, int(48 * scale)),
            max(1, int(68 * scale)),
        )
        pygame.draw.rect(screen, (20, 20, 24), arch, border_radius=12)
        pygame.draw.rect(screen, (104, 105, 112), arch, max(1, int(5 * scale)), border_radius=12)
        pygame.draw.ellipse(screen, (5, 6, 8), arch.inflate(-int(14 * scale), -int(12 * scale)))
        self._draw_badge(screen, x, arch.top, "ВХОД В ПОДЗЕМЕЛЬЕ", (140, 140, 150))

    def _set_city_area(self, area):
        self.city_bounds = tuple(area["bounds"])
        self.city_wall_tiles = {tuple(tile) for tile in area.get("wall_tiles", [])}
        self.city_wall_rects = [pygame.Rect(rect) for rect in area.get("solid_rects", [])]

    def is_city_tile(self, tile_x, tile_y):
        return is_city_tile(tile_x, tile_y, self.city_bounds)

    def player_in_city(self):
        return self.is_city_tile(int(self.player_x // self.tile_size), int(self.player_y // self.tile_size))

    def is_forest_tile(self, tile_x, tile_y):
        return is_forest_tile(tile_x, tile_y, self.forest_bounds)

    def player_in_forest(self):
        return self.is_forest_tile(int(self.player_x // self.tile_size), int(self.player_y // self.tile_size))

    def _load_terrain(self):
        """Рельеф, строения и проложенные сервером дороги приходят готовыми для отрисовки."""
        try:
            terrain = self.session.client.get_map_terrain()
        except (ServerError, AttributeError, KeyError, OSError):
            self.road_tiles = set()
            self.road_travel_seconds = 0
            return []

        if terrain.get("map_version") != MAP_VERSION:
            # Старый сервер присылает пиксели под другой размер тайла — используем локальную раскладку
            terrain = {
                **terrain,
                "width_tiles": MAP_WIDTH_TILES,
                "height_tiles": MAP_HEIGHT_TILES,
                "objects": [dict(RESPAWN_CRYSTAL)],
                "obstacles": [],
                "city_area": None,
                "forest_area": None,
                "library_area": None,
                "graveyard_area": None,
                "roads": {"routes": [], "tiles": [], "travel_seconds": 0},
            }
        self.objects = hydrate_structures(terrain.get("objects", []))
        # Старый сервер не присылает зону города — остаётся локальная раскладка стен
        if terrain.get("city_area"):
            self._set_city_area(terrain["city_area"])
        if self.show_outside_city_locations and terrain.get("forest_area"):
            self.forest_bounds = tuple(terrain["forest_area"]["bounds"])
        if terrain.get("library_area"):
            self.library_bounds = tuple(terrain["library_area"]["bounds"])
        if self.show_outside_city_locations and terrain.get("graveyard_area"):
            self.graveyard_bounds = tuple(terrain["graveyard_area"]["bounds"])
        roads = terrain.get("roads", {})
        self.road_tiles = {tuple(tile) for tile in roads.get("tiles", [])}
        self.road_routes = roads.get("routes", [])
        self.road_travel_seconds = roads.get("travel_seconds", 0)
        obstacles = []
        for obstacle in terrain.get("obstacles", []) if self.show_outside_city_locations else []:
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
                elif action == "delete_deck":
                    try:
                        self.session.delete_deck(profile.get("id"))
                        self.profile_overlay.deck_panel.open(self.session.get_decks())
                    except (ServerError, AttributeError, OSError) as error:
                        self.profile_overlay.deck_panel.error = str(error)
                return

        if self.chat is not None and self.chat.handle_event(event):
            return

        if self.dungeon_room is not None:
            if self.dungeon_room_window.is_open:
                self.dungeon_room_window.handle_event(event)
            elif self.arena is not None:
                self.arena.handle_event(event)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_e:
                self._interact_dungeon()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._interact_dungeon()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                wx, wy = self.screen_to_world(*event.pos)
                left, top, right, bottom = self._dungeon_room_world_bounds()
                self.player_target = (
                    max(left + 18, min(right + self.tile_size, wx)),
                    max(top + 18, min(bottom - 18, wy)),
                )
                self.player_state = "walk"
                self.camera_follow_player = True
            return

        # Окно гильдии модальное: пока открыто, клики по карте не проходят
        if self.guild_window.is_open:
            self.guild_window.handle_event(event)
            return
        if self.library_window.is_open:
            self.library_window.handle_event(event)
            return
        if self.talent_tree_window.is_open:
            self.talent_tree_window.handle_event(event)
            return
        if self.supplies_shop_window.is_open or self.card_shop_window.is_open:
            if self.card_shop_window.is_open:
                self.card_shop_window.handle_event(event)
                return
            self.supplies_shop_window.handle_event(event)
            return

        # Во время боя на арене ввод мыши принадлежит интерфейсу боя
        if self.arena is not None and self.arena.handle_event(event):
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
        if self.arena is not None:
            self.arena.update(dt)
            if self.arena.done:
                self._finish_arena()
        self._sync_kobold()
        # 1. Движение персонажа к целевой точке (Dota-стиль) с проверкой коллизий
        if self.player_target is not None and self.arena is None:
            tx, ty = self.player_target
            dx = tx - self.player_x
            dy = ty - self.player_y
            dist = math.hypot(dx, dy)
            step = self.player_speed * dt

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

        if self.dungeon_room is None:
            self._update_dungeon_gate(dt)
        elif self.arena is None:
            if not self._try_dungeon_room_transition():
                self._update_dungeon_encounter()
        if self.arena is None and self.dungeon_room is None:
            self._sync_graveyard()
            self._check_kobold_encounter()
        if self.dungeon_room_window.is_open:
            self.dungeon_room_window.update(dt)
        if self.dungeon_room is not None and self.dungeon_fade_alpha:
            self.dungeon_fade_alpha = max(0, self.dungeon_fade_alpha - int(510 * dt))

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
        if (self.arena is not None or self.guild_window.is_open
                or self.library_window.is_open
                or self.talent_tree_window.is_open
                or self.supplies_shop_window.is_open
                or self.card_shop_window.is_open
                or m_pos[1] <= 75
                or (self.active_entity and self.active_window_rect.collidepoint(m_pos))):
            self.hovered_entity = None
            self.hovered_player = None
        else:
            self.hovered_entity = self._find_entity_at(m_pos)
            self.hovered_player = player_at(self, m_pos, "world_map")

        # 6. Таймер уведомления о действии
        if self.action_notice_timer > 0:
            self.action_notice_timer -= dt
            if self.action_notice_timer <= 0:
                self.action_notice = None

        # 7. Скролл карты стрелками / WASD
        if self.dungeon_room is None:
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
            s_cancels = self.arena is not None and self.arena.mode == "cards"
            if (keys[pygame.K_s] and not s_cancels) or keys[pygame.K_DOWN]:
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
        if self.dungeon_room is not None:
            self._draw_dungeon_room(screen)
            return
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

                if (gx, gy) in self.city_wall_tiles:
                    cell_color = (48, 48, 52) if (gx + gy) % 2 == 0 else (42, 42, 46)
                elif is_guild_tile(gx, gy):
                    # Зона гильдии искателей приключений (часть города)
                    cell_color = (196, 160, 40) if (gx + gy) % 2 == 0 else (206, 170, 48)
                elif is_supplies_shop_tile(gx, gy):
                    cell_color = (35, 95, 155) if (gx + gy) % 2 == 0 else (42, 108, 170)
                elif is_card_shop_tile(gx, gy):
                    cell_color = (117, 70, 145) if (gx + gy) % 2 == 0 else (130, 80, 158)
                elif is_library_tile(gx, gy, self.library_bounds):
                    cell_color = (62, 62, 68) if (gx + gy) % 2 == 0 else (70, 70, 76)
                elif is_graveyard_tile(gx, gy, self.graveyard_bounds):
                    cell_color = (53, 59, 57) if (gx + gy) % 2 == 0 else (60, 66, 63)
                if self.is_city_tile(gx, gy):
                    # Городская мостовая внутри стен
                    cell_color = (108, 108, 112) if (gx + gy) % 2 == 0 else (116, 116, 120)
                elif self.is_forest_tile(gx, gy):
                    cell_color = (14, 48, 22) if (gx + gy) % 2 == 0 else (17, 54, 26)

                pygame.draw.rect(screen, cell_color, rect)

                if (gx, gy) in self.city_wall_tiles:
                    pygame.draw.rect(screen, (66, 66, 72), rect.inflate(-6, -6), border_radius=3)
                    pygame.draw.rect(screen, (28, 28, 32), rect.inflate(-6, -6), 2, border_radius=3)

                if (gx, gy) in self.road_tiles:
                    pygame.draw.line(screen, (95, 74, 44), rect.topleft, rect.topright, 1)
                    pygame.draw.line(screen, (95, 74, 44), rect.bottomleft, rect.bottomright, 1)

                if self.show_grid:
                    pygame.draw.rect(screen, (45, 52, 60), rect, 1)

        # 2. Рельеф с сервера и интерактивные объекты карты
        self._draw_terrain(screen)
        self._draw_guild_label(screen)
        self._draw_supplies_shop_label(screen)
        self._draw_card_shop_label(screen)
        self._draw_tavern_label(screen)
        self._draw_library_label(screen)
        self._draw_talent_tree_label(screen)
        if self.show_outside_city_locations:
            self._draw_graveyard_label(screen)
            self._draw_dungeon_entrance(screen)
        self._draw_objects(screen)
        if self.arena is not None:
            self.arena.draw_world(screen)

        # 3. Игровой персонаж и эффекты клика (Dota-стиль)
        self._draw_click_effect(screen)
        self._draw_player_character(screen)
        draw_active_players(self, screen, "world_map")
        draw_afk_players(self, screen, "world_map")

        # 4. Всплывающие сообщения в мире ("Слишком далеко" и т.д.)
        self._draw_floating_messages(screen)

        # 5. Всплывающее окно активного объекта (ЛКМ)
        if self.arena is None:
            self._draw_active_window(screen)

            # 6. Всплывающее окно при наведении курсора (hover tooltip)
            self._draw_hover_popup(screen, mouse_pos)

        # 7. Верхний HUD и подсказки
        self._draw_hud(screen, hover_wx, hover_wy)
        if self.arena is not None:
            self.arena.draw_ui(screen)
        if self.dungeon_entry_elapsed is not None and self.dungeon_entry_elapsed >= 2:
            shade = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
            shade.fill((0, 0, 0, self.dungeon_fade_alpha))
            screen.blit(shade, (0, 0))

        if self.guild_window.is_open:
            self.guild_window.draw(screen)
        if self.library_window.is_open:
            self.library_window.draw(screen)
        if self.talent_tree_window.is_open:
            self.talent_tree_window.draw(screen)
        if self.supplies_shop_window.is_open:
            self.supplies_shop_window.draw(screen)
        if self.card_shop_window.is_open:
            self.card_shop_window.draw(screen)
        if self.chat is not None:
            self.chat.draw(screen)
        if self.hovered_player is not None:
            draw_player_hover_card(screen, self.hovered_player)
        else:
            self.profile_overlay.draw(screen, opponent=self.session.character, show_player_only=True)

    def _draw_guild_label(self, screen):
        gx, gy, gw, _ = GUILD_BOUNDS
        sx, sy = self.world_to_screen((gx + gw / 2) * self.tile_size, gy * self.tile_size)
        self._draw_badge(screen, int(sx), int(sy) - 4, "Гильдия искателей приключений", (235, 200, 70))

    def _draw_supplies_shop_label(self, screen):
        sx, sy, width, _ = SUPPLIES_SHOP_BOUNDS
        x, y = self.world_to_screen((sx + width / 2) * self.tile_size, sy * self.tile_size)
        self._draw_badge(screen, int(x), int(y) - 4, "Магазин с припасами", (105, 185, 245))

    def _draw_card_shop_label(self, screen):
        sx, sy, width, _ = CARD_SHOP_BOUNDS
        x, y = self.world_to_screen((sx + width / 2) * self.tile_size, sy * self.tile_size)
        self._draw_badge(screen, int(x), int(y) - 4, "Карточная лавка", (205, 150, 240))

    def _draw_tavern_label(self, screen):
        sx, sy, width, _ = TAVERN_BOUNDS
        x, y = self.world_to_screen((sx + width / 2) * self.tile_size, sy * self.tile_size)
        self._draw_badge(screen, int(x), int(y) - 4, "Таверна", (225, 170, 110))

    def _draw_library_label(self, screen):
        x, y, width, _ = self.library_bounds
        sx, sy = self.world_to_screen((x + width / 2) * self.tile_size, y * self.tile_size)
        self._draw_badge(screen, int(sx), int(sy) - 4, "Библиотека", (150, 150, 175))

    def _draw_talent_tree_label(self, screen):
        sx, sy = self.world_to_screen(23 * self.tile_size, 37 * self.tile_size)
        self._draw_badge(
            screen, int(sx), int(sy) - 4, "Древо талантов", (155, 210, 125)
        )

    def _draw_graveyard_label(self, screen):
        x, y, width, _ = self.graveyard_bounds
        sx, sy = self.world_to_screen((x + width / 2) * self.tile_size, y * self.tile_size)
        self._draw_badge(screen, int(sx), int(sy) - 4, "Кладбище", (135, 155, 145))

    def _draw_kobold_camp(self, screen, obj):
        ts = self.tile_size
        cx, cy = self.world_to_screen(obj["x"], obj["y"])
        cx, cy = int(cx), int(cy)
        # Шатёр
        tent = [(cx - ts, cy - ts // 4), (cx - ts // 4, cy - ts - ts // 3), (cx + ts // 2, cy - ts // 4)]
        pygame.draw.polygon(screen, (122, 82, 46), tent)
        pygame.draw.polygon(screen, (70, 44, 24), tent, 2)
        pygame.draw.polygon(screen, (40, 26, 16), [(cx - ts // 2, cy - ts // 4), (cx - ts // 4, cy - ts // 1.4),
                                                   (cx, cy - ts // 4)])
        # Костёр
        flicker = 0.85 + 0.15 * math.sin(self.player_anim_timer * 9.0)
        pygame.draw.line(screen, (92, 60, 32), (cx - 10, cy + 10), (cx + 10, cy + 4), 4)
        pygame.draw.line(screen, (92, 60, 32), (cx - 10, cy + 4), (cx + 10, cy + 10), 4)
        pygame.draw.circle(screen, (240, 130, 40), (cx, cy + 2), int(9 * flicker))
        pygame.draw.circle(screen, (255, 220, 110), (cx, cy + 4), int(4 * flicker))
        # Три кобольда вокруг костра
        for dx, dy in ((ts, -ts // 3), (-ts, ts // 2), (ts // 2, ts)):
            draw_kobold(screen, cx + dx, cy + dy, ts)
        label = f"Лагерь кобольдов • {KOBOLD_CAMP_SIZE} врага"
        if obj.get("id") == "kobold_camp_2":
            label = f"Лесной лагерь • {KOBOLD_CAMP_SIZE} врага • союзник Ельпачино Фред"
        self._draw_badge(screen, cx, cy - int(ts * 1.5), label, (220, 90, 70))

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
            if obj.get("id") == "crystal_of_life":
                self._draw_respawn_crystal(screen, obj, pulse)

            elif obj.get("id") == "kobold":
                sx, sy = self.world_to_screen(obj["x"], obj["y"])
                draw_kobold(screen, sx, sy, self.tile_size)
                self._draw_badge(screen, sx, sy - int(self.tile_size * 0.85), "Кобольд • 1 ур.", (220, 90, 70))

            elif obj.get("id") == "ancient_ent":
                sx, sy = self.world_to_screen(obj["x"], obj["y"])
                scale = max(1, round(self.tile_size * self.zoom))
                k = scale / 48
                pygame.draw.ellipse(screen, (11, 17, 12), (
                    sx - int(42 * k), sy + int(12 * k), int(84 * k), int(20 * k)
                ))
                trunk = pygame.Rect(
                    sx - int(15 * k), sy - int(20 * k), int(30 * k), int(54 * k)
                )
                pygame.draw.rect(screen, (98, 61, 34), trunk, border_radius=max(4, int(8 * k)))
                pygame.draw.rect(screen, (53, 42, 27), trunk, max(1, int(3 * k)),
                                 border_radius=max(4, int(8 * k)))
                for dx, dy, radius in ((-26, -29, 25), (0, -45, 30), (26, -29, 25),
                                       (-14, -10, 24), (15, -11, 24)):
                    center = (sx + int(dx * k), sy + int(dy * k))
                    pygame.draw.circle(screen, (37, 104, 49), center, int(radius * k))
                    pygame.draw.circle(screen, (22, 72, 34), center, int(radius * k),
                                       max(1, int(2 * k)))
                for eye_x in (-7, 7):
                    pygame.draw.circle(screen, (255, 190, 65),
                                       (sx + int(eye_x * k), sy - int(3 * k)),
                                       max(2, int(3 * k)))
                label = "ДРЕВНИЙ ЕНТ" if not self.ancient_ent_defeated else "Энт повержен"
                self._draw_badge(screen, sx, sy - int(1.35 * scale), label,
                                 (220, 150, 75) if not self.ancient_ent_defeated else (130, 170, 125))

            elif obj.get("id") == "library":
                sx, sy = self.world_to_screen(
                    obj["tile_x"] * self.tile_size, obj["tile_y"] * self.tile_size
                )
                width = obj["tile_w"] * self.tile_size
                height = obj["tile_h"] * self.tile_size
                building = pygame.Rect(int(sx), int(sy), width, height)
                pygame.draw.rect(screen, (48, 48, 60), building, border_radius=5)
                pygame.draw.rect(screen, (112, 112, 135), building, 3, border_radius=5)
                for index in range(1, obj["tile_w"]):
                    x = building.left + index * self.tile_size
                    pygame.draw.line(screen, (72, 72, 88), (x, building.top + 8),
                                     (x, building.bottom - 8), 2)
                for index in range(1, obj["tile_h"]):
                    y = building.top + index * self.tile_size
                    pygame.draw.line(screen, (72, 72, 88), (building.left + 8, y),
                                     (building.right - 8, y), 2)
                pygame.draw.rect(
                    screen, (112, 82, 54),
                    (building.centerx - self.tile_size // 4, building.bottom - self.tile_size,
                     self.tile_size // 2, self.tile_size),
                )
                self._draw_badge(screen, building.centerx, building.top - 8,
                                 "БИБЛИОТЕКА", (165, 165, 190))

            elif obj.get("id") == "talent_tree":
                sx, sy = self.world_to_screen(obj["x"], obj["y"])
                scale = max(1, round(self.tile_size * self.zoom))
                k = scale / 48
                pygame.draw.ellipse(
                    screen, (12, 19, 13),
                    (sx - int(34 * k), sy + int(13 * k), int(68 * k), int(16 * k)),
                )
                trunk = pygame.Rect(
                    sx - int(9 * k), sy - int(5 * k), int(18 * k), int(46 * k)
                )
                pygame.draw.rect(screen, (105, 75, 43), trunk, border_radius=max(2, int(5 * k)))
                for dx, dy, radius in ((-17, -18, 19), (0, -31, 23), (17, -18, 19)):
                    center = (sx + int(dx * k), sy + int(dy * k))
                    pygame.draw.circle(screen, (78, 145, 66), center, max(2, int(radius * k)))
                    pygame.draw.circle(
                        screen, (48, 105, 48), center, max(2, int(radius * k)),
                        max(1, int(2 * k)),
                    )

            elif obj.get("id") in ("skeleton", "necromancer"):
                sx, sy = self.world_to_screen(obj["x"], obj["y"])
                if obj.get("id") == "skeleton":
                    draw_skeleton(screen, int(sx), int(sy), self.tile_size * self.zoom)
                    badge = "СКЕЛЕТ"
                    badge_color = (190, 185, 160)
                else:
                    draw_necromancer(screen, int(sx), int(sy), self.tile_size * self.zoom)
                    badge = "НЕКРОМАНСЕР"
                    badge_color = (175, 110, 195)
                self._draw_badge(
                    screen, int(sx), int(sy - int(self.tile_size * self.zoom * 0.7)),
                    badge, badge_color,
                )

            elif obj.get("id") in ("kobold_camp", "kobold_camp_2"):
                self._draw_kobold_camp(screen, obj)

            elif obj.get("id") == "lumber_camp":
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

                for tile_x, tile_y in obj.get("stump_tiles", []):
                    if (int(tile_x), int(tile_y)) in self.road_tiles:
                        continue
                    stump_x, stump_y = self.world_to_screen(
                        (int(tile_x) + 0.5) * self.tile_size,
                        (int(tile_y) + 0.5) * self.tile_size,
                    )
                    if not (-24 <= stump_x <= settings.WIDTH + 24
                            and -20 <= stump_y <= settings.HEIGHT + 20):
                        continue
                    pygame.draw.ellipse(screen, (22, 27, 16),
                                        (stump_x - 11, stump_y + 4, 24, 9))
                    pygame.draw.ellipse(screen, (84, 55, 32),
                                        (stump_x - 9, stump_y - 5, 18, 14))
                    pygame.draw.ellipse(screen, (178, 139, 82),
                                        (stump_x - 7, stump_y - 6, 14, 9))
                    pygame.draw.ellipse(screen, (125, 88, 51),
                                        (stump_x - 3, stump_y - 4, 6, 4))

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

    def _draw_respawn_crystal(self, screen, obj, pulse):
        sx, sy = self.world_to_screen(
            obj["tile_x"] * self.tile_size,
            obj["tile_y"] * self.tile_size,
        )
        width = obj["tile_w"] * self.tile_size
        height = obj["tile_h"] * self.tile_size
        bounds = pygame.Rect(sx, sy, width, height)
        if not bounds.colliderect(pygame.Rect(0, 0, settings.WIDTH, settings.HEIGHT)):
            return

        is_active = self.active_entity and self.active_entity.get("id") == obj["id"]
        is_hovered = self.hovered_entity and self.hovered_entity.get("id") == obj["id"]
        cx, cy = bounds.center
        k = self.tile_size / 32
        glow_radius = int(34 * k * pulse)
        glow = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (65, 205, 255, 36), (glow_radius, glow_radius), glow_radius)
        pygame.draw.circle(glow, (105, 230, 255, 24), (glow_radius, glow_radius), glow_radius // 2)
        screen.blit(glow, (cx - glow_radius, cy - glow_radius))

        pedestal = pygame.Rect(sx + int(12 * k), sy + height - int(28 * k), width - int(24 * k), int(20 * k))
        pygame.draw.ellipse(screen, (14, 29, 38), pedestal.move(0, 5))
        pygame.draw.ellipse(screen, (35, 92, 112), pedestal)
        pygame.draw.ellipse(screen, (105, 218, 238), pedestal, 2)
        pygame.draw.line(screen, (116, 225, 255), (pedestal.left + 8, cy + int(16 * k)),
                         (pedestal.right - 8, cy + int(16 * k)), 2)

        mid = (cx, cy + int(10 * k))
        crystal = [
            (cx, sy + int(8 * k)),
            (cx + int(18 * k), cy - int(8 * k)),
            (cx + int(12 * k), cy + int(18 * k)),
            (cx, sy + height - int(28 * k)),
            (cx - int(12 * k), cy + int(18 * k)),
            (cx - int(18 * k), cy - int(8 * k)),
        ]
        pygame.draw.polygon(screen, (35, 152, 205), crystal)
        pygame.draw.polygon(screen, (151, 240, 255), [crystal[0], crystal[1], mid])
        pygame.draw.polygon(screen, (68, 197, 232), [crystal[0], mid, crystal[5]])
        pygame.draw.polygon(screen, (33, 122, 181), [crystal[1], crystal[2], mid])
        pygame.draw.polygon(screen, (23, 93, 150), [crystal[2], crystal[3], mid])
        pygame.draw.polygon(screen, (46, 166, 211), [crystal[3], crystal[4], mid])
        pygame.draw.polygon(screen, (94, 220, 245), [crystal[4], crystal[5], mid])
        pygame.draw.polygon(screen, (205, 252, 255), crystal, 2)

        if is_active:
            pygame.draw.rect(screen, (255, 215, 60), bounds, 2, border_radius=8)
        elif is_hovered:
            pygame.draw.rect(screen, (80, 200, 255), bounds.inflate(6, 6), 2, border_radius=8)
        badge_color = (255, 215, 60) if is_active else (100, 200, 255) if is_hovered else (170, 235, 255)
        self._draw_badge(screen, cx, sy - 8, f"💎 {obj['name']} [3x3]", badge_color)

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
        if self.hovered_player is not None:
            return
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
        title_x = box_x + 12
        title = f"{ent.get('icon', '📍')} {name}"
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
        if self.active_entity is None:
            return

        ent = self.active_entity
        rect = self.active_window_rect

        win_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(win_surf, (15, 20, 28, 245), (0, 0, rect.width, rect.height), border_radius=8)
        pygame.draw.rect(win_surf, (220, 185, 60, 255), (0, 0, rect.width, rect.height), width=2, border_radius=8)
        screen.blit(win_surf, rect.topleft)

        name = ent.get("name", "Объект")
        title_x = rect.left + 14
        title = f"{ent.get('icon', '📍')} {name}"
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
            elif ent.get("id") in ("kobold", "kobold_camp", "kobold_camp_2"):
                action_label = "НАПАСТЬ"
            elif ent.get("id") == "ancient_ent":
                action_label = "ОСМОТРЕТЬ ДЕРЕВО" if self.ancient_ent_defeated else "ВЫЗВАТЬ ДРЕВНЕГО ЕНТА"
            elif ent.get("id") == "crystal_of_life":
                action_label = "ВОССТАНОВИТЬ ЗДОРОВЬЕ"
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
        character = getattr(self.session, "character", None)
        char_name = character.get("name", "Герой") if isinstance(character, dict) else "Герой"
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

        zone_str = " | Город" if self.player_in_city() else " | Лес" if self.player_in_forest() else ""
        info_str = f"Карта: {self.grid_w}x{self.grid_h} ({self.tile_size}px) | Персонаж: X={int(self.player_x)}, Y={int(self.player_y)} | Тайл: [{hover_gx}, {hover_gy}]{zone_str}"
        info_surf = self.font.render(info_str, True, (240, 240, 240))
        screen.blit(info_surf, (640, 27))

        hint_str = "ЛКМ - активировать объект | Наведение - всплывающее окно | ПКМ - бежать | Drag ЛКМ - скролл | G - Сетка"
        hint_surf = self.small_font.render(hint_str, True, (160, 170, 180))
        screen.blit(hint_surf, (20, settings.HEIGHT - 25))

    def close(self):
        pass
