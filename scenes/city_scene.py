from pathlib import Path
import math
import pygame
from core import settings
from scenes.city.buildings import CityBuildingsMixin
from scenes.city.rendering import CityRenderMixin
from scenes.city.modals import CityModalsMixin
from scenes.city.hud import CityHudMixin


class CityScene(CityBuildingsMixin, CityRenderMixin, CityModalsMixin, CityHudMixin):
    """
    Сцена локации Города Радбург (Город Света).
    Размер сетки: 100х100 тайлов (3200х3200 px).
    Тайл: 32х32 пикселя.

    Реализация разделена на модули scenes/city/ (подключены как миксины):
      - buildings.py: геометрия и хитбоксы зданий (CityBuildingsMixin).
      - rendering.py: отрисовка зданий, стен/ворот, персонажа (CityRenderMixin).
      - modals.py: модальные окна-заглушки зданий (CityModalsMixin).
      - hud.py: HUD и окно активного объекта (CityHudMixin).

    Ключевые объекты:
      1. Кристалл Жизни: в центре площади (квадрат 3х3 тайла = 9 тайлов, X: 49..51, Y: 49..51).
         Точка возрождения персонажа после гибели (вместо таверны).
      2. Главный замок: центр на координатах 75/70, размер 15х15 тайлов (X: 68..82, Y: 63..77), вход с юга.
         Заглушка с модальным меню и кнопкой "Вернуться в город".
      3. Городская Таверна: двухэтажная 10х7 тайлов (верхний угол 55/12, нижний 55/18), вход на 55/15.
      4. Городской Амбар: 12х10 тайлов (X: 5..16, Y: 35..44), вход на 16/40. Хранилище провизии.
      5. Городской Склад: 12х10 тайлов (X: 5..16, Y: 18..27), вход на 16/23. Хранилище материалов.
      6. Городская Кузница: 9х7 тайлов (X: 23..31, Y: 25..31), вход на 23/28. Ковка оружия для игроков и гарнизона.
      7. Городская Мастерская: 9х7 тайлов (X: 23..31, Y: 13..19), вход на 23/16. Изготовление брони для игроков и гарнизона.
      8. Городские Казармы: 9х13 тайлов (X: 80..88, Y: 31..43), вход на 84/43. Содержание гарнизона и солдат.
      9. Инженерная палата: 10х8 тайлов (X: 35..44, Y: 12..19), вход на 44/15. Производство оборонных сооружений и машин (катапульта, таран, требушет).
      10. Городской Университет: 15х11 тайлов (X: 16..30, Y: 84..94), вход на 23/84. Место изучения новых технологий города.
      11. Военная академия: 10х7 тайлов (X: 10..19, Y: 70..76), вход на 19/73. Обучение бойцов, прокачка карт и талантов силовой линии.
      12. Школа стихий: 15х9 тайлов (X: 30..44, Y: 62..70), вход на 44/66. Обучение магии и прокачка магических карт.
      13. 4 ворот города:
         - Главные ворота (Восток): 12 тайлов в ширину (Y: 44..55)
         - Южные ворота: 6 тайлов в ширину (X: 47..52)
         - Северные ворота: 6 тайлов в ширину (X: 47..52)
         - Западные ворота: 6 тайлов в ширину (Y: 47..52)
      Выход из города осуществляется ИСКЛЮЧИТЕЛЬНО пешком через ворота.
    """

    def __init__(self, session, gate="east"):
        self.session = session
        self.finished = False
        self.cancelled = False
        self.navigate = None
        self.exit_gate = gate

        # Размеры сетки: 100х100 тайлов
        self.grid_w = 100
        self.grid_h = 100
        self.tile_size = 32
        self.world_w = self.grid_w * self.tile_size  # 3200 px
        self.world_h = self.grid_h * self.tile_size  # 3200 px

        self.zoom = 1.0

        self.min_world_x = 0
        self.max_world_x = self.world_w
        self.min_world_y = 0
        self.max_world_y = self.world_h

        # Точки появления при входе / возрождении:
        # 1. Главные ворота (Восток, 12 тайлов): X=95, Y=50, лицом на Запад
        # 2. Северные ворота (Север, 6 тайлов): X=50, Y=4, лицом на Юг
        # 3. Южные ворота (Юг, 6 тайлов): X=50, Y=95, лицом на Север
        # 4. Западные ворота (Запад, 6 тайлов): X=4, Y=50, лицом на Восток
        # 5. Кристалл Жизни (Центр площади, 9 тайлов): X=50, Y=53, лицом на Север
        # 6. Дверь таверны (Вход на тайле 55/15): X=55, Y=16, лицом на Север
        spawn_map = {
            "east": (95 * self.tile_size + 16, 50 * self.tile_size, "w"),
            "main": (95 * self.tile_size + 16, 50 * self.tile_size, "w"),
            "north": (50 * self.tile_size, 4 * self.tile_size + 16, "s"),
            "south": (50 * self.tile_size, 95 * self.tile_size + 16, "n"),
            "west": (4 * self.tile_size + 16, 50 * self.tile_size, "e"),
            "crystal": (50 * self.tile_size + 16, 53 * self.tile_size + 16, "n"),
            "death": (50 * self.tile_size + 16, 53 * self.tile_size + 16, "n"),
            "respawn": (50 * self.tile_size + 16, 53 * self.tile_size + 16, "n"),
            "tavern": (54 * self.tile_size + 16, 15 * self.tile_size + 16, "w"),
        }

        sp = spawn_map.get(gate, spawn_map["east"])
        self.player_x = float(sp[0])
        self.player_y = float(sp[1])
        self.player_direction = sp[2]
        self.player_facing_right = (self.player_direction in ("e", "ne", "se"))
        self.player_target = None
        self.player_speed = 220.0
        self.player_state = "idle"
        self.player_anim_timer = 0.0
        self.click_effect = None

        # Камера центрируется на персонаже
        self.camera_x = self.player_x
        self.camera_y = self.player_y
        self.camera_follow_player = True

        # Скролл карты перетаскиванием (drag)
        self.dragging = False
        self.drag_start_mouse = (0, 0)
        self.drag_start_camera = (0.0, 0.0)
        self.drag_moved = False

        # Шрифты
        self.font = pygame.font.SysFont(settings.FONT_NAME, 20)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 16)
        self.grid_font = pygame.font.SysFont(settings.FONT_NAME, 11)
        self.badge_font = pygame.font.SysFont(settings.FONT_NAME, 13, bold=True)
        self.large_font = pygame.font.SysFont(settings.FONT_NAME, 24, bold=True)

        # Переключатель отображения сетки
        self.show_grid = False

        # Всплывающие сообщения
        self.floating_messages = []

        # Загрузка 8-направленных спрайтов
        self.player_directional_frames = {}
        self.player_run_directional_frames = {}
        self._load_player_directional_sprites()

        # Построение крепостных стен по периметру 100х100 тайлов с 4 проемами ворот
        self._build_city_walls()

        # Интерактивные объекты города: Кристалл Жизни и Главный замок
        self._init_city_objects()

        # Модальное окно заглушки Главного Замка
        self.castle_menu_open = False
        self.castle_modal_rect = pygame.Rect(settings.WIDTH // 2 - 340, settings.HEIGHT // 2 - 250, 680, 500)
        self.castle_back_button = pygame.Rect(self.castle_modal_rect.centerx - 140, self.castle_modal_rect.bottom - 62, 280, 44)
        self.castle_close_button = pygame.Rect(self.castle_modal_rect.right - 42, self.castle_modal_rect.top + 14, 28, 28)

        # Модальное окно заглушки Городского Амбара
        self.barn_menu_open = False
        self.barn_modal_rect = pygame.Rect(settings.WIDTH // 2 - 340, settings.HEIGHT // 2 - 250, 680, 500)
        self.barn_back_button = pygame.Rect(self.barn_modal_rect.centerx - 140, self.barn_modal_rect.bottom - 62, 280, 44)
        self.barn_close_button = pygame.Rect(self.barn_modal_rect.right - 42, self.barn_modal_rect.top + 14, 28, 28)

        # Модальное окно заглушки Городского Склада
        self.warehouse_menu_open = False
        self.warehouse_modal_rect = pygame.Rect(settings.WIDTH // 2 - 340, settings.HEIGHT // 2 - 250, 680, 500)
        self.warehouse_back_button = pygame.Rect(self.warehouse_modal_rect.centerx - 140, self.warehouse_modal_rect.bottom - 62, 280, 44)
        self.warehouse_close_button = pygame.Rect(self.warehouse_modal_rect.right - 42, self.warehouse_modal_rect.top + 14, 28, 28)

        # Модальное окно заглушки Городской Кузницы
        self.forge_menu_open = False
        self.forge_modal_rect = pygame.Rect(settings.WIDTH // 2 - 340, settings.HEIGHT // 2 - 250, 680, 500)
        self.forge_back_button = pygame.Rect(self.forge_modal_rect.centerx - 140, self.forge_modal_rect.bottom - 62, 280, 44)
        self.forge_close_button = pygame.Rect(self.forge_modal_rect.right - 42, self.forge_modal_rect.top + 14, 28, 28)

        # Модальное окно заглушки Городской Мастерской
        self.workshop_menu_open = False
        self.workshop_modal_rect = pygame.Rect(settings.WIDTH // 2 - 340, settings.HEIGHT // 2 - 250, 680, 500)
        self.workshop_back_button = pygame.Rect(self.workshop_modal_rect.centerx - 140, self.workshop_modal_rect.bottom - 62, 280, 44)
        self.workshop_close_button = pygame.Rect(self.workshop_modal_rect.right - 42, self.workshop_modal_rect.top + 14, 28, 28)

        # Модальное окно заглушки Городских Казарм
        self.barracks_menu_open = False
        self.barracks_modal_rect = pygame.Rect(settings.WIDTH // 2 - 340, settings.HEIGHT // 2 - 250, 680, 500)
        self.barracks_back_button = pygame.Rect(self.barracks_modal_rect.centerx - 140, self.barracks_modal_rect.bottom - 62, 280, 44)
        self.barracks_close_button = pygame.Rect(self.barracks_modal_rect.right - 42, self.barracks_modal_rect.top + 14, 28, 28)

        # Модальное окно заглушки Инженерной палаты
        self.engineering_menu_open = False
        self.engineering_modal_rect = pygame.Rect(settings.WIDTH // 2 - 340, settings.HEIGHT // 2 - 250, 680, 500)
        self.engineering_back_button = pygame.Rect(self.engineering_modal_rect.centerx - 140, self.engineering_modal_rect.bottom - 62, 280, 44)
        self.engineering_close_button = pygame.Rect(self.engineering_modal_rect.right - 42, self.engineering_modal_rect.top + 14, 28, 28)

        # Модальное окно заглушки Городского Университета
        self.university_menu_open = False
        self.university_modal_rect = pygame.Rect(settings.WIDTH // 2 - 340, settings.HEIGHT // 2 - 250, 680, 500)
        self.university_back_button = pygame.Rect(self.university_modal_rect.centerx - 140, self.university_modal_rect.bottom - 62, 280, 44)
        self.university_close_button = pygame.Rect(self.university_modal_rect.right - 42, self.university_modal_rect.top + 14, 28, 28)

        # Модальное окно заглушки Военной академии
        self.academy_menu_open = False
        self.academy_modal_rect = pygame.Rect(settings.WIDTH // 2 - 340, settings.HEIGHT // 2 - 250, 680, 500)
        self.academy_back_button = pygame.Rect(self.academy_modal_rect.centerx - 140, self.academy_modal_rect.bottom - 62, 280, 44)
        self.academy_close_button = pygame.Rect(self.academy_modal_rect.right - 42, self.academy_modal_rect.top + 14, 28, 28)

        # Модальное окно заглушки Школы стихий
        self.mage_school_menu_open = False
        self.mage_school_modal_rect = pygame.Rect(settings.WIDTH // 2 - 340, settings.HEIGHT // 2 - 250, 680, 500)
        self.mage_school_back_button = pygame.Rect(self.mage_school_modal_rect.centerx - 140, self.mage_school_modal_rect.bottom - 62, 280, 44)
        self.mage_school_close_button = pygame.Rect(self.mage_school_modal_rect.right - 42, self.mage_school_modal_rect.top + 14, 28, 28)

        # Выделенный объект и окно действия
        self.hovered_entity = None
        self.active_entity = None
        self.active_window_rect = pygame.Rect(settings.WIDTH - 390, settings.HEIGHT - 255, 365, 215)
        self.active_close_button = pygame.Rect(self.active_window_rect.right - 36, self.active_window_rect.top + 10, 26, 26)
        self.active_action_button = pygame.Rect(self.active_window_rect.left + 16, self.active_window_rect.bottom - 48, self.active_window_rect.width - 32, 34)
        self.action_notice = None
        self.action_notice_timer = 0.0

        # Сообщение при входе / возрождении
        if gate in ("crystal", "death", "respawn"):
            if hasattr(self.session, "character") and self.session.character:
                self.session.character["hp"] = self.session.character.get("max_hp", 100)
                try:
                    self.session.client.save_character(self.session.character)
                except Exception:
                    pass
            self._add_floating_message("💎 Ваша душа возродилась у Кристалла Жизни!", self.player_x, self.player_y - 36, (100, 240, 255))
        else:
            gate_names = {
                "east": "Главные ворота",
                "main": "Главные ворота",
                "north": "Северные ворота",
                "south": "Южные ворота",
                "west": "Западные ворота",
            }
            g_name = gate_names.get(gate, "Главные ворота")
            self._add_floating_message(f"Вы вошли в Радбург через {g_name}", self.player_x, self.player_y - 36, (255, 220, 100))

    def _load_player_directional_sprites(self):
        """Загружает 8-направленные спрайты персонажа (Idle и Run)."""
        target_h = 56
        directions = ["n", "ne", "e", "se", "s", "sw", "w", "nw"]

        # 1. Idle
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
                        raw_surf = pygame.image.load(str(ff)).convert_alpha()
                        sub = raw_surf.subsurface(crop_rect)
                        scaled = pygame.transform.smoothscale(sub, (target_w, target_h))
                        frames.append(scaled)
                    except Exception:
                        pass
                if frames:
                    self.player_directional_frames[d] = frames

        # 2. Run
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
                        raw_surf = pygame.image.load(str(ff)).convert_alpha()
                        sub = raw_surf.subsurface(crop_rect)
                        scaled = pygame.transform.smoothscale(sub, (target_w, target_h))
                        frames.append(scaled)
                    except Exception:
                        pass
                if frames:
                    self.player_run_directional_frames[d] = frames

    def world_to_screen(self, wx, wy):
        """Преобразование мировых координат в экранные пиксели."""
        sx = int((wx - self.camera_x) * self.zoom + settings.WIDTH / 2)
        sy = int((wy - self.camera_y) * self.zoom + settings.HEIGHT / 2)
        return sx, sy

    def screen_to_world(self, sx, sy):
        """Преобразование экранных пикселей в мировые координаты."""
        wx = (sx - settings.WIDTH / 2) / self.zoom + self.camera_x
        wy = (sy - settings.HEIGHT / 2) / self.zoom + self.camera_y
        return wx, wy

    def _clamp_camera(self):
        """Удержание камеры в пределах 100х100 тайлов с учетом текущего зума."""
        half_screen_w = (settings.WIDTH / 2) / self.zoom
        half_screen_h = (settings.HEIGHT / 2) / self.zoom
        self.camera_x = max(self.min_world_x + half_screen_w, min(self.max_world_x - half_screen_w, self.camera_x))
        self.camera_y = max(self.min_world_y + half_screen_h, min(self.max_world_y - half_screen_h, self.camera_y))

    def _check_collision(self, px, py):
        """Проверяет коллизию ног героя со стенами и границами карты."""
        # Разрешаем выход за пределы карты ТОЛЬКО через проемы ворот:
        # Восточные Главные ворота (Y: 44..55)
        if px >= self.max_world_x - 10:
            if not (44 * self.tile_size <= py <= 56 * self.tile_size):
                return True
        elif px <= self.min_world_x + 10:
            # Западные ворота (Y: 47..52)
            if not (47 * self.tile_size <= py <= 53 * self.tile_size):
                return True

        if py <= self.min_world_y + 6:
            # Северные ворота (X: 47..52)
            if not (47 * self.tile_size <= px <= 53 * self.tile_size):
                return True
        elif py >= self.max_world_y - 6:
            # Южные ворота (X: 47..52)
            if not (47 * self.tile_size <= px <= 53 * self.tile_size):
                return True

        feet_rect = pygame.Rect(int(px - 10), int(py - 6), 20, 10)

        # 1. Внешние крепостные стены города
        for s_rect in self.solid_rects:
            if feet_rect.colliderect(s_rect):
                return True

        # 2. Непроходимые препятствия зданий и объектов (Кристалл Жизни, Главный замок, Таверна)
        for obj in self.objects:
            for s_rect in obj.get("solid_rects", []):
                if feet_rect.colliderect(s_rect):
                    return True

        return False

    def _vector_to_direction(self, dx, dy):
        """Определяет одно из 8 направлений по вектору движения."""
        angle = math.degrees(math.atan2(dy, dx))
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

    def _add_floating_message(self, text, wx, wy, color=(255, 220, 80)):
        """Добавляет всплывающее сообщение в игровом мире."""
        self.floating_messages.append({
            "text": text,
            "world_x": float(wx),
            "world_y": float(wy),
            "timer": 2.2,
            "max_timer": 2.2,
            "color": color,
        })

    def _find_entity_at(self, screen_pos):
        """Находит интерактивную сущность под экранными координатами курсора."""
        # Проверяем персонажа игрока
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
                "desc": f"Ваш главный герой. Статус: {status_str}.",
                "icon": "👤",
            }

        # Проверяем объекты города
        for obj in reversed(self.objects):
            top_left_x = obj["tile_x"] * self.tile_size
            top_left_y = obj["tile_y"] * self.tile_size
            tw = obj["tile_w"] * self.tile_size
            th = obj["tile_h"] * self.tile_size
            sx, sy = self.world_to_screen(top_left_x, top_left_y)
            obj_rect = pygame.Rect(sx, sy, tw, th)
            if obj_rect.collidepoint(screen_pos):
                return obj

        return None

    def _is_within_one_tile(self, entity):
        """Проверяет дистанцию не дальше 1 тайла от объекта или его входа."""
        if not entity:
            return False
        if entity.get("id") == "player":
            return True

        pgx = int(self.player_x // self.tile_size)
        pgy = int(self.player_y // self.tile_size)

        entrance = entity.get("entrance_tile")
        if entrance:
            egx, egy = entrance
            d1 = max(abs(pgx - egx), abs(pgy - (egy + 1)))
            d2 = max(abs(pgx - egx), abs(pgy - egy))
            return min(d1, d2) <= 1

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

    def _trigger_active_action(self):
        """Обрабатывает действие активного объекта."""
        if not self.active_entity:
            return

        eid = self.active_entity.get("id")
        if eid == "player":
            self.camera_x = self.player_x
            self.camera_y = self.player_y
            self.camera_follow_player = True
            self._clamp_camera()
            self._add_floating_message("Камера сфокусирована", self.player_x, self.player_y - 30, (100, 220, 255))
            return

        if eid == "main_castle":
            self.castle_menu_open = True
            return

        if eid == "tavern_building":
            if not self._is_within_one_tile(self.active_entity):
                self._add_floating_message("Подойдите к двери таверны (тайл 55/15)", self.player_x, self.player_y - 34, (255, 120, 90))
                return
            self.navigate = "tavern"
            self.finished = True
            return

        if eid == "barn_building":
            if not self._is_within_one_tile(self.active_entity):
                self._add_floating_message("Подойдите к воротам амбара (тайл 16/40)", self.player_x, self.player_y - 34, (255, 120, 90))
                return
            self.barn_menu_open = True
            return

        if eid == "warehouse_building":
            if not self._is_within_one_tile(self.active_entity):
                self._add_floating_message("Подойдите к воротам склада (тайл 16/23)", self.player_x, self.player_y - 34, (255, 120, 90))
                return
            self.warehouse_menu_open = True
            return

        if eid == "forge_building":
            if not self._is_within_one_tile(self.active_entity):
                self._add_floating_message("Подойдите к дверям кузницы (тайл 23/28)", self.player_x, self.player_y - 34, (255, 120, 90))
                return
            self.forge_menu_open = True
            return

        if eid == "workshop_building":
            if not self._is_within_one_tile(self.active_entity):
                self._add_floating_message("Подойдите к дверям мастерской (тайл 23/16)", self.player_x, self.player_y - 34, (255, 120, 90))
                return
            self.workshop_menu_open = True
            return

        if eid == "barracks_building":
            if not self._is_within_one_tile(self.active_entity):
                self._add_floating_message("Подойдите к воротам казарм (тайл 84/43)", self.player_x, self.player_y - 34, (255, 120, 90))
                return
            self.barracks_menu_open = True
            return

        if eid == "engineering_building":
            if not self._is_within_one_tile(self.active_entity):
                self._add_floating_message("Подойдите к воротам инженерной палаты (тайл 44/15)", self.player_x, self.player_y - 34, (255, 120, 90))
                return
            self.engineering_menu_open = True
            return

        if eid == "university_building":
            if not self._is_within_one_tile(self.active_entity):
                self._add_floating_message("Подойдите к дверям университета (тайл 23/84)", self.player_x, self.player_y - 34, (255, 120, 90))
                return
            self.university_menu_open = True
            return

        if eid == "military_academy":
            if not self._is_within_one_tile(self.active_entity):
                self._add_floating_message("Подойдите к дверям военной академии (тайл 19/73)", self.player_x, self.player_y - 34, (255, 120, 90))
                return
            self.academy_menu_open = True
            return

        if eid == "mage_school_building":
            if not self._is_within_one_tile(self.active_entity):
                self._add_floating_message("Подойдите к дверям школы стихий (тайл 44/66)", self.player_x, self.player_y - 34, (255, 120, 90))
                return
            self.mage_school_menu_open = True
            return

        if eid == "crystal_of_life":
            if not self._is_within_one_tile(self.active_entity):
                self._add_floating_message("Подойдите ближе к Кристаллу Жизни", self.player_x, self.player_y - 34, (255, 120, 90))
                return
            if hasattr(self.session, "character") and self.session.character:
                self.session.character["hp"] = self.session.character.get("max_hp", 100)
                try:
                    self.session.client.save_character(self.session.character)
                except Exception:
                    pass
            self._add_floating_message("✨ Кристалл Жизни исцеляет ваши раны!", self.player_x, self.player_y - 36, (100, 240, 255))
            self.action_notice = "Здоровье полностью восстановлено!"
            self.action_notice_timer = 2.5

    def _any_modal_open(self):
        """True, если открыто хотя бы одно модальное окно здания."""
        return (
            self.castle_menu_open or self.barn_menu_open or self.warehouse_menu_open or self.forge_menu_open
            or self.workshop_menu_open or self.barracks_menu_open or self.engineering_menu_open
            or self.university_menu_open or self.academy_menu_open or self.mage_school_menu_open
        )

    def handle_event(self, event):
        # 1. Если открыто модальное меню замка
        if self.castle_menu_open:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                    self.castle_menu_open = False
                    return
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.castle_back_button.collidepoint(event.pos) or self.castle_close_button.collidepoint(event.pos):
                    self.castle_menu_open = False
                    return
            return

        # 2. Если открыто модальное меню амбара
        if self.barn_menu_open:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                    self.barn_menu_open = False
                    return
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.barn_back_button.collidepoint(event.pos) or self.barn_close_button.collidepoint(event.pos):
                    self.barn_menu_open = False
                    return
            return

        # 3. Если открыто модальное меню склада
        if self.warehouse_menu_open:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                    self.warehouse_menu_open = False
                    return
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.warehouse_back_button.collidepoint(event.pos) or self.warehouse_close_button.collidepoint(event.pos):
                    self.warehouse_menu_open = False
                    return
            return

        # 4. Если открыто модальное меню кузницы
        if self.forge_menu_open:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                    self.forge_menu_open = False
                    return
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.forge_back_button.collidepoint(event.pos) or self.forge_close_button.collidepoint(event.pos):
                    self.forge_menu_open = False
                    return
            return

        # 5. Если открыто модальное меню мастерской
        if self.workshop_menu_open:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                    self.workshop_menu_open = False
                    return
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.workshop_back_button.collidepoint(event.pos) or self.workshop_close_button.collidepoint(event.pos):
                    self.workshop_menu_open = False
                    return
            return

        # 6. Если открыто модальное меню казарм
        if self.barracks_menu_open:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                    self.barracks_menu_open = False
                    return
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.barracks_back_button.collidepoint(event.pos) or self.barracks_close_button.collidepoint(event.pos):
                    self.barracks_menu_open = False
                    return
            return

        # 7. Если открыто модальное меню инженерной палаты
        if self.engineering_menu_open:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                    self.engineering_menu_open = False
                    return
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.engineering_back_button.collidepoint(event.pos) or self.engineering_close_button.collidepoint(event.pos):
                    self.engineering_menu_open = False
                    return
            return

        # 8. Если открыто модальное меню университета
        if self.university_menu_open:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                    self.university_menu_open = False
                    return
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.university_back_button.collidepoint(event.pos) or self.university_close_button.collidepoint(event.pos):
                    self.university_menu_open = False
                    return
            return

        # 9. Если открыто модальное меню военной академии
        if self.academy_menu_open:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                    self.academy_menu_open = False
                    return
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.academy_back_button.collidepoint(event.pos) or self.academy_close_button.collidepoint(event.pos):
                    self.academy_menu_open = False
                    return
            return

        # 10. Если открыто модальное меню школы стихий
        if self.mage_school_menu_open:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                    self.mage_school_menu_open = False
                    return
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.mage_school_back_button.collidepoint(event.pos) or self.mage_school_close_button.collidepoint(event.pos):
                    self.mage_school_menu_open = False
                    return
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_g:
                self.show_grid = not self.show_grid
                return
            if event.key == pygame.K_SPACE:
                self.camera_x = self.player_x
                self.camera_y = self.player_y
                self.camera_follow_player = True
                self._clamp_camera()
                return

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                # Клик по окну активного объекта
                if self.active_entity is not None and self.active_window_rect.collidepoint(event.pos):
                    if self.active_close_button.collidepoint(event.pos):
                        self.active_entity = None
                        return
                    if self.active_action_button.collidepoint(event.pos):
                        self._trigger_active_action()
                        return
                    return

                # Клик по объекту или персонажу
                clicked_entity = self._find_entity_at(event.pos)
                if clicked_entity is not None:
                    self.active_entity = clicked_entity
                    self.action_notice = None
                    self.dragging = False
                    if clicked_entity.get("id") == "main_castle":
                        self.castle_menu_open = True
                    elif clicked_entity.get("id") == "barn_building":
                        self.barn_menu_open = True
                    elif clicked_entity.get("id") == "warehouse_building":
                        self.warehouse_menu_open = True
                    elif clicked_entity.get("id") == "forge_building":
                        self.forge_menu_open = True
                    elif clicked_entity.get("id") == "workshop_building":
                        self.workshop_menu_open = True
                    elif clicked_entity.get("id") == "barracks_building":
                        self.barracks_menu_open = True
                    elif clicked_entity.get("id") == "engineering_building":
                        self.engineering_menu_open = True
                    elif clicked_entity.get("id") == "university_building":
                        self.university_menu_open = True
                    elif clicked_entity.get("id") == "military_academy":
                        self.academy_menu_open = True
                    elif clicked_entity.get("id") == "mage_school_building":
                        self.mage_school_menu_open = True
                    return

                # ЛКМ: перетаскивание карты
                self.dragging = True
                self.drag_start_mouse = event.pos
                self.drag_start_camera = (self.camera_x, self.camera_y)
                self.drag_moved = False

            elif event.button == 3:
                # ПКМ: отправка персонажа в точку клика
                clicked_entity = self._find_entity_at(event.pos)
                if clicked_entity is not None and clicked_entity.get("id") != "player":
                    tx, ty = clicked_entity.get("approach_pos", (clicked_entity["x"], clicked_entity["y"]))
                else:
                    wx, wy = self.screen_to_world(event.pos[0], event.pos[1])
                    tx = max(-20.0, min(self.world_w + 20.0, wx))
                    ty = max(-20.0, min(self.world_h + 20.0, wy))

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
                self.dragging = False

        elif event.type == pygame.MOUSEMOTION:
            if self.dragging and not self._any_modal_open():
                dx = event.pos[0] - self.drag_start_mouse[0]
                dy = event.pos[1] - self.drag_start_mouse[1]
                if abs(dx) > 4 or abs(dy) > 4:
                    self.drag_moved = True
                    self.camera_x = self.drag_start_camera[0] - (dx / self.zoom)
                    self.camera_y = self.drag_start_camera[1] - (dy / self.zoom)
                    self.camera_follow_player = False
                    self._clamp_camera()

    def update(self, dt):
        # 1. Движение персонажа
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
                    self.player_target = None
                    self.player_state = "idle"
                else:
                    self.player_state = "walk"
                    self.player_direction = self._vector_to_direction(dx, dy)
                    self.player_facing_right = (dx >= 0)

            if self.camera_follow_player:
                self.camera_x += (self.player_x - self.camera_x) * min(1.0, 8.0 * dt)
                self.camera_y += (self.player_y - self.camera_y) * min(1.0, 8.0 * dt)

        # 2. Проверка выхода из города через 4 ворот (выход ТОЛЬКО через ворота)
        px, py = self.player_x, self.player_y

        # Главные ворота (Восток, 12 тайлов): X >= 98*32, Y: 44..55
        if px >= (98 * self.tile_size + 8) and (44 * self.tile_size <= py <= 56 * self.tile_size):
            self.exit_gate = "east"
            self.finished = True
            return

        # Северные ворота (Север, 6 тайлов): Y <= 32, X: 47..52
        if py <= (self.tile_size + 8) and (47 * self.tile_size <= px <= 53 * self.tile_size):
            self.exit_gate = "north"
            self.finished = True
            return

        # Южные ворота (Юг, 6 тайлов): Y >= 98*32, X: 47..52
        if py >= (98 * self.tile_size + 8) and (47 * self.tile_size <= px <= 53 * self.tile_size):
            self.exit_gate = "south"
            self.finished = True
            return

        # Западные ворота (Запад, 6 тайлов): X <= 32, Y: 47..52
        if px <= (self.tile_size + 8) and (47 * self.tile_size <= py <= 53 * self.tile_size):
            self.exit_gate = "west"
            self.finished = True
            return

        # 3. Вход в таверну при наступлении на дверь (тайл 55/15)
        pgx = int(self.player_x // self.tile_size)
        pgy = int(self.player_y // self.tile_size)
        if pgx == 55 and pgy == 15:
            self.navigate = "tavern"
            self.finished = True
            return

        # 4. Вход в амбар при наступлении на дверь (тайл 16/40)
        if pgx == 16 and pgy == 40 and not self.barn_menu_open:
            self.barn_menu_open = True
            self.player_target = None
            self.player_state = "idle"
            self.player_x = 17 * self.tile_size + 16
            self.player_y = 40 * self.tile_size + 16
            return

        # 5. Вход на склад при наступлении на дверь (тайл 16/23)
        if pgx == 16 and pgy == 23 and not self.warehouse_menu_open:
            self.warehouse_menu_open = True
            self.player_target = None
            self.player_state = "idle"
            self.player_x = 17 * self.tile_size + 16
            self.player_y = 23 * self.tile_size + 16
            return

        # 6. Вход в кузницу при наступлении на дверь (тайл 23/28)
        if pgx == 23 and pgy == 28 and not self.forge_menu_open:
            self.forge_menu_open = True
            self.player_target = None
            self.player_state = "idle"
            self.player_x = 22 * self.tile_size + 16
            self.player_y = 28 * self.tile_size + 16
            return

        # 7. Вход в мастерскую при наступлении на дверь (тайл 23/16)
        if pgx == 23 and pgy == 16 and not self.workshop_menu_open:
            self.workshop_menu_open = True
            self.player_target = None
            self.player_state = "idle"
            self.player_x = 22 * self.tile_size + 16
            self.player_y = 16 * self.tile_size + 16
            return

        # 8. Вход в казармы при наступлении на дверь (тайл 84/43)
        if pgx == 84 and pgy == 43 and not self.barracks_menu_open:
            self.barracks_menu_open = True
            self.player_target = None
            self.player_state = "idle"
            self.player_x = 84 * self.tile_size + 16
            self.player_y = 44 * self.tile_size + 16
            return

        # 9. Вход в инженерную палату при наступлении на дверь (тайл 44/15)
        if pgx == 44 and pgy == 15 and not self.engineering_menu_open:
            self.engineering_menu_open = True
            self.player_target = None
            self.player_state = "idle"
            self.player_x = 45 * self.tile_size + 16
            self.player_y = 15 * self.tile_size + 16
            return

        # 10. Вход в университет при наступлении на дверь (тайл 23/84)
        if pgx == 23 and pgy == 84 and not self.university_menu_open:
            self.university_menu_open = True
            self.player_target = None
            self.player_state = "idle"
            self.player_x = 23 * self.tile_size + 16
            self.player_y = 83 * self.tile_size + 16
            return

        # 11. Вход в военную академию при наступлении на дверь (тайл 19/73)
        if pgx == 19 and pgy == 73 and not self.academy_menu_open:
            self.academy_menu_open = True
            self.player_target = None
            self.player_state = "idle"
            self.player_x = 20 * self.tile_size + 16
            self.player_y = 73 * self.tile_size + 16
            return

        # 12. Вход в школу стихий при наступлении на дверь (тайл 44/66)
        if pgx == 44 and pgy == 66 and not self.mage_school_menu_open:
            self.mage_school_menu_open = True
            self.player_target = None
            self.player_state = "idle"
            self.player_x = 45 * self.tile_size + 16
            self.player_y = 66 * self.tile_size + 16
            return

        # 13. Таймеры анимации
        self.player_anim_timer += dt

        if self.click_effect is not None:
            self.click_effect["timer"] -= dt
            if self.click_effect["timer"] <= 0:
                self.click_effect = None

        for msg in self.floating_messages[:]:
            msg["timer"] -= dt
            msg["world_y"] -= 16.0 * dt
            if msg["timer"] <= 0:
                self.floating_messages.remove(msg)

        if self.action_notice_timer > 0:
            self.action_notice_timer -= dt
            if self.action_notice_timer <= 0:
                self.action_notice = None

        # 14. Определение объекта под курсором (hover)
        m_pos = pygame.mouse.get_pos()
        if not self._any_modal_open() and not (self.active_entity and self.active_window_rect.collidepoint(m_pos)):
            self.hovered_entity = self._find_entity_at(m_pos)
        else:
            self.hovered_entity = None

        if not self.dragging:
            self._clamp_camera()

    def draw(self, screen):
        screen.fill((16, 20, 26))

        top_left_wx, top_left_wy = self.screen_to_world(0, 0)
        bot_right_wx, bot_right_wy = self.screen_to_world(settings.WIDTH, settings.HEIGHT)

        start_gx = max(0, int(top_left_wx // self.tile_size) - 1)
        end_gx = min(self.grid_w, int(bot_right_wx // self.tile_size) + 2)
        start_gy = max(0, int(top_left_wy // self.tile_size) - 1)
        end_gy = min(self.grid_h, int(bot_right_wy // self.tile_size) + 2)

        # 1. Отрисовка мостовой и широких проспектов города 100х100
        for gy in range(start_gy, end_gy):
            for gx in range(start_gx, end_gx):
                tile_wx = gx * self.tile_size
                tile_wy = gy * self.tile_size
                sx, sy = self.world_to_screen(tile_wx, tile_wy)
                sx2, sy2 = self.world_to_screen(tile_wx + self.tile_size, tile_wy + self.tile_size)
                rect = pygame.Rect(sx, sy, sx2 - sx + 1, sy2 - sy + 1)

                is_avenue = False
                is_plaza = False

                # Центральная площадь (40..59 по X и Y, 20x20 тайлов)
                if 40 <= gx <= 59 and 40 <= gy <= 59:
                    is_plaza = True
                # Северно-Южный проспект (6 тайлов в ширину: X 47..52)
                elif 47 <= gx <= 52:
                    is_avenue = True
                # Западно-Восточный проспект (6 тайлов в ширину: Y 47..52, а к Главным воротам расширяется до 12 тайлов Y: 44..55)
                elif (47 <= gy <= 52) or (gx >= 80 and 44 <= gy <= 55):
                    is_avenue = True

                if is_plaza:
                    # Золотисто-мраморная центральная площадь
                    cell_color = (78, 74, 66) if (gx + gy) % 2 == 0 else (84, 80, 72)
                elif is_avenue:
                    # Главные проспекты из светлого тесаного камня
                    cell_color = (68, 66, 60) if (gx + gy) % 2 == 0 else (74, 72, 66)
                else:
                    # Городские кварталы (мостовая из темного булыжника)
                    cell_color = (38, 44, 52) if (gx + gy) % 2 == 0 else (42, 48, 56)

                pygame.draw.rect(screen, cell_color, rect)

                if self.show_grid:
                    pygame.draw.rect(screen, (58, 66, 76), rect, 1)

        # 2. Объекты города: Главный Замок, Таверна и Кристалл Жизни
        self._draw_city_objects(screen)

        # 3. Внешние крепостные стены и 4 ворот
        self._draw_walls_and_gates(screen)

        # 4. Эффекты клика и персонаж
        self._draw_click_effect(screen)
        self._draw_player_character(screen)

        # 5. Всплывающие сообщения
        self._draw_floating_messages(screen)

        # 6. Всплывающее окно активного объекта (ЛКМ)
        self._draw_active_window(screen)

        # 7. Верхний HUD (информация, подсказки, БЕЗ кнопок телепортации)
        self._draw_hud(screen)

        # 8. Модальное окно заглушки Главного Замка
        if self.castle_menu_open:
            self._draw_castle_modal(screen)

        # 9. Модальное окно заглушки Городского Амбара
        if self.barn_menu_open:
            self._draw_barn_modal(screen)

        # 10. Модальное окно заглушки Городского Склада
        if self.warehouse_menu_open:
            self._draw_warehouse_modal(screen)

        # 11. Модальное окно заглушки Городской Кузницы
        if self.forge_menu_open:
            self._draw_forge_modal(screen)

        # 12. Модальное окно заглушки Городской Мастерской
        if self.workshop_menu_open:
            self._draw_workshop_modal(screen)

        # 13. Модальное окно заглушки Городских Казарм
        if self.barracks_menu_open:
            self._draw_barracks_modal(screen)

        # 14. Модальное окно заглушки Инженерной палаты
        if self.engineering_menu_open:
            self._draw_engineering_modal(screen)

        # 15. Модальное окно заглушки Городского Университета
        if self.university_menu_open:
            self._draw_university_modal(screen)

        # 16. Модальное окно заглушки Военной академии
        if self.academy_menu_open:
            self._draw_academy_modal(screen)

        # 17. Модальное окно заглушки Школы стихий
        if self.mage_school_menu_open:
            self._draw_mage_school_modal(screen)

    def close(self):
        """Очистка ресурсов при закрытии сцены."""
        pass
