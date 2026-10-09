import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pygame

from core import settings
from core.production_buildings import building_level_info, building_resources, slot_resource, upgrade_requirements
from server.world_map import terrain_payload


def _payload(building, level=1, occupied=(), stage=1):
    info = building_level_info(level, building)
    requirements = upgrade_requirements(level, building)
    resources = building_resources(building)
    return {
        "building": building,
        "level": level,
        "max_workers": info["max_workers"],
        "workers": len([index for index in occupied if index < info["max_workers"]]),
        "next_harvest_seconds": 1900,
        "stage": stage,
        "storage_total": 0,
        "storage": {**{resource: 0 for resource in resources}, "limit": info["storage"]},
        "worker_slots": [
            {"slot_index": index, "resource": slot_resource(building, index), "occupied": index in occupied,
             "worker_id": f"citizen-{index}" if index in occupied else None,
             "hire_time": None, "progress_sec": 0}
            for index in range(info["max_workers"])
        ],
        "upgrade": None if requirements is None else {
            "next_level": level + 1,
            "time_seconds": requirements["time_seconds"],
            "materials": [
                {"item_id": item_id, "name": f"Материал {item_id}", "icon": None,
                 "required": required, "deposited": 0, "remaining": required,
                 "in_warehouse": required, "in_backpack": 3}
                for item_id, required in requirements["materials"].items()
            ],
            "ready": True,
            "in_progress": False,
            "finish_at": None,
            "seconds_left": None,
        },
    }


class FakeBuildingClient:
    get_map_terrain = staticmethod(terrain_payload)
    def __init__(self):
        self.calls = []
        self.city_calls = []
        self.last_payload = None
        self.active_work = None
        self.citizens = [
            {"id": index, "name": f"Горожанин {index}", "job_building": None,
             "job_slot": None, "satisfaction": "satisfied"}
            for index in range(1, 5)
        ]

    def get_city_population(self, _character_id):
        return {"citizens": self.citizens}

    def assign_city_citizen(self, _character_id, citizen_id, building, slot_index):
        citizen = next(row for row in self.citizens if row["id"] == citizen_id)
        citizen.update(job_building=building, job_slot=slot_index)
        self.city_calls.append(("assign", building, slot_index, citizen_id))
        return {"citizens": self.citizens}

    def recall_city_citizen(self, _character_id, citizen_id):
        citizen = next(row for row in self.citizens if row["id"] == citizen_id)
        self.city_calls.append(("recall", citizen_id))
        citizen.update(job_building=None, job_slot=None)
        return {"citizens": self.citizens}

    def get_player_work(self, _character_id):
        return self.active_work

    def get_building(self, building, character_id):
        state = _payload(building)
        if self.active_work and self.active_work["building"] == building:
            slot = state["worker_slots"][self.active_work["slot_index"]]
            slot.update(occupied=True, worker_id=f"player:{character_id}", is_player=True)
            state["workers"] = 1
        for citizen in self.citizens:
            if citizen["job_building"] == building:
                slot = state["worker_slots"][citizen["job_slot"]]
                slot.update(occupied=True, worker_id=f"citizen:{citizen['id']}")
        return state

    def building_action(self, building, _character_id, action, payload=None):
        payload = payload or {}
        self.last_payload = payload
        self.calls.append((building, action, payload.get("slot_index", payload.get("item_id"))))
        if action in ("workers/hire", "workers/fire", "workers/player/toggle"):
            state = _payload(building)
            slot = state["worker_slots"][payload["slot_index"]]
            if action == "workers/hire":
                slot.update(occupied=True, worker_id=f"citizen-{payload['slot_index']}")
            elif action == "workers/fire":
                slot.update(occupied=False, worker_id=None)
            else:
                worker_id = f"player:{_character_id}"
                if slot.get("worker_id") == worker_id:
                    slot.update(occupied=False, worker_id=None)
                else:
                    slot.update(occupied=True, worker_id=worker_id, is_player=True)
            return state
        return _payload(building)


class ProductionBuildingWindowTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), pygame.HIDDEN)
        from scenes.world_map_scene import WorldMapScene

        self.client = FakeBuildingClient()
        session = SimpleNamespace(character={"id": 1, "name": "Тест"}, client=self.client)
        self.scene = WorldMapScene(session)

    def tearDown(self):
        pygame.quit()

    def _open(self, object_id):
        entity = next((obj for obj in self.scene.objects if obj["id"] == object_id), None)
        if entity is None:
            required_city_level = {
                "mountain_rift": 2, "barnyard": 3, "black_pit": 4,
            }.get(object_id)
            if required_city_level is not None:
                from client.structures import hydrate_structures
                from server.world_map import terrain_payload

                terrain = terrain_payload(required_city_level)
                self.scene.objects = hydrate_structures(terrain.get("objects", []))
                entity = next(obj for obj in self.scene.objects if obj["id"] == object_id)
        if entity is None:
            raise AssertionError(f"Map object {object_id!r} is not available in this test world")
        self.scene.active_entity = entity
        self.scene.player_x, self.scene.player_y = entity["approach_pos"]
        self.scene._trigger_active_action()
        self.assertIsNotNone(self.scene.building_window)
        return self.scene.building_window

    def _click(self, position):
        self.scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=position))

    def _confirm_worker_action(self, window):
        self.scene.draw(self.screen)
        self._click(window.confirm_yes_button.center)

    def test_forester_hut_replaced_by_lumber_camp(self):
        ids = {obj["id"] for obj in self.scene.objects}
        self.assertIn("lumber_camp", ids)
        self.assertNotIn("forester_hut", ids)

    def test_reconnect_restores_active_work_window_and_plot(self):
        from scenes.world_map_scene import WorldMapScene

        self.client.active_work = {"building": "farm", "slot_index": 0}
        session = SimpleNamespace(character={"id": 1, "name": "Тест"}, client=self.client)
        scene = WorldMapScene(session, spawn_pos=(1250, 900, "e"))

        self.assertIsNotNone(scene.building_window)
        self.assertEqual(scene.building_window.building, "farm")
        self.assertTrue(scene.building_window.is_open)
        self.assertEqual(scene.building_window.selected_plot, 0)
        self.assertTrue(scene.building_window.player_is_working())
        scene.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=(20, 20)))
        self.assertIsNone(scene.player_target)

    def test_windows_draw_every_tab(self):
        for object_id in ("wheat_farm", "lumber_camp"):
            window = self._open(object_id)
            for tab in ("production", "storage", "upgrade"):
                with self.subTest(object_id=object_id, tab=tab):
                    window.tab = tab
                    self.scene.draw(self.screen)
            self.scene.building_window = None

    def test_plot_centers_are_inside_their_polygons(self):
        for object_id in ("wheat_farm", "lumber_camp"):
            window = self._open(object_id)
            for index, plot in enumerate(window.plot_geometry()):
                with self.subTest(object_id=object_id, plot=index):
                    self.assertEqual(window.plot_at(plot["center"]), index)
            self.scene.building_window = None

    def test_click_on_open_camp_plot_sends_worker(self):
        window = self._open("lumber_camp")
        self.scene.draw(self.screen)
        self._click(window.plot_geometry()[0]["center"])
        self.assertEqual(self.client.calls, [])
        self.assertEqual(window.pending_worker_action, ("hire", 0))
        self._confirm_worker_action(window)
        self.assertEqual(self.client.calls, [])
        self.assertEqual(self.client.city_calls, [("assign", "lumber_camp", 0, 1)])
        self.scene.draw(self.screen)

    def test_click_on_locked_camp_plot_explains_unlock_level(self):
        window = self._open("lumber_camp")
        self.scene.draw(self.screen)
        self._click(window.plot_geometry()[2]["center"])
        self.assertEqual(self.client.calls, [])
        self.assertIn("Опушка", window.message)
        self.assertIn("3 уровне", window.message)

    def test_click_on_open_farm_field_sends_worker(self):
        window = self._open("wheat_farm")
        self.scene.draw(self.screen)
        self._click(window.plot_geometry()[0]["center"])
        self._confirm_worker_action(window)
        self.assertEqual(self.client.calls, [])
        self.assertEqual(self.client.city_calls, [("assign", "farm", 0, 1)])

    def test_right_click_removes_worker_only_after_confirmation(self):
        window = self._open("wheat_farm")
        window.state = _payload("farm", occupied={0})
        self.scene.draw(self.screen)
        self.scene.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=3, pos=window.plot_geometry()[0]["center"]))
        self.assertEqual(window.pending_worker_action, ("fire", 0))
        self.assertEqual(self.client.calls, [])
        self._confirm_worker_action(window)
        self.assertEqual(self.client.calls, [("farm", "workers/fire", 0)])

    def test_worker_controls_are_not_in_header_and_empty_plot_is_safe(self):
        window = self._open("wheat_farm")
        self.assertFalse(hasattr(window, "remove_worker_button"))
        self.assertFalse(hasattr(window, "add_worker_button"))
        self.scene.draw(self.screen)
        self.scene.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=3, pos=window.plot_geometry()[0]["center"]))
        self.assertIsNone(window.pending_worker_action)
        self.assertEqual(self.client.calls, [])
        self.assertEqual(window.message, "На этом участке нет рабочего")

    def test_hiring_skips_a_citizen_who_is_driving_a_cart(self):
        window = self._open("wheat_farm")
        self.client.citizens[0]["work_status"] = "Ведёт повозку"
        self.client.citizens[1]["work_status"] = "Свободен"

        window.hire_worker(slot_index=0)

        self.assertEqual(self.client.city_calls, [("assign", "farm", 0, 2)])

    def test_work_button_does_not_displace_workers_when_plot_is_full(self):
        window = self._open("wheat_farm")
        window.state = _payload("farm", occupied={0, 1})
        window.selected_plot = 0

        window._work_selected_plot()

        self.assertIsNone(window.pending_worker_action)
        self.assertEqual(window.message, "На участке нет свободных мест.")
        self.assertEqual(self.client.calls, [])

    def test_work_button_requires_confirmation_and_uses_free_slot(self):
        window = self._open("wheat_farm")
        window.state = _payload("farm", occupied={0})
        self.scene.draw(self.screen)
        self._click(window.plot_geometry()[0]["center"])
        self.assertEqual(window.pending_worker_action, ("hire", 1))
        self.scene.draw(self.screen)
        self._click(window.confirm_no_button.center)
        self.assertIsNone(window.pending_worker_action)
        self._click(window.work_button.center)
        self.assertEqual(window.pending_worker_action, ("player", 1))
        self.assertEqual(self.client.calls, [])
        self._confirm_worker_action(window)
        self.assertEqual(self.client.calls, [("farm", "workers/player/toggle", 1)])
        rendered = []
        original_grid_font = self.scene.grid_font

        class Recorder:
            def render(self, text, *args):
                rendered.append(text)
                return original_grid_font.render(text, *args)

            def __getattr__(self, name):
                return getattr(original_grid_font, name)

        self.scene.grid_font = Recorder()
        try:
            self.scene.draw(self.screen)
        finally:
            self.scene.grid_font = original_grid_font
        self.assertIn("ЗАВЕРШИТЬ РАБОТУ", rendered)

    def test_worker_panel_reaches_window_bottom_and_shows_five_workers(self):
        for building, resource in (("wheat_farm", "wheat"), ("lumber_camp", "wood")):
            with self.subTest(building=building):
                window = self._open(building)
                window.state["worker_slots"] = [
                    {
                        "slot_index": index, "occupied": True,
                        "worker_id": f"citizen:{index + 1}",
                        "worker_name": f"Работник {index + 1}",
                        "resources": [resource], "resource_progress_sec": {resource: 0},
                        "timer_sec_by_resource": {resource: 240},
                        "progress_sec": 0, "is_travelling": False,
                    }
                    for index in range(5)
                ]
                self.assertEqual(
                    window.worker_stats_rect().bottom,
                    min(window.rect.bottom, settings.HEIGHT) - 2,
                )
                self.assertGreaterEqual(window.worker_stats_visible_rows(), 5)
                rendered = []
                original_small_font = self.scene.small_font

                class Recorder:
                    def render(self, text, *args):
                        rendered.append(str(text))
                        return original_small_font.render(text, *args)

                    def __getattr__(self, name):
                        return getattr(original_small_font, name)

                self.scene.small_font = Recorder()
                try:
                    window._draw_worker_stats(self.screen)
                finally:
                    self.scene.small_font = original_small_font
                for index in range(5):
                    self.assertIn(f"Работник {index + 1}", rendered)

    def test_work_button_rejects_full_storage(self):
        window = self._open("wheat_farm")
        window.selected_plot = 0
        window.state = _payload("farm", level=3)
        window.state["storage"]["wheat"] = window.state["storage"]["limit"]
        window.state["storage_total"] = window.state["storage"]["limit"]
        self.assertTrue(window.slot_storage_is_full(window.plot_slots(0)))
        self.assertFalse(window.slot_storage_is_full([{"resources": ["flax"]}]))
        self.scene.draw(self.screen)
        self._click(window.work_button.center)
        self.assertEqual(window.message, "Склад переполнен, нельзя начать добычу.")
        self.assertIsNone(window.pending_worker_action)
        self.assertEqual(self.client.calls, [])

    def test_header_shows_hourly_output_and_recalculates_after_worker_removal(self):
        window = self._open("wheat_farm")
        window.state = _payload("farm", occupied={0, 1})
        for slot in window.state["worker_slots"]:
            slot.update(
                resources=["wheat"],
                timer_sec_by_resource={"wheat": 140},
                is_travelling=False,
            )

        self.assertAlmostEqual(window.production_per_hour()["wheat"], 2 * 3600 / 140)
        window.state["worker_slots"][1]["occupied"] = False
        self.assertAlmostEqual(window.production_per_hour()["wheat"], 3600 / 140)

        rendered = []
        original_small, original_font = self.scene.small_font, self.scene.font

        class Recorder:
            def __init__(self, font):
                self.font = font

            def render(self, text, *args):
                rendered.append(str(text))
                return self.font.render(text, *args)

            def __getattr__(self, name):
                return getattr(self.font, name)

        self.scene.small_font = Recorder(original_small)
        self.scene.font = Recorder(original_font)
        try:
            self.scene.draw(self.screen)
        finally:
            self.scene.small_font = original_small
            self.scene.font = original_font
        self.assertIn("Производство в час:", rendered)
        self.assertIn("Пшеница 25,7 ед./ч", rendered)

    def test_worker_table_shows_unit_countdowns_without_personal_totals(self):
        window = self._open("wheat_farm")
        window.state = _payload("farm", occupied={0})
        slot = window.state["worker_slots"][0]
        slot.update(
            worker_id="player:1", worker_name="Игрок", is_player=True,
            resources=["wheat"], progress_sec=113,
            resource_progress_sec={"wheat": 113},
            timer_sec_by_resource={"wheat": 140},
            harvest_bonus={"wheat": 20},
        )
        window.state["player_work"] = {
            "slot_index": 0, "resource": "wheat", "resources": ["wheat"],
            "timer_sec": 140, "progress_sec": 113, "seconds_to_next": 27,
        }
        window.selected_plot = 0
        self.assertEqual(window.worker_stats_rect().width, window.LEFT_COLUMN - 20)
        self.assertEqual(
            window.worker_stats_rect().bottom,
            min(window.rect.bottom, settings.HEIGHT) - 2,
        )
        self.assertGreaterEqual(window.plots_area().left, window.worker_stats_rect().right)

        rendered = []
        rendered_colors = {}
        rendered_fonts = {}
        original_small, original_grid = self.scene.small_font, self.scene.grid_font

        class Recorder:
            def __init__(self, font, label):
                self.font = font
                self.label = label

            def render(self, text, *args):
                rendered.append(text)
                rendered_fonts[str(text)] = self.label
                if len(args) > 1:
                    rendered_colors[text] = args[1]
                return self.font.render(text, *args)

            def __getattr__(self, name):
                return getattr(self.font, name)

        self.scene.small_font = Recorder(original_small, "small")
        self.scene.grid_font = Recorder(original_grid, "grid")
        try:
            self.scene.draw(self.screen)
        finally:
            self.scene.small_font = original_small
            self.scene.grid_font = original_grid
        self.assertIn("Игрок", rendered)
        self.assertIn("+20% Пшеница", rendered)
        self.assertEqual(rendered_colors["+20% Пшеница"], (117, 225, 128))
        self.assertIn("Пшеница 0:27", rendered)
        self.assertEqual(rendered_fonts["+20% Пшеница"], "small")
        self.assertEqual(rendered_fonts["Пшеница 0:27"], "small")
        self.assertEqual(rendered_fonts["Игрок"], "small")
        self.assertNotIn("Всего:", rendered)
        self.assertNotIn("Пшеница: 14", rendered)
        self.assertFalse(any("За цикл" in text for text in rendered))

    def test_farm_upgrade_tab_lists_level_one_improvements(self):
        window = self._open("wheat_farm")
        window.tab = "upgrade"
        window.state["farm_upgrades"] = {
            "completed": {
                "ration": False, "wooden_plough": False,
                "farm_level_2": False, "ration_level_2": False, "wooden_handle": False,
            },
            "ration_plots": [], "wooden_plough": False, "wooden_handle": False,
            "active_upgrade_id": None,
            "seconds_left": 0,
        }
        window.state["warehouse_storage"] = {"wood": 100}
        window.state["treasury_silver_available"] = 100
        rendered = []
        original_small, original_font = self.scene.small_font, self.scene.font

        class Recorder:
            def __init__(self, font):
                self.font = font

            def render(self, text, *args):
                rendered.append(str(text))
                return self.font.render(text, *args)

            def __getattr__(self, name):
                return getattr(self.font, name)

        self.scene.small_font = Recorder(original_small)
        self.scene.font = Recorder(original_font)
        try:
            self.scene.draw(self.screen)
        finally:
            self.scene.small_font = original_small
            self.scene.font = original_font

        for name in (
            "Самозахват", "Усиленный деревянный плуг", "Улучшить Крестьянское поселение",
        ):
            self.assertTrue(any(name in text for text in rendered))
        self.assertFalse(any("Раздать пай" in text for text in rendered))
        self.assertFalse(any("Деревянная рукоять" in text for text in rendered))
        self.assertIn("Время улучшения: 30 мин", rendered)
        self.assertEqual(rendered.count("Время улучшения: 1 ч 0 мин"), 1)
        self.assertIn("Время улучшения: 2 ч 0 мин", rendered)
        self.assertEqual(rendered.count("НАЧАТЬ"), 2)
        self.assertEqual(set(window.farm_upgrade_buttons), {"ration", "wooden_plough"})

    def test_farm_upgrade_tab_lists_level_two_improvements(self):
        window = self._open("wheat_farm")
        window.tab = "upgrade"
        window.state["level"] = 2
        window.state["farm_upgrades"] = {
            "completed": {
                "ration": True, "wooden_plough": True, "farm_level_2": True,
                "ration_level_2": False, "wooden_handle": False,
            },
            "ration_plots": [0], "wooden_plough": True, "wooden_handle": False,
            "active_upgrade_id": None, "seconds_left": 0,
        }
        window.state["warehouse_storage"] = {"wood": 100}
        window.state["treasury_silver_available"] = 100
        rendered = []
        original_small, original_font = self.scene.small_font, self.scene.font

        class Recorder:
            def __init__(self, font):
                self.font = font

            def render(self, text, *args):
                rendered.append(str(text))
                return self.font.render(text, *args)

            def __getattr__(self, name):
                return getattr(self.font, name)

        self.scene.small_font = Recorder(original_small)
        self.scene.font = Recorder(original_font)
        try:
            self.scene.draw(self.screen)
        finally:
            self.scene.small_font = original_small
            self.scene.font = original_font

        self.assertTrue(any("Раздать пай" in text for text in rendered))
        self.assertTrue(any("Деревянная рукоять" in text for text in rendered))
        self.assertFalse(any("Самозахват" in text for text in rendered))
        self.assertFalse(any("Усиленный деревянный плуг" in text for text in rendered))
        self.assertEqual(set(window.farm_upgrade_buttons), {"ration_level_2", "wooden_handle"})

    def test_lumber_camp_upgrade_tab_shows_three_chain_cards(self):
        window = self._open("lumber_camp")
        window.tab = "upgrade"
        window.state["level"] = 1
        window.state["lumber_camp_upgrades"] = {
            "completed": {
                "logging_expansion": False, "strong_handle": False,
                "lumber_camp_level_2": False,
            },
            "bonus_plots": [], "strong_handle": False,
            "active_upgrade_id": None, "seconds_left": 0,
        }
        window.state["warehouse_storage"] = {"wood": 300}
        window.state["treasury_silver_available"] = 100
        rendered = []
        original_small, original_font = self.scene.small_font, self.scene.font

        class Recorder:
            def __init__(self, font):
                self.font = font

            def render(self, text, *args):
                rendered.append(str(text))
                return self.font.render(text, *args)

            def __getattr__(self, name):
                return getattr(self.font, name)

        self.scene.small_font = Recorder(original_small)
        self.scene.font = Recorder(original_font)
        try:
            self.scene.draw(self.screen)
        finally:
            self.scene.small_font = original_small
            self.scene.font = original_font

        for name in ("Расширение вырубки", "Усиленная рукоять", "Улучшить лесопилку"):
            self.assertTrue(any(name in text for text in rendered))
        self.assertIn("Результат: +1 место на первом участке древесины", rendered)
        self.assertIn("Результат: +8% к скорости вырубки", rendered)
        self.assertIn("Результат: Лесопилка — уровень 2", rendered)
        self.assertIn("Время улучшения: 40 мин", rendered)
        self.assertIn("Казна: 100/50 серебра", rendered)
        self.assertIn("Казна: 100/70 серебра", rendered)
        self.assertIn("300/300 древесины", rendered)
        self.assertIn("Время улучшения: 1 ч 0 мин", rendered)
        self.assertIn("Время улучшения: 2 ч 20 мин", rendered)
        self.assertEqual(set(window.building_upgrade_buttons), {"logging_expansion", "strong_handle"})
        self.assertEqual(rendered.count("СНАЧАЛА ПРЕДЫДУЩИЕ"), 1)

        with patch.object(window, "_request") as request:
            self.scene.handle_event(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, button=1,
                pos=window.building_upgrade_buttons["logging_expansion"].center,
            ))
        request.assert_called_once_with(
            "lumber-camp/upgrade", {"upgrade_id": "logging_expansion"},
        )

        window.state["level"] = 2
        window.state["lumber_camp_upgrades"]["completed"] = {
            "logging_expansion": True, "strong_handle": True,
            "lumber_camp_level_2": True,
        }
        rendered.clear()
        self.scene.small_font = Recorder(original_small)
        self.scene.font = Recorder(original_font)
        try:
            self.scene.draw(self.screen)
        finally:
            self.scene.small_font = original_small
            self.scene.font = original_font
        self.assertEqual(rendered.count("УСТАНОВЛЕНО"), 3)
        self.assertEqual(window.building_upgrade_buttons, {})

    def test_level_two_ration_slot_is_attached_to_second_wheat_field(self):
        window = self._open("wheat_farm")
        window.state = _payload("farm", level=2)
        window.state["farm_upgrades"] = {"ration_plots": [0, 1]}
        window.state["worker_slots"].extend([
            {"slot_index": 1000, "resource": "wheat", "resources": ["wheat"], "occupied": False},
            {"slot_index": 1001, "resource": "wheat", "resources": ["wheat"], "occupied": False},
        ])

        first_field = window.plot_slots(0)
        second_field = window.plot_slots(1)

        self.assertEqual([slot["slot_index"] for slot in first_field], [0, 1, 1000])
        self.assertEqual([slot["slot_index"] for slot in second_field], [2, 3, 1001])

    def test_travelling_citizen_shows_arrival_eta_not_production_timer(self):
        window = self._open("lumber_camp")
        window.state = _payload("lumber_camp", occupied={0})
        slot = window.state["worker_slots"][0]
        slot.update(
            worker_id="citizen:17", worker_name="Горожанин 5",
            resources=["wood"], resource="wood", is_travelling=True,
            travel_seconds_left=1080, resource_progress_sec={"wood": 0},
        )
        rendered = []
        original = self.scene.grid_font

        class Recorder:
            def render(self, text, *args):
                rendered.append(text)
                return original.render(text, *args)

            def __getattr__(self, name):
                return getattr(original, name)

        self.scene.grid_font = Recorder()
        try:
            window.selected_plot = 0
            with patch("ui.production_building_window.time.monotonic",
                       return_value=window.received_at):
                self.scene.draw(self.screen)
        finally:
            self.scene.grid_font = original

        self.assertIn("В пути к объекту · прибытие через 18:00", rendered)
        self.assertFalse(any(text.startswith("Древесина ") for text in rendered))

    def test_storage_tab_uses_only_shared_stock_and_unlocked_resources(self):
        window = self._open("wheat_farm")
        window.tab = "storage"
        window.state = _payload("farm")
        window.state["storage"] = {"wheat": 5, "limit": 500}
        window.state["storage_depositable"] = {
            "wheat": {"item_id": 63, "in_backpack": 0, "max_deposit": 0}
        }
        self.scene.draw(self.screen)
        self.assertEqual(set(window.storage_withdraw_buttons), {"wheat"})
        self.assertFalse(hasattr(window, "claim_buttons"))

    def test_production_storage_can_withdraw_common_stock(self):
        window = self._open("wheat_farm")
        window.state = _payload("farm")
        window.state["storage"]["wheat"] = 20
        window.state["storage_depositable"] = {
            "wheat": {"item_id": 63, "in_backpack": 0, "max_deposit": 0}
        }
        window.tab = "storage"
        self.scene.draw(self.screen)
        self.assertIn("wheat", window.storage_withdraw_buttons)
        self._click(window.storage_withdraw_buttons["wheat"].center)
        self.assertEqual(window.contribution_dialog.mode, "withdraw")

        with patch.object(window.contribution_dialog, "handle_event",
                          return_value=(("storage_withdraw", "wheat"), 5)):
            window.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(0, 0)))

        self.assertEqual(self.client.calls, [("farm", "storage/withdraw", None)])
        self.assertEqual(self.client.last_payload, {"resource": "wheat", "quantity": 5})

    def test_production_storage_can_deposit_backpack_resources(self):
        window = self._open("wheat_farm")
        window.state = _payload("farm")
        window.state["storage_depositable"] = {
            "wheat": {"item_id": 63, "in_backpack": 8, "max_deposit": 8}
        }
        window.tab = "storage"
        self.scene.draw(self.screen)
        self.assertIn("wheat", window.storage_deposit_buttons)
        self._click(window.storage_deposit_buttons["wheat"].center)
        self.assertEqual(window.contribution_dialog.mode, "deposit")

        with patch.object(window.contribution_dialog, "handle_event",
                          return_value=(("storage", "wheat"), 6)):
            window.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(0, 0)))

        self.assertEqual(self.client.calls, [("farm", "storage/deposit", None)])
        self.assertEqual(self.client.last_payload, {"resource": "wheat", "quantity": 6})

    def test_upgrade_button_spends_shared_storage_directly(self):
        window = self._open("lumber_camp")
        window.tab = "upgrade"
        self.scene.draw(self.screen)
        self.assertEqual(window.deposit_buttons, {})
        self._click(window.upgrade_button.center)
        self.assertEqual(self.client.calls, [("lumber_camp", "upgrade/start", None)])

    def test_rift_mines_draw_and_respond_to_clicks(self):
        window = self._open("mountain_rift")
        for tab in ("production", "storage", "upgrade"):
            window.tab = tab
            self.scene.draw(self.screen)
        window.tab = "production"
        self.assertEqual([group["kind"] for group in window.groups], ["iron_mine", "stone_mine", "mithril_mine", "obsidian_mine"])
        self.assertEqual([group["places"] for group in window.groups], [10, 6, 6, 3])
        geometry = window.plot_geometry()
        self._click(geometry[0]["center"])
        self._confirm_worker_action(window)
        self.assertEqual(self.client.city_calls, [("assign", "mountain_rift", 0, 1)])
        self.assertEqual(self.client.calls, [])
        self._click(geometry[1]["center"])
        self.assertEqual(window.message, "Прииск камня откроется на 2 уровне")

    def test_barnyard_pen_grows_and_hires(self):
        window = self._open("barnyard")
        for tab in ("production", "storage", "upgrade"):
            window.tab = tab
            self.scene.draw(self.screen)
        window.tab = "production"
        small = window.plot_geometry()[0]["rect"].copy()
        self._click(small.center)
        self._confirm_worker_action(window)
        self.assertEqual(self.client.city_calls, [("assign", "barnyard", 0, 1)])
        self.assertEqual(self.client.calls, [])
        window.state = _payload("barnyard", level=10, occupied=set(range(10)))
        self.scene.draw(self.screen)
        big = window.plot_geometry()[0]["rect"]
        self.assertGreater(big.width * big.height, small.width * small.height * 10)
        self.assertTrue(window.plots_area().contains(big))

    def test_black_pit_digs_and_gem_description(self):
        window = self._open("black_pit")
        for tab in ("production", "storage", "upgrade"):
            window.tab = tab
            self.scene.draw(self.screen)
        window.tab = "production"
        self.assertNotIn("Шанс", window.production_desc(1))
        self.assertIn("шанс 0.43% на каждую добытую единицу угля", window.production_desc(3))
        self.assertIn("100%", window.production_desc(3))
        self.assertIn("алмаз 8%", window.production_desc(10))
        geometry = window.plot_geometry()
        self.assertEqual(len(geometry), 10)
        # Самая большая копанка — на 6 мест (10 уровень)
        self.assertEqual(max(range(10), key=lambda index: geometry[index]["rect"].width), 9)
        self._click(geometry[0]["center"])
        self._confirm_worker_action(window)
        self.assertEqual(self.client.city_calls, [("assign", "black_pit", 0, 1)])
        self.assertEqual(self.client.calls, [])
        self._click(geometry[1]["center"])
        self.assertEqual(window.message, "Копанка (уголь) откроется на 2 уровне")
        # Все 4 стадии вагонетки рисуются
        for stage in range(4):
            window._draw_cart(self.screen, (400, 400), 60, stage)

    def test_escape_closes_window(self):
        self._open("lumber_camp")
        self.scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertIsNone(self.scene.building_window)

    def test_player_cannot_leave_building_while_working(self):
        window = self._open("lumber_camp")
        window.state["worker_slots"][0].update(
            occupied=True, worker_id="player:1", is_player=True,
        )
        self.assertTrue(window.player_is_working())

        self.scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertIs(self.scene.building_window, window)
        self._click(window.close_button.center)
        self.assertIs(self.scene.building_window, window)
        self.assertTrue(window.is_open)

        rendered = []
        original_small_font = self.scene.small_font

        class Recorder:
            def render(self, text, *args):
                rendered.append(text)
                return original_small_font.render(text, *args)

            def __getattr__(self, name):
                return getattr(original_small_font, name)

        self.scene.small_font = Recorder()
        pygame.mouse.set_pos(window.close_button.center)
        try:
            self.scene.draw(self.screen)
        finally:
            self.scene.small_font = original_small_font
        self.assertIn("ПОКИНУТЬ", rendered)
        self.assertIn("Чтобы покинуть место, завершите работу.", rendered)


if __name__ == "__main__":
    unittest.main()
