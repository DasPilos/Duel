from pathlib import Path
import math
import time
import pygame
from core import settings
from core.carry_weight import character_movement_speed_multiplier
from core.player_movement import find_tile_path, follow_path
from core.currency import Currency
from core.cart_progress import CART_GRADES
from client.network import ServerError
from scenes.city.buildings import CityBuildingsMixin
from scenes.city.rendering import CityRenderMixin, build_citizen_house_lots
from scenes.city.modals import CityModalsMixin, WORKSHOP_TABS
from scenes.city.hud import CityHudMixin
from ui.city_storage_window import CityStorageWindow
from ui.castle_window import CastleWindow
from ui.stable_window import StableWindow
from ui.character_profile_overlay import CharacterProfileOverlay
from ui.chat import ChatPanel
from ui.afk_presence import draw_afk_players


class CityScene(CityBuildingsMixin, CityRenderMixin, CityModalsMixin, CityHudMixin):
    CITY_POPULATION_REFRESH_SECONDS = 10.0

    """
    РЎС†РµРЅР° Р»РѕРєР°С†РёРё Р“РѕСЂРѕРґР° Р Р°РґР±СѓСЂРі (Р“РѕСЂРѕРґ РЎРІРµС‚Р°).
    Р Р°Р·РјРµСЂ СЃРµС‚РєРё: 100С…100 С‚Р°Р№Р»РѕРІ (3200С…3200 px).
    РўР°Р№Р»: 32С…32 РїРёРєСЃРµР»СЏ.

    Р РµР°Р»РёР·Р°С†РёСЏ СЂР°Р·РґРµР»РµРЅР° РЅР° РјРѕРґСѓР»Рё scenes/city/ (РїРѕРґРєР»СЋС‡РµРЅС‹ РєР°Рє РјРёРєСЃРёРЅС‹):
      - buildings.py: РіРµРѕРјРµС‚СЂРёСЏ Рё С…РёС‚Р±РѕРєСЃС‹ Р·РґР°РЅРёР№ (CityBuildingsMixin).
      - rendering.py: РѕС‚СЂРёСЃРѕРІРєР° Р·РґР°РЅРёР№, СЃС‚РµРЅ/РІРѕСЂРѕС‚, РїРµСЂСЃРѕРЅР°Р¶Р° (CityRenderMixin).
      - modals.py: РјРѕРґР°Р»СЊРЅС‹Рµ РѕРєРЅР°-Р·Р°РіР»СѓС€РєРё Р·РґР°РЅРёР№ (CityModalsMixin).
      - hud.py: HUD Рё РѕРєРЅРѕ Р°РєС‚РёРІРЅРѕРіРѕ РѕР±СЉРµРєС‚Р° (CityHudMixin).

    РљР»СЋС‡РµРІС‹Рµ РѕР±СЉРµРєС‚С‹:
      1. РљСЂРёСЃС‚Р°Р»Р» Р–РёР·РЅРё: РІ С†РµРЅС‚СЂРµ РїР»РѕС‰Р°РґРё (РєРІР°РґСЂР°С‚ 3С…3 С‚Р°Р№Р»Р° = 9 С‚Р°Р№Р»РѕРІ, X: 49..51, Y: 49..51).
         РўРѕС‡РєР° РІРѕР·СЂРѕР¶РґРµРЅРёСЏ РїРµСЂСЃРѕРЅР°Р¶Р° РїРѕСЃР»Рµ РіРёР±РµР»Рё (РІРјРµСЃС‚Рѕ С‚Р°РІРµСЂРЅС‹).
      2. Р“Р»Р°РІРЅС‹Р№ Р·Р°РјРѕРє: С†РµРЅС‚СЂ РЅР° РєРѕРѕСЂРґРёРЅР°С‚Р°С… 75/70, СЂР°Р·РјРµСЂ 15С…15 С‚Р°Р№Р»РѕРІ (X: 68..82, Y: 63..77), РІС…РѕРґ СЃ СЋРіР°.
         Р—Р°РіР»СѓС€РєР° СЃ РјРѕРґР°Р»СЊРЅС‹Рј РјРµРЅСЋ Рё РєРЅРѕРїРєРѕР№ "Р’РµСЂРЅСѓС‚СЊСЃСЏ РІ РіРѕСЂРѕРґ".
      3. Р“РѕСЂРѕРґСЃРєР°СЏ РўР°РІРµСЂРЅР°: РґРІСѓС…СЌС‚Р°Р¶РЅР°СЏ 10С…7 С‚Р°Р№Р»РѕРІ (РІРµСЂС…РЅРёР№ СѓРіРѕР» 55/12, РЅРёР¶РЅРёР№ 55/18), РІС…РѕРґ РЅР° 55/15.
      4. Р“РѕСЂРѕРґСЃРєРѕР№ РђРјР±Р°СЂ: 12С…10 С‚Р°Р№Р»РѕРІ (X: 5..16, Y: 35..44), РІС…РѕРґ РЅР° 16/40. РҐСЂР°РЅРёР»РёС‰Рµ РїСЂРѕРІРёР·РёРё.
      5. Р“РѕСЂРѕРґСЃРєРѕР№ РЎРєР»Р°Рґ: 12С…10 С‚Р°Р№Р»РѕРІ (X: 5..16, Y: 18..27), РІС…РѕРґ РЅР° 16/23. РҐСЂР°РЅРёР»РёС‰Рµ РјР°С‚РµСЂРёР°Р»РѕРІ.
      6. Р“РѕСЂРѕРґСЃРєР°СЏ РљСѓР·РЅРёС†Р°: 9С…7 С‚Р°Р№Р»РѕРІ (X: 23..31, Y: 25..31), РІС…РѕРґ РЅР° 23/28. РљРѕРІРєР° РѕСЂСѓР¶РёСЏ РґР»СЏ РёРіСЂРѕРєРѕРІ Рё РіР°СЂРЅРёР·РѕРЅР°.
      7. Р“РѕСЂРѕРґСЃРєР°СЏ РњР°СЃС‚РµСЂСЃРєР°СЏ: 9С…7 С‚Р°Р№Р»РѕРІ (X: 23..31, Y: 13..19), РІС…РѕРґ РЅР° 23/16. РР·РіРѕС‚РѕРІР»РµРЅРёРµ Р±СЂРѕРЅРё РґР»СЏ РёРіСЂРѕРєРѕРІ Рё РіР°СЂРЅРёР·РѕРЅР°.
      8. Р“РѕСЂРѕРґСЃРєРёРµ РљР°Р·Р°СЂРјС‹: 9С…13 С‚Р°Р№Р»РѕРІ (X: 80..88, Y: 31..43), РІС…РѕРґ РЅР° 84/43. РЎРѕРґРµСЂР¶Р°РЅРёРµ РіР°СЂРЅРёР·РѕРЅР° Рё СЃРѕР»РґР°С‚.
      9. РРЅР¶РµРЅРµСЂРЅР°СЏ РїР°Р»Р°С‚Р°: 10С…8 С‚Р°Р№Р»РѕРІ (X: 35..44, Y: 12..19), РІС…РѕРґ РЅР° 44/15. РџСЂРѕРёР·РІРѕРґСЃС‚РІРѕ РѕР±РѕСЂРѕРЅРЅС‹С… СЃРѕРѕСЂСѓР¶РµРЅРёР№ Рё РјР°С€РёРЅ (РєР°С‚Р°РїСѓР»СЊС‚Р°, С‚Р°СЂР°РЅ, С‚СЂРµР±СѓС€РµС‚).
      10. Р“РѕСЂРѕРґСЃРєРѕР№ РЈРЅРёРІРµСЂСЃРёС‚РµС‚: 15С…11 С‚Р°Р№Р»РѕРІ (X: 16..30, Y: 84..94), РІС…РѕРґ РЅР° 23/84. РњРµСЃС‚Рѕ РёР·СѓС‡РµРЅРёСЏ РЅРѕРІС‹С… С‚РµС…РЅРѕР»РѕРіРёР№ РіРѕСЂРѕРґР°.
      11. Р’РѕРµРЅРЅР°СЏ Р°РєР°РґРµРјРёСЏ: 10С…7 С‚Р°Р№Р»РѕРІ (X: 10..19, Y: 70..76), РІС…РѕРґ РЅР° 19/73. РћР±СѓС‡РµРЅРёРµ Р±РѕР№С†РѕРІ, РїСЂРѕРєР°С‡РєР° РєР°СЂС‚ Рё С‚Р°Р»Р°РЅС‚РѕРІ СЃРёР»РѕРІРѕР№ Р»РёРЅРёРё.
      12. РЁРєРѕР»Р° СЃС‚РёС…РёР№: 15С…9 С‚Р°Р№Р»РѕРІ (X: 30..44, Y: 62..70), РІС…РѕРґ РЅР° 44/66. РћР±СѓС‡РµРЅРёРµ РјР°РіРёРё Рё РїСЂРѕРєР°С‡РєР° РјР°РіРёС‡РµСЃРєРёС… РєР°СЂС‚.
      13. 4 РІРѕСЂРѕС‚ РіРѕСЂРѕРґР°:
         - Р“Р»Р°РІРЅС‹Рµ РІРѕСЂРѕС‚Р° (Р’РѕСЃС‚РѕРє): 12 С‚Р°Р№Р»РѕРІ РІ С€РёСЂРёРЅСѓ (Y: 44..55)
         - Р®Р¶РЅС‹Рµ РІРѕСЂРѕС‚Р°: 6 С‚Р°Р№Р»РѕРІ РІ С€РёСЂРёРЅСѓ (X: 47..52)
         - РЎРµРІРµСЂРЅС‹Рµ РІРѕСЂРѕС‚Р°: 6 С‚Р°Р№Р»РѕРІ РІ С€РёСЂРёРЅСѓ (X: 47..52)
         - Р—Р°РїР°РґРЅС‹Рµ РІРѕСЂРѕС‚Р°: 6 С‚Р°Р№Р»РѕРІ РІ С€РёСЂРёРЅСѓ (Y: 47..52)
      Р’С‹С…РѕРґ РёР· РіРѕСЂРѕРґР° РѕСЃСѓС‰РµСЃС‚РІР»СЏРµС‚СЃСЏ РРЎРљР›Р®Р§РРўР•Р›Р¬РќРћ РїРµС€РєРѕРј С‡РµСЂРµР· РІРѕСЂРѕС‚Р°.
    """

    def __init__(self, session, gate="east", spawn_pos=None):
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
        self.exit_gate = gate

        # Р Р°Р·РјРµСЂС‹ СЃРµС‚РєРё: 100С…100 С‚Р°Р№Р»РѕРІ
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

        # РўРѕС‡РєРё РїРѕСЏРІР»РµРЅРёСЏ РїСЂРё РІС…РѕРґРµ / РІРѕР·СЂРѕР¶РґРµРЅРёРё:
        # 1. Р“Р»Р°РІРЅС‹Рµ РІРѕСЂРѕС‚Р° (Р’РѕСЃС‚РѕРє, 12 С‚Р°Р№Р»РѕРІ): X=95, Y=50, Р»РёС†РѕРј РЅР° Р—Р°РїР°Рґ
        # 2. РЎРµРІРµСЂРЅС‹Рµ РІРѕСЂРѕС‚Р° (РЎРµРІРµСЂ, 6 С‚Р°Р№Р»РѕРІ): X=50, Y=4, Р»РёС†РѕРј РЅР° Р®Рі
        # 3. Р®Р¶РЅС‹Рµ РІРѕСЂРѕС‚Р° (Р®Рі, 6 С‚Р°Р№Р»РѕРІ): X=50, Y=95, Р»РёС†РѕРј РЅР° РЎРµРІРµСЂ
        # 4. Р—Р°РїР°РґРЅС‹Рµ РІРѕСЂРѕС‚Р° (Р—Р°РїР°Рґ, 6 С‚Р°Р№Р»РѕРІ): X=4, Y=50, Р»РёС†РѕРј РЅР° Р’РѕСЃС‚РѕРє
        # 5. РљСЂРёСЃС‚Р°Р»Р» Р–РёР·РЅРё (Р¦РµРЅС‚СЂ РїР»РѕС‰Р°РґРё, 9 С‚Р°Р№Р»РѕРІ): X=50, Y=53, Р»РёС†РѕРј РЅР° РЎРµРІРµСЂ
        # 6. Р”РІРµСЂСЊ С‚Р°РІРµСЂРЅС‹ (Р’С…РѕРґ РЅР° С‚Р°Р№Р»Рµ 55/15): X=55, Y=16, Р»РёС†РѕРј РЅР° РЎРµРІРµСЂ
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

        sp = spawn_pos if spawn_pos is not None else spawn_map.get(gate, spawn_map["east"])
        self.player_x = float(sp[0])
        self.player_y = float(sp[1])
        self.player_direction = sp[2]
        self.player_facing_right = (self.player_direction in ("e", "ne", "se"))
        self.player_speed = 220.0
        self.player_state = "idle"
        self.player_anim_timer = 0.0
        self.move_path = []

        # РљР°РјРµСЂР° С†РµРЅС‚СЂРёСЂСѓРµС‚СЃСЏ РЅР° РїРµСЂСЃРѕРЅР°Р¶Рµ
        self.camera_x = self.player_x
        self.camera_y = self.player_y
        self.camera_follow_player = True

        # РЁСЂРёС„С‚С‹
        self.font = pygame.font.SysFont(settings.FONT_NAME, 20)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 16)
        self.grid_font = pygame.font.SysFont(settings.FONT_NAME, 11)
        self.badge_font = pygame.font.SysFont(settings.FONT_NAME, 13, bold=True)
        self.large_font = pygame.font.SysFont(settings.FONT_NAME, 24, bold=True)
        self.profile_overlay = CharacterProfileOverlay(self.small_font)
        self.chat = (ChatPanel(session, "city", profile_overlay=self.profile_overlay)
                     if hasattr(session, "social_snapshot") else None)

        # РџРµСЂРµРєР»СЋС‡Р°С‚РµР»СЊ РѕС‚РѕР±СЂР°Р¶РµРЅРёСЏ СЃРµС‚РєРё
        self.show_grid = False

        # Р’СЃРїР»С‹РІР°СЋС‰РёРµ СЃРѕРѕР±С‰РµРЅРёСЏ
        self.floating_messages = []

        # Р—Р°РіСЂСѓР·РєР° 8-РЅР°РїСЂР°РІР»РµРЅРЅС‹С… СЃРїСЂР°Р№С‚РѕРІ
        self.player_directional_frames = {}
        self.player_run_directional_frames = {}
        self._load_player_directional_sprites()

        # РџРѕСЃС‚СЂРѕРµРЅРёРµ РєСЂРµРїРѕСЃС‚РЅС‹С… СЃС‚РµРЅ РїРѕ РїРµСЂРёРјРµС‚СЂСѓ 100С…100 С‚Р°Р№Р»РѕРІ СЃ 4 РїСЂРѕРµРјР°РјРё РІРѕСЂРѕС‚
        self._build_city_walls()

        # РРЅС‚РµСЂР°РєС‚РёРІРЅС‹Рµ РѕР±СЉРµРєС‚С‹ РіРѕСЂРѕРґР°: РљСЂРёСЃС‚Р°Р»Р» Р–РёР·РЅРё Рё Р“Р»Р°РІРЅС‹Р№ Р·Р°РјРѕРє
        self._init_city_objects()
        self.citizen_house_lots = build_citizen_house_lots(self.objects)

        # РњРѕРґР°Р»СЊРЅРѕРµ РѕРєРЅРѕ Р·Р°РіР»СѓС€РєРё Р“Р»Р°РІРЅРѕРіРѕ Р—Р°РјРєР°
        self.castle_menu_open = False
        self.city_population_count = 4
        self.city_upgrade_state = {}
        self.castle_window = CastleWindow(self)
        self.castle_modal_rect = self.castle_window.rect
        self.castle_back_button = self.castle_window.close_button
        self.castle_close_button = self.castle_window.close_button
        self.city_population_refresh_at = 0.0
        self._refresh_city_population(force=True)

        # Р“РѕСЂРѕРґСЃРєРёРµ С…СЂР°РЅРёР»РёС‰Р° (РђРјР±Р°СЂ, РЎРєР»Р°Рґ): СЃРѕСЃС‚РѕСЏРЅРёРµ Рё СѓР»СѓС‡С€РµРЅРёРµ РЅР° СЃРµСЂРІРµСЂРµ
        self.barn_menu_open = False
        self.warehouse_menu_open = False
        self.barn_window = CityStorageWindow(self, "barn")
        self.warehouse_window = CityStorageWindow(self, "warehouse")

        self.stable_window = StableWindow(self)
        self.stable_menu_open = False

        # РњРѕРґР°Р»СЊРЅРѕРµ РѕРєРЅРѕ Р·Р°РіР»СѓС€РєРё Р“РѕСЂРѕРґСЃРєРѕР№ РљСѓР·РЅРёС†С‹
        self.forge_menu_open = False
        self.forge_modal_rect = pygame.Rect((settings.WIDTH - 1600) // 2, (settings.HEIGHT - 900) // 2, 1600, 900)
        self.forge_back_button = pygame.Rect(self.forge_modal_rect.centerx - 140, self.forge_modal_rect.bottom - 62, 280, 44)
        self.forge_close_button = pygame.Rect(self.forge_modal_rect.right - 48, self.forge_modal_rect.top + 15, 30, 30)
        from core.forge_recipes import FORGE_TABS
        forge_tab_labels = FORGE_TABS
        forge_tab_gap = 8
        forge_tab_width = (self.forge_modal_rect.width - 48 - forge_tab_gap * (len(forge_tab_labels) - 1)) // len(forge_tab_labels)
        self.forge_tabs = {}
        for index, (key, _label) in enumerate(forge_tab_labels):
            left = self.forge_modal_rect.left + 24 + index * (forge_tab_width + forge_tab_gap)
            width = (self.forge_modal_rect.right - 24 - left
                     if index == len(forge_tab_labels) - 1 else forge_tab_width)
            self.forge_tabs[key] = pygame.Rect(left, self.forge_modal_rect.top + 70, width, 34)
        self.forge_tab_labels = dict(forge_tab_labels)
        self.forge_tab = "weapons"
        self.forge_scroll = 0
        self.forge_action_buttons = []
        self.forge_info_popup_item = None
        self.forge_state = {"queue": [], "queue_count": 0, "queue_limit": 5, "queue_total_seconds": 0, "warehouse": []}
        self.forge_player_materials = {}
        self.forge_message = None
        self.last_forge_refresh = 0.0
        self.last_forge_tick = time.time()

        # РњРѕРґР°Р»СЊРЅРѕРµ РѕРєРЅРѕ Р·Р°РіР»СѓС€РєРё Р“РѕСЂРѕРґСЃРєРѕР№ РњР°СЃС‚РµСЂСЃРєРѕР№
        self.workshop_menu_open = False
        self.workshop_modal_rect = pygame.Rect(settings.WIDTH // 2 - 800, settings.HEIGHT // 2 - 450, 1600, 900)
        self.workshop_close_button = pygame.Rect(self.workshop_modal_rect.right - 42, self.workshop_modal_rect.top + 14, 28, 28)
        self.workshop_back_button = self.workshop_close_button
        self.workshop_tab_labels = dict(WORKSHOP_TABS)
        self.workshop_tab = "helmets"
        self.workshop_tabs = {}
        tab_gap = 8
        tab_width = (self.workshop_modal_rect.width - 48 - tab_gap * (len(WORKSHOP_TABS) - 1)) // len(WORKSHOP_TABS)
        for index, (key, _label) in enumerate(WORKSHOP_TABS):
            left = self.workshop_modal_rect.left + 24 + index * (tab_width + tab_gap)
            width = (self.workshop_modal_rect.right - 24 - left
                     if index == len(WORKSHOP_TABS) - 1 else tab_width)
            self.workshop_tabs[key] = pygame.Rect(left, self.workshop_modal_rect.top + 70, width, 34)
        self.workshop_cart_button = None
        self.workshop_cart_buttons = {}
        self.workshop_cart_scroll = 0
        self.workshop_message = None
        self.workshop_last_refresh = 0.0
        self.workshop_state_received_at = 0.0
        self.workshop_state = {"queue": [], "queue_limit": 5, "warehouse": []}

        # РњРѕРґР°Р»СЊРЅРѕРµ РѕРєРЅРѕ Р·Р°РіР»СѓС€РєРё Р“РѕСЂРѕРґСЃРєРёС… РљР°Р·Р°СЂРј
        self.barracks_menu_open = False
        self.barracks_modal_rect = pygame.Rect(settings.WIDTH // 2 - 340, settings.HEIGHT // 2 - 250, 680, 500)
        self.barracks_back_button = pygame.Rect(self.barracks_modal_rect.centerx - 140, self.barracks_modal_rect.bottom - 62, 280, 44)
        self.barracks_close_button = pygame.Rect(self.barracks_modal_rect.right - 42, self.barracks_modal_rect.top + 14, 28, 28)

        # РњРѕРґР°Р»СЊРЅРѕРµ РѕРєРЅРѕ Р·Р°РіР»СѓС€РєРё РРЅР¶РµРЅРµСЂРЅРѕР№ РїР°Р»Р°С‚С‹
        self.engineering_menu_open = False
        self.engineering_modal_rect = pygame.Rect(settings.WIDTH // 2 - 340, settings.HEIGHT // 2 - 250, 680, 500)
        self.engineering_back_button = pygame.Rect(self.engineering_modal_rect.centerx - 140, self.engineering_modal_rect.bottom - 62, 280, 44)
        self.engineering_close_button = pygame.Rect(self.engineering_modal_rect.right - 42, self.engineering_modal_rect.top + 14, 28, 28)

        # РњРѕРґР°Р»СЊРЅРѕРµ РѕРєРЅРѕ Р·Р°РіР»СѓС€РєРё Р“РѕСЂРѕРґСЃРєРѕРіРѕ РЈРЅРёРІРµСЂСЃРёС‚РµС‚Р°
        self.university_menu_open = False
        self.university_modal_rect = pygame.Rect(settings.WIDTH // 2 - 340, settings.HEIGHT // 2 - 250, 680, 500)
        self.university_back_button = pygame.Rect(self.university_modal_rect.centerx - 140, self.university_modal_rect.bottom - 62, 280, 44)
        self.university_close_button = pygame.Rect(self.university_modal_rect.right - 42, self.university_modal_rect.top + 14, 28, 28)

        # РњРѕРґР°Р»СЊРЅРѕРµ РѕРєРЅРѕ Р·Р°РіР»СѓС€РєРё Р’РѕРµРЅРЅРѕР№ Р°РєР°РґРµРјРёРё
        self.academy_menu_open = False
        self.academy_modal_rect = pygame.Rect(settings.WIDTH // 2 - 340, settings.HEIGHT // 2 - 250, 680, 500)
        self.academy_back_button = pygame.Rect(self.academy_modal_rect.centerx - 140, self.academy_modal_rect.bottom - 62, 280, 44)
        self.academy_close_button = pygame.Rect(self.academy_modal_rect.right - 42, self.academy_modal_rect.top + 14, 28, 28)

        # РњРѕРґР°Р»СЊРЅРѕРµ РѕРєРЅРѕ Р·Р°РіР»СѓС€РєРё РЁРєРѕР»С‹ СЃС‚РёС…РёР№
        self.mage_school_menu_open = False
        self.mage_school_modal_rect = pygame.Rect(settings.WIDTH // 2 - 340, settings.HEIGHT // 2 - 250, 680, 500)
        self.mage_school_back_button = pygame.Rect(self.mage_school_modal_rect.centerx - 140, self.mage_school_modal_rect.bottom - 62, 280, 44)
        self.mage_school_close_button = pygame.Rect(self.mage_school_modal_rect.right - 42, self.mage_school_modal_rect.top + 14, 28, 28)

        # Р’С‹РґРµР»РµРЅРЅС‹Р№ РѕР±СЉРµРєС‚ Рё РѕРєРЅРѕ РґРµР№СЃС‚РІРёСЏ
        self.hovered_entity = None
        self.active_entity = None
        self.active_window_rect = pygame.Rect(settings.WIDTH - 390, settings.HEIGHT - 255, 365, 215)
        self.active_close_button = pygame.Rect(self.active_window_rect.right - 36, self.active_window_rect.top + 10, 26, 26)
        self.active_action_button = pygame.Rect(self.active_window_rect.left + 16, self.active_window_rect.bottom - 48, self.active_window_rect.width - 32, 34)
        self.action_notice = None
        self.action_notice_timer = 0.0

        # РЎРѕРѕР±С‰РµРЅРёРµ РїСЂРё РІС…РѕРґРµ / РІРѕР·СЂРѕР¶РґРµРЅРёРё
        if gate in ("crystal", "death", "respawn"):
            if hasattr(self.session, "character") and self.session.character:
                self.session.character["hp"] = self.session.character.get("max_hp", 100)
                try:
                    self.session.client.save_character(self.session.character)
                except Exception:
                    pass
            self._add_floating_message("рџ’Ћ Р’Р°С€Р° РґСѓС€Р° РІРѕР·СЂРѕРґРёР»Р°СЃСЊ Сѓ РљСЂРёСЃС‚Р°Р»Р»Р° Р–РёР·РЅРё!", self.player_x, self.player_y - 36, (100, 240, 255))
        else:
            gate_names = {
                "east": "Р“Р»Р°РІРЅС‹Рµ РІРѕСЂРѕС‚Р°",
                "main": "Р“Р»Р°РІРЅС‹Рµ РІРѕСЂРѕС‚Р°",
                "north": "РЎРµРІРµСЂРЅС‹Рµ РІРѕСЂРѕС‚Р°",
                "south": "Р®Р¶РЅС‹Рµ РІРѕСЂРѕС‚Р°",
                "west": "Р—Р°РїР°РґРЅС‹Рµ РІРѕСЂРѕС‚Р°",
            }
            g_name = gate_names.get(gate, "Р“Р»Р°РІРЅС‹Рµ РІРѕСЂРѕС‚Р°")
            self._add_floating_message(f"Р’С‹ РІРѕС€Р»Рё РІ Р Р°РґР±СѓСЂРі С‡РµСЂРµР· {g_name}", self.player_x, self.player_y - 36, (255, 220, 100))

    def _load_player_directional_sprites(self):
        """Р—Р°РіСЂСѓР¶Р°РµС‚ 8-РЅР°РїСЂР°РІР»РµРЅРЅС‹Рµ СЃРїСЂР°Р№С‚С‹ РїРµСЂСЃРѕРЅР°Р¶Р° (Idle Рё Run)."""
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
        """РџСЂРµРѕР±СЂР°Р·РѕРІР°РЅРёРµ РјРёСЂРѕРІС‹С… РєРѕРѕСЂРґРёРЅР°С‚ РІ СЌРєСЂР°РЅРЅС‹Рµ РїРёРєСЃРµР»Рё."""
        sx = int((wx - self.camera_x) * self.zoom + settings.WIDTH / 2)
        sy = int((wy - self.camera_y) * self.zoom + settings.HEIGHT / 2)
        return sx, sy

    def screen_to_world(self, sx, sy):
        """РџСЂРµРѕР±СЂР°Р·РѕРІР°РЅРёРµ СЌРєСЂР°РЅРЅС‹С… РїРёРєСЃРµР»РµР№ РІ РјРёСЂРѕРІС‹Рµ РєРѕРѕСЂРґРёРЅР°С‚С‹."""
        wx = (sx - settings.WIDTH / 2) / self.zoom + self.camera_x
        wy = (sy - settings.HEIGHT / 2) / self.zoom + self.camera_y
        return wx, wy

    def _clamp_camera(self):
        """РЈРґРµСЂР¶Р°РЅРёРµ РєР°РјРµСЂС‹ РІ РїСЂРµРґРµР»Р°С… 100С…100 С‚Р°Р№Р»РѕРІ СЃ СѓС‡РµС‚РѕРј С‚РµРєСѓС‰РµРіРѕ Р·СѓРјР°."""
        half_screen_w = (settings.WIDTH / 2) / self.zoom
        half_screen_h = (settings.HEIGHT / 2) / self.zoom
        self.camera_x = max(self.min_world_x + half_screen_w, min(self.max_world_x - half_screen_w, self.camera_x))
        self.camera_y = max(self.min_world_y + half_screen_h, min(self.max_world_y - half_screen_h, self.camera_y))

    def _check_collision(self, px, py):
        """РџСЂРѕРІРµСЂСЏРµС‚ РєРѕР»Р»РёР·РёСЋ РЅРѕРі РіРµСЂРѕСЏ СЃРѕ СЃС‚РµРЅР°РјРё Рё РіСЂР°РЅРёС†Р°РјРё РєР°СЂС‚С‹."""
        # Р Р°Р·СЂРµС€Р°РµРј РІС‹С…РѕРґ Р·Р° РїСЂРµРґРµР»С‹ РєР°СЂС‚С‹ РўРћР›Р¬РљРћ С‡РµСЂРµР· РїСЂРѕРµРјС‹ РІРѕСЂРѕС‚:
        # Р’РѕСЃС‚РѕС‡РЅС‹Рµ Р“Р»Р°РІРЅС‹Рµ РІРѕСЂРѕС‚Р° (Y: 44..55)
        if px >= self.max_world_x - 10:
            if not (44 * self.tile_size <= py <= 56 * self.tile_size):
                return True
        elif px <= self.min_world_x + 10:
            self.finished = False
            self.cancelled = False
            if not (47 * self.tile_size <= py <= 53 * self.tile_size):
                return True

        if py <= self.min_world_y + 6:
            # РЎРµРІРµСЂРЅС‹Рµ РІРѕСЂРѕС‚Р° (X: 47..52)
            if not (47 * self.tile_size <= px <= 53 * self.tile_size):
                return True
        elif py >= self.max_world_y - 6:
            # Р®Р¶РЅС‹Рµ РІРѕСЂРѕС‚Р° (X: 47..52)
            if not (47 * self.tile_size <= px <= 53 * self.tile_size):
                return True

        feet_rect = pygame.Rect(int(px - 10), int(py - 6), 20, 10)

        # 1. Р’РЅРµС€РЅРёРµ РєСЂРµРїРѕСЃС‚РЅС‹Рµ СЃС‚РµРЅС‹ РіРѕСЂРѕРґР°
        for s_rect in self.solid_rects:
            if feet_rect.colliderect(s_rect):
                return True

        # 2. РќРµРїСЂРѕС…РѕРґРёРјС‹Рµ РїСЂРµРїСЏС‚СЃС‚РІРёСЏ Р·РґР°РЅРёР№ Рё РѕР±СЉРµРєС‚РѕРІ (РљСЂРёСЃС‚Р°Р»Р» Р–РёР·РЅРё, Р“Р»Р°РІРЅС‹Р№ Р·Р°РјРѕРє, РўР°РІРµСЂРЅР°)
        for obj in self.objects:
            for s_rect in obj.get("solid_rects", []):
                if feet_rect.colliderect(s_rect):
                    return True

        # Residential houses are solid building footprints, not walkable decoration.
        for house_rect in self._citizen_house_solid_rects():
            if feet_rect.colliderect(house_rect):
                return True

        return False

    def _vector_to_direction(self, dx, dy):
        """РћРїСЂРµРґРµР»СЏРµС‚ РѕРґРЅРѕ РёР· 8 РЅР°РїСЂР°РІР»РµРЅРёР№ РїРѕ РІРµРєС‚РѕСЂСѓ РґРІРёР¶РµРЅРёСЏ."""
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
        """Р”РѕР±Р°РІР»СЏРµС‚ РІСЃРїР»С‹РІР°СЋС‰РµРµ СЃРѕРѕР±С‰РµРЅРёРµ РІ РёРіСЂРѕРІРѕРј РјРёСЂРµ."""
        self.floating_messages.append({
            "text": text,
            "world_x": float(wx),
            "world_y": float(wy),
            "timer": 2.2,
            "max_timer": 2.2,
            "color": color,
        })

    def _find_entity_at(self, screen_pos):
        """РќР°С…РѕРґРёС‚ РёРЅС‚РµСЂР°РєС‚РёРІРЅСѓСЋ СЃСѓС‰РЅРѕСЃС‚СЊ РїРѕРґ СЌРєСЂР°РЅРЅС‹РјРё РєРѕРѕСЂРґРёРЅР°С‚Р°РјРё РєСѓСЂСЃРѕСЂР°."""
        # РџСЂРѕРІРµСЂСЏРµРј РїРµСЂСЃРѕРЅР°Р¶Р° РёРіСЂРѕРєР°
        psx, psy = self.world_to_screen(self.player_x, self.player_y)
        player_rect = pygame.Rect(psx - 22, psy - 58, 44, 62)
        if player_rect.collidepoint(screen_pos):
            char_name = getattr(self.session, "character", {}).get("name", "Р“РµСЂРѕР№") if hasattr(self.session, "character") else "Р“РµСЂРѕР№"
            status_str = "Р‘РµР¶РёС‚" if self.player_state == "walk" else "Р’ РїРѕРєРѕРµ"
            return {
                "id": "player",
                "name": char_name,
                "type": "РРіСЂРѕРІРѕР№ РїРµСЂСЃРѕРЅР°Р¶",
                "x": self.player_x,
                "y": self.player_y,
                "radius": 22,
                "desc": f"Р’Р°С€ РіР»Р°РІРЅС‹Р№ РіРµСЂРѕР№. РЎС‚Р°С‚СѓСЃ: {status_str}.",
                "icon": "рџ‘¤",
            }

        # РџСЂРѕРІРµСЂСЏРµРј РѕР±СЉРµРєС‚С‹ РіРѕСЂРѕРґР°
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
        """РџСЂРѕРІРµСЂСЏРµС‚ РґРёСЃС‚Р°РЅС†РёСЋ РЅРµ РґР°Р»СЊС€Рµ 1 С‚Р°Р№Р»Р° РѕС‚ РѕР±СЉРµРєС‚Р° РёР»Рё РµРіРѕ РІС…РѕРґР°."""
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
        """РћР±СЂР°Р±Р°С‚С‹РІР°РµС‚ РґРµР№СЃС‚РІРёРµ Р°РєС‚РёРІРЅРѕРіРѕ РѕР±СЉРµРєС‚Р°."""
        if not self.active_entity:
            return

        eid = self.active_entity.get("id")
        if eid == "player":
            self.profile_overlay.open(self.session.character, None)
            return

        if eid == "main_castle":
            self._open_castle()
            return

        if eid == "tavern_building":
            if not self._is_within_one_tile(self.active_entity):
                self._add_floating_message("РџРѕРґРѕР№РґРёС‚Рµ Рє РґРІРµСЂРё С‚Р°РІРµСЂРЅС‹ (С‚Р°Р№Р» 55/15)", self.player_x, self.player_y - 34, (255, 120, 90))
                return
            self.navigate = "tavern"
            self.finished = True
            return

        if eid == "barn_building":
            if not self._is_within_one_tile(self.active_entity):
                self._add_floating_message("РџРѕРґРѕР№РґРёС‚Рµ Рє РІРѕСЂРѕС‚Р°Рј Р°РјР±Р°СЂР° (С‚Р°Р№Р» 16/40)", self.player_x, self.player_y - 34, (255, 120, 90))
                return
            self._open_barn()
            return

        if eid == "warehouse_building":
            if not self._is_within_one_tile(self.active_entity):
                self._add_floating_message("РџРѕРґРѕР№РґРёС‚Рµ Рє РІРѕСЂРѕС‚Р°Рј СЃРєР»Р°РґР° (С‚Р°Р№Р» 16/23)", self.player_x, self.player_y - 34, (255, 120, 90))
                return
            self._open_warehouse()
            return

        if eid == "stable_building":
            if not self._is_within_one_tile(self.active_entity):
                self._add_floating_message("РџРѕРґРѕР№РґРёС‚Рµ Рє РІРѕСЂРѕС‚Р°Рј РєРѕРЅСЋС€РЅРё (С‚Р°Р№Р» 85/11)", self.player_x, self.player_y - 34, (255, 120, 90))
                return
            self.stable_window.open()
            self.stable_menu_open = self.stable_window.is_open
            return

        if eid == "forge_building":
            if not self._is_within_one_tile(self.active_entity):
                self._add_floating_message("РџРѕРґРѕР№РґРёС‚Рµ Рє РґРІРµСЂСЏРј РєСѓР·РЅРёС†С‹ (С‚Р°Р№Р» 23/28)", self.player_x, self.player_y - 34, (255, 120, 90))
                return
            self._open_forge()
            return

        if eid == "workshop_building":
            if not self._is_within_one_tile(self.active_entity):
                self._add_floating_message("РџРѕРґРѕР№РґРёС‚Рµ Рє РґРІРµСЂСЏРј РјР°СЃС‚РµСЂСЃРєРѕР№ (С‚Р°Р№Р» 23/16)", self.player_x, self.player_y - 34, (255, 120, 90))
                return
            self._open_workshop()
            return

        if eid == "barracks_building":
            if not self._is_within_one_tile(self.active_entity):
                self._add_floating_message("РџРѕРґРѕР№РґРёС‚Рµ Рє РІРѕСЂРѕС‚Р°Рј РєР°Р·Р°СЂРј (С‚Р°Р№Р» 84/43)", self.player_x, self.player_y - 34, (255, 120, 90))
                return
            self.barracks_menu_open = True
            return

        if eid == "engineering_building":
            if not self._is_within_one_tile(self.active_entity):
                self._add_floating_message("РџРѕРґРѕР№РґРёС‚Рµ Рє РІРѕСЂРѕС‚Р°Рј РёРЅР¶РµРЅРµСЂРЅРѕР№ РїР°Р»Р°С‚С‹ (С‚Р°Р№Р» 44/15)", self.player_x, self.player_y - 34, (255, 120, 90))
                return
            self.engineering_menu_open = True
            return

        if eid == "university_building":
            if not self._is_within_one_tile(self.active_entity):
                self._add_floating_message("РџРѕРґРѕР№РґРёС‚Рµ Рє РґРІРµСЂСЏРј СѓРЅРёРІРµСЂСЃРёС‚РµС‚Р° (С‚Р°Р№Р» 23/84)", self.player_x, self.player_y - 34, (255, 120, 90))
                return
            self.university_menu_open = True
            return

        if eid == "military_academy":
            if not self._is_within_one_tile(self.active_entity):
                self._add_floating_message("РџРѕРґРѕР№РґРёС‚Рµ Рє РґРІРµСЂСЏРј РІРѕРµРЅРЅРѕР№ Р°РєР°РґРµРјРёРё (С‚Р°Р№Р» 19/73)", self.player_x, self.player_y - 34, (255, 120, 90))
                return
            self.academy_menu_open = True
            return

        if eid == "mage_school_building":
            if not self._is_within_one_tile(self.active_entity):
                self._add_floating_message("РџРѕРґРѕР№РґРёС‚Рµ Рє РґРІРµСЂСЏРј С€РєРѕР»С‹ СЃС‚РёС…РёР№ (С‚Р°Р№Р» 44/66)", self.player_x, self.player_y - 34, (255, 120, 90))
                return
            self.mage_school_menu_open = True
            return

        if eid == "crystal_of_life":
            if not self._is_within_one_tile(self.active_entity):
                self._add_floating_message("РџРѕРґРѕР№РґРёС‚Рµ Р±Р»РёР¶Рµ Рє РљСЂРёСЃС‚Р°Р»Р»Сѓ Р–РёР·РЅРё", self.player_x, self.player_y - 34, (255, 120, 90))
                return
            if hasattr(self.session, "character") and self.session.character:
                self.session.character["hp"] = self.session.character.get("max_hp", 100)
                try:
                    self.session.client.save_character(self.session.character)
                except Exception:
                    pass
            self._add_floating_message("вњЁ РљСЂРёСЃС‚Р°Р»Р» Р–РёР·РЅРё РёСЃС†РµР»СЏРµС‚ РІР°С€Рё СЂР°РЅС‹!", self.player_x, self.player_y - 36, (100, 240, 255))
            self.action_notice = "Р—РґРѕСЂРѕРІСЊРµ РїРѕР»РЅРѕСЃС‚СЊСЋ РІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРѕ!"
            self.action_notice_timer = 2.5

    def _open_castle(self):
        self.castle_window.open()
        self.castle_menu_open = self.castle_window.is_open

    def _open_barn(self):
        self.barn_window.open()
        self.barn_menu_open = True

    def _open_warehouse(self):
        self.warehouse_window.open()
        self.warehouse_menu_open = True

    def _open_forge(self):
        self.forge_menu_open = True
        self.forge_scroll = 0
        self.forge_info_popup_item = None
        self._refresh_forge_state()
        self.last_forge_refresh = time.time()
        self.last_forge_tick = time.time()

    def _open_workshop(self):
        self.workshop_menu_open = True
        self.workshop_message = None
        self._refresh_workshop_state()

    def _refresh_workshop_state(self):
        if not hasattr(self, "session") or self.session is None:
            return
        try:
            state = self.session.client.get_building(
                "stable", self.session.character["id"]
            )
        except Exception as error:
            self.workshop_message = str(error)
            return

        grade = state.get("cart_progress", {}).get("grades", {}).get("1", {})
        finish_at = grade.get("body_finish_at")
        server_time = float(state.get("server_time", time.time()))
        cart_progress = state.get("cart_progress", {})
        queue = []
        for grade_key, grade_progress in cart_progress.get("grades", {}).items():
            orders = list(grade_progress.get("production_orders", []))
            if not orders and grade_progress.get("body_finish_at") is not None:
                orders = [{"finish_at": grade_progress["body_finish_at"]}]
            for order in orders:
                order_finish = float(order["finish_at"])
                order_grade = int(order.get("grade", grade_key))
                queue.append({
                    "order_id": order.get("order_id"),
                    "grade": order_grade,
                    "item_name": CART_GRADES.get(str(order_grade), {}).get("name", "РџРѕРІРѕР·РєР°"),
                    "finish_at": order_finish,
                    "duration_seconds": int(
                        CART_GRADES.get(str(order_grade), {}).get("production_seconds", 40 * 60)
                    ),
                    "seconds_left": max(0, int(order_finish - server_time)),
                })
        queue.sort(key=lambda order: order["finish_at"])
        self.workshop_state.update({
            "body_owned": bool(grade.get("body_owned")),
            "body_finish_at": finish_at,
            "server_time": server_time,
            "received_monotonic": time.monotonic(),
            "grade": grade,
            "cart_progress": cart_progress,
            "warehouse_storage": state.get("warehouse_storage", {}) or {},
            "treasury_silver_available": int(state.get("treasury_silver_available", 0)),
            "queue_limit": 5,
            "queue": queue,
        })
        self.workshop_state_received_at = time.monotonic()
        self.workshop_last_refresh = self.workshop_state_received_at
        self.workshop_message = None

    def _order_workshop_cart(self, grade=1):
        self.stable_window._building_action("cart/purchase", {"grade": int(grade)})
        message = self.stable_window.message
        if self.stable_window.state is not None:
            self._refresh_workshop_state()
        self.workshop_message = message

    def _refresh_forge_state(self):
        if not hasattr(self, "session") or self.session is None:
            return
        try:
            if hasattr(self.session, "get_forge_state"):
                self.forge_state = self.session.get_forge_state()
            elif hasattr(self.session, "client") and hasattr(self.session, "character") and self.session.character:
                self.forge_state = self.session.client.get_forge_state(self.session.character["id"])
        except Exception:
            pass
        self._refresh_player_inventory_materials()

    def _refresh_player_inventory_materials(self):
        self.forge_player_materials = {}
        self.forge_player_copper = 0
        if not hasattr(self, "session") or self.session is None:
            return
        try:
            if hasattr(self.session, "character") and self.session.character:
                char = self.session.character
                self.forge_player_copper = Currency.to_copper(char.get("copper", 0), char.get("silver", 0), char.get("gold", 0))
            if hasattr(self.session, "client") and hasattr(self.session, "character") and self.session.character:
                inv_payload = self.session.client.get_inventory(self.session.character["id"])
                self.session.character["carried_weight_kg"] = float(
                    inv_payload.get("carried_weight_kg", 0)
                )
                items = inv_payload.get("inventory", [])
                for it in items:
                    m_id = it.get("item_id")
                    qty = it.get("quantity", 0)
                    self.forge_player_materials[m_id] = self.forge_player_materials.get(m_id, 0) + qty
        except Exception:
            pass

    def _update_forge_timer(self):
        now = time.time()
        dt = now - getattr(self, "last_forge_tick", now)
        self.last_forge_tick = now
        if not getattr(self, "forge_menu_open", False):
            return
        if now - getattr(self, "last_forge_refresh", 0.0) >= 1.0:
            self._refresh_forge_state()
            self.last_forge_refresh = now
        elif getattr(self, "forge_state", None):
            queue = self.forge_state.get("queue", [])
            if queue and queue[0].get("status") == "working":
                curr_left = max(0.0, queue[0].get("seconds_left", 0) - dt)
                queue[0]["seconds_left"] = curr_left
                self.forge_state["queue_total_seconds"] = max(0, int(sum(q.get("seconds_left", 0) for q in queue)))

    def _handle_forge_click(self, pos):
        craft_buttons = [b for b in getattr(self, "forge_action_buttons", []) if b[0] in ("craft", "collect", "info_btn")]
        for action_type, target_id, btn_rect, enabled in craft_buttons:
            if btn_rect.collidepoint(pos):
                if action_type == "info_btn":
                    self.forge_info_popup_item = target_id
                    return
                if not enabled:
                    return
                if action_type == "craft":
                    self.order_forge_item(target_id)
                elif action_type == "collect":
                    self.collect_forge_order(target_id)
                return

        card_clicks = [b for b in getattr(self, "forge_action_buttons", []) if b[0] == "card"]
        for action_type, target_id, btn_rect, enabled in card_clicks:
            if btn_rect.collidepoint(pos):
                self.forge_info_popup_item = target_id
                return

    def _handle_forge_popup_click(self, pos):
        popup_rect = getattr(self, "forge_popup_rect", None)
        if popup_rect is None or not popup_rect.collidepoint(pos):
            self.forge_info_popup_item = None
            return True
        close_btn = getattr(self, "forge_popup_close_btn", None)
        cancel_btn = getattr(self, "forge_popup_cancel_btn", None)
        craft_btn = getattr(self, "forge_popup_craft_btn", None)
        if (close_btn and close_btn.collidepoint(pos)) or (cancel_btn and cancel_btn.collidepoint(pos)):
            self.forge_info_popup_item = None
            return True
        if craft_btn and craft_btn.collidepoint(pos):
            item_id = self.forge_info_popup_item
            self.forge_info_popup_item = None
            self.order_forge_item(item_id)
            return True
        return True

    def order_forge_item(self, item_id):
        if not hasattr(self, "session") or self.session is None:
            return
        try:
            if hasattr(self.session, "order_forge_item"):
                self.session.order_forge_item(item_id)
            elif hasattr(self.session, "client") and hasattr(self.session, "character") and self.session.character:
                self.session.client.order_forge_item(self.session.character["id"], item_id)
            if hasattr(self.session, "client") and hasattr(self.session, "character") and self.session.character:
                try:
                    self.session.character = self.session.client.load_character(self.session.character["id"])
                except Exception:
                    pass
            self._refresh_forge_state()
            self.forge_message = ("Р—Р°РєР°Р· РїСЂРёРЅСЏС‚ РІ РєСѓР·РЅРёС†Сѓ! РљСѓР·РЅРµС† РїСЂРёСЃС‚СѓРїРёР» Рє СЂР°Р±РѕС‚Рµ.", (120, 240, 120), time.time() + 4.0)
        except Exception as err:
            err_msg = getattr(err, "message", str(err))
            self.forge_message = (f"РћС€РёР±РєР°: {err_msg}", (255, 100, 90), time.time() + 4.0)

    def collect_forge_order(self, order_id):
        if not hasattr(self, "session") or self.session is None:
            return
        try:
            if hasattr(self.session, "collect_forge_order"):
                self.session.collect_forge_order(order_id)
            elif hasattr(self.session, "client") and hasattr(self.session, "character") and self.session.character:
                self.session.client.collect_forge_order(self.session.character["id"], order_id)
            self._refresh_forge_state()
            self.forge_message = ("РџСЂРµРґРјРµС‚ СѓСЃРїРµС€РЅРѕ Р·Р°Р±СЂР°РЅ СЃРѕ СЃРєР»Р°РґР° РІ РІР°С€ СЂСЋРєР·Р°Рє!", (120, 240, 120), time.time() + 4.0)
        except Exception as err:
            err_msg = getattr(err, "message", str(err))
            self.forge_message = (f"РћС€РёР±РєР°: {err_msg}", (255, 100, 90), time.time() + 4.0)

    def _any_modal_open(self):
        """True, РµСЃР»Рё РѕС‚РєСЂС‹С‚Рѕ С…РѕС‚СЏ Р±С‹ РѕРґРЅРѕ РјРѕРґР°Р»СЊРЅРѕРµ РѕРєРЅРѕ Р·РґР°РЅРёСЏ."""
        return (
            self.castle_menu_open or self.barn_menu_open or self.warehouse_menu_open or self.stable_menu_open or self.forge_menu_open
            or self.workshop_menu_open or self.barracks_menu_open or self.engineering_menu_open
            or self.university_menu_open or self.academy_menu_open or self.mage_school_menu_open
        )

    def handle_event(self, event):
        if self.profile_overlay.is_open:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.profile_overlay.close()
                return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                action, profile = self.profile_overlay.handle_click(event.pos)
                if action == "stat_change":
                    self._save_profile_card(profile)

        if self.chat is not None and self.chat.handle_event(event):
            return

        # 1. Р•СЃР»Рё РѕС‚РєСЂС‹С‚Рѕ РјРѕРґР°Р»СЊРЅРѕРµ РјРµРЅСЋ Р·Р°РјРєР°
        if self.castle_menu_open:
            self.castle_window.handle_event(event)
            self.castle_menu_open = self.castle_window.is_open
            return

        # 2. Р•СЃР»Рё РѕС‚РєСЂС‹С‚Рѕ РѕРєРЅРѕ Р°РјР±Р°СЂР°
        if self.barn_menu_open:
            self.barn_window.handle_event(event)
            self.barn_menu_open = self.barn_window.is_open
            return

        # 3. Р•СЃР»Рё РѕС‚РєСЂС‹С‚Рѕ РѕРєРЅРѕ СЃРєР»Р°РґР°
        if self.warehouse_menu_open:
            self.warehouse_window.handle_event(event)
            self.warehouse_menu_open = self.warehouse_window.is_open
            return

        if self.stable_menu_open:
            self.stable_window.handle_event(event)
            self.stable_menu_open = self.stable_window.is_open
            return

        # 4. Р•СЃР»Рё РѕС‚РєСЂС‹С‚Рѕ РјРѕРґР°Р»СЊРЅРѕРµ РјРµРЅСЋ РєСѓР·РЅРёС†С‹
        if self.forge_menu_open:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                    if getattr(self, "forge_info_popup_item", None) is not None:
                        self.forge_info_popup_item = None
                    else:
                        self.forge_menu_open = False
                    return
            elif event.type == pygame.MOUSEWHEEL:
                if getattr(self, "forge_info_popup_item", None) is None:
                    self.forge_scroll = max(0, self.forge_scroll - event.y * 36)
                return
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if getattr(self, "forge_info_popup_item", None) is not None:
                        self._handle_forge_popup_click(event.pos)
                        return
                    if self.forge_back_button.collidepoint(event.pos) or self.forge_close_button.collidepoint(event.pos):
                        self.forge_menu_open = False
                        return
                    for tab, button in self.forge_tabs.items():
                        if button.collidepoint(event.pos):
                            self.forge_tab = tab
                            self.forge_scroll = 0
                            return
                    self._handle_forge_click(event.pos)
                elif event.button == 4 and getattr(self, "forge_info_popup_item", None) is None:
                    self.forge_scroll = max(0, self.forge_scroll - 36)
                elif event.button == 5 and getattr(self, "forge_info_popup_item", None) is None:
                    self.forge_scroll = self.forge_scroll + 36
            return

        # 5. Р•СЃР»Рё РѕС‚РєСЂС‹С‚Рѕ РјРѕРґР°Р»СЊРЅРѕРµ РјРµРЅСЋ РјР°СЃС‚РµСЂСЃРєРѕР№
        if self.workshop_menu_open:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                    self.workshop_menu_open = False
                    return
            elif event.type == pygame.MOUSEWHEEL:
                if self.workshop_tab == "carts":
                    self.workshop_cart_scroll = max(0, self.workshop_cart_scroll - event.y * 48)
                return
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5):
                if self.workshop_tab == "carts":
                    direction = -1 if event.button == 4 else 1
                    self.workshop_cart_scroll = max(0, self.workshop_cart_scroll + direction * 48)
                return
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.workshop_back_button.collidepoint(event.pos) or self.workshop_close_button.collidepoint(event.pos):
                    self.workshop_menu_open = False
                    return
                for tab, button in self.workshop_tabs.items():
                    if button.collidepoint(event.pos):
                        self.workshop_tab = tab
                        return
                if self.workshop_tab == "carts":
                    for grade, button in self.workshop_cart_buttons.items():
                        if button.collidepoint(event.pos):
                            self._order_workshop_cart(grade)
                            return
            return

        # 6. Р•СЃР»Рё РѕС‚РєСЂС‹С‚Рѕ РјРѕРґР°Р»СЊРЅРѕРµ РјРµРЅСЋ РєР°Р·Р°СЂРј
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

        # 7. Р•СЃР»Рё РѕС‚РєСЂС‹С‚Рѕ РјРѕРґР°Р»СЊРЅРѕРµ РјРµРЅСЋ РёРЅР¶РµРЅРµСЂРЅРѕР№ РїР°Р»Р°С‚С‹
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

        # 8. Р•СЃР»Рё РѕС‚РєСЂС‹С‚Рѕ РјРѕРґР°Р»СЊРЅРѕРµ РјРµРЅСЋ СѓРЅРёРІРµСЂСЃРёС‚РµС‚Р°
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

        # 9. Р•СЃР»Рё РѕС‚РєСЂС‹С‚Рѕ РјРѕРґР°Р»СЊРЅРѕРµ РјРµРЅСЋ РІРѕРµРЅРЅРѕР№ Р°РєР°РґРµРјРёРё
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

        # 10. Р•СЃР»Рё РѕС‚РєСЂС‹С‚Рѕ РјРѕРґР°Р»СЊРЅРѕРµ РјРµРЅСЋ С€РєРѕР»С‹ СЃС‚РёС…РёР№
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

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if not self._keyboard_movement_blocked() and not self._any_modal_open():
                wx, wy = self.screen_to_world(*event.pos)
                path = find_tile_path(
                    (self.player_x, self.player_y), (wx, wy), self._check_collision, self.tile_size
                )
                self.move_path = path or []
            return

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                # РљР»РёРє РїРѕ РѕРєРЅСѓ Р°РєС‚РёРІРЅРѕРіРѕ РѕР±СЉРµРєС‚Р°
                if self.active_entity is not None and self.active_window_rect.collidepoint(event.pos):
                    if self.active_close_button.collidepoint(event.pos):
                        self.active_entity = None
                        return
                    if self.active_action_button.collidepoint(event.pos):
                        self._trigger_active_action()
                        return
                    return

                # РљР»РёРє РїРѕ РѕР±СЉРµРєС‚Сѓ РёР»Рё РїРµСЂСЃРѕРЅР°Р¶Сѓ
                clicked_entity = self._find_entity_at(event.pos)
                if clicked_entity is not None:
                    self.active_entity = clicked_entity
                    self.action_notice = None
                    if clicked_entity.get("id") == "main_castle":
                        self._open_castle()
                    elif clicked_entity.get("id") == "barn_building":
                        self._open_barn()
                    elif clicked_entity.get("id") == "warehouse_building":
                        self._open_warehouse()
                    elif clicked_entity.get("id") == "stable_building":
                        self.stable_window.open()
                        self.stable_menu_open = self.stable_window.is_open
                    elif clicked_entity.get("id") == "forge_building":
                        self._open_forge()
                    elif clicked_entity.get("id") == "workshop_building":
                        self._open_workshop()
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

                # РљР»РёРє РїРѕ РїСѓСЃС‚РѕР№ Р·РµРјР»Рµ -> СЃР±СЂРѕСЃРёС‚СЊ Р°РєС‚РёРІРЅС‹Р№ РѕР±СЉРµРєС‚
                self.active_entity = None

    def _keyboard_movement_blocked(self):
        """РљР»Р°РІРёС€Рё WASD РЅРµ РґРІРёРіР°СЋС‚ РїРµСЂСЃРѕРЅР°Р¶Р°, РїРѕРєР° РѕС‚РєСЂС‹С‚ РІРІРѕРґ РІ С‡Р°С‚ РёР»Рё РѕРІРµСЂР»РµР№ РїСЂРѕС„РёР»СЏ."""
        if self.profile_overlay.is_open:
            return True
        return self.chat is not None and self.chat.message_input.focused and not self.chat.collapsed

    def _save_profile_card(self, profile):
        try:
            saved_profile = self.session.save_character_profile(profile)
        except Exception as error:
            self.action_notice = str(error)
            self.action_notice_timer = 2.0
            return
        if saved_profile is not None:
            self.profile_overlay.update_profile(saved_profile)

    def _refresh_city_population(self, force=False):
        now = time.monotonic()
        if self.castle_window.is_open and not force:
            return False
        if not force and now < self.city_population_refresh_at:
            return False
        self.city_population_refresh_at = now + self.CITY_POPULATION_REFRESH_SECONDS
        try:
            state = self.session.client.get_city_population(
                self.session.character["id"]
            )
        except (ServerError, AttributeError, KeyError, OSError, TypeError, ValueError):
            return False
        self.city_population_count = max(0, int(state.get("population", self.city_population_count)))
        self.city_upgrade_state = dict(state.get("city_upgrade", {}))
        self.castle_upgrades_active = [dict(item) for item in state.get("castle_upgrades_active", [])]
        return True

    def update(self, dt):
        self._refresh_city_population()
        if self.workshop_menu_open:
            now = time.monotonic()
            queue = self.workshop_state.get("queue", [])
            elapsed = now - self.workshop_state.get("received_monotonic", now)
            server_time = self.workshop_state.get("server_time", time.time())
            for order in queue:
                order["seconds_left"] = max(0, int(
                    float(order["finish_at"]) - server_time - elapsed
                ))
            if now - self.workshop_last_refresh >= 5:
                self._refresh_workshop_state()
        if self.chat is not None:
            self.chat.update(dt)
        # 1. Движение персонажа по пути (ПКМ, как в Dota 2)
        if self.move_path and not self._any_modal_open():
            step = self.player_speed * character_movement_speed_multiplier(
                getattr(self.session, "character", None)
            ) * dt
            prev_x, prev_y = self.player_x, self.player_y
            self.player_x, self.player_y, moved = follow_path(
                self.player_x, self.player_y, self.move_path, step, self._check_collision
            )
            if moved:
                self.player_state = "walk"
                dx = self.player_x - prev_x
                dy = self.player_y - prev_y
                if dx or dy:
                    self.player_direction = self._vector_to_direction(dx, dy)
                    self.player_facing_right = dx >= 0
            else:
                self.move_path = []
                self.player_state = "idle"
        else:
            self.player_state = "idle"

        # РљР°РјРµСЂР° РІСЃРµРіРґР° С†РµРЅС‚СЂРёСЂСѓРµС‚СЃСЏ РЅР° РїРµСЂСЃРѕРЅР°Р¶Рµ
        self.camera_follow_player = True
        self.camera_x = self.player_x
        self.camera_y = self.player_y
        self._clamp_camera()

        # 2. РџСЂРѕРІРµСЂРєР° РІС‹С…РѕРґР° РёР· РіРѕСЂРѕРґР° С‡РµСЂРµР· 4 РІРѕСЂРѕС‚ (РІС‹С…РѕРґ РўРћР›Р¬РљРћ С‡РµСЂРµР· РІРѕСЂРѕС‚Р°)
        px, py = self.player_x, self.player_y

        # Р“Р»Р°РІРЅС‹Рµ РІРѕСЂРѕС‚Р° (Р’РѕСЃС‚РѕРє, 12 С‚Р°Р№Р»РѕРІ): X >= 98*32, Y: 44..55
        if px >= (98 * self.tile_size + 8) and (44 * self.tile_size <= py <= 56 * self.tile_size):
            self.exit_gate = "east"
            self.finished = True
            return

        # РЎРµРІРµСЂРЅС‹Рµ РІРѕСЂРѕС‚Р° (РЎРµРІРµСЂ, 6 С‚Р°Р№Р»РѕРІ): Y <= 32, X: 47..52
        if py <= (self.tile_size + 8) and (47 * self.tile_size <= px <= 53 * self.tile_size):
            self.exit_gate = "north"
            self.finished = True
            return

        # Р®Р¶РЅС‹Рµ РІРѕСЂРѕС‚Р° (Р®Рі, 6 С‚Р°Р№Р»РѕРІ): Y >= 98*32, X: 47..52
        if py >= (98 * self.tile_size + 8) and (47 * self.tile_size <= px <= 53 * self.tile_size):
            self.exit_gate = "south"
            self.finished = True
            return

        # Р—Р°РїР°РґРЅС‹Рµ РІРѕСЂРѕС‚Р° (Р—Р°РїР°Рґ, 6 С‚Р°Р№Р»РѕРІ): X <= 32, Y: 47..52
        if px <= (self.tile_size + 8) and (47 * self.tile_size <= py <= 53 * self.tile_size):
            self.exit_gate = "west"
            self.finished = True
            return

        # 3. Р’С…РѕРґ РІ С‚Р°РІРµСЂРЅСѓ РїСЂРё РЅР°СЃС‚СѓРїР»РµРЅРёРё РЅР° РґРІРµСЂСЊ (С‚Р°Р№Р» 55/15)
        pgx = int(self.player_x // self.tile_size)
        pgy = int(self.player_y // self.tile_size)
        if pgx == 55 and pgy == 15:
            self.navigate = "tavern"
            self.finished = True
            return

        # 4. Р’С…РѕРґ РІ Р°РјР±Р°СЂ РїСЂРё РЅР°СЃС‚СѓРїР»РµРЅРёРё РЅР° РґРІРµСЂСЊ (С‚Р°Р№Р» 16/40)
        if pgx == 16 and pgy == 40 and not self.barn_menu_open:
            self._open_barn()
            self.player_state = "idle"
            self.player_x = 17 * self.tile_size + 16
            self.player_y = 40 * self.tile_size + 16
            return

        # 5. Р’С…РѕРґ РЅР° СЃРєР»Р°Рґ РїСЂРё РЅР°СЃС‚СѓРїР»РµРЅРёРё РЅР° РґРІРµСЂСЊ (С‚Р°Р№Р» 16/23)
        if pgx == 16 and pgy == 23 and not self.warehouse_menu_open:
            self._open_warehouse()
            self.player_state = "idle"
            self.player_x = 17 * self.tile_size + 16
            self.player_y = 23 * self.tile_size + 16
            return

        # 6. Р’С…РѕРґ РІ РєСѓР·РЅРёС†Сѓ РїСЂРё РЅР°СЃС‚СѓРїР»РµРЅРёРё РЅР° РґРІРµСЂСЊ (С‚Р°Р№Р» 23/28)
        if pgx == 23 and pgy == 28 and not self.forge_menu_open:
            self._open_forge()
            self.player_state = "idle"
            self.player_x = 22 * self.tile_size + 16
            self.player_y = 28 * self.tile_size + 16
            return

        # 7. Р’С…РѕРґ РІ РјР°СЃС‚РµСЂСЃРєСѓСЋ РїСЂРё РЅР°СЃС‚СѓРїР»РµРЅРёРё РЅР° РґРІРµСЂСЊ (С‚Р°Р№Р» 23/16)
        if pgx == 23 and pgy == 16 and not self.workshop_menu_open:
            self._open_workshop()
            self.player_state = "idle"
            self.player_x = 22 * self.tile_size + 16
            self.player_y = 16 * self.tile_size + 16
            return

        # 8. Р’С…РѕРґ РІ РєР°Р·Р°СЂРјС‹ РїСЂРё РЅР°СЃС‚СѓРїР»РµРЅРёРё РЅР° РґРІРµСЂСЊ (С‚Р°Р№Р» 84/43)
        if pgx == 84 and pgy == 43 and not self.barracks_menu_open:
            self.barracks_menu_open = True
            self.player_state = "idle"
            self.player_x = 84 * self.tile_size + 16
            self.player_y = 44 * self.tile_size + 16
            return

        # 9. Р’С…РѕРґ РІ РёРЅР¶РµРЅРµСЂРЅСѓСЋ РїР°Р»Р°С‚Сѓ РїСЂРё РЅР°СЃС‚СѓРїР»РµРЅРёРё РЅР° РґРІРµСЂСЊ (С‚Р°Р№Р» 44/15)
        if pgx == 44 and pgy == 15 and not self.engineering_menu_open:
            self.engineering_menu_open = True
            self.player_state = "idle"
            self.player_x = 45 * self.tile_size + 16
            self.player_y = 15 * self.tile_size + 16
            return

        # 10. Р’С…РѕРґ РІ СѓРЅРёРІРµСЂСЃРёС‚РµС‚ РїСЂРё РЅР°СЃС‚СѓРїР»РµРЅРёРё РЅР° РґРІРµСЂСЊ (С‚Р°Р№Р» 23/84)
        if pgx == 23 and pgy == 84 and not self.university_menu_open:
            self.university_menu_open = True
            self.player_state = "idle"
            self.player_x = 23 * self.tile_size + 16
            self.player_y = 83 * self.tile_size + 16
            return

        # 11. Р’С…РѕРґ РІ РІРѕРµРЅРЅСѓСЋ Р°РєР°РґРµРјРёСЋ РїСЂРё РЅР°СЃС‚СѓРїР»РµРЅРёРё РЅР° РґРІРµСЂСЊ (С‚Р°Р№Р» 19/73)
        if pgx == 19 and pgy == 73 and not self.academy_menu_open:
            self.academy_menu_open = True
            self.player_state = "idle"
            self.player_x = 20 * self.tile_size + 16
            self.player_y = 73 * self.tile_size + 16
            return

        # 12. Р’С…РѕРґ РІ С€РєРѕР»Сѓ СЃС‚РёС…РёР№ РїСЂРё РЅР°СЃС‚СѓРїР»РµРЅРёРё РЅР° РґРІРµСЂСЊ (С‚Р°Р№Р» 44/66)
        if pgx == 44 and pgy == 66 and not self.mage_school_menu_open:
            self.mage_school_menu_open = True
            self.player_state = "idle"
            self.player_x = 45 * self.tile_size + 16
            self.player_y = 66 * self.tile_size + 16
            return

        # 13. РўР°Р№РјРµСЂС‹ Р°РЅРёРјР°С†РёРё
        self.player_anim_timer += dt

        for msg in self.floating_messages[:]:
            msg["timer"] -= dt
            msg["world_y"] -= 16.0 * dt
            if msg["timer"] <= 0:
                self.floating_messages.remove(msg)

        if self.action_notice_timer > 0:
            self.action_notice_timer -= dt
            if self.action_notice_timer <= 0:
                self.action_notice = None

        # 14. РћРїСЂРµРґРµР»РµРЅРёРµ РѕР±СЉРµРєС‚Р° РїРѕРґ РєСѓСЂСЃРѕСЂРѕРј (hover)
        m_pos = pygame.mouse.get_pos()
        if not self._any_modal_open() and not (self.active_entity and self.active_window_rect.collidepoint(m_pos)):
            self.hovered_entity = self._find_entity_at(m_pos)
        else:
            self.hovered_entity = None

        self._clamp_camera()

    def draw(self, screen):
        screen.fill((16, 20, 26))

        top_left_wx, top_left_wy = self.screen_to_world(0, 0)
        bot_right_wx, bot_right_wy = self.screen_to_world(settings.WIDTH, settings.HEIGHT)

        start_gx = max(0, int(top_left_wx // self.tile_size) - 1)
        end_gx = min(self.grid_w, int(bot_right_wx // self.tile_size) + 2)
        start_gy = max(0, int(top_left_wy // self.tile_size) - 1)
        end_gy = min(self.grid_h, int(bot_right_wy // self.tile_size) + 2)

        # 1. РћС‚СЂРёСЃРѕРІРєР° РјРѕСЃС‚РѕРІРѕР№ Рё С€РёСЂРѕРєРёС… РїСЂРѕСЃРїРµРєС‚РѕРІ РіРѕСЂРѕРґР° 100С…100
        for gy in range(start_gy, end_gy):
            for gx in range(start_gx, end_gx):
                tile_wx = gx * self.tile_size
                tile_wy = gy * self.tile_size
                sx, sy = self.world_to_screen(tile_wx, tile_wy)
                sx2, sy2 = self.world_to_screen(tile_wx + self.tile_size, tile_wy + self.tile_size)
                rect = pygame.Rect(sx, sy, sx2 - sx + 1, sy2 - sy + 1)

                is_avenue = False
                is_plaza = False

                # Р¦РµРЅС‚СЂР°Р»СЊРЅР°СЏ РїР»РѕС‰Р°РґСЊ (40..59 РїРѕ X Рё Y, 20x20 С‚Р°Р№Р»РѕРІ)
                if 40 <= gx <= 59 and 40 <= gy <= 59:
                    is_plaza = True
                # РЎРµРІРµСЂРЅРѕ-Р®Р¶РЅС‹Р№ РїСЂРѕСЃРїРµРєС‚ (6 С‚Р°Р№Р»РѕРІ РІ С€РёСЂРёРЅСѓ: X 47..52)
                elif 47 <= gx <= 52:
                    is_avenue = True
                # Р—Р°РїР°РґРЅРѕ-Р’РѕСЃС‚РѕС‡РЅС‹Р№ РїСЂРѕСЃРїРµРєС‚ (6 С‚Р°Р№Р»РѕРІ РІ С€РёСЂРёРЅСѓ: Y 47..52, Р° Рє Р“Р»Р°РІРЅС‹Рј РІРѕСЂРѕС‚Р°Рј СЂР°СЃС€РёСЂСЏРµС‚СЃСЏ РґРѕ 12 С‚Р°Р№Р»РѕРІ Y: 44..55)
                elif (47 <= gy <= 52) or (gx >= 80 and 44 <= gy <= 55):
                    is_avenue = True

                if is_plaza:
                    # Р—РѕР»РѕС‚РёСЃС‚Рѕ-РјСЂР°РјРѕСЂРЅР°СЏ С†РµРЅС‚СЂР°Р»СЊРЅР°СЏ РїР»РѕС‰Р°РґСЊ
                    cell_color = (78, 74, 66) if (gx + gy) % 2 == 0 else (84, 80, 72)
                elif is_avenue:
                    # Р“Р»Р°РІРЅС‹Рµ РїСЂРѕСЃРїРµРєС‚С‹ РёР· СЃРІРµС‚Р»РѕРіРѕ С‚РµСЃР°РЅРѕРіРѕ РєР°РјРЅСЏ
                    cell_color = (68, 66, 60) if (gx + gy) % 2 == 0 else (74, 72, 66)
                else:
                    # Р“РѕСЂРѕРґСЃРєРёРµ РєРІР°СЂС‚Р°Р»С‹ (РјРѕСЃС‚РѕРІР°СЏ РёР· С‚РµРјРЅРѕРіРѕ Р±СѓР»С‹Р¶РЅРёРєР°)
                    cell_color = (38, 44, 52) if (gx + gy) % 2 == 0 else (42, 48, 56)

                pygame.draw.rect(screen, cell_color, rect)

                if self.show_grid:
                    pygame.draw.rect(screen, (58, 66, 76), rect, 1)

        # 2. РћР±СЉРµРєС‚С‹ РіРѕСЂРѕРґР°: Р“Р»Р°РІРЅС‹Р№ Р—Р°РјРѕРє, РўР°РІРµСЂРЅР° Рё РљСЂРёСЃС‚Р°Р»Р» Р–РёР·РЅРё
        self._draw_city_objects(screen)

        # 3. Р”РѕРјР° Р¶РёС‚РµР»РµР№ РїРѕРІРµСЂС… С„РѕРЅР° Рё РїРѕР·Р°РґРё РєСЂРµРїРѕСЃС‚РЅС‹С… СЃС‚РµРЅ.
        self._draw_citizen_houses(screen)

        # 4. Р’РЅРµС€РЅРёРµ РєСЂРµРїРѕСЃС‚РЅС‹Рµ СЃС‚РµРЅС‹ Рё 4 РІРѕСЂРѕС‚
        self._draw_walls_and_gates(screen)
        self._draw_city_upgrade_construction(screen)

        # 5. Р­С„С„РµРєС‚С‹ РєР»РёРєР° Рё РїРµСЂСЃРѕРЅР°Р¶
        self._draw_player_character(screen)
        draw_afk_players(self, screen, "city")

        # 5. Р’СЃРїР»С‹РІР°СЋС‰РёРµ СЃРѕРѕР±С‰РµРЅРёСЏ
        self._draw_floating_messages(screen)

        # 6. Р’СЃРїР»С‹РІР°СЋС‰РµРµ РѕРєРЅРѕ Р°РєС‚РёРІРЅРѕРіРѕ РѕР±СЉРµРєС‚Р° (Р›РљРњ)
        self._draw_active_window(screen)

        # 7. Р’РµСЂС…РЅРёР№ HUD (РёРЅС„РѕСЂРјР°С†РёСЏ, РїРѕРґСЃРєР°Р·РєРё, Р‘Р•Р— РєРЅРѕРїРѕРє С‚РµР»РµРїРѕСЂС‚Р°С†РёРё)
        self._draw_hud(screen)

        # 8. РњРѕРґР°Р»СЊРЅРѕРµ РѕРєРЅРѕ Р·Р°РіР»СѓС€РєРё Р“Р»Р°РІРЅРѕРіРѕ Р—Р°РјРєР°
        if self.castle_menu_open:
            self._draw_castle_modal(screen)

        # 9. РњРѕРґР°Р»СЊРЅРѕРµ РѕРєРЅРѕ Р·Р°РіР»СѓС€РєРё Р“РѕСЂРѕРґСЃРєРѕРіРѕ РђРјР±Р°СЂР°
        if self.barn_menu_open:
            self.barn_window.draw(screen)

        # 10. РњРѕРґР°Р»СЊРЅРѕРµ РѕРєРЅРѕ Р·Р°РіР»СѓС€РєРё Р“РѕСЂРѕРґСЃРєРѕРіРѕ РЎРєР»Р°РґР°
        if self.warehouse_menu_open:
            self.warehouse_window.draw(screen)

        if self.stable_menu_open:
            self.stable_window.draw(screen)

        # 11. РњРѕРґР°Р»СЊРЅРѕРµ РѕРєРЅРѕ Р·Р°РіР»СѓС€РєРё Р“РѕСЂРѕРґСЃРєРѕР№ РљСѓР·РЅРёС†С‹
        if self.forge_menu_open:
            self._update_forge_timer()
            self._draw_forge_modal(screen)

        # 12. РњРѕРґР°Р»СЊРЅРѕРµ РѕРєРЅРѕ Р·Р°РіР»СѓС€РєРё Р“РѕСЂРѕРґСЃРєРѕР№ РњР°СЃС‚РµСЂСЃРєРѕР№
        if self.workshop_menu_open:
            self._draw_workshop_modal(screen)

        # 13. РњРѕРґР°Р»СЊРЅРѕРµ РѕРєРЅРѕ Р·Р°РіР»СѓС€РєРё Р“РѕСЂРѕРґСЃРєРёС… РљР°Р·Р°СЂРј
        if self.barracks_menu_open:
            self._draw_barracks_modal(screen)

        # 14. РњРѕРґР°Р»СЊРЅРѕРµ РѕРєРЅРѕ Р·Р°РіР»СѓС€РєРё РРЅР¶РµРЅРµСЂРЅРѕР№ РїР°Р»Р°С‚С‹
        if self.engineering_menu_open:
            self._draw_engineering_modal(screen)

        # 15. РњРѕРґР°Р»СЊРЅРѕРµ РѕРєРЅРѕ Р·Р°РіР»СѓС€РєРё Р“РѕСЂРѕРґСЃРєРѕРіРѕ РЈРЅРёРІРµСЂСЃРёС‚РµС‚Р°
        if self.university_menu_open:
            self._draw_university_modal(screen)

        # 16. РњРѕРґР°Р»СЊРЅРѕРµ РѕРєРЅРѕ Р·Р°РіР»СѓС€РєРё Р’РѕРµРЅРЅРѕР№ Р°РєР°РґРµРјРёРё
        if self.academy_menu_open:
            self._draw_academy_modal(screen)

        # 17. РњРѕРґР°Р»СЊРЅРѕРµ РѕРєРЅРѕ Р·Р°РіР»СѓС€РєРё РЁРєРѕР»С‹ СЃС‚РёС…РёР№
        if self.mage_school_menu_open:
            self._draw_mage_school_modal(screen)

        if self.chat is not None:
            self.chat.draw(screen)
        self.profile_overlay.draw(screen, opponent=self.session.character, show_player_only=True)

    def close(self):
        """РћС‡РёСЃС‚РєР° СЂРµСЃСѓСЂСЃРѕРІ РїСЂРё Р·Р°РєСЂС‹С‚РёРё СЃС†РµРЅС‹."""
        pass
