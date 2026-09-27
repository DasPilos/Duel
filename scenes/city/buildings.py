"""Данные зданий города: геометрия, хитбоксы и описания (CityScene.objects/solid_rects)."""
import pygame


class CityBuildingsMixin:
    """Инициализация объектов города и крепостных стен. Требует self.tile_size (CityScene)."""

    def _init_city_objects(self):
        """Инициализирует объекты внутри города (Кристалл Жизни и Главный замок)."""
        # 1. Кристалл Жизни (в центре площади, квадрат 3х3 тайла = 9 тайлов, 96х96 px)
        # Центр площади: 50, 50 -> тайлы 49..51 по X и Y
        crystal_gx, crystal_gy = 49, 49
        crystal_px = crystal_gx * self.tile_size  # 1568 px
        crystal_py = crystal_gy * self.tile_size  # 1568 px
        crystal_w_px = 3 * self.tile_size         # 96 px
        crystal_h_px = 3 * self.tile_size         # 96 px

        # 2. Главный замок (центр на координатах 75/70, размер 15х15 тайлов, 480х480 px, вход с юга)
        # Центр 75, 70 -> левый верхний угол: 75 - 7 = 68, 70 - 7 = 63 (тайлы X: 68..82, Y: 63..77)
        castle_w_tiles = 15
        castle_h_tiles = 15
        castle_gx = 75 - 7  # 68
        castle_gy = 70 - 7  # 63
        castle_px = castle_gx * self.tile_size  # 2176 px
        castle_py = castle_gy * self.tile_size  # 2016 px
        castle_w_px = castle_w_tiles * self.tile_size  # 480 px
        castle_h_px = castle_h_tiles * self.tile_size  # 480 px
        gate_gx = 75
        gate_gy = 77  # Южная стена замка: Y = 63 + 15 - 1 = 77

        # 3. Городская Таверна (верхний угол 55/12, нижний 55/18, размер 10х7 тайлов = 320х224 px)
        # Вход на тайле 55/15 со стороны площади (западная стена)
        tavern_w_tiles = 10
        tavern_h_tiles = 7
        tavern_gx = 55
        tavern_gy = 12
        tavern_px = tavern_gx * self.tile_size  # 1760 px
        tavern_py = tavern_gy * self.tile_size  # 384 px
        tavern_w_px = tavern_w_tiles * self.tile_size  # 320 px
        tavern_h_px = tavern_h_tiles * self.tile_size  # 224 px
        tavern_door_gx = 55
        tavern_door_gy = 15

        # Непроходимые стены таверны (X: 55..64, Y: 12..18) с проемом для входа на тайле 55/15:
        # Тайлы 55/12..55/14 (северная часть западной стены), тайлы 55/16..55/18 (южная часть),
        # а также остальной массив здания (X: 56..64, Y: 12..18)
        tavern_solids = [
            # Основной массив здания (X: 56..64, Y: 12..18 = 9х7 тайлов)
            pygame.Rect((tavern_gx + 1) * self.tile_size, tavern_py, (tavern_w_tiles - 1) * self.tile_size, tavern_h_px),
            # Западная стена выше двери (Y: 12..14 = 3 тайла)
            pygame.Rect(tavern_px, tavern_py, self.tile_size, 3 * self.tile_size),
            # Западная стена ниже двери (Y: 16..18 = 3 тайла)
            pygame.Rect(tavern_px, tavern_py + 4 * self.tile_size, self.tile_size, 3 * self.tile_size),
        ]

        # 4. Городской Амбар 1-го уровня (вход на тайле 16/40, по Y: 16/44 на 5/44, по X: 16/35 на 16/44)
        # Размер: 12х10 тайлов (X: 5..16, Y: 35..44 = 384х320 px)
        barn_w_tiles = 12
        barn_h_tiles = 10
        barn_gx = 5
        barn_gy = 35
        barn_px = barn_gx * self.tile_size  # 160 px
        barn_py = barn_gy * self.tile_size  # 1120 px
        barn_w_px = barn_w_tiles * self.tile_size  # 384 px
        barn_h_px = barn_h_tiles * self.tile_size  # 320 px
        barn_door_gx = 16
        barn_door_gy = 40

        # Непроходимые стены амбара с проемом для ворот/двери на тайле 16/40:
        # Основной массив (X: 5..15 = 11 тайлов в ширину, Y: 35..44 = 10 тайлов в высоту)
        # Восточная стена выше двери (X: 16, Y: 35..39 = 5 тайлов)
        # Восточная стена ниже двери (X: 16, Y: 41..44 = 4 тайла)
        barn_solids = [
            pygame.Rect(barn_px, barn_py, 11 * self.tile_size, barn_h_px),
            pygame.Rect(barn_px + 11 * self.tile_size, barn_py, self.tile_size, 5 * self.tile_size),
            pygame.Rect(barn_px + 11 * self.tile_size, barn_py + 6 * self.tile_size, self.tile_size, 4 * self.tile_size),
        ]

        # 5. Городской Склад материалов 1-го уровня (на 7 тайлов выше амбара)
        # Габариты: 12х10 тайлов (X: 5..16, Y: 18..27 = 384х320 px)
        # Расположение дверей такое же, как у амбара: восточная стена, тайл 16/23
        warehouse_w_tiles = 12
        warehouse_h_tiles = 10
        warehouse_gx = 5
        warehouse_gy = 18
        warehouse_px = warehouse_gx * self.tile_size  # 160 px
        warehouse_py = warehouse_gy * self.tile_size  # 576 px
        warehouse_w_px = warehouse_w_tiles * self.tile_size  # 384 px
        warehouse_h_px = warehouse_h_tiles * self.tile_size  # 320 px
        warehouse_door_gx = 16
        warehouse_door_gy = 23

        warehouse_solids = [
            pygame.Rect(warehouse_px, warehouse_py, 11 * self.tile_size, warehouse_h_px),
            pygame.Rect(warehouse_px + 11 * self.tile_size, warehouse_py, self.tile_size, 5 * self.tile_size),
            pygame.Rect(warehouse_px + 11 * self.tile_size, warehouse_py + 6 * self.tile_size, self.tile_size, 4 * self.tile_size),
        ]

        # 6. Городская Кузница 1-го уровня (размер 9 по X, 7 по Y: 23/25 на 31/31)
        # Вход на тайле 23/28
        forge_w_tiles = 9
        forge_h_tiles = 7
        forge_gx = 23
        forge_gy = 25
        forge_px = forge_gx * self.tile_size  # 736 px
        forge_py = forge_gy * self.tile_size  # 800 px
        forge_w_px = forge_w_tiles * self.tile_size  # 288 px
        forge_h_px = forge_h_tiles * self.tile_size  # 224 px
        forge_door_gx = 23
        forge_door_gy = 28

        forge_solids = [
            pygame.Rect((forge_gx + 1) * self.tile_size, forge_py, (forge_w_tiles - 1) * self.tile_size, forge_h_px),
            pygame.Rect(forge_px, forge_py, self.tile_size, 3 * self.tile_size),
            pygame.Rect(forge_px, forge_py + 4 * self.tile_size, self.tile_size, 3 * self.tile_size),
        ]

        # 7. Городская Мастерская 1-го уровня (на 5 тайлов выше кузницы: размер 9 по X, 7 по Y: 23/13 на 31/19)
        # Вход на тайле 23/16
        workshop_w_tiles = 9
        workshop_h_tiles = 7
        workshop_gx = 23
        workshop_gy = 13
        workshop_px = workshop_gx * self.tile_size  # 736 px
        workshop_py = workshop_gy * self.tile_size  # 416 px
        workshop_w_px = workshop_w_tiles * self.tile_size  # 288 px
        workshop_h_px = workshop_h_tiles * self.tile_size  # 224 px
        workshop_door_gx = 23
        workshop_door_gy = 16

        workshop_solids = [
            pygame.Rect((workshop_gx + 1) * self.tile_size, workshop_py, (workshop_w_tiles - 1) * self.tile_size, workshop_h_px),
            pygame.Rect(workshop_px, workshop_py, self.tile_size, 3 * self.tile_size),
            pygame.Rect(workshop_px, workshop_py + 4 * self.tile_size, self.tile_size, 3 * self.tile_size),
        ]

        # 8. Городские Казармы 1-го уровня (от 80/43 до 88/31: размер 9 по X, 13 по Y: X: 80..88, Y: 31..43)
        # Вход на тайле 84/43 (южная стена казарм)
        barracks_w_tiles = 9
        barracks_h_tiles = 13
        barracks_gx = 80
        barracks_gy = 31
        barracks_px = barracks_gx * self.tile_size  # 2560 px
        barracks_py = barracks_gy * self.tile_size  # 992 px
        barracks_w_px = barracks_w_tiles * self.tile_size  # 288 px
        barracks_h_px = barracks_h_tiles * self.tile_size  # 416 px
        barracks_door_gx = 84
        barracks_door_gy = 43

        # Непроходимые стены казарм с дверью/воротами на тайле 84/43 (южная стена):
        # Основной массив здания (X: 80..88, Y: 31..42 = 9х12 тайлов)
        # Южная стена слева от двери (X: 80..83 = 4 тайла, Y: 43)
        # Южная стена справа от двери (X: 85..88 = 4 тайла, Y: 43)
        barracks_solids = [
            pygame.Rect(barracks_px, barracks_py, barracks_w_px, (barracks_h_tiles - 1) * self.tile_size),
            pygame.Rect(barracks_px, barracks_py + (barracks_h_tiles - 1) * self.tile_size, 4 * self.tile_size, self.tile_size),
            pygame.Rect(barracks_px + 5 * self.tile_size, barracks_py + (barracks_h_tiles - 1) * self.tile_size, 4 * self.tile_size, self.tile_size),
        ]

        # 9. Инженерная палата 1-го уровня (от 35/19 до 44/12: размер 10 по X, 8 по Y: X: 35..44, Y: 12..19)
        # Вход на тайле 44/15 (восточная стена, обращенная к площади)
        eng_w_tiles = 10
        eng_h_tiles = 8
        eng_gx = 35
        eng_gy = 12
        eng_px = eng_gx * self.tile_size  # 1120 px
        eng_py = eng_gy * self.tile_size  # 384 px
        eng_w_px = eng_w_tiles * self.tile_size  # 320 px
        eng_h_px = eng_h_tiles * self.tile_size  # 256 px
        eng_door_gx = 44
        eng_door_gy = 15

        # Непроходимые стены с проемом для ворот/двери на тайле 44/15 (восточная стена):
        # Основной массив здания (X: 35..43, Y: 12..19 = 9х8 тайлов)
        # Восточная стена выше двери (X: 44, Y: 12..14 = 3 тайла)
        # Восточная стена ниже двери (X: 44, Y: 16..19 = 4 тайла)
        eng_solids = [
            pygame.Rect(eng_px, eng_py, 9 * self.tile_size, eng_h_px),
            pygame.Rect(eng_px + 9 * self.tile_size, eng_py, self.tile_size, 3 * self.tile_size),
            pygame.Rect(eng_px + 9 * self.tile_size, eng_py + 4 * self.tile_size, self.tile_size, 4 * self.tile_size),
        ]

        # 10. Городской Университет 1-го уровня (от 16/84 до 30/94: размер 15 по X, 11 по Y: X: 16..30, Y: 84..94)
        # Вход на тайле 23/84 (северная стена университета)
        univ_w_tiles = 15
        univ_h_tiles = 11
        univ_gx = 16
        univ_gy = 84
        univ_px = univ_gx * self.tile_size  # 512 px
        univ_py = univ_gy * self.tile_size  # 2688 px
        univ_w_px = univ_w_tiles * self.tile_size  # 480 px
        univ_h_px = univ_h_tiles * self.tile_size  # 352 px
        univ_door_gx = 23
        univ_door_gy = 84

        # Непроходимые стены университета с проемом для дверей на тайле 23/84 (северная стена):
        # Основной массив корпуса (X: 16..30, Y: 85..94 = 15х10 тайлов)
        # Северная стена слева от двери (X: 16..22 = 7 тайлов, Y: 84)
        # Северная стена справа от двери (X: 24..30 = 7 тайлов, Y: 84)
        univ_solids = [
            pygame.Rect(univ_px, univ_py + self.tile_size, univ_w_px, (univ_h_tiles - 1) * self.tile_size),
            pygame.Rect(univ_px, univ_py, 7 * self.tile_size, self.tile_size),
            pygame.Rect(univ_px + 8 * self.tile_size, univ_py, 7 * self.tile_size, self.tile_size),
        ]

        # 11. Военная академия 1-го уровня (от 10/70 до 19/76: размер 10 по X, 7 по Y: X: 10..19, Y: 70..76)
        # Вход на тайле 19/73 (восточная стена академии)
        academy_w_tiles = 10
        academy_h_tiles = 7
        academy_gx = 10
        academy_gy = 70
        academy_px = academy_gx * self.tile_size  # 320 px
        academy_py = academy_gy * self.tile_size  # 2240 px
        academy_w_px = academy_w_tiles * self.tile_size  # 320 px
        academy_h_px = academy_h_tiles * self.tile_size  # 224 px
        academy_door_gx = 19
        academy_door_gy = 73

        # Непроходимые стены академии с проемом для дверей на тайле 19/73 (восточная стена):
        # Основной массив здания (X: 10..18, Y: 70..76 = 9х7 тайлов)
        # Восточная стена выше двери (X: 19, Y: 70..72 = 3 тайла)
        # Восточная стена ниже двери (X: 19, Y: 74..76 = 3 тайла)
        academy_solids = [
            pygame.Rect(academy_px, academy_py, 9 * self.tile_size, academy_h_px),
            pygame.Rect(academy_px + 9 * self.tile_size, academy_py, self.tile_size, 3 * self.tile_size),
            pygame.Rect(academy_px + 9 * self.tile_size, academy_py + 4 * self.tile_size, self.tile_size, 3 * self.tile_size),
        ]

        # 12. Школа стихий 1-го уровня (от 30/70 до 44/62: размер 15 по X, 9 по Y: X: 30..44, Y: 62..70)
        # Вход на тайле 44/66 (восточная стена школы)
        mage_w_tiles = 15
        mage_h_tiles = 9
        mage_gx = 30
        mage_gy = 62
        mage_px = mage_gx * self.tile_size  # 960 px
        mage_py = mage_gy * self.tile_size  # 1984 px
        mage_w_px = mage_w_tiles * self.tile_size  # 480 px
        mage_h_px = mage_h_tiles * self.tile_size  # 288 px
        mage_door_gx = 44
        mage_door_gy = 66

        # Непроходимые стены школы стихий с дверью на тайле 44/66 (восточная стена):
        # Основной массив (X: 30..43, Y: 62..70 = 14х9 тайлов)
        # Восточная стена выше двери (X: 44, Y: 62..65 = 4 тайла)
        # Восточная стена ниже двери (X: 44, Y: 67..70 = 4 тайла)
        mage_solids = [
            pygame.Rect(mage_px, mage_py, 14 * self.tile_size, mage_h_px),
            pygame.Rect(mage_px + 14 * self.tile_size, mage_py, self.tile_size, 4 * self.tile_size),
            pygame.Rect(mage_px + 14 * self.tile_size, mage_py + 5 * self.tile_size, self.tile_size, 4 * self.tile_size),
        ]

        self.objects = [
            {
                "id": "crystal_of_life",
                "name": "Кристалл Жизни",
                "type": "Святыня (3х3 тайла)",
                "tile_x": crystal_gx,
                "tile_y": crystal_gy,
                "tile_w": 3,
                "tile_h": 3,
                "x": crystal_px + crystal_w_px // 2,
                "y": crystal_py + crystal_h_px // 2,
                "radius": 52,
                "entrance_tile": (50, 52),
                "approach_pos": (50 * self.tile_size + 16, 53 * self.tile_size + 16),
                "desc": "Священный Кристалл Жизни (3х3 тайла). Сердце Радбурга. Принимает души павших героев и возрождает их к жизни после смерти в бою.",
                "icon": "💎",
                "solid_rects": [
                    pygame.Rect(crystal_px, crystal_py, crystal_w_px, crystal_h_px)
                ],
            },
            {
                "id": "main_castle",
                "name": "Главный замок",
                "type": "Королевская цитадель (15х15)",
                "is_placeholder": True,
                "tile_x": castle_gx,
                "tile_y": castle_gy,
                "tile_w": castle_w_tiles,
                "tile_h": castle_h_tiles,
                "origin_desc": "Центр замка: [75, 70]",
                "x": castle_px + castle_w_px // 2,
                "y": castle_py + castle_h_px // 2,
                "radius": 240,
                "entrance_tile": (gate_gx, gate_gy),
                "approach_pos": (gate_gx * self.tile_size + 16, (gate_gy + 1) * self.tile_size + 16),
                "desc": "Главный замок Радбурга. В будущем здесь можно будет узнать жизненно важные сведения о городе и взять королевские премиум-квесты.",
                "icon": "🏰",
                "solid_rects": [
                    # Северные, западные и восточные стены с внутренним замком
                    pygame.Rect(castle_px, castle_py, castle_w_px, castle_h_px - 32),
                    # Южная стена слева от ворот (X: 68..73 = 6 тайлов)
                    pygame.Rect(castle_px, castle_py + castle_h_px - 32, 6 * self.tile_size, 32),
                    # Южная стена справа от ворот (X: 77..82 = 6 тайлов)
                    pygame.Rect(castle_px + 9 * self.tile_size, castle_py + castle_h_px - 32, 6 * self.tile_size, 32),
                ],
            },
            {
                "id": "tavern_building",
                "name": "Городская Таверна",
                "type": "Здание 10х7 (2 этажа)",
                "is_placeholder": True,
                "tile_x": tavern_gx,
                "tile_y": tavern_gy,
                "tile_w": tavern_w_tiles,
                "tile_h": tavern_h_tiles,
                "origin_desc": "Верхний угол [55, 12], нижний [55, 18], вход [55, 15]",
                "x": tavern_px + tavern_w_px // 2,
                "y": tavern_py + tavern_h_px // 2,
                "radius": 140,
                "entrance_tile": (tavern_door_gx, tavern_door_gy),
                "approach_pos": ((tavern_door_gx - 1) * self.tile_size + 16, tavern_door_gy * self.tile_size + 16),
                "desc": "Двухэтажная таверна Радбурга (10х7 тайлов). Верхний угол 55/12, нижний 55/18. Вход с запада на тайле 55/15.",
                "icon": "🍺",
                "solid_rects": tavern_solids,
            },
            {
                "id": "barn_building",
                "name": "Городской Амбар",
                "type": "Склад провизии (Уровень 1)",
                "is_placeholder": True,
                "tile_x": barn_gx,
                "tile_y": barn_gy,
                "tile_w": barn_w_tiles,
                "tile_h": barn_h_tiles,
                "origin_desc": "Вход на тайле [16, 40], размер 12х10 (X: 5..16, Y: 35..44)",
                "x": barn_px + barn_w_px // 2,
                "y": barn_py + barn_h_px // 2,
                "radius": 180,
                "entrance_tile": (barn_door_gx, barn_door_gy),
                "approach_pos": ((barn_door_gx + 1) * self.tile_size + 16, barn_door_gy * self.tile_size + 16),
                "desc": "Городской амбар 1-го уровня (12х10 тайлов). Здесь хранится провизия города. Защищает жителей и гарнизон Радбурга от голода.",
                "icon": "🌾",
                "solid_rects": barn_solids,
            },
            {
                "id": "warehouse_building",
                "name": "Городской Склад",
                "type": "Склад материалов (Уровень 1)",
                "is_placeholder": True,
                "tile_x": warehouse_gx,
                "tile_y": warehouse_gy,
                "tile_w": warehouse_w_tiles,
                "tile_h": warehouse_h_tiles,
                "origin_desc": "Вход на тайле [16, 23], размер 12х10 (X: 5..16, Y: 18..27)",
                "x": warehouse_px + warehouse_w_px // 2,
                "y": warehouse_py + warehouse_h_px // 2,
                "radius": 180,
                "entrance_tile": (warehouse_door_gx, warehouse_door_gy),
                "approach_pos": ((warehouse_door_gx + 1) * self.tile_size + 16, warehouse_door_gy * self.tile_size + 16),
                "desc": "Городской склад 1-го уровня (12х10 тайлов). Здесь хранятся все материалы города: древесина, камень, уголь, железная руда, железо.",
                "icon": "📦",
                "solid_rects": warehouse_solids,
            },
            {
                "id": "forge_building",
                "name": "Городская Кузница",
                "type": "Оружейная кузница (Уровень 1)",
                "is_placeholder": True,
                "tile_x": forge_gx,
                "tile_y": forge_gy,
                "tile_w": forge_w_tiles,
                "tile_h": forge_h_tiles,
                "origin_desc": "Вход на тайле [23, 28], размер 9х7 (X: 23..31, Y: 25..31)",
                "x": forge_px + forge_w_px // 2,
                "y": forge_py + forge_h_px // 2,
                "radius": 130,
                "entrance_tile": (forge_door_gx, forge_door_gy),
                "approach_pos": ((forge_door_gx - 1) * self.tile_size + 16, forge_door_gy * self.tile_size + 16),
                "desc": "Кузница Радбурга 1-го уровня (9х7 тайлов). Ковка смертоносного оружия для игроков и вооружения защитников гарнизона города.",
                "icon": "⚒️",
                "solid_rects": forge_solids,
            },
            {
                "id": "workshop_building",
                "name": "Городская Мастерская",
                "type": "Бронная мастерская (Уровень 1)",
                "is_placeholder": True,
                "tile_x": workshop_gx,
                "tile_y": workshop_gy,
                "tile_w": workshop_w_tiles,
                "tile_h": workshop_h_tiles,
                "origin_desc": "Вход на тайле [23, 16], размер 9х7 (X: 23..31, Y: 13..19)",
                "x": workshop_px + workshop_w_px // 2,
                "y": workshop_py + workshop_h_px // 2,
                "radius": 130,
                "entrance_tile": (workshop_door_gx, workshop_door_gy),
                "approach_pos": ((workshop_door_gx - 1) * self.tile_size + 16, workshop_door_gy * self.tile_size + 16),
                "desc": "Бронная мастерская Радбурга 1-го уровня (9х7 тайлов). Изготовление прочных доспехов, щитов и лат для героев и гарнизона.",
                "icon": "🛡️",
                "solid_rects": workshop_solids,
            },
            {
                "id": "barracks_building",
                "name": "Городские Казармы",
                "type": "Военный комплекс (Уровень 1)",
                "is_placeholder": True,
                "tile_x": barracks_gx,
                "tile_y": barracks_gy,
                "tile_w": barracks_w_tiles,
                "tile_h": barracks_h_tiles,
                "origin_desc": "Вход на тайле [84, 43], размер 9х13 (X: 80..88, Y: 31..43)",
                "x": barracks_px + barracks_w_px // 2,
                "y": barracks_py + barracks_h_px // 2,
                "radius": 190,
                "entrance_tile": (barracks_door_gx, barracks_door_gy),
                "approach_pos": (barracks_door_gx * self.tile_size + 16, (barracks_door_gy + 1) * self.tile_size + 16),
                "desc": "Городские казармы 1-го уровня (9х13 тайлов). Здесь содержатся и тренируются солдаты гарнизона Радбурга.",
                "icon": "🏰",
                "solid_rects": barracks_solids,
            },
            {
                "id": "engineering_building",
                "name": "Инженерная палата",
                "type": "Осадная мастерская (Уровень 1)",
                "is_placeholder": True,
                "tile_x": eng_gx,
                "tile_y": eng_gy,
                "tile_w": eng_w_tiles,
                "tile_h": eng_h_tiles,
                "origin_desc": "Вход на тайле [44, 15], размер 10х8 (X: 35..44, Y: 12..19)",
                "x": eng_px + eng_w_px // 2,
                "y": eng_py + eng_h_px // 2,
                "radius": 150,
                "entrance_tile": (eng_door_gx, eng_door_gy),
                "approach_pos": ((eng_door_gx + 1) * self.tile_size + 16, eng_door_gy * self.tile_size + 16),
                "desc": "Инженерная палата Радбурга 1-го уровня (10х8 тайлов). Производство оборонных сооружений и осадных машин: катапульты, тараны, требушеты.",
                "icon": "⚙️",
                "solid_rects": eng_solids,
            },
            {
                "id": "university_building",
                "name": "Городской Университет",
                "type": "Академия наук (Уровень 1)",
                "is_placeholder": True,
                "tile_x": univ_gx,
                "tile_y": univ_gy,
                "tile_w": univ_w_tiles,
                "tile_h": univ_h_tiles,
                "origin_desc": "Вход на тайле [23, 84], размер 15х11 (X: 16..30, Y: 84..94)",
                "x": univ_px + univ_w_px // 2,
                "y": univ_py + univ_h_px // 2,
                "radius": 220,
                "entrance_tile": (univ_door_gx, univ_door_gy),
                "approach_pos": (univ_door_gx * self.tile_size + 16, (univ_door_gy - 1) * self.tile_size + 16),
                "desc": "Университет Радбурга 1-го уровня (15х11 тайлов). Место изучения передовых технологий, военных трактатов и научных открытий.",
                "icon": "🏛️",
                "solid_rects": univ_solids,
            },
            {
                "id": "military_academy",
                "name": "Военная академия",
                "type": "Академия бойцов (Уровень 1)",
                "is_placeholder": True,
                "tile_x": academy_gx,
                "tile_y": academy_gy,
                "tile_w": academy_w_tiles,
                "tile_h": academy_h_tiles,
                "origin_desc": "Вход на тайле [19, 73], размер 10х7 (X: 10..19, Y: 70..76)",
                "x": academy_px + academy_w_px // 2,
                "y": academy_py + academy_h_px // 2,
                "radius": 140,
                "entrance_tile": (academy_door_gx, academy_door_gy),
                "approach_pos": ((academy_door_gx + 1) * self.tile_size + 16, academy_door_gy * self.tile_size + 16),
                "desc": "Военная академия Радбурга 1-го уровня (10х7 тайлов). Обучение воинов, прокачка карт, развитие ветвей талантов силовой линии и открытие улучшений.",
                "icon": "⚔️",
                "solid_rects": academy_solids,
            },
            {
                "id": "mage_school_building",
                "name": "Школа стихий",
                "type": "Школа магии (Уровень 1)",
                "is_placeholder": True,
                "tile_x": mage_gx,
                "tile_y": mage_gy,
                "tile_w": mage_w_tiles,
                "tile_h": mage_h_tiles,
                "origin_desc": "Вход на тайле [44, 66], размер 15х9 (X: 30..44, Y: 62..70)",
                "x": mage_px + mage_w_px // 2,
                "y": mage_py + mage_h_px // 2,
                "radius": 190,
                "entrance_tile": (mage_door_gx, mage_door_gy),
                "approach_pos": ((mage_door_gx + 1) * self.tile_size + 16, mage_door_gy * self.tile_size + 16),
                "desc": "Школа стихий Радбурга 1-го уровня (15х9 тайлов). Центр изучения заклинаний, медитаций и прокачки магических карт стихий.",
                "icon": "🔮",
                "solid_rects": mage_solids,
            },
        ]

    def _build_city_walls(self):
        """
        Строит твердые стены периметра города 100х100 тайлов (толщина 2 тайла = 64 px):
        - Северная стена (Y: 0..1): проем ворот X: 47..52 (6 тайлов)
        - Южная стена (Y: 98..99): проем ворот X: 47..52 (6 тайлов)
        - Западная стена (X: 0..1): проем ворот Y: 47..52 (6 тайлов)
        - Восточная стена (X: 98..99): Главные ворота Y: 44..55 (12 тайлов)
        """
        self.solid_rects = [
            # 1. Северная стена (Y: 0..64): левая и правая части
            pygame.Rect(0, 0, 47 * self.tile_size, 2 * self.tile_size),
            pygame.Rect(53 * self.tile_size, 0, (100 - 53) * self.tile_size, 2 * self.tile_size),

            # 2. Южная стена (Y: 98*32..3200): левая и правая части
            pygame.Rect(0, 98 * self.tile_size, 47 * self.tile_size, 2 * self.tile_size),
            pygame.Rect(53 * self.tile_size, 98 * self.tile_size, (100 - 53) * self.tile_size, 2 * self.tile_size),

            # 3. Западная стена (X: 0..64): верхняя и нижняя части
            pygame.Rect(0, 2 * self.tile_size, 2 * self.tile_size, (47 - 2) * self.tile_size),
            pygame.Rect(0, 53 * self.tile_size, 2 * self.tile_size, (98 - 53) * self.tile_size),

            # 4. Восточная стена (X: 98*32..3200): верхняя и нижняя части
            pygame.Rect(98 * self.tile_size, 2 * self.tile_size, 2 * self.tile_size, (44 - 2) * self.tile_size),
            pygame.Rect(98 * self.tile_size, 56 * self.tile_size, 2 * self.tile_size, (98 - 56) * self.tile_size),

            # 5. Угловые бастионы 5х5 тайлов (160х160 px) для массивности крепости
            pygame.Rect(0, 0, 5 * self.tile_size, 5 * self.tile_size),
            pygame.Rect(95 * self.tile_size, 0, 5 * self.tile_size, 5 * self.tile_size),
            pygame.Rect(0, 95 * self.tile_size, 5 * self.tile_size, 5 * self.tile_size),
            pygame.Rect(95 * self.tile_size, 95 * self.tile_size, 5 * self.tile_size, 5 * self.tile_size),
        ]
