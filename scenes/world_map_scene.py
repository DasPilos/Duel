from pathlib import Path
import math
import random
import time
import pygame
from core import settings
from core.currency import Currency
from core.carry_weight import character_movement_speed_multiplier
from combat.fighter import Fighter
from combat.fighter_profile import apply_fighter_profile
from combat.world_stats import (
    get_attack_reach,
    get_move_speed,
    get_world_max_hp,
    get_world_max_mana,
)
from core.mob_profiles import NPC_KEYS, npc_profiles
from core.npc_catalog import NPC_FRAME, NPC_FRAMES_PER_ROW, NPC_ROW_DOWN, NPC_ROW_LEFT, NPC_ROW_RIGHT, NPC_ROW_UP, facing_row, npc_catalog, sheet_path
from core.player_movement import find_tile_path, follow_path
from core.tile_mask import mask_blocks_rect
from core.production_buildings import plot_slot_ranges
from client.network import ServerError
from client.structures import hydrate_structures
from ui.character_card import CharacterCard
from ui.character_profile import profile_from_fighter
from ui.hud import draw_button, draw_city_upgrade_line, upgrade_line_font
from ui.character_profile_overlay import CharacterProfileOverlay
from ui.sprite_loader import FighterSprite
from ui.sfx import play_dash_sound, play_dash_whirl_sound, play_random_sound, set_run_sound, swing_sounds_for_weapon
from combat.dash import (
    DASH_COOLDOWN,
    DASH_HIT_RADIUS,
    DASH_MIN_LENGTH,
    DASH_TRAIL_DURATION,
    dash_end_point,
)
from ui.hotbar import HOTBAR_FLASH_DURATION, HOTBAR_KEYS, draw_hotbar, hotbar_index_for_key, hotbar_slot_rects
from ui.chat import ChatDialog, PresenceState
from ui.combat_log import CombatLog
from ui.afk_presence import draw_active_players, draw_afk_players
from ui.catalog_icons import draw_building_icon
from ui.map_travel import draw_mobile_hover_card, draw_traveling_entities, mobile_entity_at
from ui.production_building_window import VIEWS, ProductionBuildingWindow, object_building, point_in_polygon
from scenes.city.exterior import draw_city_exterior
from scenes.map_common import draw_map_badge, screen_px_to_world
from scenes.player_sprites import (
    WARRIOR_ATTACK_ANIMATIONS,
    load_player_directional_sprites,
    player_frame,
    player_label_top,
    player_profession,
)
from ui.profession_icons import PROFESSION_ICON_SIZE, draw_profession_icon_before, profession_icon


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


MOB_LEVEL = 1
# Длительность маркера клика ПКМ по земле (секунды).
CLICK_EFFECT_DURATION = 0.35
# Синхронизация с сервером мира: чаще во время рывка (секунды).
WORLD_SYNC_INTERVAL = 0.1
WORLD_SYNC_DASH_INTERVAL = 0.05
# Цвета строк лога боя, которые присылает сервер мира.
WORLD_LOG_COLORS = {"player": settings.PLAYER_LOG_COLOR, "enemy": settings.ENEMY_HIT_LOG_COLOR, "miss": settings.NO_HIT_LOG_COLOR}
DASH_HOTBAR_SLOT = 0  # слот «1» на панели: первый спец-удар — рывок
HERO_HIT_SECONDS = 0.45  # сколько играет анимация получения удара
HERO_DEATH_SECONDS = 1.0  # сколько герой падает; после этого держится последний кадр, пока здоровье на нуле
DASH_TRAIL_SIZE = 64  # px на земле (умножается на зум) — размер спрайта следа
DASH_AIM_COLOR = (90, 255, 120)
# Профили мобов — только виды из редактора карт; их характеристики и экипировка приходят с сервера в снимке мира.
MOB_PROFILES = dict(npc_profiles())  # бесы карты: название и подписи в логе боя
PLAYER_REPATH_INTERVAL = 0.3  # как часто пересчитывать путь к движущемуся мобу
PLAYER_STALL_TIMEOUT = 0.4  # если персонаж не может продвинуться так долго, путь сбрасывается
DAMAGE_NUMBER_DURATION = 5.0
DAMAGE_COLOR_NORMAL = (255, 255, 255)  # обычный урон — белый
DAMAGE_COLOR_CRIT = (255, 50, 50)  # критический урон — красный, шрифт вдвое крупнее
DAMAGE_COLOR_DODGE = (120, 200, 255)  # «Уворот» — голубой
DAMAGE_COLOR_BLOCK = (190, 195, 205)  # «Блок» — серебристый
DAMAGE_COLOR_MISS = (200, 200, 200)  # «Промах» — серый
EDGE_SCROLL_MARGIN = 40  # px от края окна: курсор в этой полосе двигает камеру
EDGE_SCROLL_SPEED = 600.0  # скорость краевой прокрутки, px экрана в секунду
DRAG_THRESHOLD = 6  # px: дальше этого ЛКМ — перетаскивание карты, а не клик
DOUBLE_CLICK_MS = 350
MOB_SPRITE_SIZE = (90, 53)
MOB_WALK_FPS = 8
MOB_WALK_HOLD_MS = 300  # моб считается идущим, пока его позиция менялась за последние 300 мс
MOB_CORPSE_FALL_MS = 500  # без листа смерти тело валится на бок
MOB_DEATH_FPS = 7  # лист смерти: 7 кадров в одну строку, после последнего тело держится
MOB_CORPSE_HOLD_MS = 30_000  # последний кадр остаётся на карте
MOB_CORPSE_FADE_MS = 15_000
# Совпадает с CORPSE_LOOT_RANGE сервера мира (2 тайла)
CORPSE_LOOT_RANGE_TILES = 2
CORPSE_WINDOW_SIZE = (360, 190)


def _tiles_word(count):
    last_two = count % 100
    if 11 <= last_two <= 14:
        return "тайлов"
    last = count % 10
    if last == 1:
        return "тайл"
    if 2 <= last <= 4:
        return "тайла"
    return "тайлов"  # затем труп медленно гаснет


def _mob_facing_row(angle):
    """Строка листа NPC по углу взгляда моба: вниз, вверх, вправо или влево."""
    dx, dy = math.cos(angle), math.sin(angle)
    if abs(dx) >= abs(dy):
        return NPC_ROW_RIGHT if dx >= 0 else NPC_ROW_LEFT
    return NPC_ROW_DOWN if dy >= 0 else NPC_ROW_UP


def mob_frame(mob, now_ms):
    """Кадр моба: атака по замаху (лист attack), ходьба пока моб двигался, иначе первый кадр. None — кадров нет."""
    frames = mob.get("frames")
    if not frames:
        return None
    row = _mob_facing_row(mob.get("facing", 0.0))
    attack_frames = mob.get("attack_frames")
    if mob.get("windup", 0.0) > 0 and attack_frames:
        progress = (now_ms - mob["attack_started"]) / max(1.0, mob["attack_ms"])
        index = min(NPC_FRAMES_PER_ROW - 1, max(0, int(progress * NPC_FRAMES_PER_ROW)))
        return attack_frames[row][index]
    moving = now_ms - mob.get("moved_at", -MOB_WALK_HOLD_MS) < MOB_WALK_HOLD_MS
    index = int(now_ms / 1000 * MOB_WALK_FPS) % NPC_FRAMES_PER_ROW if moving else 0
    return frames[row][index]


def mob_death_frame(mob, now_ms):
    """Смерть моба: лист смерти до последнего кадра, без листа — тело валится на бок. Держится MOB_CORPSE_HOLD_MS и гаснет за MOB_CORPSE_FADE_MS. None — уже не показываем."""
    frames = mob.get("frames")
    death_frames = mob.get("death_frames")
    died_at = mob.get("died_at")
    if died_at is None or not (death_frames or frames):
        return None
    elapsed = now_ms - died_at
    if elapsed >= MOB_CORPSE_HOLD_MS + MOB_CORPSE_FADE_MS:
        return None
    if death_frames:
        index = min(len(death_frames) - 1, int(elapsed / 1000 * MOB_DEATH_FPS))
        body = death_frames[index]
    else:
        fall = min(1.0, max(0.0, elapsed / MOB_CORPSE_FALL_MS))
        body = pygame.transform.rotate(frames[_mob_facing_row(mob.get("facing", 0.0))][0], 90 * fall)
    if elapsed > MOB_CORPSE_HOLD_MS:
        fade = (elapsed - MOB_CORPSE_HOLD_MS) / MOB_CORPSE_FADE_MS
        body = body.copy()  # кадры общие для всех мобов этого вида, гаснуть должен только этот труп
        body.set_alpha(int(255 * (1 - fade)))
    return body


_DIRECTION_VECTORS = {
    "n": (0.0, -1.0), "ne": (0.7071, -0.7071), "e": (1.0, 0.0), "se": (0.7071, 0.7071),
    "s": (0.0, 1.0), "sw": (-0.7071, 0.7071), "w": (-1.0, 0.0), "nw": (-0.7071, -0.7071),
}

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


# Только тайлы травы одного тона с бесшовными краями: остальные темнее и дают видимые швы между клетками
MAP_GRASS_TILES = tuple(f"grass_{i}" for i in range(1, 6))
# Тёмная подстилка под кронами и трава с ягодами: опушка переходит от тёмной земли к светлой поляне через ягодную полосу
MAP_FLOOR_TILES = tuple(f"floor_dark_{i}" for i in range(1, 5))
MAP_BERRY_TILES = tuple(f"berry_{i}" for i in range(1, 4))
MAP_FLOOR_RING = 1
MAP_BERRY_RING = 5
MAP_WATER_TILES = ("water_1", "water_2", "water_3")
# Листы деревьев художника: кадры по 6 в ряд, всего 10 кадров (анимация покачивания)
MAP_TREE_SHEETS = {"tree1": (160, 256), "tree2": (160, 288), "tree3": (160, 224), "old_tree1": (160, 256), "old_tree2": (160, 288), "old_tree3": (160, 224), "big_tree": (352, 416)}
MAP_TREE_FRAMES = 10
MAP_TREE_FRAMES_PER_ROW = 6
MAP_TREE_COLUMNS = {"big_tree": 5}
MAP_TREE_FRAME_MS = 140
MAP_TREE_SCALE = 0.5
MAP_PROP_SPRITES = {"stump": ("stump_1", "stump_2"), "log": ("log_1", "log_2")}
MAP_PROP_SCALE = 0.5
# Сухой край карты — мёртвые деревья того же художника; остальной лес — зелёные
MAP_DEAD_TREES = ("old_tree1", "old_tree2", "old_tree3", "big_tree")
MAP_BRIDGE_SPRITE = "bridge_horizontal"
MAP_SHORE_LEFT = ("shore_left_0", "shore_left_1", "shore_left_2")
MAP_SHORE_BOTTOM = ("shore_bottom_0", "shore_bottom_1", "shore_bottom_2")
# Дорога: сплошная земля листа художника внутри и его кромка с травой там, где дорога кончается
MAP_ROAD_CORE_TILES = tuple(f"road_core_{i}" for i in range(1, 5))
MAP_ROAD_EDGE_VARIANTS = 3
MAP_ROAD_NEIGHBOURS = (("n", 0, -1), ("s", 0, 1), ("e", 1, 0), ("w", -1, 0))


def _map_hash(gx, gy):
    """Хэш клетки: одна и та же клетка всегда получает один и тот же вариант спрайта."""
    h = ((gx * 73856093) ^ (gy * 19349663)) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 0x5BD1E995) & 0xFFFFFFFF
    return h ^ (h >> 15)


def build_ground_kinds(cover, width, height):
    """Вид земли у леса: тёмная подстилка под кронами и на краю, ягодная трава в полосе 2–5 тайлов, на полянах ягоды пятнами."""
    distance = {tile: 0 for tile in cover}
    frontier = list(cover)
    for depth in range(1, MAP_BERRY_RING + 1):
        next_frontier = []
        for gx, gy in frontier:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    tile = (gx + dx, gy + dy)
                    if 0 <= tile[0] < width and 0 <= tile[1] < height and tile not in distance:
                        distance[tile] = depth
                        next_frontier.append(tile)
        frontier = next_frontier
    kinds = {}
    for gy in range(height):
        for gx in range(width):
            tile = (gx, gy)
            h = _map_hash(gx, gy)
            depth = distance.get(tile)
            if depth == 0:
                kinds[tile] = "floor"
            elif depth is not None and depth <= MAP_FLOOR_RING:
                if h % 5 < 3:
                    kinds[tile] = "floor"
            elif depth is not None:
                if h % 7 != 0:
                    kinds[tile] = "berry"
            elif _map_hash(gx // 5, gy // 5) % 4 == 0 and h % 5 < 3:
                kinds[tile] = "berry"
    return kinds


# Целые клетки художника: сторона либо внутри венца (непрозрачна), либо снаружи (прозрачна)
MAP_MOUNTAIN_DIR = Path(__file__).resolve().parent.parent / "assets" / "map" / "mountains"
_MOUNTAIN_SIDE_OFFSETS = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}
_mountain_tile_cache = {}
_rock_info_cache = {}
_mountain_roles_cache = {}


def _edge_gap(p, q):
    gap = abs(p[0] - q[0]) / 255.0
    if p[0] and q[0]:
        gap += (abs(p[1] - q[1]) + abs(p[2] - q[2]) + abs(p[3] - q[3])) / 765.0
    return gap


def _rock_info(name):
    info = _rock_info_cache.get(name)
    if info is None:
        surface = _mountain_tile_image(name)
        size = surface.get_width()
        last = size - 1

        def pixel(x, y):
            r, g, b, a = surface.get_at((x, y))
            return (a, r, g, b)

        edges = {
            "N": tuple(pixel(i, 0) for i in range(size)),
            "S": tuple(pixel(i, last) for i in range(size)),
            "W": tuple(pixel(0, i) for i in range(size)),
            "E": tuple(pixel(last, i) for i in range(size)),
        }
        opacity = {side: sum(p[0] for p in line) / (255.0 * size) for side, line in edges.items()}
        info = (edges, opacity)
        _rock_info_cache[name] = info
    return info


def build_mountain_roles(cells):
    """Для каждой клетки венца выбирает целую клетку художника: стороны совпадают с соседями, края стыкуются по пикселям."""
    if not cells:
        return {}
    key = frozenset(cells)
    cached = _mountain_roles_cache.get(key)
    if cached is not None:
        return dict(cached)
    names = sorted(path.stem for path in MAP_MOUNTAIN_DIR.glob("rock_*.png"))
    infos = {name: _rock_info(name) for name in names}
    roles = {}
    for x, y in sorted(cells, key=lambda cell: (cell[1], cell[0])):
        closed = {side: (x + dx, y + dy) in cells for side, (dx, dy) in _MOUNTAIN_SIDE_OFFSETS.items()}
        openness = {}
        for name in names:
            opacity = infos[name][1]
            openness[name] = sum(
                (1.0 - opacity[side]) if is_closed else opacity[side] for side, is_closed in closed.items()
            )
        best_open = min(openness.values())
        candidates = [name for name in names if openness[name] <= best_open + 0.5]
        left = roles.get((x - 1, y))
        top = roles.get((x, y - 1))

        def seam(name):
            edges = infos[name][0]
            total = 0.0
            if left is not None:
                left_edge = infos[left][0]["E"]
                total += sum(_edge_gap(p, q) for p, q in zip(edges["W"], left_edge)) / len(left_edge)
            if top is not None:
                top_edge = infos[top][0]["S"]
                total += sum(_edge_gap(p, q) for p, q in zip(edges["N"], top_edge)) / len(top_edge)
            return total

        roles[(x, y)] = min(candidates, key=lambda name: openness[name] + seam(name))
    _mountain_roles_cache[key] = dict(roles)
    return roles


def _mountain_tile_image(name):
    image = _mountain_tile_cache.get(name)
    if image is None:
        image = pygame.image.load(str(MAP_MOUNTAIN_DIR / f"{name}.png"))
        _mountain_tile_cache[name] = image
    return image


def _build_road_tile(core, edge_sprites, edge_sides):
    """Тайл дороги: внутри сплошная земля, у края — кромка с травой. На углу кромки пересекаются по прозрачности."""
    if not edge_sides:
        return core
    surface = edge_sprites[edge_sides[0]].copy()
    for side in edge_sides[1:]:
        surface.blit(edge_sprites[side], (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return surface


def _tile_set(rows):
    """Строки [y, x_начало, x_конец] от сервера → множество тайлов (x, y)."""
    return frozenset((x, y) for y, x_start, x_end in rows for x in range(x_start, x_end + 1))



class WorldMapScene:
    """
    Сцена глобальной карты.
    Тайл: 32x32 пикселя.
    Размер карты: 512 тайлов по ширине (16384 px) x 256 тайлов по высоте (8192 px).
    Координатная сетка начинается с левого верхнего угла: (0, 0) = [0, 0].
    """

    CITY_VISUAL_REFRESH_SECONDS = 10.0
    # Высота миникарты; ширина считается по пропорциям сетки (квадрат для башни 125x125)
    MINIMAP_HEIGHT = 192
    MINIMAP_GRASS = (92, 116, 62)
    MINIMAP_COLORS = {
        "forest": (34, 72, 38),
        "dry": (118, 98, 62),
        "water": (40, 112, 150),
        "mountain": (122, 114, 104),
        "road": (176, 146, 96),
        "bridge": (196, 150, 84),
    }
    MINIMAP_MARGIN = (5, 5)
    OVERHEAD_BAR_HEIGHT = 10  # высота полосок ХП/МП над персонажем и мобом (было 5, вдвое больше)
    PLAYER_PANEL_MARGIN = 5
    PLAYER_PANEL_GAP = 6
    PLAYER_PANEL_PORTRAIT = 128
    PLAYER_PANEL_BAR_WIDTH = 240
    PLAYER_PANEL_BAR_HEIGHT = 14

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
        # Карта и точка появления приходят с сервера мира (_apply_map_size)
        self.uniform_grass = False
        self.default_spawn = (self.world_w // 2, self.world_h // 2)
        self.forest_tiles = frozenset()
        self.water_tiles = frozenset()
        self.dry_tiles = frozenset()
        self.mountain_tiles = frozenset()
        self.impassable_tiles = frozenset()
        self.mountain_roles = {}
        self.ground_kinds = {}
        self.bridges = []
        self.prop_anchors = {}
        self.blocked_tiles = frozenset()
        self.partial_masks = {}
        self._map_sprite_cache = None

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

        self.player_speed = 220.0
        self.player_state = "idle"
        self.player_anim_timer = 0.0
        self.hotbar_flash_index = None
        self.hotbar_flash_timer = 0.0
        self.dash_aiming = False  # режим прицеливания рывка: после «1» ждём ЛКМ
        self.world_dash_active = False  # рывок ведёт сервер: клиент показывает его позицию из снимка
        self.dash_cooldown = 0.0
        self.whirlwinds = []  # точки следа вихря: dict с x, y, timer
        self.whirlwind_sprite = self._load_whirlwind_sprite()

        # Камера центрируется на игроке
        self.camera_x = self.player_x
        self.camera_y = self.player_y
        self.camera_follow_player = True
        # Перетаскивание карты ЛКМ и распознавание двойного клика
        self._press_pos = None
        self._press_camera = (self.camera_x, self.camera_y)
        self._dragging = False
        self._last_click_time = None
        self._last_click_pos = None

        # Шрифты
        self.font = pygame.font.SysFont(settings.FONT_NAME, 20)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 16)
        self.grid_font = pygame.font.SysFont(settings.FONT_NAME, 11)
        self.badge_font = pygame.font.SysFont(settings.FONT_NAME, 13, bold=True)
        self.large_font = pygame.font.SysFont(settings.FONT_NAME, 24, bold=True)
        self.damage_font = pygame.font.SysFont(settings.FONT_NAME, 22, bold=True)
        self.crit_damage_font = pygame.font.SysFont(settings.FONT_NAME, 44, bold=True)
        self.profile_overlay = CharacterProfileOverlay(self.small_font)
        self.combat_log = CombatLog()
        self.presence = None
        self.chat = None
        if hasattr(session, "social_snapshot"):
            self.presence = PresenceState(
                session, "world_map",
                presence_provider=lambda: {
                    "position_x": self.player_x,
                    "position_y": self.player_y,
                    "position_direction": self.player_direction,
                },
                travelers_provider=self._get_traveling_citizens,
                convoys_provider=self._get_traveling_convoys,
            )
            self.chat = ChatDialog(session, "world_map", self.presence)

        # UI элементы

        # Переключатель отображения тонкой сетки (клавиша G)
        self.show_grid = False

        # Интерактивные сущности, наведение (hover) и активное состояние (ЛКМ)
        self.hovered_entity = None
        self.hovered_mobile_entity = None
        self.active_entity = None
        self.active_window_rect = pygame.Rect(settings.WIDTH - 390, settings.HEIGHT - 255, 365, 215)
        self.active_close_button = pygame.Rect(self.active_window_rect.right - 36, self.active_window_rect.top + 10, 26, 26)
        self.active_action_button = pygame.Rect(self.active_window_rect.left + 16, self.active_window_rect.bottom - 48, self.active_window_rect.width - 32, 34)
        # Моб, карточка которого закреплена двойным кликом (закрывается крестиком или Escape)
        self.pinned_mob = None
        self.action_notice = None
        self.action_notice_timer = 0.0
        self.attack_windup = 0.0  # >0 — идёт замах перед ударом
        self.attack_windup_total = 0.0  # полная длительность текущего замаха (для анимации позы)
        self.attack_variant = 0  # какую из двух атак героя играть; выбирается случайно в начале каждого замаха
        self.hit_timer = 0.0  # >0 — идёт анимация получения удара
        self.death_timer = None  # секунды с начала смерти героя; None — герой жив
        self._last_world_hp = None  # здоровье из прошлого снимка сервера (первый снимок только задаёт точку отсчёта)
        self.attack_backswing = 0.0  # >0 — откат после удара: стоим на месте
        # Синхронизация с сервером мира: последний полученный seq, таймер и запросы на отправку
        self.world_seq = 0
        self.world_sync_timer = 0.0
        self.world_dash_target = None
        self.world_swing_id = None
        self.world_sync_failed = False
        # Управление ПКМ: путь к точке на земле и цель-моб для атаки
        self.move_path = []
        self.move_stall = 0.0
        self.attack_target = None
        self.repath_timer = 0.0
        # Маркер клика ПКМ по земле: расходящееся кольцо на точке назначения
        self.click_effect = None
        # Боевой Fighter игрока: урон, уворот и крит считаются по его характеристикам и оружию
        self.combat_fighter = self._build_player_combat_fighter()

        # Окна производственных зданий (поселение, лагерь лесорубов); открыто не больше одного
        self.building_windows = {building: ProductionBuildingWindow(self, building) for building in VIEWS}
        self.building_window = None

        # Всплывающие сообщения в игровом мире
        self.floating_messages = []
        self.damage_numbers = []
        self.last_too_far_phrase = None

        # Строения карты живут на сервере и приходят вместе с рельефом (_load_terrain)
        self.objects = []
        self.road_tiles = set()
        self.road_routes = []
        self.road_travel_seconds = 0
        self.city_visual_state = {"city_level": 1, "active": False}
        self.city_visual_refresh_at = 0.0
        self.layout_city_level = 1

        self.minimap_surface = None
        self.terrain_version = None
        self.obstacles = self._load_terrain()
        self._build_minimap(self.obstacles)
        if spawn_pos is None and spawn_gate not in gate_spawns:
            self.player_x = float(self.default_spawn[0])
            self.player_y = float(self.default_spawn[1])

        # Анимация строения лесника 10х10 тайлов (3 кадра анимации дыма из assets/forester's1.png)
        self.forester_frames = []
        self._load_forester_sprite()

        # Мобы карты приходят со снимком сервера мира (_apply_world_mobs), экипировка мобов — в том же снимке
        self.mobs = []
        self.player_corpses = []
        self.corpse_window_id = None
        self.world_mobs_by_id = {}
        self.mob_sprite = self._load_mob_sprite()
        self._npc_mob_frames = {}

        # Загрузка 8-направленных спрайтов idle (из assets/2Idle/) и бега (из assets/3run/)
        self.player_directional_frames = {}
        self.player_run_directional_frames = {}
        load_player_directional_sprites(self)
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

    def _get_traveling_citizens(self):
        client = getattr(self.session, "client", None)
        get_travelers = getattr(client, "get_world_traveling_citizens", None)
        character = getattr(self.session, "character", None) or {}
        if get_travelers is None or character.get("id") is None:
            return []
        try:
            return get_travelers(character["id"])
        except (ServerError, AttributeError, KeyError, OSError):
            return []

    def _get_traveling_convoys(self):
        client = getattr(self.session, "client", None)
        getter = getattr(client, "get_traveling_convoys", None)
        character = getattr(self.session, "character", None) or {}
        if getter is None or character.get("id") is None:
            return []
        try:
            return getter(character["id"])
        except (ServerError, AttributeError, KeyError, OSError):
            return []

    @staticmethod
    def cart_travel_seconds(tile_count):
        """Время в пути повозки по грунтовой дороге для заданного числа тайлов (базовая скорость: 1 тайл = 60 сек)."""
        return tile_count * settings.CART_ROAD_SECONDS_PER_TILE

    @staticmethod
    def _mob_body_rect(mob):
        """Прямоугольник тела моба 90х53 в мировых координатах."""
        return pygame.Rect(0, 0, MOB_SPRITE_SIZE[0], MOB_SPRITE_SIZE[1]).move(
            int(mob["x"] - MOB_SPRITE_SIZE[0] / 2), int(mob["y"] - MOB_SPRITE_SIZE[1] / 2))

    def _distance_to_mob_body(self, mob):
        """Расстояние от центра персонажа до ближайшей точки тела моба (0 если внутри)."""
        rect = self._mob_body_rect(mob)
        nearest_x = min(max(self.player_x, rect.left), rect.right)
        nearest_y = min(max(self.player_y, rect.top), rect.bottom)
        return math.hypot(self.player_x - nearest_x, self.player_y - nearest_y)

    def _set_move_target(self, goal):
        """Строит путь по тайлам до точки на земле. Возвращает False, если точка недостижима."""
        path = find_tile_path((self.player_x, self.player_y), goal, self._player_blocked, self.tile_size,
                              partial_tiles=self.partial_masks)
        self.attack_target = None
        if path is None:
            self.move_path = []
            return False
        self.move_path = path
        self.move_stall = 0.0
        return True

    def _set_attack_target(self, mob):
        """ПКМ по мобу: запоминаем цель и сразу строим путь до её тела."""
        self.attack_target = mob
        self.repath_timer = 0.0
        self._repath_to_attack_target()

    def _repath_to_attack_target(self):
        """Путь к движущемуся мобу: цель — центр моба, ходьба останавливается на дистанции удара."""
        mob = self.attack_target
        path = find_tile_path((self.player_x, self.player_y), (mob["x"], mob["y"]), self._mob_goal_blocked,
                              self.tile_size, partial_tiles=self.partial_masks)
        self.move_path = path or []
        self.move_stall = 0.0

    def _mob_goal_blocked(self, px, py):
        """Коллизия при погоне за мобом: тело своей цели не считаем препятствием, иначе путь к ней не строится."""
        if self._check_collision(px, py):
            return True
        feet_rect = pygame.Rect(int(px - 10), int(py - 6), 20, 10)
        for mob in self.mobs:
            if mob["hp"] <= 0 or mob is self.attack_target:
                continue
            if feet_rect.colliderect(self._mob_body_rect(mob)):
                return True
        return False

    def _update_attack_target(self, dt):
        """Персонаж идёт к цели-мобу, пока она вне зоны удара. Замах, удар и урон считает сервер."""
        mob = self.attack_target
        if mob is None:
            return
        if mob["hp"] <= 0:
            self.attack_target = None
            self.move_path = []
            return
        if self.attack_windup > 0 or self.attack_backswing > 0:
            self.move_path = []
            return
        if self._distance_to_mob_body(mob) > get_attack_reach(self.combat_fighter):
            self.repath_timer -= dt
            if self.repath_timer <= 0 or not self.move_path:
                self.repath_timer = PLAYER_REPATH_INTERVAL
                self._repath_to_attack_target()
            return
        self.move_path = []
        self._face_towards(mob["x"], mob["y"])

    def _world_sync_request(self, dt, force=False):
        """Отправляет на сервер намерения игрока (позиция, цель удара, рывок) и применяет снимок мира."""
        self.world_sync_timer -= dt
        if not force and self.world_dash_target is None and self.world_sync_timer > 0:
            return
        self.world_sync_timer = WORLD_SYNC_DASH_INTERVAL if self.world_dash_active else WORLD_SYNC_INTERVAL
        attack_id = self.attack_target["id"] if self.attack_target is not None else None
        dash_target = self.world_dash_target
        self.world_dash_target = None
        try:
            snap = self.session.client.world_sync(
                self.session.character["id"], self.player_x, self.player_y,
                attack_id, dash_target, self.world_seq)
        except (ServerError, OSError) as error:
            if not self.world_sync_failed:
                self.action_notice = str(error)
                self.action_notice_timer = 2.0
            self.world_sync_failed = True
            return
        self.world_sync_failed = False
        self.world_seq = snap["seq"]
        self._apply_world_snapshot(snap)

    def resync_with_server(self):
        """После переподключения запрашивает полный снимок мира, а не дельту."""
        self.world_seq = 0
        self._world_sync_request(0, force=True)

    def _track_player_hp(self, hp):
        """Анимации героя по здоровью из снимка: падение здоровья запускает получение удара, ноль — смерть."""
        previous, self._last_world_hp = self._last_world_hp, hp
        if previous is None:
            return
        if hp <= 0 < previous:
            self.death_timer = 0.0
            self.hit_timer = 0.0
        elif hp > 0:
            self.death_timer = None
            if hp < previous:
                self.hit_timer = HERO_HIT_SECONDS

    def _hero_reaction_progress(self):
        """(прогресс удара, прогресс смерти) для player_frame; None — анимация не идёт."""
        hit = 1.0 - self.hit_timer / HERO_HIT_SECONDS if self.hit_timer > 0 else None
        death = min(1.0, self.death_timer / HERO_DEATH_SECONDS) if self.death_timer is not None else None
        return hit, death

    def _apply_world_snapshot(self, snap):
        """Применяет снимок сервера: позицию (если отвергнута или идёт рывок), бой, мобов, след и события."""
        self._sync_terrain_version(snap)
        player = snap["player"]
        self.world_dash_active = bool(player["dash_active"])
        if not snap["accepted"] or self.world_dash_active:
            self.player_x = float(player["x"])
            self.player_y = float(player["y"])
            self.move_path = []
        windup = float(player["windup"])
        if windup > 0 and self.attack_windup <= 0:
            self.attack_variant = random.randrange(len(WARRIOR_ATTACK_ANIMATIONS))
        self.attack_windup = windup
        self.attack_windup_total = float(player["windup_total"])
        self.attack_backswing = float(player["backswing"])
        self.dash_cooldown = float(player["dash_cooldown"])
        self._track_player_hp(player["hp"])
        self.combat_fighter.hp = player["hp"]
        self.combat_fighter.max_hp = player["max_hp"]
        self.combat_fighter.mp = player["mp"]
        self.combat_fighter.max_mp = player["max_mp"]
        swing_id = player["swing_id"]
        if self.world_swing_id is not None and swing_id != self.world_swing_id:
            play_random_sound(swing_sounds_for_weapon(self.combat_fighter.equipment.get("weapon")))
        self.world_swing_id = swing_id
        self.whirlwinds = [{"x": t["x"], "y": t["y"], "timer": t["ttl"]} for t in snap["trails"]]
        self._apply_world_mobs(snap["mobs"])
        self.player_corpses = [dict(corpse) for corpse in snap.get("corpses", [])]
        if self._corpse_by_id(self.corpse_window_id) is None:
            self.corpse_window_id = None
        if self.attack_target is not None and self.attack_target["hp"] <= 0:
            self.attack_target = None
            self.move_path = []
        for event in snap["events"]:
            self._apply_world_event(event)

    def _sync_terrain_version(self, snap):
        """Сервер опубликовал новую карту: рельеф перечитывается сразу, без перезахода в мир."""
        version = snap.get("terrain_version")
        if version is None or version == self.terrain_version:
            return
        obstacles = self._load_terrain()
        if obstacles:
            self.obstacles = obstacles
            self._build_minimap(obstacles)

    def _apply_world_event(self, event):
        """Событие боя от сервера: цифры урона, подписи, лог, уведомления и монеты (сервер уже сохранил их)."""
        kind = event["type"]
        if kind == "number":
            self._spawn_hit_number(event["value"], event["critical"], event["x"], event["y"])
        elif kind == "label":
            self._spawn_attack_label(event["outcome"], event["x"], event["y"])
        elif kind == "log":
            self.combat_log.add(event["text"], WORLD_LOG_COLORS.get(event["color"], settings.PLAYER_LOG_COLOR))
        elif kind == "notice":
            self.action_notice = event["text"]
            self.action_notice_timer = 2.0
        elif kind == "message":
            self._add_floating_message(event["text"], event["x"], event["y"])
        elif kind == "currency":
            self.session.character.update(event["currency"])
        elif kind == "progress":
            self.session.character.update(event["character"])
            if (self.profile_overlay.is_open and self.profile_overlay.profile is not None
                    and self.profile_overlay.profile.get("id") == self.session.character.get("id")):
                self.profile_overlay.update_profile(self._own_player_card_profile())
        elif kind == "whirl":
            play_dash_whirl_sound()

    def _face_towards(self, x, y):
        dx, dy = x - self.player_x, y - self.player_y
        if dx or dy:
            self.player_direction = self._vector_to_direction(dx, dy)
            self.player_facing_right = dx >= 0

    def _spawn_attack_label(self, outcome, wx, wy):
        """Подпись без урона: «Промах», «Уворот» или «Блок»."""
        if outcome == "dodge":
            self._spawn_damage_number(wx, wy, 0, DAMAGE_COLOR_DODGE, text="Уворот")
        elif outcome == "block":
            self._spawn_damage_number(wx, wy, 0, DAMAGE_COLOR_BLOCK, text="Блок")
        else:
            self._spawn_damage_number(wx, wy, 0, DAMAGE_COLOR_MISS, text="Промах")

    def _spawn_hit_number(self, amount, critical, wx, wy):
        """Цифра урона: белая обычная, красная и вдвое крупнее при критическом ударе."""
        if critical:
            self._spawn_damage_number(wx, wy, amount, DAMAGE_COLOR_CRIT, big=True)
        else:
            self._spawn_damage_number(wx, wy, amount, DAMAGE_COLOR_NORMAL)

    def _spawn_damage_number(self, wx, wy, amount, color, text=None, big=False):
        """Всплывающая надпись над точкой мира (урон, «Промах», «Блок», «Уворот»); висит DAMAGE_NUMBER_DURATION секунд и поднимается вверх.

        big=True — критический урон: шрифт вдвое крупнее.
        """
        self.damage_numbers.append({
            "text": text if text is not None else f"-{amount}",
            "world_x": float(wx),
            "world_y": float(wy),
            "timer": DAMAGE_NUMBER_DURATION,
            "max_timer": DAMAGE_NUMBER_DURATION,
            "color": color,
            "big": big,
        })

    def _update_damage_numbers(self, dt):
        """Двигает цифры урона вверх и убирает истёкшие."""
        for num in self.damage_numbers[:]:
            num["timer"] -= dt
            num["world_y"] -= 12.0 * dt
            if num["timer"] <= 0:
                self.damage_numbers.remove(num)

    def _draw_damage_numbers(self, screen):
        """Рисует цифры урона; последние 0.8 с плавно прозрачнеют."""
        for num in self.damage_numbers:
            sx, sy = self.world_to_screen(num["world_x"], num["world_y"])
            if not (-60 <= sx <= settings.WIDTH + 60 and -60 <= sy <= settings.HEIGHT + 60):
                continue
            font = self.crit_damage_font if num.get("big") else self.damage_font
            alpha = int(255 * min(1.0, num["timer"] / 0.8))
            text_surf = font.render(num["text"], True, num["color"])
            text_surf.set_alpha(alpha)
            shadow = font.render(num["text"], True, (10, 10, 12))
            shadow.set_alpha(alpha)
            rect = text_surf.get_rect(center=(sx, sy))
            screen.blit(shadow, rect.move(2, 2))
            screen.blit(text_surf, rect)

    def _build_mob_fighter(self, kind, stats=None, level=None, equipment=None):
        """Боевой Fighter моба по профилю из MOB_PROFILES: уровень, характеристики и экипировка из снимка сервера; бонусы предметов суммируются."""
        profile = MOB_PROFILES[kind]
        fighter = Fighter(profile["name"], level=level or MOB_LEVEL)
        fighter.stats.update(stats if stats else profile["stats"])  # характеристики из снимка сервера, если пришли
        fighter.equipment = {slot: dict(item) for slot, item in (equipment or {}).items()}
        modifiers = {}
        for item in fighter.equipment.values():
            for stat_key, bonus in item["bonuses"].items():
                modifiers[stat_key] = modifiers.get(stat_key, 0) + bonus
        fighter.equipment_stat_modifiers = modifiers
        fighter.recalculate_parameters()
        self._apply_world_resource_formulas(fighter)
        fighter.hp = fighter.max_hp
        return fighter

    def _apply_world_resource_formulas(self, fighter):
        """Мировые HP и ману считаем по выносливости и интеллекту (combat/world_stats.py); текущие значения не выше максимума."""
        equipment_hp = int(fighter.equipment_stat_modifiers.get("hp", 0))
        equipment_mp = int(fighter.equipment_stat_modifiers.get("mp", 0))
        fighter.max_hp = get_world_max_hp(fighter, equipment_hp)
        fighter.max_mp = get_world_max_mana(fighter, equipment_mp)
        fighter.hp = min(fighter.hp, fighter.max_hp)
        fighter.mp = min(fighter.mp, fighter.max_mp)

    def _build_player_combat_fighter(self):
        """Боевой Fighter игрока из данных сессии; без персонажа остаётся базовый уровень 1."""
        fighter = Fighter("Игрок", level=1)
        character = getattr(self.session, "character", None)
        if character:
            apply_fighter_profile(fighter, character)
        self._apply_world_resource_formulas(fighter)
        return fighter

    def _player_facing_angle(self):
        """Угол взгляда персонажа в радианах (по 8 направлениям), как у мобов в поле facing."""
        dx, dy = _DIRECTION_VECTORS.get(self.player_direction, (0.0, 1.0))
        return math.atan2(dy, dx)

    def _mob_sprite_for(self, kind):
        """Спрайт моба по виду: бесы — первый кадр ходьбы вниз из листа NPC, остальные — прежний спрайт."""
        frames = self._mob_walk_frames(kind)
        if frames is None:
            return self.mob_sprite
        return frames[NPC_ROW_DOWN][0]

    def _mob_walk_frames(self, kind):
        """Кадры ходьбы NPC по строкам листа (направления): {строка: [кадр, ...]}, масштаб 77x77. None — у вида нет листа."""
        return self._mob_sheet_frames(kind, "walk")

    def _mob_sheet_frames(self, kind, action):
        """Кадры листа NPC (walk или attack) по строкам направления. None — у вида нет листа или он не загрузился."""
        if kind not in NPC_KEYS:
            return None
        key = (kind, action)
        if key not in self._npc_mob_frames:
            npc = next(item for item in npc_catalog() if item["key"] == kind)
            try:
                sheet = pygame.image.load(str(sheet_path(npc, action))).convert_alpha()
                self._npc_mob_frames[key] = {
                    row: [
                        pygame.transform.smoothscale(
                            sheet.subsurface(pygame.Rect(col * 64, row * 64, 64, 64)).copy(), (77, 77))
                        for col in range(NPC_FRAMES_PER_ROW)
                    ]
                    for row in range(4)
                }
            except (pygame.error, OSError):
                self._npc_mob_frames[key] = None
        return self._npc_mob_frames[key]

    def _mob_death_frames(self, kind):
        """Кадры листа смерти вида (одна строка, 7 кадров 64 px) или None, если листа нет."""
        if kind not in NPC_KEYS:
            return None
        key = (kind, "death")
        if key not in self._npc_mob_frames:
            npc = next(item for item in npc_catalog() if item["key"] == kind)
            try:
                sheet = pygame.image.load(str(sheet_path(npc, "death"))).convert_alpha()
                self._npc_mob_frames[key] = [
                    pygame.transform.smoothscale(
                        sheet.subsurface(pygame.Rect(col * 64, 0, 64, 64)).copy(), (77, 77))
                    for col in range(sheet.get_width() // 64)
                ]
            except (pygame.error, OSError):
                self._npc_mob_frames[key] = None
        return self._npc_mob_frames[key]

    def _load_mob_sprite(self):
        """Спрайт разбойника из assets/mobs/woodland_bandit.png. Мобы клиента только отображаются, их состояние приходит с сервера."""
        sprite_path = Path(__file__).resolve().parent.parent / "assets" / "mobs" / "woodland_bandit.png"
        if not sprite_path.is_file():
            return None
        try:
            return pygame.image.load(str(sprite_path)).convert_alpha()
        except pygame.error as e:
            print(f"Ошибка загрузки спрайта разбойника: {e}")
            return None

    def _apply_world_mobs(self, payloads):
        """Обновляет мобов по снимку сервера. Объекты сохраняются, чтобы закреплённая карточка и цель оставались валидными."""
        for payload in payloads:
            mob = self.world_mobs_by_id.get(payload["id"])
            if mob is None:
                mob = {
                    "id": payload["id"],
                    "entity_kind": "mob",
                    "kind": payload["kind"],
                    "name": payload["name"],
                    "icon": "💀",
                    "desc": payload["desc"],
                    "fighter": self._build_mob_fighter(payload["kind"], payload.get("stats"), payload.get("level"), payload.get("equipment")),
                    "sprite": self._mob_sprite_for(payload["kind"]),
                    "frames": self._mob_walk_frames(payload["kind"]),
                    "attack_frames": self._mob_sheet_frames(payload["kind"], "attack"),
                    "death_frames": self._mob_death_frames(payload["kind"]),
                    "radius": 30,
                }
                self.world_mobs_by_id[mob["id"]] = mob
                self.mobs.append(mob)
            now = pygame.time.get_ticks()
            if (mob.get("x"), mob.get("y")) != (payload["x"], payload["y"]):
                mob["moved_at"] = now
            if payload["state"] == "dead" and mob.get("state") not in (None, "dead"):
                mob["died_at"] = now
            if payload["windup"] > 0 and mob.get("windup", 0.0) <= 0:
                mob["attack_started"] = now
                mob["attack_ms"] = payload["windup_total"] * 1000
            if mob.get("x") is not None and (mob["x"], mob["y"]) != (payload["x"], payload["y"]):
                mob["moving_until"] = pygame.time.get_ticks() + 300  # шёл — проигрываем ходьбу
            mob.update({
                "level": payload.get("level", 1),
                "x": payload["x"],
                "y": payload["y"],
                "windup": payload["windup"],
                "home_x": payload["home_x"],
                "home_y": payload["home_y"],
                "hp": payload["hp"],
                "max_hp": payload["max_hp"],
                "state": payload["state"],
                "facing": payload["facing"],
                "coins": payload["coins"],
            })

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
        return screen_px_to_world(sx, sy, self.zoom, self.camera_x, self.camera_y)

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
            char_name = getattr(self.session, "character", None) or {}
            char_name = char_name.get("name", "Герой")
            status_str = "Бежит" if self.player_state == "walk" else "В покое"
            return {
                "id": "player",
                "name": char_name,
                "type": "Игровой персонаж",
                "x": self.player_x,
                "y": self.player_y,
                "radius": 22,
                "desc": f"Ваш главный герой. Статус: {status_str}. Движение и бой: ПКМ.",
                "icon": "👤",
            }

        # 2. Мобы карты: попадание по самому спрайту моба
        for mob in self.mobs:
            msx, msy = self.world_to_screen(mob["x"], mob["y"])
            mob_sprite = mob.get("sprite")
            mob_rect = mob_sprite.get_rect(center=(msx, msy)) if mob_sprite is not None else pygame.Rect(0, 0, 90, 53)
            if mob_rect.collidepoint(screen_pos):
                return mob

        # 3. Проверяем объекты из self.objects (сверху вниз)
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
        if self.active_entity.get("entity_kind") == "mob":
            self.action_notice = f"{self.active_entity['name']}: HP {self.active_entity['hp']}/{self.active_entity['max_hp']}"
            self.action_notice_timer = 2.0
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

    def _player_blocked(self, px, py):
        """Коллизия для персонажа: препятствия карты и тело моба (спрайт непрозрачный, пройти сквозь него нельзя)."""
        if self._check_collision(px, py):
            return True
        feet_rect = pygame.Rect(int(px - 10), int(py - 6), 20, 10)
        for mob in self.mobs:
            if mob["hp"] <= 0:
                continue
            body = pygame.Rect(0, 0, MOB_SPRITE_SIZE[0], MOB_SPRITE_SIZE[1])
            body.center = (int(mob["x"]), int(mob["y"]))
            if feet_rect.colliderect(body):
                return True
        return False

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
        return self._rect_touches_blocked_tile(feet_rect)

    def _load_terrain(self):
        """Рельеф, строения и проложенные сервером дороги приходят готовыми для отрисовки."""
        try:
            terrain = self.session.client.get_map_terrain()
        except (ServerError, AttributeError, KeyError, OSError):
            self.road_tiles = set()
            self.road_travel_seconds = 0
            self.city_visual_state = {"city_level": 1, "active": False}
            return []
        self._apply_city_layout(terrain)
        self._apply_map_size(terrain.get("map", {}))
        self.terrain_version = terrain.get("map", {}).get("version")
        self._apply_tile_terrain(terrain.get("tiles", {}), terrain.get("props", []), terrain.get("bridges", []))
        self.city_visual_state = dict(terrain.get(
            "city_visual_state", {"city_level": 1, "active": False}
        ))
        self.layout_city_level = int(self.city_visual_state.get("city_level", 1))
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
            elif obstacle.get("type") == "tower":
                surface, origin = self._render_tower(points)
            elif obstacle.get("type") == "mountains" and self.uniform_grass:
                surface, origin = self._render_mountain_tiles(bounds)
            else:
                surface, origin = self._render_mountains(points, obstacle.get("peaks", []), passages)
            obstacles.append({
                **obstacle, "points": points, "bounds": bounds, "passages": passages, "surface": surface, "origin": origin,
            })
        return obstacles

    def _apply_map_size(self, map_info):
        """Размер карты и точка появления приходят с сервера мира; без них остаётся 512x256."""
        self.grid_w = int(map_info.get("tiles_w", self.grid_w))
        self.grid_h = int(map_info.get("tiles_h", self.grid_h))
        self.world_w = self.grid_w * self.tile_size
        self.world_h = self.grid_h * self.tile_size
        self.max_world_x = self.world_w
        self.max_world_y = self.world_h
        self.uniform_grass = bool(map_info.get("uniform_grass", False))
        spawn = map_info.get("spawn")
        self.default_spawn = tuple(spawn) if spawn else (self.world_w // 2, self.world_h // 2)

    def _apply_tile_terrain(self, tiles, props, bridges):
        """Лес, сухой край, вода, горы, пни, брёвна и мосты приходят клетками карты: лес и пни рисуются спрайтами из assets/map/."""
        self.forest_tiles = _tile_set(tiles.get("forest", []))
        self.water_tiles = _tile_set(tiles.get("water", []))
        self.dry_tiles = _tile_set(tiles.get("dry", []))
        self.mountain_tiles = _tile_set(tiles.get("mountain", []))
        self.impassable_tiles = _tile_set(tiles.get("impassable", []))
        self.partial_masks = {(int(x), int(y)): str(mask) for x, y, mask in tiles.get("partial", [])}
        self.mountain_roles = build_mountain_roles(self.mountain_tiles) if self.uniform_grass else {}
        self.ground_kinds = (
            build_ground_kinds(self.forest_tiles | self.dry_tiles, self.grid_w, self.grid_h) if self.uniform_grass else {}
        )
        self.bridges = [[tuple(tile) for tile in bridge["tiles"]] for bridge in bridges]
        self.prop_anchors = {}
        prop_tiles = set()
        for prop in props:
            footprint = [tuple(tile) for tile in prop["tiles"]]
            prop_tiles.update(footprint)
            self.prop_anchors[min(footprint)] = {"type": prop["type"], "width": len(footprint)}
        self.blocked_tiles = (
            self.forest_tiles | self.dry_tiles | self.water_tiles | self.mountain_tiles | self.impassable_tiles | prop_tiles
        ) - frozenset(self.partial_masks)

    def _rect_touches_blocked_tile(self, rect):
        if not self.blocked_tiles and not self.partial_masks:
            return False
        size = self.tile_size
        for tile_y in range(rect.top // size, (rect.bottom - 1) // size + 1):
            for tile_x in range(rect.left // size, (rect.right - 1) // size + 1):
                mask = self.partial_masks.get((tile_x, tile_y))
                if mask is not None:
                    if mask_blocks_rect(mask, tile_x, tile_y, size, rect.left, rect.top, rect.right, rect.bottom):
                        return True
                elif (tile_x, tile_y) in self.blocked_tiles:
                    return True
        return False

    def _map_sprites(self):
        """Спрайты земли, воды, кромки и деревьев из assets/map; грузятся при первом показе карты."""
        if self._map_sprite_cache is None:
            map_dir = Path(__file__).resolve().parent.parent / "assets" / "map"
            def flipped_variants(names):
                # Отражения дают разнообразие без швов: края тайлов бесшовные, поэтому стык остаётся ровным
                variants = []
                for name in names:
                    base = pygame.image.load(str(map_dir / "tiles" / f"{name}.png")).convert()
                    variants.extend([base, pygame.transform.flip(base, True, False),
                                     pygame.transform.flip(base, False, True), pygame.transform.flip(base, True, True)])
                return variants

            grass = flipped_variants(MAP_GRASS_TILES)
            floor = flipped_variants(MAP_FLOOR_TILES)
            berry = flipped_variants(MAP_BERRY_TILES)
            water = [pygame.image.load(str(map_dir / "tiles" / f"{name}.png")).convert() for name in MAP_WATER_TILES]
            road_core = [pygame.image.load(str(map_dir / "tiles" / f"{name}.png")).convert_alpha() for name in MAP_ROAD_CORE_TILES]
            road_edge = {
                side: [
                    pygame.image.load(str(map_dir / "tiles" / f"road_edge_{side}_{i}.png")).convert_alpha()
                    for i in range(1, MAP_ROAD_EDGE_VARIANTS + 1)
                ]
                for side, _, _ in MAP_ROAD_NEIGHBOURS
            }
            trees = {"green": [], "dead": []}
            for name, (frame_w, frame_h) in MAP_TREE_SHEETS.items():
                sheet = pygame.image.load(str(map_dir / "trees" / f"{name}.png")).convert_alpha()
                size = (round(frame_w * MAP_TREE_SCALE), round(frame_h * MAP_TREE_SCALE))
                frames = []
                for index in range(MAP_TREE_FRAMES):
                    cols = MAP_TREE_COLUMNS.get(name, MAP_TREE_FRAMES_PER_ROW)
                    col, row = index % cols, index // cols
                    frame = sheet.subsurface(pygame.Rect(col * frame_w, row * frame_h, frame_w, frame_h))
                    frames.append(pygame.transform.smoothscale(frame, size))
                trees["dead" if name in MAP_DEAD_TREES else "green"].append(frames)
            props = {}
            for kind, names in MAP_PROP_SPRITES.items():
                images = []
                for name in names:
                    image = pygame.image.load(str(map_dir / "props" / f"{name}.png")).convert_alpha()
                    size = (round(image.get_width() * MAP_PROP_SCALE), round(image.get_height() * MAP_PROP_SCALE))
                    images.append(pygame.transform.smoothscale(image, size))
                props[kind] = images
            bridge = pygame.image.load(str(map_dir / "props" / f"{MAP_BRIDGE_SPRITE}.png")).convert_alpha()
            rims = map_dir / "rims"
            left = [pygame.image.load(str(rims / f"{name}.png")).convert() for name in MAP_SHORE_LEFT]
            bottom = [pygame.image.load(str(rims / f"{name}.png")).convert() for name in MAP_SHORE_BOTTOM]
            shores = {
                "left": left,
                "right": [pygame.transform.flip(image, True, False) for image in left],
                "bottom": bottom,
                "top": [pygame.transform.flip(image, False, True) for image in bottom],
            }
            self._map_sprite_cache = {
                "grass": grass, "floor": floor, "berry": berry, "water": water, "road_core": road_core, "road_edge": road_edge, "trees": trees, "props": props, "bridge": bridge,
                "shores": shores, "roads": {},
            }
        return self._map_sprite_cache

    def _road_surface(self, sprites, gx, gy):
        """Поверхность тайла дороги: кэшируется по сторонам, где дорога кончается, и вариантам земли и кромки."""
        edge_sides = tuple(side for side, dx, dy in MAP_ROAD_NEIGHBOURS if (gx + dx, gy + dy) not in self.road_tiles)
        h = _map_hash(gx, gy)
        core_index = h % len(sprites["road_core"])
        variant = (h >> 8) % MAP_ROAD_EDGE_VARIANTS
        key = (edge_sides, core_index, variant)
        cache = sprites["roads"]
        if key not in cache:
            edge_sprites = {side: sprites["road_edge"][side][variant] for side in edge_sides}
            cache[key] = _build_road_tile(sprites["road_core"][core_index], edge_sprites, edge_sides)
        return cache[key]

    def _draw_forest_trees(self, screen, trees, props):
        """Деревья леса и пни у его края. Деревья стоят не по сетке: в клетке одно или два со сдвигом, часть клеток пустая.
        Сухой лес продолжается за края карты: клетки за краем повторяют ближайший тайл края."""
        size = self.tile_size
        top_left_wx, top_left_wy = self.screen_to_world(0, 0)
        bot_right_wx, bot_right_wy = self.screen_to_world(settings.WIDTH, settings.HEIGHT)
        map_gx0, map_gy0 = self.min_world_x // size, self.min_world_y // size
        map_gx1, map_gy1 = self.max_world_x // size, self.max_world_y // size
        # Высокие деревья уходят вверх от своего тайла, поэтому строки над экраном тоже проверяются
        start_gx = max(map_gx0, int(top_left_wx // size) - 2)
        end_gx = min(map_gx1, int(bot_right_wx // size) + 3)
        start_gy = max(map_gy0, int(top_left_wy // size) - 6)
        end_gy = min(map_gy1, int(bot_right_wy // size) + 2)
        slots = []
        for gy in range(start_gy, end_gy):
            for gx in range(start_gx, end_gx):
                prop = self.prop_anchors.get((gx, gy))
                if prop:
                    self._draw_prop(screen, props[prop["type"]], prop["width"], gx, gy)
                if (gx, gy) in self.dry_tiles:
                    pool = trees["dead"]
                elif (gx, gy) in self.forest_tiles:
                    pool = trees["green"]
                else:
                    continue
                self._add_tree_slots(slots, gx, gy, pool)
        # Ряд клеток за краем карты: сухой лес уходит за горизонт, а не обрывается прямой линией
        outer_gx0 = max(map_gx0 - 1, int(top_left_wx // size) - 2)
        outer_gx1 = min(map_gx1 + 1, int(bot_right_wx // size) + 3)
        outer_gy0 = max(map_gy0 - 1, int(top_left_wy // size) - 6)
        outer_gy1 = min(map_gy1 + 1, int(bot_right_wy // size) + 2)
        for gy in range(outer_gy0, outer_gy1):
            for gx in range(outer_gx0, outer_gx1):
                if map_gx0 <= gx < map_gx1 and map_gy0 <= gy < map_gy1:
                    continue
                edge_gx = min(max(gx, map_gx0), map_gx1 - 1)
                edge_gy = min(max(gy, map_gy0), map_gy1 - 1)
                if (edge_gx, edge_gy) in self.dry_tiles:
                    self._add_tree_slots(slots, gx, gy, trees["dead"])
        slots.sort(key=lambda slot: slot[0])
        for base_y, base_x, tree in slots:
            sx, sy = self.world_to_screen(base_x, base_y)
            screen.blit(tree, (sx - tree.get_width() // 2, sy - tree.get_height()))

    def _add_tree_slots(self, slots, gx, gy, pool):
        """Место и кадр деревьев клетки: хэш задаёт сдвиг, вариант и пустоту, поэтому каждая клетка выглядит по-своему."""
        size = self.tile_size
        h = _map_hash(gx, gy)
        if h % 5 == 0:
            return
        layers = 2 if (h >> 3) % 3 == 0 else 1
        ticks = pygame.time.get_ticks()
        for layer in range(layers):
            lh = _map_hash(gx * 3 + layer * 101, gy * 7 + layer * 53)
            frames = pool[lh % len(pool)]
            frame = (ticks // MAP_TREE_FRAME_MS + (lh >> 8)) % MAP_TREE_FRAMES
            dx = ((lh >> 4) % 13 - 6) * size // 12
            dy = ((lh >> 12) % 7 - 3) * size // 12
            slots.append(((gy + 1) * size + dy, gx * size + size // 2 + dx, frames[frame]))

    def _draw_bridges(self, screen, sprites):
        """Мост художника в натуральном размере лежит по центру своего пролёта на дороге, без растяжки."""
        size = self.tile_size
        image = sprites["bridge"]
        for run in self.bridges:
            xs = [tile_x for tile_x, _ in run]
            ys = [tile_y for _, tile_y in run]
            centre_x = (min(xs) + max(xs) + 1) * size // 2
            centre_y = (min(ys) + max(ys) + 1) * size // 2
            sx, sy = self.world_to_screen(centre_x, centre_y)
            screen.blit(image, (sx - image.get_width() // 2, sy - image.get_height() // 2))

    def _draw_prop(self, screen, images, width, gx, gy):
        """Пень или бревно стоит на нижней границе своего тайла; бревно занимает width тайлов и центрируется на них."""
        size = self.tile_size
        image = images[_map_hash(gx, gy) % len(images)]
        sx, sy = self.world_to_screen(gx * size + width * size // 2, (gy + 1) * size)
        screen.blit(image, (sx - image.get_width() // 2, sy - image.get_height()))

    def _draw_shore_rims(self, screen, shores, start_gx, end_gx, start_gy, end_gy, edge_x, edge_y):
        """Каменная кромка берега художника: кусочки кладутся на сухие тайлы рядом с водой."""
        for gy in range(start_gy, end_gy):
            for gx in range(start_gx, end_gx):
                if (gx, gy) not in self.water_tiles:
                    continue
                left, right = edge_x[gx], edge_x[gx + 1]
                top, bottom = edge_y[gy], edge_y[gy + 1]
                variant = (gx * 3 + gy * 5) % len(shores["left"])
                if (gx - 1, gy) not in self.water_tiles:
                    rim = shores["left"][variant]
                    screen.blit(rim, (left - rim.get_width(), top))
                if (gx + 1, gy) not in self.water_tiles:
                    screen.blit(shores["right"][variant], (right, top))
                if (gx, gy - 1) not in self.water_tiles:
                    rim = shores["top"][variant]
                    screen.blit(rim, (left, top - rim.get_height()))
                if (gx, gy + 1) not in self.water_tiles:
                    screen.blit(shores["bottom"][variant], (left, bottom))

    def _apply_city_layout(self, terrain):
        """Строения и дороги зависят от уровня города, поэтому их можно перечитать при апгрейде."""
        self.objects = hydrate_structures(terrain.get("objects", []))
        roads = terrain.get("roads", {})
        self.road_tiles = {tuple(tile) for tile in roads.get("tiles", [])}
        # Тропинки от полянок выглядят как дорога, но не входят в маршруты между строениями
        self.road_tiles |= _tile_set(terrain.get("tiles", {}).get("paths", []))
        self.road_routes = roads.get("routes", [])
        self.road_travel_seconds = roads.get("travel_seconds", 0)

    def _minimap_size(self):
        height = self.MINIMAP_HEIGHT
        return (max(1, round(height * self.grid_w / self.grid_h)), height)

    @staticmethod
    def _minimap_tile_rect(tile_x, tile_y, scale_x, scale_y):
        left = int(tile_x * scale_x)
        top = int(tile_y * scale_y)
        right = max(left + 1, int((tile_x + 1) * scale_x))
        bottom = max(top + 1, int((tile_y + 1) * scale_y))
        return (left, top, right - left, bottom - top)

    def _build_minimap(self, obstacles):
        """Полная карта мира в уменьшении: трава, лес, сухой край, вода, горы, мосты, дороги и строения."""
        width, height = self._minimap_size()
        scale_x = width / self.grid_w
        scale_y = height / self.grid_h
        surface = pygame.Surface((width, height))
        surface.fill(self.MINIMAP_GRASS)

        for obstacle in obstacles:
            color = {
                "forest": self.MINIMAP_COLORS["forest"],
                "lake": self.MINIMAP_COLORS["water"],
                "tower": (120, 112, 100),
                "mountains": self.MINIMAP_COLORS["mountain"],
            }.get(obstacle.get("type"), self.MINIMAP_COLORS["mountain"])
            points = [(x / self.tile_size * scale_x, y / self.tile_size * scale_y) for x, y in obstacle["points"]]
            if len(points) >= 3:
                pygame.draw.polygon(surface, color, points)

        tile_layers = (
            (self.mountain_tiles, self.MINIMAP_COLORS["mountain"]),
            (self.forest_tiles, self.MINIMAP_COLORS["forest"]),
            (self.dry_tiles, self.MINIMAP_COLORS["dry"]),
            (self.water_tiles, self.MINIMAP_COLORS["water"]),
            (self.road_tiles, self.MINIMAP_COLORS["road"]),
        )
        for tiles, color in tile_layers:
            for tile_x, tile_y in tiles:
                pygame.draw.rect(surface, color, self._minimap_tile_rect(tile_x, tile_y, scale_x, scale_y))

        for bridge in self.bridges:
            for tile_x, tile_y in bridge:
                pygame.draw.rect(surface, self.MINIMAP_COLORS["bridge"],
                                 self._minimap_tile_rect(tile_x, tile_y, scale_x, scale_y))

        for obj in self.objects:
            x = obj.get("tile_x", 0) * scale_x
            y = obj.get("tile_y", 0) * scale_y
            w = max(2, obj.get("tile_w", 1) * scale_x)
            h = max(2, obj.get("tile_h", 1) * scale_y)
            color = (230, 190, 90) if obj.get("id") in ("town_radburg", "main_castle") else (200, 200, 210)
            pygame.draw.rect(surface, color, (x, y, w, h))

        pygame.draw.rect(surface, (220, 180, 70), surface.get_rect(), 2)
        self.minimap_surface = surface

    def _draw_minimap(self, screen):
        if self.minimap_surface is None:
            return
        width, height = self._minimap_size()
        left = self.MINIMAP_MARGIN[0]
        top = settings.HEIGHT - self.MINIMAP_MARGIN[1] - height
        screen.blit(self.minimap_surface, (left, top))

        scale_x = width / self.world_w
        scale_y = height / self.world_h
        marker = (left + self.player_x * scale_x, top + self.player_y * scale_y)
        pygame.draw.circle(screen, (255, 255, 255), (int(marker[0]), int(marker[1])), 3)
        pygame.draw.circle(screen, (220, 60, 60), (int(marker[0]), int(marker[1])), 2)
        for corpse in self.player_corpses:
            cx = left + corpse["x"] * scale_x
            cy = top + corpse["y"] * scale_y
            pygame.draw.rect(screen, (210, 210, 220), (int(cx) - 2, int(cy) - 2, 5, 5))
            tiles = round(self._corpse_distance_tiles(corpse))
            label = self.badge_font.render(f"{tiles} {_tiles_word(tiles)}", True, (235, 235, 245))
            screen.blit(label, (int(cx) + 5, int(cy) - 7))

    def _refresh_city_visual_state(self):
        now = time.monotonic()
        if now < self.city_visual_refresh_at:
            return False
        self.city_visual_refresh_at = now + self.CITY_VISUAL_REFRESH_SECONDS
        try:
            population = self.session.client.get_city_population(
                self.session.character["id"]
            )
        except (ServerError, AttributeError, KeyError, OSError, TypeError, ValueError):
            return False
        self.city_visual_state = dict(population.get("city_upgrade", {}))
        self.city_visual_state.setdefault("city_level", int(population.get("castle_level", 1)))
        self.castle_upgrades_active = [dict(item) for item in population.get("castle_upgrades_active", [])]
        new_level = int(self.city_visual_state.get("city_level", 1))
        if new_level != self.layout_city_level:
            try:
                terrain = self.session.client.get_map_terrain()
            except (ServerError, AttributeError, KeyError, OSError):
                return True
            self._apply_city_layout(terrain)
            self.layout_city_level = new_level
            self._build_minimap(self.obstacles)
        return True

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

    def _render_mountain_tiles(self, bounds):
        """Горный венец тайлами художника: склон и основание смотрят наружу, плато травой, без стыков разных тайлов."""
        size = self.tile_size
        left, top = bounds.left // size, bounds.top // size
        surface = pygame.Surface((bounds.width, bounds.height), pygame.SRCALPHA)
        for tile_y in range(top, (bounds.bottom - 1) // size + 1):
            for tile_x in range(left, (bounds.right - 1) // size + 1):
                name = self.mountain_roles.get((tile_x, tile_y))
                if name is not None:
                    surface.blit(_mountain_tile_image(name), ((tile_x - left) * size, (tile_y - top) * size))
        return surface, (bounds.left, bounds.top)

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

    @staticmethod
    def _render_tower(points):
        """Заглушка башни: каменный блок с зубцами и донжоном, пока нет спрайта."""
        xs = [x for x, _ in points]
        ys = [y for _, y in points]
        origin = (min(xs), min(ys))
        surface = pygame.Surface((max(xs) - min(xs) + 1, max(ys) - min(ys) + 1), pygame.SRCALPHA)
        rect = surface.get_rect()
        stone, dark = (92, 88, 84), (58, 55, 52)
        pygame.draw.rect(surface, stone, rect)
        pygame.draw.rect(surface, dark, rect, 4)
        for x in range(0, rect.width, 16):
            pygame.draw.rect(surface, dark, (x, 0, 8, 6))
            pygame.draw.rect(surface, dark, (x, rect.height - 6, 8, 6))
        keep = rect.inflate(-rect.width // 2, -rect.height // 2)
        pygame.draw.rect(surface, (70, 66, 62), keep)
        pygame.draw.rect(surface, dark, keep, 2)
        return surface, origin

    def _draw_terrain(self, screen):
        for obstacle in self.obstacles:
            sx, sy = self.world_to_screen(*obstacle["origin"])
            surface = obstacle["surface"]
            if sx < settings.WIDTH and sy < settings.HEIGHT and sx + surface.get_width() > 0 and sy + surface.get_height() > 0:
                screen.blit(surface, (sx, sy))
                if "max_hp" in obstacle:
                    hp_label = self.small_font.render(
                        f"ХП {obstacle['hp']}/{obstacle['max_hp']}", True, (240, 230, 200))
                    screen.blit(hp_label, (sx + (surface.get_width() - hp_label.get_width()) // 2,
                                           sy - hp_label.get_height() - 2))

    def handle_event(self, event):
        if self.profile_overlay.is_open:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.profile_overlay.close()
                return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                action, profile = self.profile_overlay.handle_click(event.pos)
                if action == "stat_change":
                    self._save_profile_card(profile)

                return

        if self.chat is not None and self.chat.handle_event(event):
            return
        if self.combat_log.handle_event(event):
            return

        # Окно здания поглощает остальные взаимодействия с картой
        if self.building_window is not None:
            self.building_window.handle_event(event)
            if not self.building_window.is_open:
                self.building_window = None
            return

        if self.chat is not None and self.chat.open_from_key(event):
            return

        if event.type == pygame.KEYDOWN:
            slot = hotbar_index_for_key(event.key)
            if slot is not None:
                self._press_hotbar_slot(slot)
                return
            if event.key == pygame.K_ESCAPE:
                if self.corpse_window_id is not None:
                    self.corpse_window_id = None
                    return
                if self.dash_aiming:
                    self.dash_aiming = False
                    return
                if self.pinned_mob is not None:
                    self.pinned_mob = None
                    return
                if self.active_entity is not None:
                    self.active_entity = None
                return
            if event.key == pygame.K_g:
                self.show_grid = not self.show_grid
                return
            if event.key == pygame.K_SPACE:
                # Центрировать камеру на персонаже и снова следовать за ним
                self.camera_x = self.player_x
                self.camera_y = self.player_y
                self.camera_follow_player = True
                self._clamp_camera()
                return

        # Прицел рывка: ЛКМ по миру запускает рывок, ПКМ отменяет прицел (клики по интерфейсу идут обычным путём)
        if self.dash_aiming and event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and not self._is_ui_point(event.pos):
                self._fire_dash(self.screen_to_world(*event.pos))
                return
            if event.button == 3:
                self.dash_aiming = False
                return

        # Закреплённая карточка моба поверх карты: клики по ней не уходят в мир
        if event.type == pygame.MOUSEBUTTONDOWN and self.pinned_mob is not None:
            if self._mob_card_rect().collidepoint(event.pos):
                if event.button == 1 and self._mob_card_close_rect().collidepoint(event.pos):
                    self.pinned_mob = None
                return

        # ЛКМ: нажатие на кнопки активного окна срабатывает сразу; остальное решается при отпускании
        # (протяжка ЛКМ — перетаскивание карты, короткий клик — выбор, двойной — действие).
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.corpse_window_id is not None:
                window_rect, close_rect, loot_rect = self._corpse_window_layout()
                if window_rect.collidepoint(event.pos):
                    if close_rect.collidepoint(event.pos):
                        self.corpse_window_id = None
                    elif loot_rect.collidepoint(event.pos):
                        self._loot_corpse()
                    return
            if self.active_entity is not None and self.active_window_rect.collidepoint(event.pos):
                if self.active_close_button.collidepoint(event.pos):
                    self.active_entity = None
                    return
                if self.active_action_button.collidepoint(event.pos):
                    self._trigger_active_action()
                    return
                return  # Поглощаем клик по телу окна
            self._press_pos = event.pos
            self._press_camera = (self.camera_x, self.camera_y)
            self._dragging = False
            return

        if event.type == pygame.MOUSEMOTION and self._press_pos is not None:
            dx = event.pos[0] - self._press_pos[0]
            dy = event.pos[1] - self._press_pos[1]
            if not self._dragging and math.hypot(dx, dy) > DRAG_THRESHOLD:
                self._dragging = True
                self.camera_follow_player = False
            if self._dragging:
                # Карта едет за курсором: камера уходит в противоположную сторону
                self.camera_x = self._press_camera[0] - dx / self.zoom
                self.camera_y = self._press_camera[1] - dy / self.zoom
                self._clamp_camera()
            return

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self._press_pos is not None:
            was_dragging = self._dragging
            self._press_pos = None
            self._dragging = False
            if not was_dragging:
                self._handle_left_click(event.pos)
            return

        # ПКМ (как в Dota 2): по мобу — идти и бить, по земле — идти в точку
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if self.active_entity is not None and self.active_window_rect.collidepoint(event.pos):
                return
            if self._keyboard_movement_blocked():
                return
            wx, wy = self.screen_to_world(*event.pos)
            # Замах нельзя отменить: ПКМ во время замаха игнорируется; во время рывка персонаж занят
            if self.attack_windup > 0 or self.world_dash_active:
                return
            mob = self._mob_at_world_point(wx, wy)
            if mob is not None:
                self._set_attack_target(mob)
            else:
                self._set_move_target((wx, wy))
                self.click_effect = {"x": wx, "y": wy, "timer": CLICK_EFFECT_DURATION}

    def _handle_left_click(self, pos):
        """Короткий клик выбирает объект; второй клик в пределах DOUBLE_CLICK_MS — двойной."""
        now = pygame.time.get_ticks()
        is_double = (
            self._last_click_time is not None
            and self._last_click_pos is not None
            and now - self._last_click_time < DOUBLE_CLICK_MS
            and math.hypot(pos[0] - self._last_click_pos[0], pos[1] - self._last_click_pos[1]) <= DRAG_THRESHOLD
        )
        # Тройной клик не должен считаться вторым двойным: после двойного трекер сбрасывается
        self._last_click_time = None if is_double else now
        self._last_click_pos = None if is_double else pos

        corpse = self._player_corpse_at(pos)
        if corpse is not None:
            self.active_entity = None
            self._open_corpse_window(corpse)
            return

        entity = self._find_entity_at(pos)
        if is_double:
            self._handle_double_click(entity)
            return
        if entity is not None and (entity.get("id") == "player" or entity.get("entity_kind") == "mob"):
            # Одиночный клик по персонажу и мобу ничего не открывает: информация — по двойному клику
            self.active_entity = None
            self.action_notice = None
            return
        self.active_entity = entity
        self.action_notice = None

    def _handle_double_click(self, entity):
        if entity is None:
            return
        if entity.get("id") == "player":
            # Двойной клик по персонажу открывает его профиль слева
            self.active_entity = None
            self.profile_overlay.open(self.session.character, None)
            return
        if entity.get("entity_kind") == "mob":
            # Двойной клик по мобу закрепляет его карточку справа
            self.active_entity = None
            self.pinned_mob = entity
            return
        self.active_entity = entity
        self._trigger_active_action()
        if self.building_window is not None:
            # Окно здания заменяет всплывающее окно объекта
            self.active_entity = None

    def _mob_at_world_point(self, wx, wy):
        for mob in self.mobs:
            if mob["hp"] > 0 and self._mob_body_rect(mob).collidepoint(wx, wy):
                return mob
        return None

    def _follow_move_path(self, dt):
        """Идёт по пути из тайлов. Путь сбрасывается при остановке или на последней точке."""
        if not self.move_path:
            return False
        step = get_move_speed(self.combat_fighter, character_movement_speed_multiplier(
            getattr(self.session, "character", None)
        )) * dt
        self.player_x, self.player_y, moved = follow_path(
            self.player_x, self.player_y, self.move_path, step, self._check_collision
        )
        if moved:
            self.move_stall = 0.0
            self.player_state = "walk"
            if self.move_path:
                dx = self.move_path[0][0] - self.player_x
                dy = self.move_path[0][1] - self.player_y
                if dx or dy:
                    self.player_direction = self._vector_to_direction(dx, dy)
                    self.player_facing_right = dx >= 0
        else:
            self.move_stall += dt
            if self.move_stall >= PLAYER_STALL_TIMEOUT:
                self.move_path = []
                self.move_stall = 0.0
        if not self.move_path:
            self.player_state = "idle"
        return moved

    def _press_hotbar_slot(self, slot):
        """Нажатие 1–0: слот подсвечивается; «1» включает или выключает прицел рывка."""
        self.hotbar_flash_index = slot
        self.hotbar_flash_timer = HOTBAR_FLASH_DURATION
        if slot != DASH_HOTBAR_SLOT:
            return
        if self.dash_aiming:
            self.dash_aiming = False
            return
        if self.dash_cooldown > 0:
            self._add_floating_message(f"Рывок: {math.ceil(self.dash_cooldown)} с", self.player_x, self.player_y - 30)
            return
        if self.attack_windup > 0 or self.world_dash_active:
            return
        self.dash_aiming = True

    def _is_ui_point(self, pos):
        """Клик по интерфейсу (верхняя полоса, окно объекта, карточка моба, панель 1–0, чат), а не по миру."""
        if pos[1] <= 75:
            return True
        if self.active_entity is not None and self.active_window_rect.collidepoint(pos):
            return True
        if self.pinned_mob is not None and self._mob_card_rect().collidepoint(pos):
            return True
        if any(rect.collidepoint(pos) for rect in hotbar_slot_rects(settings.WIDTH, settings.HEIGHT)):
            return True
        return self.chat is not None and self.chat.contains(pos)

    def _fire_dash(self, target):
        """Рывок: клиент отправляет направление на сервер, дальность, урон и кулдаун считает сервер."""
        self.dash_aiming = False
        if self.attack_windup > 0 or self.world_dash_active or self.dash_cooldown > 0:
            return
        if math.hypot(target[0] - self.player_x, target[1] - self.player_y) < DASH_MIN_LENGTH:
            self._add_floating_message("Слишком близко", self.player_x, self.player_y - 30)
            return
        self.attack_target = None
        self.move_path = []
        self._face_towards(target[0], target[1])
        self.world_dash_target = {"x": target[0], "y": target[1]}
        play_dash_sound()
        self._world_sync_request(0.0, force=True)

    def _load_whirlwind_sprite(self):
        """PNG следа вихря (заглушка); без файла след рисуется кругом."""
        sprite_path = Path(__file__).resolve().parent.parent / "assets" / "effects" / "whirlwind_trail.png"
        if not sprite_path.is_file():
            return None
        try:
            return pygame.image.load(str(sprite_path)).convert_alpha()
        except pygame.error as e:
            print(f"Ошибка загрузки следа вихря: {e}")
            return None

    def _draw_whirlwinds(self, screen):
        """След вихря: каждая точка пути рывка гаснет за DASH_TRAIL_DURATION секунд."""
        size = max(2, int(DASH_TRAIL_SIZE * self.zoom))
        for point in self.whirlwinds:
            sx, sy = self.world_to_screen(point["x"], point["y"])
            fade = point["timer"] / DASH_TRAIL_DURATION
            if self.whirlwind_sprite is not None:
                sprite = pygame.transform.smoothscale(self.whirlwind_sprite, (size, size))
                sprite.set_alpha(int(255 * fade))
                screen.blit(sprite, sprite.get_rect(center=(sx, sy)))
            else:
                pygame.draw.circle(screen, (120, 220, 255), (sx, sy), size // 2, 2)

    def _draw_dash_aim(self, screen):
        """Прицел рывка: зелёная полоса шириной 2 × DASH_HIT_RADIUS от персонажа до точки курсора (не дальше дальности)."""
        mx, my = pygame.mouse.get_pos()
        start = (self.player_x, self.player_y)
        end = dash_end_point(start, self.screen_to_world(mx, my))
        sx, sy = self.world_to_screen(*start)
        ex, ey = self.world_to_screen(*end)
        radius = max(1, int(DASH_HIT_RADIUS * self.zoom))
        left = int(min(sx, ex)) - radius - 2
        top = int(min(sy, ey)) - radius - 2
        width = int(abs(ex - sx)) + 2 * radius + 4
        height = int(abs(ey - sy)) + 2 * radius + 4
        surf = pygame.Surface((width, height), pygame.SRCALPHA)
        local_start = (sx - left, sy - top)
        local_end = (ex - left, ey - top)
        pygame.draw.line(surf, (*DASH_AIM_COLOR, 60), local_start, local_end, radius * 2)
        pygame.draw.circle(surf, (*DASH_AIM_COLOR, 60), local_end, radius)
        pygame.draw.circle(surf, (*DASH_AIM_COLOR, 200), local_end, radius, 2)
        screen.blit(surf, (left, top))

    def _hotbar_slot_states(self):
        """Состояние слотов панели 1–0: у рывка подпись, кулдаун и активный прицел; остальные слоты пустые."""
        states = [None] * len(HOTBAR_KEYS)
        states[DASH_HOTBAR_SLOT] = {
            "name": "Рывок",
            "cooldown": self.dash_cooldown,
            "cooldown_total": DASH_COOLDOWN,
            "active": self.dash_aiming,
        }
        return states

    def _keyboard_movement_blocked(self):
        """Перемещение ПКМ не работает, пока открыт ввод в чат или окно/оверлей."""
        if self.building_window is not None and self.building_window.is_open:
            return True
        if self.combat_log.captures_keyboard():
            return True
        return self.chat is not None and self.chat.captures_keyboard()

    def _save_profile_card(self, profile):
        try:
            saved_profile = self.session.save_character_profile(profile)
        except ServerError as error:
            self.action_notice = str(error)
            self.action_notice_timer = 2.0
            return
        if saved_profile is not None:
            self.profile_overlay.update_profile(saved_profile)

    def _edge_scroll(self, dt):
        """Двигает камеру, когда курсор у края экрана (только если окно не перекрывает край)."""
        if not pygame.mouse.get_focused():
            return
        mx, my = pygame.mouse.get_pos()
        if my <= 75 or (self.chat is not None and self.chat.contains((mx, my))):
            return
        if self.active_entity is not None and self.active_window_rect.collidepoint(mx, my):
            return
        if self.building_window is not None:
            return
        step = EDGE_SCROLL_SPEED / self.zoom * dt
        dx = 0.0
        dy = 0.0
        if mx <= EDGE_SCROLL_MARGIN:
            dx -= step
        elif mx >= settings.WIDTH - EDGE_SCROLL_MARGIN:
            dx += step
        if my <= EDGE_SCROLL_MARGIN:
            dy -= step
        elif my >= settings.HEIGHT - EDGE_SCROLL_MARGIN:
            dy += step
        if dx or dy:
            self.camera_x += dx
            self.camera_y += dy

    def update(self, dt):
        self._refresh_city_visual_state()
        if self.presence is not None:
            self.presence.update(dt)
        if self.chat is not None:
            self.chat.update(dt)
        self.combat_log.update(dt)
        if self.pinned_mob is not None and (self.pinned_mob["hp"] <= 0
                                            or not any(m is self.pinned_mob for m in self.mobs)):
            self.pinned_mob = None
        # Откат тратит свою часть кадра только на таймер удара; движение по пути идёт полным кадром
        attack_dt = dt
        if self.attack_backswing > 0:
            spent = min(self.attack_backswing, dt)
            self.attack_backswing -= spent
            attack_dt = dt - spent
        if self.click_effect is not None:
            self.click_effect["timer"] -= dt
            if self.click_effect["timer"] <= 0:
                self.click_effect = None
        if self.hotbar_flash_timer > 0:
            self.hotbar_flash_timer = max(0.0, self.hotbar_flash_timer - dt)
        self.dash_cooldown = max(0.0, self.dash_cooldown - dt)
        # Замах тикает локально между снимками; сервер присылает точное значение при каждой синхронизации
        self.attack_windup = max(0.0, self.attack_windup - dt)
        # 1. Движение: путь по ПКМ или преследование моба для удара. Рывок двигает сервер, клиент его не считает
        if self.world_dash_active:
            self.player_state = "walk"
        else:
            if self.attack_target is not None:
                self._update_attack_target(attack_dt)
            # Во время замаха персонаж стоит на месте (анимация замаха и удар); в откате уже может идти
            if self.attack_windup > 0:
                self.player_state = "idle"
            elif self.move_path:
                self._follow_move_path(dt)
            if self.attack_target is None and not self.move_path:
                self.player_state = "idle"
        # Намерения (позиция, цель, рывок) уходят на сервер, снимок мира применяется сразу
        self._world_sync_request(dt)
        set_run_sound(self.player_state == "walk" and not self.world_dash_active)

        # Камера следует за персонажем, пока игрок не начал её двигать сам (SPACE возвращает слежение)
        if self.camera_follow_player:
            self.camera_x = self.player_x
            self.camera_y = self.player_y
        else:
            self._edge_scroll(dt)
        self._clamp_camera()

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
        self.hit_timer = max(0.0, self.hit_timer - dt)
        if self.death_timer is not None:
            self.death_timer += dt

        # 3. Обновление плавающих сообщений
        for msg in self.floating_messages[:]:
            msg["timer"] -= dt
            msg["world_y"] -= 20.0 * dt
            if msg["timer"] <= 0:
                self.floating_messages.remove(msg)
        self._update_damage_numbers(dt)

        # 5. Определение сущности под курсором мыши (hover)
        m_pos = pygame.mouse.get_pos()
        if self.building_window is not None or m_pos[1] <= 75 or (self.active_entity and self.active_window_rect.collidepoint(m_pos)):
            self.hovered_entity = None
            self.hovered_mobile_entity = None
        else:
            self.hovered_entity = self._find_entity_at(m_pos)
            self.hovered_mobile_entity = mobile_entity_at(self, m_pos, "world_map")

        # 6. Таймер уведомления о действии
        if self.action_notice_timer > 0:
            self.action_notice_timer -= dt
            if self.action_notice_timer <= 0:
                self.action_notice = None

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

        sprites = self._map_sprites() if self.uniform_grass else None
        # 1. Базовая земля (чистая плоская заливка top-down, без искажений)
        half_gy = self.grid_h // 2
        # Экранная X зависит только от wx, Y только от wy: считаем границы тайлов один раз.
        edge_x = {gx: self.world_to_screen(gx * self.tile_size, 0)[0]
                  for gx in range(start_gx, end_gx + 1)}
        edge_y = {gy: self.world_to_screen(0, gy * self.tile_size)[1]
                  for gy in range(start_gy, end_gy + 1)}
        for gy in range(start_gy, end_gy):
            for gx in range(start_gx, end_gx):
                sx, sy = edge_x[gx], edge_y[gy]
                sx2, sy2 = edge_x[gx + 1], edge_y[gy + 1]

                rect = pygame.Rect(sx, sy, sx2 - sx + 1, sy2 - sy + 1)

                if self.uniform_grass or gy < half_gy:
                    # Северная половина карты (Свет) - приглушенная зеленая трава
                    cell_color = (28, 42, 32) if (gx + gy) % 2 == 0 else (31, 46, 35)
                else:
                    # Южная половина карты (Тьма) - каменистая пустошь
                    cell_color = (36, 32, 34) if (gx + gy) % 2 == 0 else (40, 35, 38)

                if (gx, gy) in self.road_tiles:
                    # Запасной цвет дороги, если спрайты не загружены
                    cell_color = (120, 96, 60) if (gx + gy) % 2 == 0 else (128, 103, 65)

                if sprites and (gx, gy) in self.water_tiles:
                    screen.blit(sprites["water"][_map_hash(gx, gy) % len(sprites["water"])], rect.topleft)
                elif sprites:
                    kind = self.ground_kinds.get((gx, gy))
                    variants = sprites[kind] if kind else sprites["grass"]
                    screen.blit(variants[_map_hash(gx, gy) % len(variants)], rect.topleft)
                    if (gx, gy) in self.road_tiles:
                        screen.blit(self._road_surface(sprites, gx, gy), rect.topleft)
                else:
                    pygame.draw.rect(screen, cell_color, rect)

                if (gx, gy) in self.road_tiles and not sprites:
                    pygame.draw.line(screen, (95, 74, 44), rect.topleft, rect.topright, 1)
                    pygame.draw.line(screen, (95, 74, 44), rect.bottomleft, rect.bottomright, 1)

                if self.show_grid:
                    pygame.draw.rect(screen, (45, 52, 60), rect, 1)

        # 2. Рельеф с сервера и интерактивные объекты карты
        if sprites:
            self._draw_shore_rims(screen, sprites["shores"], start_gx, end_gx, start_gy, end_gy, edge_x, edge_y)
            self._draw_bridges(screen, sprites)
            self._draw_forest_trees(screen, sprites["trees"], sprites["props"])
        self._draw_terrain(screen)
        self._draw_objects(screen)
        self._draw_click_effect(screen)
        self._draw_whirlwinds(screen)
        if self.dash_aiming:
            self._draw_dash_aim(screen)
        self._draw_mobs(screen)
        self._draw_player_corpses(screen)
        self._draw_damage_numbers(screen)

        # 3. Игровой персонаж
        self._draw_player_character(screen)
        draw_active_players(self, screen, "world_map")
        draw_traveling_entities(self, screen, "world_map")
        draw_afk_players(self, screen, "world_map")

        # 4. Всплывающие сообщения в мире ("Слишком далеко" и т.д.)
        self._draw_floating_messages(screen)

        # 5. Миникарта и HUD рисуются до всех карточек и окон, чтобы карточки перекрывали их
        self._draw_minimap(screen)
        self._draw_hud(screen)
        self._draw_player_panel(screen)
        draw_hotbar(screen, hotbar_slot_rects(settings.WIDTH, settings.HEIGHT), self.small_font,
                    self.hotbar_flash_index if self.hotbar_flash_timer > 0 else None,
                    slots=self._hotbar_slot_states())

        # 6. Координаты рисуются до всплывающих окон, чтобы карточки всегда были поверх них
        self._draw_coords_box(screen, hover_wx, hover_wy)

        # 7. Всплывающее окно активного объекта (ЛКМ)
        self._draw_active_window(screen)
        self._draw_corpse_window(screen)

        # 8. Всплывающее окно при наведении курсора (hover tooltip)
        self._draw_hover_popup(screen, mouse_pos)

        # 9. Окно производственного здания
        if self.building_window is not None:
            self.building_window.draw(screen)
        if self.chat is not None:
            self.chat.draw(screen)
        self.combat_log.draw(screen)
        if self.pinned_mob is not None:
            self._draw_mob_hover_card(screen, self.pinned_mob, closable=True)
        if self.profile_overlay.is_open:
            self.profile_overlay.update_profile(self._own_player_card_profile())
            self.profile_overlay.draw(screen, show_player_only=True)
        elif (self.hovered_mobile_entity is not None
                and self.hovered_mobile_entity.get("entity_kind") == "player"):
            draw_mobile_hover_card(self, screen, self.hovered_mobile_entity)

    def _draw_mobs(self, screen):
        """Рисует мобов карты 90х53 px по центру их точки, с полоской HP над спрайтом."""
        now = pygame.time.get_ticks()
        for mob in self.mobs:
            if mob["hp"] <= 0:
                body = mob_death_frame(mob, now)
                if body is not None:
                    screen.blit(body, body.get_rect(center=self.world_to_screen(mob["x"], mob["y"])))
                continue
            sprite = mob_frame(mob, now) or mob.get("sprite")
            if sprite is None:
                continue
            sx, sy = self.world_to_screen(mob["x"], mob["y"])
            rect = sprite.get_rect(center=(sx, sy))
            if not rect.colliderect(pygame.Rect(0, 0, settings.WIDTH, settings.HEIGHT)):
                continue
            screen.blit(sprite, rect)

            is_active = self.active_entity is not None and self.active_entity.get("id") == mob["id"]
            is_hovered = self.hovered_entity is not None and self.hovered_entity.get("id") == mob["id"]
            if is_active:
                pygame.draw.rect(screen, (255, 215, 60), rect.inflate(8, 8), 2, border_radius=6)
            elif is_hovered:
                pygame.draw.rect(screen, (80, 200, 255), rect.inflate(8, 8), 2, border_radius=6)

            hp_ratio = max(0.0, min(1.0, mob["hp"] / mob["max_hp"]))
            bar = pygame.Rect(0, 0, 100, 5)
            bar.midbottom = (rect.centerx, rect.top - 3)
            pygame.draw.rect(screen, (40, 10, 10), bar)
            pygame.draw.rect(screen, (200, 40, 40), (bar.left, bar.top, int(bar.width * hp_ratio), bar.height))
            self._draw_overhead_label(screen, f"ХП {int(mob['hp'])}/{int(mob['max_hp'])}", (255, 110, 110), (bar.centerx, bar.top - 1))

    def _corpse_by_id(self, corpse_id):
        if corpse_id is None:
            return None
        return next((corpse for corpse in self.player_corpses if corpse["id"] == corpse_id), None)

    def _corpse_distance_tiles(self, corpse):
        return math.hypot(corpse["x"] - self.player_x, corpse["y"] - self.player_y) / self.tile_size

    @staticmethod
    def _corpse_marker_rect(screen_x, screen_y):
        rect = pygame.Rect(0, 0, 28, 20)
        rect.midbottom = (screen_x, screen_y)
        return rect

    def _player_corpse_at(self, pos):
        for corpse in self.player_corpses:
            sx, sy = self.world_to_screen(corpse["x"], corpse["y"])
            if self._corpse_marker_rect(sx, sy).collidepoint(pos):
                return corpse
        return None

    def _draw_player_corpses(self, screen):
        """Труп игрока: серый холмик с крестом; жёлтая рамка — труп, чьё окно открыто."""
        for corpse in self.player_corpses:
            sx, sy = self.world_to_screen(corpse["x"], corpse["y"])
            rect = self._corpse_marker_rect(sx, sy)
            if not rect.colliderect(pygame.Rect(0, 0, settings.WIDTH, settings.HEIGHT)):
                continue
            is_open = corpse["id"] == self.corpse_window_id
            color = (255, 215, 60) if is_open else (190, 190, 200)
            pygame.draw.ellipse(screen, (70, 70, 78), rect)
            pygame.draw.ellipse(screen, color, rect, 2)
            pygame.draw.line(screen, color, (rect.centerx, rect.top + 4), (rect.centerx, rect.bottom - 4), 2)
            pygame.draw.line(screen, color, (rect.left + 6, rect.centery - 2), (rect.right - 6, rect.centery - 2), 2)
            self._draw_overhead_label(screen, "Труп", color, (rect.centerx, rect.top - 2))

    def _corpse_window_layout(self):
        """(окно, кнопка закрытия, кнопка «Забрать все») по центру экрана."""
        window = pygame.Rect(0, 0, *CORPSE_WINDOW_SIZE)
        window.center = (settings.WIDTH // 2, settings.HEIGHT // 2)
        close = pygame.Rect(window.right - 36, window.top + 10, 26, 26)
        loot = pygame.Rect(0, 0, 200, 40)
        loot.midbottom = (window.centerx, window.bottom - 16)
        return window, close, loot

    def _open_corpse_window(self, corpse):
        if self._corpse_distance_tiles(corpse) > CORPSE_LOOT_RANGE_TILES:
            self.action_notice = "Подойдите ближе к трупу"
            self.action_notice_timer = 2.0
            return
        self.corpse_window_id = corpse["id"]

    def _loot_corpse(self):
        corpse = self._corpse_by_id(self.corpse_window_id)
        if corpse is None:
            return
        try:
            result = self.session.client.world_loot_corpse(self.session.character["id"], corpse["id"])
        except (ServerError, OSError) as error:
            self.action_notice = str(error)
            self.action_notice_timer = 2.0
            return
        self.session.character.update(result["currency"])
        self.player_corpses = [dict(item) for item in result["corpses"]]
        self.corpse_window_id = None
        self.action_notice = f"Забрано из трупа: {Currency.format_amount(corpse['copper'])}"
        self.action_notice_timer = 2.0

    def _draw_corpse_window(self, screen):
        """Окно трупа: монеты в трупе, кошелёк игрока и кнопка «Забрать все»."""
        corpse = self._corpse_by_id(self.corpse_window_id)
        if corpse is None:
            return
        window, close_rect, loot_rect = self._corpse_window_layout()
        surface = pygame.Surface(window.size, pygame.SRCALPHA)
        pygame.draw.rect(surface, (15, 20, 28, 245), (0, 0, window.width, window.height), border_radius=8)
        pygame.draw.rect(surface, (220, 185, 60, 255), (0, 0, window.width, window.height), width=2, border_radius=8)
        screen.blit(surface, window.topleft)
        screen.blit(self.font.render("Труп игрока", True, (255, 225, 120)), (window.left + 14, window.top + 12))

        m_pos = pygame.mouse.get_pos()
        close_bg = (180, 50, 50) if close_rect.collidepoint(m_pos) else (45, 30, 35)
        pygame.draw.rect(screen, close_bg, close_rect, border_radius=4)
        pygame.draw.rect(screen, (220, 100, 100), close_rect, width=1, border_radius=4)
        close_label = self.small_font.render("✕", True, (255, 255, 255))
        screen.blit(close_label, close_label.get_rect(center=close_rect.center))

        pygame.draw.line(screen, (50, 65, 80), (window.left + 14, window.top + 44), (window.right - 14, window.top + 44), 1)
        character = self.session.character
        wallet = Currency(copper=int(character.get("copper") or 0),
                          silver=int(character.get("silver") or 0),
                          gold=int(character.get("gold") or 0))
        lines = [
            (f"В трупе монет: {Currency.format_amount(corpse['copper'])}", (255, 225, 120)),
            (f"Ваш кошелёк: {Currency.format_amount(wallet.total_copper())}", (200, 220, 240)),
            (f"Расстояние: {round(self._corpse_distance_tiles(corpse))} {_tiles_word(round(self._corpse_distance_tiles(corpse)))}",
             (160, 175, 190)),
        ]
        for index, (text, color) in enumerate(lines):
            screen.blit(self.small_font.render(text, True, color), (window.left + 14, window.top + 56 + index * 26))

        btn_col = (60, 120, 70) if loot_rect.collidepoint(m_pos) else (40, 90, 50)
        draw_button(screen, loot_rect, "Забрать все", self.small_font, color=btn_col, text_color=(255, 255, 255))

    def _draw_badge(self, screen, cx, bottom_y, text, border_color):
        """Вспомогательный метод для аккуратной плашки с текстом над объектом."""
        draw_map_badge(self.badge_font, screen, cx, bottom_y, text, border_color)

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

            elif obj.get("id") == "town_radburg":
                top_left_x = obj["tile_x"] * self.tile_size
                top_left_y = obj["tile_y"] * self.tile_size
                sx, sy = self.world_to_screen(top_left_x, top_left_y)
                obj_w = obj["tile_w"] * self.tile_size
                obj_h = obj["tile_h"] * self.tile_size
                city_rect = pygame.Rect(sx, sy, obj_w, obj_h)
                if not city_rect.colliderect(pygame.Rect(0, 0, settings.WIDTH, settings.HEIGHT)):
                    continue
                draw_city_exterior(screen, city_rect, self.city_visual_state)
                is_active = self.active_entity and self.active_entity.get("id") == obj["id"]
                is_hovered = self.hovered_entity and self.hovered_entity.get("id") == obj["id"]
                if is_active:
                    pygame.draw.rect(screen, (255, 215, 60), city_rect, 3, border_radius=8)
                elif is_hovered:
                    pygame.draw.rect(screen, (80, 200, 255), city_rect.inflate(8, 8), 2, border_radius=8)
                else:
                    pygame.draw.rect(screen, (100, 125, 155), city_rect, 2, border_radius=8)
                badge_color = (255, 215, 60) if is_active else (100, 200, 255) if is_hovered else (220, 200, 160)
                level = int(self.city_visual_state.get("city_level", 1))
                self._draw_badge(screen, city_rect.centerx, sy - 12,
                                 f"Город Радбург · ур. {level}", badge_color)

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

    def _mob_card_rect(self):
        return pygame.Rect(settings.ENEMY_CARD_RECT)

    def _mob_card_close_rect(self):
        frame = self._mob_card_rect()
        return pygame.Rect(frame.right - 34, frame.y + 10, 24, 24)

    def _draw_mob_hover_card(self, screen, mob=None, closable=False):
        """Карточка моба справа, в стиле карточки игрока (красная рамка).

        closable=True — закреплённая карточка с крестиком в правом верхнем углу.
        """
        if mob is None:
            mob = self.hovered_entity
        frame = self._mob_card_rect()
        pygame.draw.rect(screen, (28, 22, 26), frame, border_radius=10)
        pygame.draw.rect(screen, (200, 70, 70), frame, width=3, border_radius=10)

        fighter = mob.get("fighter")
        if fighter is not None:
            fighter.hp = max(0, int(mob.get("hp", 0)))
            fighter.max_hp = max(1, int(mob.get("max_hp", fighter.max_hp)))
            profile = profile_from_fighter(fighter)
            profile["max_mp"] = 0
            profile["mp"] = 0
            coins = mob.get("coins") or {}
            profile["copper"] = int(coins.get("copper", 0))
            profile["silver"] = int(coins.get("silver", 0))
            profile["gold"] = int(coins.get("gold", 0))
            self._mob_card().draw(
                screen,
                frame,
                profile,
                border_color=(200, 70, 70),
                title="ВРАГ РЯДОМ",
                editable=False,
                mob_mode=True,
                sprite=self._mob_card_sprite(),
            )

        if closable:
            close = self._mob_card_close_rect()
            pygame.draw.rect(screen, (60, 36, 40), close, border_radius=4)
            pygame.draw.rect(screen, (200, 70, 70), close, width=1, border_radius=4)
            pygame.draw.line(screen, (240, 200, 200), (close.x + 7, close.y + 7), (close.right - 7, close.bottom - 7), 2)
            pygame.draw.line(screen, (240, 200, 200), (close.right - 7, close.y + 7), (close.x + 7, close.bottom - 7), 2)

    def _own_player_card_profile(self):
        """Профиль своего персонажа с живыми HP/MP боевого бойца (урон и регенерация), а не из сохранения."""
        profile = dict(self.session.character)
        fighter = self.combat_fighter
        profile.update(
            hp=int(fighter.hp),
            max_hp=int(fighter.max_hp),
            mp=int(fighter.mp),
            max_mp=int(fighter.max_mp),
            max_hp_includes_equipment=True,
        )
        return profile

    def _draw_own_player_hover_card(self, screen):
        """Карточка своего персонажа слева при наведении — на месте левого профиля (двойной клик)."""
        character = self._own_player_card_profile()
        card = CharacterCard.get_or_create(character.get("character_id", character.get("id")))
        card.draw(
            screen,
            pygame.Rect(settings.PLAYER_CARD_RECT),
            profile=character,
            border_color=(95, 174, 225),
            title="ВЫ",
            editable=False,
        )

    def _mob_card(self):
        """Одна карточка моба на сцену: не регистрируется в общем реестре карточек игроков."""
        if getattr(self, "_mob_card_instance", None) is None:
            self._mob_card_instance = CharacterCard()
        return self._mob_card_instance

    def _mob_card_sprite(self):
        """Спрайт скелета для карточки, масштабированный до размера спрайта игрока."""
        if getattr(self, "_mob_card_sprite_instance", None) is None:
            sprite_path = Path(__file__).resolve().parent.parent / "assets" / "mobs" / "woodland_bandit.png"
            sprite = FighterSprite(path=sprite_path)
            if sprite.image is not None:
                target_height = int(sprite.image.get_height() * settings.FIGHTER_SPRITE_SCALE)
                scale = target_height / sprite.image.get_height()
                sprite.image = pygame.transform.smoothscale(
                    sprite.image,
                    (int(sprite.image.get_width() * scale), target_height),
                )
            self._mob_card_sprite_instance = sprite
        return self._mob_card_sprite_instance

    def _draw_hover_popup(self, screen, mouse_pos):
        """Отрисовывает всплывающее окно (tooltip) при наведении курсора на объект."""
        if self.hovered_mobile_entity is not None:
            if self.hovered_mobile_entity.get("entity_kind") != "player":
                draw_mobile_hover_card(self, screen, self.hovered_mobile_entity)
            return
        if self.hovered_entity is None:
            return
        if self.hovered_entity.get("entity_kind") == "mob":
            if self.pinned_mob is None:
                self._draw_mob_hover_card(screen)
            return
        if self.profile_overlay.is_open or self.pinned_mob is not None:
            return
        if self.hovered_entity.get("id") == "player":
            self._draw_own_player_hover_card(screen)
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
        building_icon = draw_building_icon(screen, ent.get("id"), (box_x + 10, box_y + 5), 32)
        title_x = box_x + 50 if building_icon else box_x + 12
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

        status_text = "● АКТИВЕН"
        status_color = (80, 255, 120)
        if ent.get("entity_kind") == "mob":
            status_text = f"HP {ent['hp']} / {ent['max_hp']}"
            status_color = (255, 110, 110)
        status_surf = self.badge_font.render(status_text, True, status_color)
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
            if ent.get("id") == "lumber_camp":
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
        progress = 1.0 - (self.click_effect["timer"] / CLICK_EFFECT_DURATION)
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

        character = getattr(self.session, "character", None) or {}
        windup_total = self.attack_windup_total or self.attack_windup
        attacking = self.attack_windup > 0
        attack_progress = 1.0 - self.attack_windup / max(windup_total, 1e-6) if attacking else 0.0
        hit_progress, death_progress = self._hero_reaction_progress()
        frame_surf = player_frame(
            self, character, self.player_direction, self.player_anim_timer,
            moving=self.player_state == "walk", attacking=attacking, attack_progress=attack_progress,
            attack_variant=self.attack_variant, hit_progress=hit_progress, death_progress=death_progress,
        )

        if frame_surf is not None:
            # Ноги персонажа касаются земли в точке (sx, sy)
            frame_rect = frame_surf.get_rect(midbottom=(sx, sy))
            screen.blit(frame_surf, frame_rect)
            name_y = player_label_top(character, frame_rect) - 4
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

        # Над головой: полоска МП у спрайта с подписью, над ней ХП с подписью, сверху ник
        fighter = self.combat_fighter
        bar_w, bar_h, gap = 100, self.OVERHEAD_BAR_HEIGHT, 2
        mp_rect = pygame.Rect(0, 0, bar_w, bar_h)
        mp_rect.midbottom = (sx, name_y)
        mp_label = self._draw_overhead_label(screen, f"МП {int(fighter.mp)}/{int(fighter.max_mp)}", (120, 170, 255), (sx, mp_rect.top - 1))
        hp_rect = pygame.Rect(0, 0, bar_w, bar_h)
        hp_rect.midbottom = (sx, mp_label.top - gap)
        hp_label = self._draw_overhead_label(screen, f"ХП {int(fighter.hp)}/{int(fighter.max_hp)}", (255, 110, 110), (sx, hp_rect.top - 1))
        self._draw_overhead_bar(screen, hp_rect, fighter.hp / max(1, fighter.max_hp), (190, 55, 55))
        self._draw_overhead_bar(screen, mp_rect, fighter.mp / max(1, fighter.max_mp), (60, 120, 220))

        char_name = (getattr(self.session, "character", None) or {}).get("name", "Герой")
        name_surf = self.grid_font.render(char_name, True, (255, 235, 150))
        n_rect = name_surf.get_rect(midbottom=(sx, hp_label.top - gap))
        bg = n_rect.inflate(8, 2)
        pygame.draw.rect(screen, (15, 18, 24, 210), bg, border_radius=3)
        pygame.draw.rect(screen, (180, 150, 60), bg, 1, border_radius=3)
        draw_profession_icon_before(screen, player_profession(character), bg)
        screen.blit(name_surf, n_rect)

    def _draw_overhead_bar(self, screen, rect, ratio, color):
        """Тонкая полоска ХП/МП над персонажем или мобом (без цифр внутри)."""
        ratio = max(0.0, min(1.0, ratio))
        pygame.draw.rect(screen, (40, 10, 10), rect)
        pygame.draw.rect(screen, color, (rect.x, rect.y, int(rect.width * ratio), rect.height))

    def _draw_overhead_label(self, screen, text, color, midbottom):
        """Подпись «ХП x/y» или «МП x/y» над полоской, с тенью для читаемости. Возвращает прямоугольник подписи."""
        shadow = self.grid_font.render(text, True, (0, 0, 0))
        surf = self.grid_font.render(text, True, color)
        rect = surf.get_rect(midbottom=midbottom)
        screen.blit(shadow, rect.move(1, 1))
        screen.blit(surf, rect)
        return rect

    def _draw_coords_box(self, screen, hover_wx, hover_wy):
        """Координаты курсора и героя над миникартой в левом нижнем углу (рисуется под всплывающими окнами)."""
        ts = self.tile_size
        cursor_str = f"Курсор: X={int(hover_wx)}, Y={int(hover_wy)} (тайл: {int(hover_wx // ts)}, {int(hover_wy // ts)})"
        hero_str = f"Персонаж: X={int(self.player_x)}, Y={int(self.player_y)} (тайл: {int(self.player_x // ts)}, {int(self.player_y // ts)})"
        lines = [self.font.render(text, True, (240, 240, 240)) for text in (cursor_str, hero_str)]
        line_h = max(surf.get_height() for surf in lines)
        text_w = max(surf.get_width() for surf in lines)
        minimap_top = settings.HEIGHT - self.MINIMAP_MARGIN[1] - self.MINIMAP_HEIGHT
        box = pygame.Rect(0, 0, text_w + 32, len(lines) * line_h + 18)
        box.bottomleft = (self.MINIMAP_MARGIN[0], minimap_top - self.MINIMAP_MARGIN[1])
        box_surf = pygame.Surface(box.size, pygame.SRCALPHA)
        pygame.draw.rect(box_surf, (15, 18, 24, 235), box_surf.get_rect(), border_radius=6)
        pygame.draw.rect(box_surf, (220, 180, 70), box_surf.get_rect(), 1, border_radius=6)
        screen.blit(box_surf, box.topleft)
        for i, surf in enumerate(lines):
            screen.blit(surf, (box.x + 16, box.y + 9 + i * line_h))

    def _draw_hud(self, screen):
        """Строка улучшений города."""
        draw_city_upgrade_line(
            screen, upgrade_line_font(), self.city_visual_state,
            getattr(self, "castle_upgrades_active", None),
        )

    def _draw_player_panel(self, screen):
        """Панель персонажа в левом верхнем углу: иконка и ник сверху, портрет слева, полоски ХП и МП справа от портрета."""
        margin = self.PLAYER_PANEL_MARGIN
        gap = self.PLAYER_PANEL_GAP
        portrait_size = self.PLAYER_PANEL_PORTRAIT
        character = getattr(self.session, "character", None) or {}
        name = character.get("name") or "Герой"
        fighter = self.combat_fighter

        icon = profession_icon(player_profession(character))
        name_x = margin
        if icon is not None:
            screen.blit(icon, (margin, margin))
            name_x += PROFESSION_ICON_SIZE + gap
        name_surf = self.font.render(name, True, (255, 235, 150))
        screen.blit(name_surf, name_surf.get_rect(midleft=(name_x, margin + PROFESSION_ICON_SIZE // 2)))

        portrait = pygame.Rect(margin, margin + PROFESSION_ICON_SIZE + gap, portrait_size, portrait_size)
        pygame.draw.rect(screen, (15, 18, 24), portrait, border_radius=4)
        frame = player_frame(self, character, self.player_direction, self.player_anim_timer, moving=False)
        if frame is not None:
            fit = portrait_size - 8
            scale = min(fit / frame.get_width(), fit / frame.get_height())
            scaled = pygame.transform.smoothscale(frame, (max(1, round(frame.get_width() * scale)), max(1, round(frame.get_height() * scale))))
            screen.blit(scaled, scaled.get_rect(center=portrait.center))
        pygame.draw.rect(screen, (180, 150, 60), portrait, 1, border_radius=4)

        bar_h = self.PLAYER_PANEL_BAR_HEIGHT
        text_h = self.font.get_height()
        rows = (
            (f"{int(fighter.hp)}/{int(fighter.max_hp)} ХП", (255, 110, 110), (210, 80, 80), fighter.hp, fighter.max_hp),
            (f"{int(fighter.mp)}/{int(fighter.max_mp)} МП", (120, 170, 255), (60, 140, 220), fighter.mp, fighter.max_mp),
        )
        x = portrait.right + gap + 4
        y = portrait.top
        for label, text_color, bar_color, value, maximum in rows:
            screen.blit(self.font.render(label, True, text_color), (x, y))
            y += text_h + 2
            bar = pygame.Rect(x, y, self.PLAYER_PANEL_BAR_WIDTH, bar_h)
            ratio = max(0.0, min(1.0, value / max(1, maximum)))
            pygame.draw.rect(screen, (20, 22, 28), bar)
            pygame.draw.rect(screen, bar_color, (bar.x, bar.y, int(bar.width * ratio), bar.height))
            pygame.draw.rect(screen, (60, 66, 76), bar, 1)
            y += bar_h + gap * 3

    def close(self):
        if self.presence is not None:
            self.presence.close()
        if self.chat is not None:
            self.chat.hide()
        character = getattr(self.session, "character", None)
        if character:
            try:
                self.session.client.world_leave(character["id"])
            except (ServerError, OSError):
                pass

