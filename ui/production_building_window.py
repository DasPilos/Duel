"""Окно производственного здания (поселение, лагерь лесорубов). Только отрисовка серверного состояния и отправка действий."""

import math
import random
import time
from pathlib import Path

import pygame

from client.network import ServerError
from core import settings
from core.production_buildings import (
    CYCLE_DURATION_SEC,
    RESOURCES,
    building_config,
    building_level_info,
    building_resources,
    plot_slot_ranges,
)
from ui.catalog_icons import draw_building_icon, draw_item_icon
from ui.hud import draw_button
from ui.material_contribution_dialog import MaterialContributionDialog

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "town"

# Положение полей поселения в правой части окна (доли ширины/высоты), в порядке участков
FARM_FIELD_LAYOUT = (
    (0.42, 0.36, 0.15, 0.22),
    (0.60, 0.38, 0.11, 0.17),
    (0.28, 0.40, 0.11, 0.17),
    (0.43, 0.08, 0.11, 0.17),
    (0.45, 0.68, 0.11, 0.17),
    (0.24, 0.06, 0.15, 0.22),
    (0.59, 0.06, 0.15, 0.22),
    (0.23, 0.64, 0.18, 0.28),
    (0.60, 0.64, 0.18, 0.28),
    (0.02, 0.08, 0.18, 0.30),
    (0.80, 0.10, 0.18, 0.30),
    (0.02, 0.52, 0.18, 0.30),
)

VIEWS = {
    "farm": {
        "object_id": "wheat_farm",
        "asset_dir": "farm",
        "shape": "fields",
        "harvest_label": "Сбор урожая",
        "plot_names": {("wheat", "field"): "Поле", ("flax", "field"): "Поле", ("cotton", "field"): "Поле"},
    },
    "lumber_camp": {
        "object_id": "lumber_camp",
        "asset_dir": "lumber_camp",
        "shape": "pie",
        "harvest_label": "Сбор",
        "plot_names": {
            ("wood", "edge"): "Край леса",
            ("berries", "edge"): "Опушка",
            ("wood", "inner"): "Чаща",
            ("berries", "inner"): "Большая поляна",
        },
    },
    "mountain_rift": {
        "object_id": "mountain_rift",
        "asset_dir": "mountain_rift",
        "shape": "rift",
        "harvest_label": "Сбор",
        "group_by_kind": True,
        "plot_names": {
            ("iron", "iron_mine"): "Прииск железа",
            ("stone", "stone_mine"): "Прииск камня",
            ("mithril", "mithril_mine"): "Прииск мифрила",
            ("obsidian", "obsidian_mine"): "Прииск обсидиана",
        },
    },
    "barnyard": {
        "object_id": "barnyard",
        "asset_dir": "farm",
        "shape": "pen",
        "harvest_label": "Сбор",
        "group_by_kind": True,
        "plot_names": {(("leather", "meat"), "pen"): "Загон"},
    },
    "black_pit": {
        "object_id": "black_pit",
        "asset_dir": "farm",
        "shape": "digs",
        "harvest_label": "Сбор",
        "plot_names": {("coal", "dig"): "Копанка"},
    },
}

# Центры копанок Чёрной копи (доли области) в порядке открытия; размер — по числу мест
DIG_LAYOUT = (
    (0.50, 0.50), (0.33, 0.42), (0.66, 0.40), (0.42, 0.76), (0.62, 0.74),
    (0.20, 0.72), (0.82, 0.68), (0.22, 0.22), (0.80, 0.24), (0.50, 0.17),
)

# Размещение приисков вдоль ущелья: (доля пути от входа, сторона: -1 северо-запад, +1 юго-восток)
RIFT_MINE_LAYOUT = {
    "iron_mine": (0.22, -1),
    "stone_mine": (0.34, 1),
    "mithril_mine": (0.62, -1),
    "obsidian_mine": (0.8, 1),
}
ORE_COLORS = {
    "iron": (200, 120, 90),
    "stone": (185, 185, 178),
    "mithril": (150, 205, 245),
    "obsidian": (140, 70, 190),
}


def object_building(object_id):
    """Здание, которое открывается с объекта карты (или None)."""
    return next((building for building, view in VIEWS.items() if view["object_id"] == object_id), None)


def format_duration(seconds):
    hours, rem = divmod(int(seconds), 3600)
    minutes = rem // 60
    return f"{hours} ч {minutes} мин" if hours > 0 else f"{minutes} мин"


def format_clock(seconds):
    hours, rest = divmod(max(0, int(seconds)), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours} ч {minutes:02d} м {secs:02d} с"


def wrap_text_lines(font, text, max_width):
    lines = []
    current = ""
    for word in text.split(" "):
        trial = f"{current} {word}".strip()
        if font.size(trial)[0] <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def point_in_polygon(point, polygon):
    x, y = point
    inside = False
    count = len(polygon)
    for i in range(count):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % count]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


class ProductionBuildingWindow:
    LEFT_COLUMN = 300
    WORKER_PANEL_WIDTH = 300
    WORKER_ROW_HEIGHT = 64
    HOUSE_SIZE = 28
    REFRESH_SECONDS = 5
    # Лес: внутреннее кольцо (чаща и большие поляны) занимает такую долю радиуса
    INNER_RADIUS = 0.58

    def __init__(self, scene, building, view=None):
        self.scene = scene
        self.building = building
        self.view = view or VIEWS[building]
        self.plots = building_config(building)["plots"]
        self.groups = self._build_groups()
        self.resources = building_resources(building)
        self.state = None
        self.is_open = False
        self.tab = "production"
        self.message = None
        self.last_refresh = 0.0
        self.received_at = 0.0
        self.deposit_buttons = {}
        self.contribution_dialog = MaterialContributionDialog(scene)
        self.selected_plot = None
        self.worker_stats_scroll = 0
        self.pending_worker_action = None
        self._geometry_cache = None
        self._surfaces = {}
        self._textures = {}
        self._house = None

        self.rect = pygame.Rect(settings.WIDTH // 2 - 850, settings.HEIGHT // 2 - 500, 1700, 1000)
        self.close_button = pygame.Rect(self.rect.right - 164, self.rect.top + 12, 144, 32)
        self.upgrade_button = pygame.Rect(0, 0, 250, 34)
        self.work_button = pygame.Rect(self.rect.right - 346, self.rect.top + 106, 112, 30)
        self.confirm_dialog_rect = pygame.Rect(settings.WIDTH // 2 - 260, settings.HEIGHT // 2 - 125, 520, 250)
        self.confirm_yes_button = pygame.Rect(self.confirm_dialog_rect.right - 258,
                              self.confirm_dialog_rect.bottom - 60, 120, 38)
        self.confirm_no_button = pygame.Rect(self.confirm_dialog_rect.right - 126,
                             self.confirm_dialog_rect.bottom - 60, 110, 38)
        self.production_tab = pygame.Rect(self.rect.left + 24, self.rect.top + 80, 190, 30)
        self.storage_tab = pygame.Rect(self.rect.left + 220, self.rect.top + 80, 190, 30)
        self.upgrade_tab = pygame.Rect(self.rect.left + 416, self.rect.top + 80, 190, 30)

    # ---------- состояние с сервера ----------

    @property
    def name(self):
        return building_config(self.building)["name"]

    def _state(self):
        return self.state or {}

    def level(self):
        return int(self._state().get("level", 1))

    def workers(self):
        return int(self._state().get("workers", 0))

    def player_is_working(self):
        worker_id = f"player:{self.scene.session.character['id']}"
        return any(slot.get("worker_id") == worker_id
                   for slot in self._state().get("worker_slots", []))

    def storage_total(self):
        return int(self._state().get("storage_total", 0))

    def stage(self):
        return int(self._state().get("stage", 0))

    def _since_received(self):
        """Сколько секунд прошло с ответа сервера (только чтобы таймеры тикали между обновлениями)."""
        return time.monotonic() - self.received_at

    def open(self):
        self.load()
        self.is_open = True

    def load(self):
        self.last_refresh = time.monotonic()
        try:
            self.state = self.scene.session.client.get_building(self.building, self.scene.session.character["id"])
        except (ServerError, KeyError, AttributeError, OSError):
            self.state = None
            return False
        self.received_at = time.monotonic()
        return True

    def _request(self, action, payload=None):
        """Действие на сервере; ответ сервера заменяет локальное состояние."""
        try:
            self.state = self.scene.session.client.building_action(
                self.building, self.scene.session.character["id"], action, payload
            )
            self.received_at = time.monotonic()
            self.message = None
            if action in ("upgrade/deposit", "player-harvest/claim", "storage/deposit"):
                refresh_carrying_state = getattr(self.scene.session, "refresh_carrying_state", None)
                if refresh_carrying_state is not None:
                    refresh_carrying_state()
        except ServerError as error:
            self.message = str(error)
        except (KeyError, AttributeError, OSError):
            self.message = "Сервер недоступен"

    def hire_worker(self, slot_index=None):
        if slot_index is None:
            slot = next((item for item in self._state().get("worker_slots", []) if not item["occupied"]), None)
            if slot is None:
                return
            slot_index = slot["slot_index"]
        self._request("workers/hire", {"slot_index": slot_index, "worker_id": f"citizen-{slot_index + 1}"})

    def fire_worker(self, slot_index=None):
        if slot_index is None:
            slot = next((item for item in reversed(self._state().get("worker_slots", [])) if item["occupied"]), None)
            if slot is None:
                return
            slot_index = slot["slot_index"]
        self._request("workers/fire", {"slot_index": slot_index})

    def deposit_material(self, item_id, quantity):
        self._request("upgrade/deposit", {"item_id": item_id, "quantity": quantity})

    def start_upgrade(self):
        self._request("upgrade/start")

    def _refresh_if_due(self):
        """Здание общее для фракции: пока окно открыто, состояние перечитывается с сервера каждые несколько секунд."""
        if time.monotonic() - self.last_refresh >= self.REFRESH_SECONDS:
            self.load()

    # ---------- тексты ----------

    def production_desc(self, level):
        info = building_level_info(level, self.building)
        per_cycle = ", ".join(
            f"{RESOURCES[resource]['label'].lower()} {CYCLE_DURATION_SEC // RESOURCES[resource]['timer_sec']}"
            for resource in self.resources
            if "timer_sec" in RESOURCES[resource]
        )
        bonus = building_config(self.building).get("bonus")
        chance = bonus["cycle_chance"].get(int(level), 0) if bonus else 0
        if chance:
            gems = ", ".join(
                f"{RESOURCES[gem]['label'].lower()} {weight}%" for gem, weight in bonus["weights"][int(level)].items()
            )
            per_cycle += (
                f". Шанс камня {chance * 100:g}% за цикл отгрузки на всю копь, если работает "
                f"хотя бы 1 горожанин и склад не переполнен ({gems}; каждый 1 кг)"
            )
        return (
            f"Горожанин за цикл {CYCLE_DURATION_SEC // 60} мин: {per_cycle}. "
            f"Склад: {info['storage']}. Горожан: {info['max_workers']}."
        )

    def harvest_countdown(self):
        state = self.state
        if state is None or self.workers() <= 0:
            return "ожидание рабочего"
        if self.storage_total() >= state["storage"]["limit"]:
            return "склад заполнен"
        return format_clock(state["cycle_seconds_left"] - self._since_received())

    def status(self):
        """Возвращает (статус, цвет)."""
        state = self.state
        if state is None:
            return "Нет связи с сервером", (240, 90, 80)
        if (state.get("upgrade") or {}).get("in_progress"):
            return "Идёт улучшение", (120, 190, 240)
        if self.storage_total() >= state["storage"]["limit"]:
            return "Склад переполнен", (240, 90, 80)
        if self.workers() > 0:
            return "Работает", (110, 230, 120)
        return "Нет рабочих", (240, 210, 90)

    def _build_groups(self):
        """Участки на экране: у полей и леса — по одному на открытие, у разлома — прииск со всеми местами."""
        groups = []
        by_kind = {}
        for (level, places, resource, kind), slots in zip(self.plots, plot_slot_ranges(self.building)):
            group = by_kind.get(kind) if self.view.get("group_by_kind") else None
            if group is None:
                group = {"level": level, "resource": resource, "kind": kind, "slots": [], "places": 0}
                groups.append(group)
                by_kind[kind] = group
            group["slots"].extend(slots)
            group["places"] += places
        return groups

    def plot_name(self, index):
        group = self.groups[index]
        name = self.view["plot_names"][(group["resource"], group["kind"])]
        if self.view.get("group_by_kind"):
            return name
        return f"{name} ({RESOURCES[group['resource']]['label'].lower()})"

    # ---------- геометрия участков ----------

    def plots_area(self):
        top = self.rect.top + 174
        left = self.rect.left + self.LEFT_COLUMN
        right = self.rect.right - 20
        return pygame.Rect(left, top, max(100, right - left), self.rect.bottom - 20 - top)

    def worker_stats_rect(self):
        top = self.rect.top + 174
        bottom = min(
            self.rect.bottom - 20,
            getattr(settings, "CHAT_ZONE_START", self.rect.bottom - 20) - 8,
        )
        return pygame.Rect(self.rect.left + 10, top, self.LEFT_COLUMN - 20,
                           max(120, bottom - top))

    def plot_geometry(self):
        """Контуры участков: rect (габарит), points (полигон), center (точка внутри), house_y (ряд домиков)."""
        area = self.plots_area()
        key = (area, self.level())
        if self._geometry_cache is not None and self._geometry_cache[0] == key:
            return self._geometry_cache[1]
        plots = {
            "pie": self._pie_geometry, "rift": self._rift_geometry, "pen": self._pen_geometry, "digs": self._digs_geometry,
        }.get(self.view["shape"], self._fields_geometry)(area)
        self._geometry_cache = (key, plots)
        self._surfaces = {}
        return plots

    @staticmethod
    def _polygon_plot(points, center, house_y):
        xs = [x for x, _ in points]
        ys = [y for _, y in points]
        rect = pygame.Rect(int(min(xs)), int(min(ys)), int(max(xs) - min(xs)) + 2, int(max(ys) - min(ys)) + 2)
        return {"rect": rect, "points": points, "center": (int(center[0]), int(center[1])), "house_y": house_y}

    def _fields_geometry(self, area):
        """Поля поселения: неровные сглаженные прямоугольники."""
        plots = []
        for index, (fx, fy, fw, fh) in enumerate(FARM_FIELD_LAYOUT):
            field = pygame.Rect(
                area.left + int(fx * area.width),
                area.top + int(fy * area.height),
                int(fw * area.width),
                int(fh * area.height),
            )
            rng = random.Random(index * 7 + 3)
            points = []
            for step in range(10):
                angle = 2 * math.pi * step / 10 + rng.uniform(-0.12, 0.12)
                cos, sin = math.cos(angle), math.sin(angle)
                radius = rng.uniform(0.86, 1.0)
                px = math.copysign(abs(cos) ** 0.55, cos) * field.width / 2 * radius
                py = math.copysign(abs(sin) ** 0.55, sin) * field.height / 2 * radius
                points.append((field.centerx + px, field.centery + py))
            plot = self._polygon_plot(points, field.center, field.bottom + 2)
            plots.append(plot)
        return plots

    def _pie_geometry(self, area):
        """Лес: неровный круг, разрезанный как пирог — внешнее кольцо (края, опушки) и сердцевина (чаща, поляны)."""
        cx, cy = area.center
        radius_x = area.width * 0.36
        radius_y = area.height * 0.47
        rng = random.Random(self.building)
        phases = [rng.uniform(0, 2 * math.pi) for _ in range(3)]

        def edge(angle):
            # Неровный край леса: сумма гармоник
            wobble = (0.06 * math.sin(3 * angle + phases[0]) + 0.04 * math.sin(5 * angle + phases[1])
                      + 0.025 * math.sin(9 * angle + phases[2]))
            return 0.92 + wobble

        def point(angle, scale):
            return (cx + math.cos(angle) * radius_x * scale, cy + math.sin(angle) * radius_y * scale)

        def inner_edge(angle):
            return self.INNER_RADIUS + 0.03 * math.sin(4 * angle + phases[1])

        outer = [i for i, plot in enumerate(self.plots) if plot[3] == "edge"]
        inner = [i for i, plot in enumerate(self.plots) if plot[3] == "inner"]
        plots = [None] * len(self.plots)
        gap = 0.012

        def slices(indices, start_angle):
            weights = [self.plots[i][1] for i in indices]
            total = sum(weights)
            angle = start_angle
            for index, weight in zip(indices, weights):
                span = 2 * math.pi * weight / total
                yield index, angle + gap, angle + span - gap
                angle += span

        for index, a0, a1 in slices(outer, -math.pi / 2):
            steps = max(6, int((a1 - a0) * 18))
            arc = [a0 + (a1 - a0) * s / steps for s in range(steps + 1)]
            points = [point(a, edge(a)) for a in arc] + [point(a, inner_edge(a) + 0.02) for a in reversed(arc)]
            mid = (a0 + a1) / 2
            center = point(mid, (edge(mid) + inner_edge(mid)) / 2)
            plots[index] = self._polygon_plot(points, center, int(center[1]) + 14)

        for index, a0, a1 in slices(inner, -math.pi / 2 + 0.3):
            steps = max(6, int((a1 - a0) * 14))
            arc = [a0 + (a1 - a0) * s / steps for s in range(steps + 1)]
            mid = (a0 + a1) / 2
            points = [point(mid, 0.05)] + [point(a, inner_edge(a) - 0.02) for a in arc]
            center = point(mid, self.INNER_RADIUS * 0.55)
            plots[index] = self._polygon_plot(points, center, int(center[1]) + 14)
        return plots

    def _rift_axis(self, area):
        """Ущелье идёт по диагонали: вход слева снизу, глубина справа сверху."""
        start = (area.left + area.width * 0.06, area.bottom - area.height * 0.02)
        end = (area.right - area.width * 0.08, area.top + area.height * 0.1)
        length = math.hypot(end[0] - start[0], end[1] - start[1])
        along = ((end[0] - start[0]) / length, (end[1] - start[1]) / length)
        normal = (-along[1], along[0])
        return start, end, along, normal

    def _rift_geometry(self, area):
        start, end, along, normal = self._rift_axis(area)
        plots = []
        for index, group in enumerate(self.groups):
            t, side = RIFT_MINE_LAYOUT[group["kind"]]
            cx = start[0] + (end[0] - start[0]) * t + normal[0] * side * 230
            cy = start[1] + (end[1] - start[1]) * t + normal[1] * side * 230
            cx = max(area.left + 180, min(area.right - 180, cx))
            cy = max(area.top + 130, min(area.bottom - 130, cy))
            rng = random.Random(index * 11 + 5)
            points = []
            for step in range(14):
                angle = 2 * math.pi * step / 14
                scale = rng.uniform(0.82, 1.0)
                points.append((cx + math.cos(angle) * 165 * scale, cy + math.sin(angle) * 115 * scale))
            plot = self._polygon_plot(points, (cx, cy), int(cy) + 40)
            # Палатка стоит на краю уступа, ближе к ущелью
            plot["tent"] = (int(cx - normal[0] * side * 70 + along[0] * 95), int(cy - normal[1] * side * 70 + along[1] * 95))
            plots.append(plot)
        return plots
        for index, plot in enumerate(self.plot_geometry()):
            if plot["rect"].collidepoint(position) and point_in_polygon(position, plot["points"]):
                return index
        return None

    def plot_slots(self, index):
        """Слоты участка, которые уже есть на сервере (участок открыт, если есть все его слоты)."""
        by_index = {slot["slot_index"]: slot for slot in self._state().get("worker_slots", [])}
        wanted = plot_slot_ranges(self.building)[index]
        slots = [by_index[i] for i in wanted if i in by_index]
        return slots if len(slots) == len(wanted) else None

    def _pen_geometry(self, area):
        """Загон: площадь пропорциональна числу мест, на 10 уровне — почти всё поле; домики рядом под ним."""
        places = building_level_info(self.level(), self.building)["max_workers"]
        scale = 0.92 * math.sqrt(places / self.groups[0]["places"])
        field = pygame.Rect(area.left, area.top, area.width, area.height - self.HOUSE_SIZE - 16)
        pen = pygame.Rect(0, 0, int(field.width * scale), int(field.height * scale))
        pen.center = field.center
        points = [pen.topleft, pen.topright, pen.bottomright, pen.bottomleft]
        return [self._polygon_plot(points, pen.center, pen.bottom + 8)]

    def _digs_geometry(self, area):
        """Копанки: неровные ямы, площадь пропорциональна числу мест; домики горняков под ними."""
        plots = []
        for index, (fx, fy) in enumerate(DIG_LAYOUT):
            places = self.groups[index]["places"]
            rx = 62 * math.sqrt(places)
            ry = rx * 0.6
            cx, cy = area.left + fx * area.width, area.top + fy * area.height
            rng = random.Random(index * 13 + 1)
            points = []
            for step in range(12):
                angle = 2 * math.pi * step / 12
                scale = rng.uniform(0.82, 1.0)
                points.append((cx + math.cos(angle) * rx * scale, cy + math.sin(angle) * ry * scale))
            plots.append(self._polygon_plot(points, (cx, cy), int(cy + ry) + 4))
        return plots

    def plot_at(self, position):
        for index, plot in enumerate(self.plot_geometry()):
            if plot["rect"].collidepoint(position) and point_in_polygon(position, plot["points"]):
                return index
        return None

    def plot_slots(self, index):
        """Открытые слоты участка (есть на сервере) или None, если участок ещё закрыт."""
        by_index = {slot["slot_index"]: slot for slot in self._state().get("worker_slots", [])}
        slots = [by_index[i] for i in self.groups[index]["slots"] if i in by_index]
        return slots or None

    def click_plot(self, index):
        slots = self.plot_slots(index)
        if slots is None:
            self.message = f"{self.plot_name(index)} откроется на {self.groups[index]['level']} уровне"
            return
        self.selected_plot = index
        free_slot = next((slot for slot in slots if not slot["occupied"]), None)
        if free_slot is None:
            self.message = "Нет свободного места. Снимите горожанина правой кнопкой мыши."
            return
        self._queue_worker_action("hire", free_slot["slot_index"])

    def remove_plot_worker(self, index):
        slots = self.plot_slots(index)
        if slots is None:
            return
        self.selected_plot = index
        npc_slot = next((slot for slot in reversed(slots)
                         if slot["occupied"] and not slot.get("is_player", False)), None)
        if npc_slot is not None:
            self._queue_worker_action("fire", npc_slot["slot_index"])
            return
        self.message = "На этом участке нет рабочего"

    def _queue_worker_action(self, action, slot_index):
        self.pending_worker_action = (action, int(slot_index))

    def _confirm_worker_action(self):
        action, slot_index = self.pending_worker_action
        self.pending_worker_action = None
        if action == "hire":
            self.hire_worker(slot_index)
        elif action == "fire":
            self.fire_worker(slot_index)
        else:
            storage = self._state().get("storage", {})
            if self._state().get("player_work") is None and self.storage_total() >= storage.get("limit", 0):
                self.message = "Склад переполнен, нельзя начать добычу."
                return
            self._request("workers/player/toggle", {"slot_index": slot_index})

    def _work_selected_plot(self):
        if self.selected_plot is None:
            self.message = "Сначала выберите поле добычи."
            return
        slots = self.plot_slots(self.selected_plot)
        if not slots:
            return
        character_id = self.scene.session.character["id"]
        player_worker_id = f"player:{character_id}"
        own_slot = next((slot for slot in slots if slot.get("worker_id") == player_worker_id), None)
        storage = self._state().get("storage", {})
        if own_slot is None and self.storage_total() >= storage.get("limit", 0):
            self.message = "Склад переполнен, нельзя начать добычу."
            return
        target_slot = own_slot or next(
            (slot for slot in slots if slot["occupied"] and not slot.get("is_player", False)), None
        ) or next((slot for slot in slots if not slot["occupied"]), None)
        if target_slot is None:
            self.message = "На участке работают другие игроки."
            return
        self._queue_worker_action("player", target_slot["slot_index"])

    # ---------- картинки ----------

    def _texture(self, resource, stage):
        key = (resource, stage)
        if key not in self._textures:
            path = ASSETS_DIR / self.view["asset_dir"] / f"field_{resource}_stage_{stage + 1}.png"
            try:
                self._textures[key] = pygame.image.load(str(path)).convert()
            except (pygame.error, OSError):
                fallback = pygame.Surface((64, 64))
                fallback.fill((90, 70, 40))
                self._textures[key] = fallback
        return self._textures[key]

    def _house_image(self):
        if self._house is None:
            path = ASSETS_DIR / self.view["asset_dir"] / "house.png"
            try:
                image = pygame.image.load(str(path)).convert_alpha()
            except (pygame.error, OSError):
                image = pygame.Surface((32, 32), pygame.SRCALPHA)
                pygame.draw.rect(image, (150, 105, 65), (6, 12, 20, 18))
            self._house = pygame.transform.smoothscale(image, (self.HOUSE_SIZE, self.HOUSE_SIZE))
        return self._house

    def _plot_surface(self, index, plot, resource, stage, dimmed):
        """Текстура стадии, обрезанная по контуру участка (кэшируется)."""
        key = (index, resource, stage, dimmed)
        surface = self._surfaces.get(key)
        if surface is not None:
            return surface
        rect = plot["rect"]
        surface = pygame.Surface(rect.size, pygame.SRCALPHA)
        texture = self._texture(resource, stage)
        for tx in range(0, rect.width, texture.get_width()):
            for ty in range(0, rect.height, texture.get_height()):
                surface.blit(texture, (tx, ty))
        if dimmed:
            surface.fill((120, 120, 120, 255), special_flags=pygame.BLEND_RGBA_MULT)
        mask = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.polygon(mask, (255, 255, 255, 255), [(x - rect.left, y - rect.top) for x, y in plot["points"]])
        surface.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        self._surfaces[key] = surface
        return surface

    # ---------- события ----------

    def handle_event(self, event):
        """Окно поглощает все события, пока открыто."""
        if self.pending_worker_action is not None:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.pending_worker_action = None
                return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.confirm_yes_button.collidepoint(event.pos):
                    self._confirm_worker_action()
                    return
                if self.confirm_no_button.collidepoint(event.pos) or not self.confirm_dialog_rect.collidepoint(event.pos):
                    self.pending_worker_action = None
                    return
            return
        if self.contribution_dialog.is_open:
            result = self.contribution_dialog.handle_event(event)
            if result is not None:
                self.deposit_material(*result)
            return
        if (event.type == pygame.MOUSEWHEEL and self.tab == "production"
                and self.worker_stats_rect().collidepoint(pygame.mouse.get_pos())):
            occupied = sum(1 for slot in self._state().get("worker_slots", []) if slot["occupied"])
            visible = max(1, (self.worker_stats_rect().height - 58) // self.WORKER_ROW_HEIGHT)
            self.worker_stats_scroll = max(
                0, min(max(0, occupied - visible), self.worker_stats_scroll - event.y)
            )
            return
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                if self.player_is_working():
                    self.message = "Чтобы покинуть место, завершите работу."
                else:
                    self.is_open = False
            return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button not in (1, 3):
            return
        pos = event.pos
        if event.button == 1 and self.close_button.collidepoint(pos):
            if self.player_is_working():
                self.message = "Чтобы покинуть место, завершите работу."
            else:
                self.is_open = False
        elif event.button == 1 and self.production_tab.collidepoint(pos):
            self.tab = "production"
        elif event.button == 1 and self.storage_tab.collidepoint(pos):
            self.tab = "storage"
        elif event.button == 1 and self.upgrade_tab.collidepoint(pos):
            self.tab = "upgrade"
            self.load()
        elif event.button == 1 and self.work_button.collidepoint(pos) and self.tab == "production":
            self._work_selected_plot()
        elif self.tab == "production":
            index = self.plot_at(pos)
            if index is not None:
                if event.button == 1:
                    self.click_plot(index)
                else:
                    self.remove_plot_worker(index)
        elif event.button == 1 and self.tab == "upgrade":
            for item_id, button in self.deposit_buttons.items():
                if button.collidepoint(pos):
                    material = next((item for item in self._state()["upgrade"]["materials"]
                                     if item["item_id"] == item_id), None)
                    if material:
                        self.contribution_dialog.open(
                            item_id,
                            material["name"],
                            material["in_warehouse"],
                            material["required"] - material["deposited"],
                        )
                    return
            if self.upgrade_button.collidepoint(pos):
                self.start_upgrade()
        elif event.button == 1 and self.tab == "storage":
            for resource, button in self.claim_buttons.items():
                if button.collidepoint(pos):
                    quantity = self._state().get("player_harvest_claims", {}).get(resource, 0)
                    self._request("player-harvest/claim", {"resource": resource, "quantity": quantity})
                    return

    # ---------- отрисовка ----------

    def _draw_forest_backdrop(self, screen):
        """Подложка леса: тёмная зелень вокруг секторов, чтобы лес читался единым массивом."""
        plots = self.plot_geometry()
        for plot in plots:
            pygame.draw.polygon(screen, (22, 40, 22), plot["points"])
            pygame.draw.polygon(screen, (16, 30, 16), plot["points"], 6)

    def _draw_plots(self, screen, m_pos):
        if self.view["shape"] == "rift":
            self._draw_rift(screen, m_pos)
            return
        if self.view["shape"] == "pen":
            self._draw_pen(screen, m_pos)
            return
        if self.view["shape"] == "digs":
            self._draw_digs(screen, m_pos)
            return
        scene = self.scene
        state = self._state()
        stage = self.stage()
        hovered = self.plot_at(m_pos)
        house = self._house_image()
        tooltip = None
        if self.view["shape"] == "pie":
            self._draw_forest_backdrop(screen)
        for index, plot in enumerate(self.plot_geometry()):
            group = self.groups[index]
            unlock_level, places, resource = group["level"], group["places"], group["resource"]
            slots = self.plot_slots(index)
            rect = plot["rect"]
            if slots is None:
                pygame.draw.polygon(screen, (42, 42, 40), plot["points"])
                pygame.draw.polygon(screen, (75, 75, 68), plot["points"], 2)
                lock = scene.small_font.render(f"{RESOURCES[resource]['label']} · ур. {unlock_level}", True, (130, 130, 120))
                screen.blit(lock, lock.get_rect(center=plot["center"]))
                if index == hovered:
                    tooltip = f"{self.plot_name(index)}, мест: {places}. Откроется на {unlock_level} уровне"
                continue
            workers = sum(1 for slot in slots if slot["occupied"])
            player_worker_id = f"player:{self.scene.session.character['id']}"
            player_working = any(slot.get("worker_id") == player_worker_id for slot in slots)
            npc_available = any(slot["occupied"] and not slot.get("is_player", False) for slot in slots)
            surface = self._plot_surface(index, plot, resource, stage if workers else 0, dimmed=not workers)
            screen.blit(surface, rect.topleft)
            border = (235, 200, 95) if workers else (130, 110, 75)
            if index == hovered:
                border = (255, 240, 170)
            pygame.draw.polygon(screen, border, plot["points"], 2)
            # Домик на каждого работающего горожанина
            start_x = plot["center"][0] - workers * (self.HOUSE_SIZE + 4) // 2
            for number in range(workers):
                screen.blit(house, (start_x + number * (self.HOUSE_SIZE + 4), plot["house_y"]))
            if index == hovered:
                if player_working:
                    action = "остановить вашу добычу"
                elif npc_available:
                    action = "заменить горожанина собой"
                else:
                    action = "встать на добычу"
                tooltip = f"{self.plot_name(index)}: работников {workers} / {places}. Клик — {action}"
        self._draw_tooltip(screen, tooltip, m_pos)

    def _draw_tooltip(self, screen, tooltip, m_pos):
        if tooltip:
            surf = self.scene.small_font.render(tooltip, True, (245, 235, 200))
            box = surf.get_rect(topleft=(m_pos[0] + 16, m_pos[1] + 16)).inflate(16, 10)
            box.clamp_ip(self.rect)
            pygame.draw.rect(screen, (20, 22, 16), box, border_radius=6)
            pygame.draw.rect(screen, (200, 170, 80), box, 1, border_radius=6)
            screen.blit(surf, surf.get_rect(center=box.center))

    def _rift_backdrop(self):
        """Большая гора, расколотая по диагонали ущельем-проходом (рисуется один раз)."""
        area = self.plots_area()
        cached = self._surfaces.get("rift_backdrop")
        if cached is not None:
            return cached
        surface = pygame.Surface(area.size, pygame.SRCALPHA)
        rng = random.Random("rift")
        w, h = area.size
        ridge = [(0, h)]
        for step in range(13):
            x = w * step / 12
            ridge.append((x, h * (0.05 + 0.18 * abs(math.sin(step * 1.7))) + rng.uniform(0, 30)))
        ridge.append((w, h))
        pygame.draw.polygon(surface, (74, 68, 64), ridge)
        for _ in range(60):
            x, y = rng.uniform(0, w), rng.uniform(h * 0.25, h)
            size = rng.uniform(30, 90)
            shade = rng.randrange(-14, 14)
            color = (78 + shade, 72 + shade, 68 + shade)
            pygame.draw.polygon(surface, color, [(x - size, y), (x - size * 0.2, y - size * 0.7), (x + size, y)])
        start, end, along, normal = self._rift_axis(pygame.Rect(0, 0, w, h))
        # Ущелье: шире у входа, уже в глубине; рваные края
        left_edge, right_edge = [], []
        for step in range(25):
            t = step / 24
            half = 95 - 55 * t + rng.uniform(-10, 10)
            px = start[0] + (end[0] - start[0]) * t
            py = start[1] + (end[1] - start[1]) * t
            left_edge.append((px - normal[0] * half, py - normal[1] * half))
            right_edge.append((px + normal[0] * (half + rng.uniform(-8, 8)), py + normal[1] * (half + rng.uniform(-8, 8))))
        canyon = left_edge + list(reversed(right_edge))
        pygame.draw.polygon(surface, (34, 28, 26), [(x + normal[0] * 18, y + normal[1] * 18) for x, y in canyon])
        pygame.draw.polygon(surface, (112, 92, 68), canyon)
        pygame.draw.lines(surface, (44, 38, 34), False, left_edge, 4)
        pygame.draw.lines(surface, (44, 38, 34), False, right_edge, 4)
        for _ in range(40):
            t = rng.uniform(0.02, 0.98)
            offset = rng.uniform(-40, 40) * (1 - t * 0.6)
            px = start[0] + (end[0] - start[0]) * t + normal[0] * offset
            py = start[1] + (end[1] - start[1]) * t + normal[1] * offset
            pygame.draw.circle(surface, (90, 76, 58), (int(px), int(py)), rng.randrange(3, 8))
        self._surfaces["rift_backdrop"] = surface
        return surface

    def _draw_tent(self, screen, position, text):
        x, y = position
        pygame.draw.polygon(screen, (196, 168, 116), [(x - 24, y + 14), (x, y - 20), (x + 24, y + 14)])
        pygame.draw.polygon(screen, (110, 84, 52), [(x - 24, y + 14), (x, y - 20), (x + 24, y + 14)], 2)
        pygame.draw.polygon(screen, (60, 44, 30), [(x - 7, y + 14), (x, y - 2), (x + 7, y + 14)])
        label = self.scene.small_font.render(text, True, (255, 240, 190))
        box = label.get_rect(midtop=(x, y + 17)).inflate(10, 4)
        pygame.draw.rect(screen, (24, 20, 16), box, border_radius=5)
        pygame.draw.rect(screen, (180, 150, 90), box, 1, border_radius=5)
        screen.blit(label, label.get_rect(center=box.center))

    def _draw_cart(self, screen, center, width, stage):
        """Вагонетка по стадии цикла: 0 пустая, 1 наполовину, 2 полная, 3 полная с горкой."""
        cx, cy = center
        height = int(width * 0.5)
        body = [(cx - width // 2, cy - height // 2), (cx + width // 2, cy - height // 2),
                (cx + width // 2 - 6, cy + height // 2), (cx - width // 2 + 6, cy + height // 2)]
        pygame.draw.polygon(screen, (132, 98, 64), body)
        top = cy - height // 2
        coal = (12, 12, 14)
        if stage >= 1:
            level_y = cy if stage == 1 else top + 3
            fill = [(cx - width // 2 + 3, level_y), (cx + width // 2 - 3, level_y),
                    (cx + width // 2 - 7, cy + height // 2 - 2), (cx - width // 2 + 7, cy + height // 2 - 2)]
            pygame.draw.polygon(screen, coal, fill)
            for offset in range(-width // 2 + 8, width // 2 - 6, 7):
                pygame.draw.circle(screen, (90, 90, 100), (cx + offset, level_y + 2), 1)
        if stage == 3:
            heap = [(cx - width // 2 + 2, top + 2), (cx, top - height // 2 - 6), (cx + width // 2 - 2, top + 2)]
            pygame.draw.polygon(screen, coal, heap)
            pygame.draw.lines(screen, (90, 90, 100), False, heap, 1)
        pygame.draw.polygon(screen, (84, 58, 34), body, 3)
        pygame.draw.line(screen, (170, 170, 176), (cx - width // 2, top), (cx + width // 2, top), 2)
        for wheel_x in (cx - width // 3, cx + width // 3):
            pygame.draw.circle(screen, (40, 36, 34), (wheel_x, cy + height // 2 + 4), max(4, width // 9))
            pygame.draw.circle(screen, (110, 100, 90), (wheel_x, cy + height // 2 + 4), max(4, width // 9), 2)

    def _draw_digs(self, screen, m_pos):
        """Копанки Чёрной копи: размер по числу мест, в каждой вагонетка по стадии цикла, домик на каждого горняка."""
        scene = self.scene
        area = self.plots_area()
        pygame.draw.rect(screen, (60, 56, 52), area, border_radius=8)
        state = self._state()
        stage = self.stage()
        hovered = self.plot_at(m_pos)
        house = self._house_image()
        tooltip = None
        for index, plot in enumerate(self.plot_geometry()):
            group = self.groups[index]
            places = group["places"]
            slots = self.plot_slots(index)
            if slots is None:
                pygame.draw.polygon(screen, (44, 42, 40), plot["points"])
                pygame.draw.polygon(screen, (78, 74, 68), plot["points"], 2)
                lock = scene.small_font.render(f"Копанка · ур. {group['level']}", True, (130, 126, 120))
                screen.blit(lock, lock.get_rect(center=plot["center"]))
                if index == hovered:
                    tooltip = f"{self.plot_name(index)}, мест: {places}. Откроется на {group['level']} уровне"
                continue
            workers = sum(1 for slot in slots if slot["occupied"])
            pygame.draw.polygon(screen, (24, 23, 25), plot["points"])
            rng = random.Random(index)
            rect = plot["rect"]
            for _ in range(rect.width * rect.height // 500):
                point = (rng.randrange(rect.left, rect.right), rng.randrange(rect.top, rect.bottom))
                if point_in_polygon(point, plot["points"]):
                    pygame.draw.circle(screen, (44, 44, 48), point, rng.randrange(2, 5))
            border = (255, 240, 170) if index == hovered else (200, 170, 90) if workers else (110, 100, 86)
            pygame.draw.polygon(screen, border, plot["points"], 3)
            self._draw_cart(screen, plot["center"], 36 + 10 * places, stage if workers else 0)
            start_x = plot["center"][0] - workers * (self.HOUSE_SIZE + 4) // 2
            for number in range(workers):
                screen.blit(house, (start_x + number * (self.HOUSE_SIZE + 4), plot["house_y"]))
            if index == hovered:
                action = "снять" if workers == places else "отправить"
                tooltip = f"{self.plot_name(index)}: горняков {workers} / {places}. Клик — {action} горожанина"
        self._draw_tooltip(screen, tooltip, m_pos)

    def _draw_pen(self, screen, m_pos):
        scene = self.scene
        area = self.plots_area()
        pygame.draw.rect(screen, (52, 78, 40), area, border_radius=8)
        plot = self.plot_geometry()[0]
        pen = plot["rect"]
        slots = self.plot_slots(0) or []
        workers = sum(1 for slot in slots if slot["occupied"])
        hovered = self.plot_at(m_pos) == 0
        pygame.draw.rect(screen, (112, 112, 58), pen)
        rng = random.Random(7)
        for _ in range(pen.width * pen.height // 900):
            x, y = rng.randrange(pen.left, pen.right), rng.randrange(pen.top, pen.bottom)
            pygame.draw.circle(screen, (128, 104, 64), (x, y), rng.randrange(2, 6))
        # Скот: по два животных на каждого работающего горожанина
        for number in range(workers * 2):
            x = rng.randrange(pen.left + 30, max(pen.left + 31, pen.right - 40))
            y = rng.randrange(pen.top + 24, max(pen.top + 25, pen.bottom - 20))
            spotted = number % 2 == 0
            body = (240, 238, 230) if spotted else (130, 88, 58)
            pygame.draw.ellipse(screen, body, (x - 18, y - 10, 36, 20))
            pygame.draw.circle(screen, body, (x + 19, y - 5), 8)
            for leg in (-12, -4, 6, 12):
                pygame.draw.line(screen, (60, 46, 36), (x + leg, y + 8), (x + leg, y + 15), 3)
            if spotted:
                pygame.draw.circle(screen, (30, 28, 26), (x - 5, y - 2), 6)
        fence = (255, 240, 170) if hovered else (150, 108, 62)
        for offset in (6, 16):
            pygame.draw.rect(screen, fence, pen.inflate(-offset, -offset), 3)
        for x in range(pen.left, pen.right + 1, 34):
            pygame.draw.rect(screen, (98, 68, 38), (x - 3, pen.top - 4, 7, 14))
            pygame.draw.rect(screen, (98, 68, 38), (x - 3, pen.bottom - 10, 7, 14))
        for y in range(pen.top, pen.bottom + 1, 34):
            pygame.draw.rect(screen, (98, 68, 38), (pen.left - 4, y - 3, 14, 7))
            pygame.draw.rect(screen, (98, 68, 38), (pen.right - 10, y - 3, 14, 7))
        # Домик на каждое место: занятые светятся, свободные затенены
        house = self._house_image()
        dim = house.copy()
        dim.fill((90, 90, 90, 255), special_flags=pygame.BLEND_RGBA_MULT)
        step = self.HOUSE_SIZE + 6
        start_x = pen.centerx - len(slots) * step // 2
        for number, slot in enumerate(slots):
            screen.blit(house if slot["occupied"] else dim, (start_x + number * step, plot["house_y"]))
        tooltip = None
        if hovered:
            action = "снять" if workers == len(slots) else "отправить"
            more = f" (до {self.groups[0]['places']} с улучшениями)" if len(slots) < self.groups[0]["places"] else ""
            tooltip = f"Загон: горожан {workers} / {len(slots)}{more}. Клик — {action} горожанина"
        caption = scene.small_font.render(f"Загон · горожан {workers}/{len(slots)}", True, (250, 235, 190))
        screen.blit(caption, caption.get_rect(midbottom=(pen.centerx, pen.top - 6)))
        self._draw_tooltip(screen, tooltip, m_pos)

    def _draw_rift(self, screen, m_pos):
        scene = self.scene
        area = self.plots_area()
        screen.blit(self._rift_backdrop(), area.topleft)
        hovered = self.plot_at(m_pos)
        tooltip = None
        for index, plot in enumerate(self.plot_geometry()):
            group = self.groups[index]
            name = self.plot_name(index)
            slots = self.plot_slots(index)
            cx, cy = plot["center"]
            ore = ORE_COLORS[group["resource"]]
            if slots is None:
                pygame.draw.polygon(screen, (52, 50, 48), plot["points"])
                pygame.draw.polygon(screen, (84, 80, 74), plot["points"], 2)
                lock = scene.small_font.render(f"{name} · ур. {group['level']}", True, (140, 136, 128))
                screen.blit(lock, lock.get_rect(center=(cx, cy)))
                if index == hovered:
                    tooltip = f"{name}, мест до {group['places']}. Откроется на {group['level']} уровне"
                continue
            workers = sum(1 for slot in slots if slot["occupied"])
            pygame.draw.polygon(screen, (98, 90, 82), plot["points"])
            border = (255, 240, 170) if index == hovered else (235, 200, 95) if workers else (140, 124, 100)
            pygame.draw.polygon(screen, border, plot["points"], 2)
            # Вход в шахту: тёмная арка в деревянной крепи, вокруг вкрапления руды
            arch = pygame.Rect(cx - 34, cy - 40, 68, 70)
            pygame.draw.ellipse(screen, (18, 14, 12), arch)
            pygame.draw.rect(screen, (18, 14, 12), (arch.left, arch.centery, arch.width, arch.height // 2))
            pygame.draw.line(screen, (120, 84, 46), (arch.left, arch.centery - 6), (arch.left, arch.bottom), 6)
            pygame.draw.line(screen, (120, 84, 46), (arch.right, arch.centery - 6), (arch.right, arch.bottom), 6)
            pygame.draw.line(screen, (140, 98, 54), (arch.left - 6, arch.centery - 8), (arch.right + 6, arch.centery - 8), 7)
            rng = random.Random(index)
            for _ in range(14):
                angle = rng.uniform(0, 2 * math.pi)
                distance = rng.uniform(55, 110)
                pygame.draw.circle(screen, ore, (int(cx + math.cos(angle) * distance), int(cy + math.sin(angle) * distance * 0.65)), rng.randrange(3, 6))
            if workers:
                pygame.draw.circle(screen, (255, 190, 90), (cx, cy + 12), 5)
            self._draw_tent(screen, plot["tent"], f"{workers}/{len(slots)}")
            caption = scene.small_font.render(name, True, (250, 235, 190))
            screen.blit(caption, caption.get_rect(midtop=(cx, cy + 40)))
            if index == hovered:
                action = "снять" if workers == len(slots) else "отправить"
                more = f" (до {group['places']} с улучшениями)" if len(slots) < group["places"] else ""
                tooltip = f"{name}: горожан {workers} / {len(slots)}{more}. Клик — {action} горожанина"
        self._draw_tooltip(screen, tooltip, m_pos)

    def draw(self, screen):
        scene = self.scene
        self._refresh_if_due()

        overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 18, 215))
        screen.blit(overlay, (0, 0))

        rect = self.rect
        modal = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(modal, (24, 26, 18, 250), (0, 0, rect.width, rect.height), border_radius=12)
        pygame.draw.rect(modal, (220, 185, 70), (0, 0, rect.width, rect.height), width=2, border_radius=12)
        screen.blit(modal, rect.topleft)

        level = self.level()
        m_pos = pygame.mouse.get_pos()

        status_text, status_col = self.status()
        title = scene.large_font.render(self.name, True, (255, 225, 130))
        building_icon = draw_building_icon(screen, self.building, (rect.left + 14, rect.top + 5), 40)
        title_x = rect.left + 62 if building_icon else rect.left + 24
        screen.blit(title, (title_x, rect.top + 16))
        screen.blit(scene.small_font.render(f"Уровень {level}", True, (215, 205, 170)),
                    (rect.left + 24, rect.top + 52))
        screen.blit(scene.small_font.render(status_text, True, status_col),
                    (rect.right - 250, rect.top + 25))

        for tab, button, label in (
            ("production", self.production_tab, "ПРОИЗВОДСТВО"),
            ("storage", self.storage_tab, "СКЛАД"),
            ("upgrade", self.upgrade_tab, "УЛУЧШЕНИЕ"),
        ):
            draw_button(screen, button, label, scene.small_font, color=(75, 120, 155) if self.tab == tab else (45, 50, 58))

        max_workers = self._state().get("max_workers", building_level_info(level, self.building)["max_workers"])
        screen.blit(scene.small_font.render(f"Горожане: {self.workers()} / {max_workers}", True, (235, 220, 170)), (rect.left + 24, rect.top + 112))
        screen.blit(scene.small_font.render(f"{self.view['harvest_label']}: {self.harvest_countdown()}", True, (190, 220, 235)), (rect.left + 24, rect.top + 132))
        if self.message:
            screen.blit(scene.small_font.render(self.message, True, (240, 150, 120)), (rect.left + 440, rect.top + 112))
        if self.tab == "production":
            selected_slots = self.plot_slots(self.selected_plot) if self.selected_plot is not None else None
            has_player_here = bool(selected_slots and any(
                slot.get("worker_id") == f"player:{self.scene.session.character['id']}"
                for slot in selected_slots
            ))
            storage = self._state().get("storage", {})
            storage_full = self.storage_total() >= storage.get("limit", 0)
            can_work = self.selected_plot is not None and selected_slots is not None and (
                has_player_here or not storage_full
            )
            label = "ЗАВЕРШИТЬ РАБОТУ" if has_player_here else "РАБОТАТЬ"
            draw_button(screen, self.work_button, label, scene.grid_font,
                        color=(75, 125, 70) if can_work else (55, 57, 53),
                        text_color=(240, 238, 220) if can_work else (140, 142, 132))

        is_working = self.player_is_working()
        close_hover = self.close_button.collidepoint(m_pos)
        close_color = (55, 57, 53) if is_working else (160, 45, 45) if close_hover else (45, 30, 35)
        close_text_color = (145, 147, 139) if is_working else (255, 255, 255)
        draw_button(screen, self.close_button, "ПОКИНУТЬ", scene.small_font,
                    color=close_color, text_color=close_text_color)
        if is_working and close_hover:
            self._draw_tooltip(screen, "Чтобы покинуть место, завершите работу.", m_pos)

        curr_y = rect.top + 160
        pygame.draw.line(screen, (100, 90, 55), (rect.left + 22, curr_y), (rect.right - 22, curr_y), 1)
        curr_y += 14

        if self.tab == "storage":
            self._draw_storage_tab(screen, curr_y)
        elif self.tab == "upgrade":
            self._draw_upgrade_tab(screen, curr_y, m_pos)
        else:
            self._draw_worker_stats(screen)
            self._draw_plots(screen, m_pos)
            self._draw_worker_stats(screen)
        self.contribution_dialog.draw(screen)
        self._draw_worker_confirmation(screen)

    def _draw_worker_confirmation(self, screen):
        if self.pending_worker_action is None:
            return
        shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        screen.blit(shade, (0, 0))
        rect = self.confirm_dialog_rect
        pygame.draw.rect(screen, (28, 31, 28), rect, border_radius=6)
        pygame.draw.rect(screen, (185, 151, 86), rect, 2, border_radius=6)
        action, _slot_index = self.pending_worker_action
        prompt = {
            "hire": "Поставить горожанина на работу?",
            "fire": "Снять горожанина с работы?",
            "player": ("Остановить вашу добычу?" if self._state().get("player_work")
                       else "Встать на добычу вместо горожанина?"),
        }[action]
        title = self.scene.font.render(prompt, True, (235, 218, 183))
        screen.blit(title, title.get_rect(center=(rect.centerx, rect.top + 74)))
        draw_button(screen, self.confirm_yes_button, "ПОДТВЕРДИТЬ", self.scene.small_font,
                    color=(70, 119, 65), text_color=(245, 241, 221))
        draw_button(screen, self.confirm_no_button, "ОТМЕНА", self.scene.small_font,
                    color=(63, 59, 51), text_color=(220, 214, 194))

    def _draw_player_work_status(self, screen):
        work = self._state().get("player_work")
        if not work:
            return
        plot_index = next((index for index, group in enumerate(self.groups)
                           if work["slot_index"] in group["slots"]), None)
        if plot_index is None:
            return
        plot = self.plot_geometry()[plot_index]
        rect = pygame.Rect(plot["rect"].left - 290, plot["rect"].top + 8, 280, 94)
        rect.clamp_ip(self.rect)
        pygame.draw.rect(screen, (18, 25, 27), rect, border_radius=5)
        pygame.draw.rect(screen, (109, 166, 112), rect, 1, border_radius=5)
        name = self.scene.session.character.get("name", "Игрок")
        title = self.scene.small_font.render(f"Добывает: {name}", True, (193, 230, 183))
        screen.blit(title, (rect.left + 10, rect.top + 8))
        seconds_left = max(0, work["seconds_to_next"] - self._since_received())
        timer = self.scene.grid_font.render(
            f"До начисления: {format_clock(seconds_left)}", True, (226, 213, 176)
        )
        screen.blit(timer, (rect.left + 10, rect.top + 34))
        totals = work.get("total_produced", {})
        screen.blit(self.scene.grid_font.render("Добыто:", True, (198, 211, 195)),
                    (rect.left + 10, rect.top + 58))
        icon_x = rect.left + 70
        for resource in work.get("resources", []):
            draw_item_icon(screen, resource, (icon_x, rect.top + 57), 18)
            label = self.scene.grid_font.render(
                f"{RESOURCES[resource]['label']}: {totals.get(resource, 0)}",
                True, (198, 211, 195),
            )
            screen.blit(label, (icon_x + 20, rect.top + 59))
            icon_x += 24 + label.get_width() + 8

    def _draw_worker_stats(self, screen):
        rect = self.worker_stats_rect()
        state = self._state()
        slots = [slot for slot in state.get("worker_slots", []) if slot["occupied"]]
        scene = self.scene
        pygame.draw.rect(screen, (21, 27, 29), rect, border_radius=6)
        pygame.draw.rect(screen, (94, 119, 91), rect, 1, border_radius=6)
        screen.blit(scene.font.render("Работники объекта", True, (220, 211, 178)),
                    (rect.left + 12, rect.top + 12))
        header_bottom = rect.top + 42
        pygame.draw.line(screen, (67, 83, 68), (rect.left + 10, header_bottom),
                         (rect.right - 10, header_bottom), 1)
        visible_rows = max(1, (rect.height - 52) // self.WORKER_ROW_HEIGHT)
        max_scroll = max(0, len(slots) - visible_rows)
        self.worker_stats_scroll = max(0, min(max_scroll, self.worker_stats_scroll))
        if not slots:
            empty = scene.small_font.render("Нет занятых мест", True, (145, 150, 142))
            screen.blit(empty, (rect.left + 12, header_bottom + 18))
            return

        clip_rect = pygame.Rect(rect.left + 6, header_bottom + 2, rect.width - 12, rect.bottom - header_bottom - 6)
        previous_clip = screen.get_clip()
        screen.set_clip(clip_rect)
        elapsed = self._since_received()
        own_id = self.scene.session.character["id"]
        lifetime = state.get("player_harvest_totals", {})
        for visible_index, slot in enumerate(slots[self.worker_stats_scroll:self.worker_stats_scroll + visible_rows]):
            row_y = header_bottom + 4 + visible_index * self.WORKER_ROW_HEIGHT
            row = pygame.Rect(rect.left + 7, row_y, rect.width - 14, self.WORKER_ROW_HEIGHT - 2)
            pygame.draw.rect(screen, (35, 42, 39) if visible_index % 2 == 0 else (30, 36, 35), row)
            name = slot.get("worker_name") or "Горожанин"
            is_player = slot.get("worker_id") == f"player:{own_id}"
            name_color = (151, 211, 156) if is_player else (213, 207, 187)
            screen.blit(scene.small_font.render(name, True, name_color), (row.left + 7, row.top + 5))

            resource_progress = slot.get("resource_progress_sec", {})
            resource_lines = []
            resources = slot.get("resources", [slot.get("resource")])
            for resource in resources:
                if not resource or resource not in RESOURCES or "timer_sec" not in RESOURCES[resource]:
                    continue
                timer = RESOURCES[resource]["timer_sec"]
                progress = (resource_progress.get(resource, slot.get("progress_sec", 0)) + elapsed) % timer
                remaining = max(0, math.ceil(timer - progress))
                hours, remainder = divmod(remaining, 3600)
                minutes, seconds = divmod(remainder, 60)
                clock = f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"
                resource_lines.append((resource, clock))
            if resource_lines:
                icon_x = row.left + 7
                for resource, clock in resource_lines:
                    draw_item_icon(screen, resource, (icon_x, row.top + 27), 16)
                    text = scene.grid_font.render(
                        f"{RESOURCES[resource]['label']} {clock}", True, (190, 205, 184)
                    )
                    screen.blit(text, (icon_x + 18, row.top + 29))
                    icon_x += 22 + text.get_width() + 8
            else:
                screen.blit(scene.grid_font.render("Цикл: —", True, (190, 205, 184)),
                            (row.left + 7, row.top + 29))

            if is_player:
                screen.blit(scene.grid_font.render("Всего:", True, (154, 181, 149)),
                            (row.left + 7, row.top + 46))
                icon_x = row.left + 55
                for resource in resources:
                    if resource not in RESOURCES:
                        continue
                    draw_item_icon(screen, resource, (icon_x, row.top + 45), 14)
                    label = scene.grid_font.render(
                        f"{RESOURCES[resource]['label']}: {lifetime.get(resource, 0)}",
                        True, (154, 181, 149),
                    )
                    screen.blit(label, (icon_x + 16, row.top + 47))
                    icon_x += 20 + label.get_width() + 7
        screen.set_clip(previous_clip)

    def _draw_storage_tab(self, screen, curr_y):
        scene = self.scene
        rect = self.rect
        storage = self._state().get("storage", {})
        forecast = self._state().get("forecast", {})
        player_claims = self._state().get("player_harvest_claims", {})
        self.claim_buttons = {}
        screen.blit(scene.font.render(f"Склад: {self.storage_total()} / {storage.get('limit', 0)}", True, (255, 225, 130)), (rect.left + 24, curr_y))
        curr_y += 34
        for resource in self.resources:
            claimable = player_claims.get(resource, 0)
            text = (f"{RESOURCES[resource]['label']}: {storage.get(resource, 0)}   "
                    f"(к концу цикла +{forecast.get(resource, 0)})   Ваша добыча: {claimable}")
            draw_item_icon(screen, resource, (rect.left + 12, curr_y + 2), 24)
            screen.blit(scene.font.render(text, True, (215, 215, 205)), (rect.left + 42, curr_y))
            if claimable > 0:
                button = pygame.Rect(rect.left + 1050, curr_y - 2, 190, 28)
                draw_button(screen, button, f"ЗАБРАТЬ {claimable}", scene.small_font,
                            color=(69, 112, 67), text_color=(235, 232, 215))
                self.claim_buttons[resource] = button
            curr_y += 30
        hint = scene.small_font.render("Вместимость общая для всех ресурсов; излишек при выгрузке сгорает", True, (150, 155, 165))
        screen.blit(hint, (rect.left + 24, curr_y + 12))

    def _draw_upgrade_tab(self, screen, curr_y, m_pos):
        scene = self.scene
        rect = self.rect
        upgrade = self._state().get("upgrade")
        self.deposit_buttons = {}
        if upgrade is None:
            screen.blit(scene.font.render("Здание достигло максимального уровня", True, (195, 195, 175)), (rect.left + 24, curr_y))
            return
        title = f"Улучшение до уровня {upgrade['next_level']} — время стройки {format_duration(upgrade['time_seconds'])}"
        screen.blit(scene.font.render(title, True, (255, 225, 130)), (rect.left + 24, curr_y))
        curr_y += 30
        screen.blit(scene.small_font.render(self.production_desc(upgrade["next_level"]), True, (190, 195, 180)), (rect.left + 24, curr_y))
        curr_y += 34
        screen.blit(scene.small_font.render("Материалы списываются с общего склада", True, (220, 210, 170)), (rect.left + 24, curr_y))
        curr_y += 28
        for material in upgrade["materials"]:
            done = material["deposited"] >= material["required"]
            text = f"{material['name']}: {material['deposited']}/{material['required']}   на складе: {material['in_warehouse']}"
            draw_item_icon(screen, material, (rect.left + 12, curr_y + 2), 24)
            screen.blit(scene.small_font.render(text, True, (140, 230, 140) if done else (230, 200, 120)), (rect.left + 42, curr_y + 6))
            if not done and not upgrade["in_progress"]:
                button = pygame.Rect(rect.left + 520, curr_y, 140, 28)
                draw_button(screen, button, "ВНЕСТИ", scene.small_font,
                            color=(80, 140, 85) if material["in_warehouse"] > 0 else (55, 55, 60))
                self.deposit_buttons[material["item_id"]] = button
            curr_y += 36
        curr_y += 12
        if upgrade["in_progress"]:
            left = upgrade["seconds_left"] - self._since_received()
            screen.blit(scene.font.render(f"Идёт стройка: осталось {format_clock(left)}", True, (120, 190, 240)), (rect.left + 24, curr_y))
            return
        self.upgrade_button.topleft = (rect.left + 24, curr_y)
        ready = upgrade["ready"]
        hover = ready and self.upgrade_button.collidepoint(m_pos)
        color = ((110, 180, 110) if hover else (80, 140, 85)) if ready else (55, 55, 60)
        draw_button(screen, self.upgrade_button, "УЛУЧШИТЬ", scene.small_font, color=color, text_color=(255, 255, 255) if ready else (150, 150, 155))
