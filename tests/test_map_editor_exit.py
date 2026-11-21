import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from client import map_drafts
from core.map_catalog import catalog_definitions
from scenes import map_editor_scene as scene_module
from scenes.map_editor_scene import MapEditorScene
from scenes.map_editor_ui import ExitDialog
from client.map_editor_state import MapEditorState


def key(code, text=""):
    return pygame.event.Event(pygame.KEYDOWN, key=code, mod=0, unicode=text, scancode=0)


def scan_key(code, scancode, text=""):
    """Клавиша с физической позицией: на русской раскладке key даёт кириллицу, скан-код остаётся латинским."""
    return pygame.event.Event(pygame.KEYDOWN, key=code, mod=0, unicode=text, scancode=scancode)


def click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)


class MapEditorExitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1920, 1080))

    def setUp(self):
        self.scene = MapEditorScene(None, catalog_definitions(), lambda: False)
        self.scene.has_map = True
        self.scene.state = MapEditorState(self.scene.catalog, [], 16, 16)
        self.scene.state.name = "Тест"

    def make_dirty(self):
        self.scene.state.dirty = True

    def choice_center(self, code):
        for choice_code, rect, _label in self.scene.exit_dialog.choices():
            if choice_code == code:
                return rect.center
        self.fail(f"нет кнопки {code}")

    def test_escape_without_changes_closes_at_once(self):
        self.assertTrue(self.scene.handle_event(key(pygame.K_ESCAPE)))
        self.assertIsNone(self.scene.exit_dialog)

    def test_escape_with_changes_asks_instead_of_closing(self):
        self.make_dirty()
        self.assertFalse(self.scene.handle_event(key(pygame.K_ESCAPE)))
        self.assertIsNotNone(self.scene.exit_dialog)

    def test_escape_in_the_dialog_stays_in_the_editor(self):
        self.make_dirty()
        self.scene.handle_event(key(pygame.K_ESCAPE))
        self.assertFalse(self.scene.handle_event(key(pygame.K_ESCAPE)))
        self.assertIsNone(self.scene.exit_dialog)

    def test_window_close_also_asks_first(self):
        self.make_dirty()
        self.assertFalse(self.scene.handle_event(pygame.event.Event(pygame.QUIT)))
        self.assertIsNotNone(self.scene.exit_dialog)
        self.assertFalse(self.scene.handle_event(pygame.event.Event(pygame.QUIT)))
        self.assertIsNotNone(self.scene.exit_dialog)

    def test_discard_needs_a_second_confirmation(self):
        self.make_dirty()
        self.scene.handle_event(key(pygame.K_ESCAPE))
        self.assertFalse(self.scene.handle_event(click(self.choice_center("discard"))))
        self.assertTrue(self.scene.exit_dialog.confirming)
        self.assertTrue(self.scene.handle_event(key(pygame.K_RETURN)))

    def test_escape_on_the_confirmation_goes_back_to_the_choices(self):
        self.make_dirty()
        self.scene.handle_event(key(pygame.K_ESCAPE))
        self.scene.handle_event(click(self.choice_center("discard")))
        self.assertFalse(self.scene.handle_event(key(pygame.K_ESCAPE)))
        self.assertIsNotNone(self.scene.exit_dialog)
        self.assertFalse(self.scene.exit_dialog.confirming)

    def test_cancel_button_keeps_the_editor_open(self):
        self.make_dirty()
        self.scene.handle_event(key(pygame.K_ESCAPE))
        self.assertFalse(self.scene.handle_event(click(self.choice_center("cancel"))))
        self.assertIsNone(self.scene.exit_dialog)
        self.assertTrue(self.scene._dirty())

    def test_click_outside_the_dialog_cancels_it(self):
        self.make_dirty()
        self.scene.handle_event(key(pygame.K_ESCAPE))
        self.assertFalse(self.scene.handle_event(click((2, 2))))
        self.assertIsNone(self.scene.exit_dialog)

    def test_save_and_exit_closes_after_a_successful_save(self):
        self.make_dirty()
        self.scene.handle_event(key(pygame.K_ESCAPE))
        with patch.object(map_drafts, "list_drafts", return_value=[]), \
                patch.object(self.scene, "_write_draft", return_value=None) as write:
            self.assertFalse(self.scene.handle_event(key(pygame.K_RETURN)))
            self.assertIsNotNone(self.scene.save_dialog)
            self.assertTrue(self.scene.handle_event(key(pygame.K_RETURN, "\r")))
        write.assert_called_once_with("Тест", None)

    def test_failed_save_keeps_the_save_dialog_open(self):
        self.make_dirty()
        self.scene.handle_event(key(pygame.K_ESCAPE))
        with patch.object(map_drafts, "list_drafts", return_value=[]), \
                patch.object(self.scene, "_write_draft", return_value="нет места"):
            self.scene.handle_event(key(pygame.K_RETURN))
            self.assertFalse(self.scene.handle_event(key(pygame.K_RETURN)))
        self.assertIsNotNone(self.scene.save_dialog)
        self.assertEqual(self.scene.save_dialog.message, "нет места")

    def test_cancelling_the_save_returns_to_the_exit_question(self):
        self.make_dirty()
        self.scene.handle_event(key(pygame.K_ESCAPE))
        with patch.object(map_drafts, "list_drafts", return_value=[]):
            self.scene.handle_event(key(pygame.K_RETURN))
            self.assertFalse(self.scene.handle_event(key(pygame.K_ESCAPE)))
        self.assertIsNone(self.scene.save_dialog)
        self.assertIsNotNone(self.scene.exit_dialog)
        self.assertFalse(self.scene.exit_after_save)

    def test_plain_save_dialog_cancel_does_not_exit(self):
        self.make_dirty()
        with patch.object(map_drafts, "list_drafts", return_value=[]):
            self.scene.save()
            self.assertFalse(self.scene.handle_event(key(pygame.K_ESCAPE)))
        self.assertIsNone(self.scene.save_dialog)
        self.assertIsNone(self.scene.exit_dialog)

    def test_dialog_draws_both_steps(self):
        screen = pygame.display.get_surface()
        self.make_dirty()
        self.scene.handle_event(key(pygame.K_ESCAPE))
        self.scene.draw(screen)
        self.scene.handle_event(click(self.choice_center("discard")))
        self.scene.draw(screen)
        self.assertIsInstance(self.scene.exit_dialog, ExitDialog)


def ctrl_key(code, scancode, shift=False):
    mod = pygame.KMOD_LCTRL | (pygame.KMOD_LSHIFT if shift else 0)
    return pygame.event.Event(pygame.KEYDOWN, key=code, mod=mod, unicode="", scancode=scancode)


def wheel(steps):
    return pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=steps)


class MapEditorCtrlShortcutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1920, 1080))

    def setUp(self):
        self.scene = MapEditorScene(None, catalog_definitions(), lambda: False)
        self.scene.has_map = True
        self.scene.state = MapEditorState(self.scene.catalog, [], 16, 16)
        self.ground_key = next(item["item_key"] for item in self.scene.catalog if item["kind"] == "ground")
        self.scene.state.ground[(2, 2)] = self.ground_key
        self.scene.state.select(2, 2, 3, 3)

    def test_ctrl_c_copies_selection_on_russian_layout(self):
        # На русской раскладке физическая клавиша C даёт key=1089 («с»), скан-код остаётся KSCAN_C.
        self.scene.handle_event(ctrl_key(1089, pygame.KSCAN_C))
        self.assertIsNotNone(self.scene.stamp)
        self.assertEqual(self.scene.stamp["ground"], [(0, 0, self.ground_key)])

    def test_ctrl_v_switches_to_stamp_on_russian_layout(self):
        self.scene.handle_event(ctrl_key(1089, pygame.KSCAN_C))
        self.scene.handle_event(ctrl_key(1084, pygame.KSCAN_V))
        self.assertEqual(self.scene.tool, "stamp")

    def test_ctrl_shift_z_redoes_and_ctrl_z_undoes(self):
        self.assertEqual(scene_module._ctrl_command(ctrl_key(122, pygame.KSCAN_Z, shift=True)), "redo")
        self.assertEqual(scene_module._ctrl_command(ctrl_key(122, pygame.KSCAN_Z)), "undo")


class MapEditorToolWheelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1920, 1080))

    def setUp(self):
        self.scene = MapEditorScene(None, catalog_definitions(), lambda: False)
        self.scene.has_map = True
        self.scene.state = MapEditorState(self.scene.catalog, [], 16, 16)
        self.ground_key = next(item["item_key"] for item in self.scene.catalog if item["kind"] == "ground")
        grid = self.scene.grid_rect()
        self.grid_pos = (grid.x + self.scene.zoom // 2, grid.y + self.scene.zoom // 2)

    def scroll(self, steps, pos=None, mods=0):
        with patch.object(pygame.mouse, "get_pos", return_value=pos or self.grid_pos), patch.object(pygame.key, "get_mods", return_value=mods):
            self.scene.handle_event(wheel(steps))

    def test_wheel_over_grid_cycles_tools(self):
        self.scroll(1)
        self.assertEqual(self.scene.tool, "fill")
        self.scroll(1)
        self.assertEqual(self.scene.tool, "erase")
        self.scroll(-1)
        self.assertEqual(self.scene.tool, "fill")

    def test_wheel_skips_stamp_without_buffer(self):
        self.scene.tool = "select"
        self.scroll(1)
        self.assertEqual(self.scene.tool, "brush")

    def test_wheel_reaches_stamp_when_buffer_is_filled(self):
        self.scene.stamp = {"ground": [(0, 0, self.ground_key)]}
        self.scene.tool = "select"
        self.scroll(1)
        self.assertEqual(self.scene.tool, "stamp")

    def test_ctrl_wheel_zooms_and_keeps_tool(self):
        zoom = self.scene.zoom
        self.scroll(1, mods=pygame.KMOD_LCTRL)
        self.assertEqual(self.scene.tool, "brush")
        self.assertNotEqual(self.scene.zoom, zoom)

    def test_wheel_over_toolbar_keeps_tool(self):
        self.scroll(1, pos=(300, scene_module.MENU_H + 10))
        self.assertEqual(self.scene.tool, "brush")

    def test_e_key_selects_eraser(self):
        self.scene.handle_event(scan_key(pygame.K_e, pygame.KSCAN_E))
        self.assertEqual(self.scene.tool, "erase")

    def test_e_key_selects_eraser_on_russian_layout(self):
        self.scene.handle_event(scan_key(1091, pygame.KSCAN_E, text="у"))
        self.assertEqual(self.scene.tool, "erase")

    def test_left_click_with_eraser_removes_tile(self):
        self.scene.state.ground[(0, 0)] = self.ground_key
        self.scene.tool = "erase"
        self.scene.handle_event(click(self.grid_pos))
        self.scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=self.grid_pos))
        self.assertNotIn((0, 0), self.scene.state.ground)

    def test_cursor_follows_tool_over_grid(self):
        self.scene.hover = (0, 0)
        for tool in ("brush", "fill", "erase", "select"):
            self.scene.tool = tool
            self.assertEqual(self.scene._cursor_kind(), tool)

    def test_cursor_is_arrow_outside_grid_and_other_sections(self):
        self.scene.tool = "erase"
        self.scene.hover = None
        self.assertEqual(self.scene._cursor_kind(), "arrow")
        self.scene.hover = (0, 0)
        self.scene.section = "npc"
        self.assertEqual(self.scene._cursor_kind(), "arrow")


class MapEditorHotkeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1920, 1080))

    def setUp(self):
        self.scene = MapEditorScene(None, catalog_definitions(), lambda: False)
        self.scene.has_map = True
        self.scene.state = MapEditorState(self.scene.catalog, [], 16, 16)

    def test_brush_size_brackets_work_on_russian_layout(self):
        self.scene.brush_size = 3
        self.scene.handle_event(scan_key(1098, pygame.KSCAN_RIGHTBRACKET, text="ъ"))
        self.assertEqual(self.scene.brush_size, 4)
        self.scene.handle_event(scan_key(1093, pygame.KSCAN_LEFTBRACKET, text="х"))
        self.assertEqual(self.scene.brush_size, 3)

    def test_plain_letter_keys_use_physical_position(self):
        self.scene.handle_event(scan_key(1072, pygame.KSCAN_F, text="а"))
        self.assertEqual(self.scene.tool, "fill")
        self.scene.handle_event(scan_key(1084, pygame.KSCAN_V, text="м"))
        self.assertEqual(self.scene.tool, "select")
        grid = self.scene.show_grid
        self.scene.handle_event(scan_key(1087, pygame.KSCAN_G, text="п"))
        self.assertNotEqual(self.scene.show_grid, grid)

    def test_plain_letter_key_on_latin_layout_still_works(self):
        self.scene.handle_event(scan_key(pygame.K_f, pygame.KSCAN_F, text="f"))
        self.assertEqual(self.scene.tool, "fill")

    def test_click_inside_selection_starts_new_selection(self):
        self.scene.tool = "select"
        self.scene.state.select(2, 2, 4, 4)
        self.scene._grid_primary((3, 3))
        self.assertEqual(self.scene.drag["mode"], "select")
        self.assertEqual(self.scene.state.selection, (3, 3, 3, 3))

    def test_shift_click_inside_selection_moves_it(self):
        self.scene.tool = "select"
        self.scene.state.select(2, 2, 4, 4)
        self.scene._grid_primary((3, 3), shift=True)
        self.assertEqual(self.scene.drag["mode"], "move")
