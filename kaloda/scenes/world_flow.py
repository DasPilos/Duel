"""Мир Колоды как одна сцена: сама переключает экраны, поэтому общему циклу игры нужен один вход."""

import pygame

from client.network import ServerError
from kaloda.client import KalodaSession
from kaloda.combat.card_database import is_mage_profession
from kaloda.map_config import TAVERN_EXIT_POS
from kaloda.scenes.backyard_scene import BackyardScene
from kaloda.scenes.character_room import CharacterRoom
from kaloda.scenes.character_scene import CharacterScene
from kaloda.scenes.create_character_scene import CreateCharacterScene
from kaloda.scenes.duel_scene import DuelScene
from kaloda.scenes.mage_battle_scene import MageBattleScene
from kaloda.scenes.tavern_scene import TavernScene
from kaloda.scenes.world_map_scene import WorldMapScene
from ui.inventory_window import InventoryWindow
from ui.scene_transition import SceneTransition

# Экраны, где работает рюкзак (клавиша I и кнопка в профиле)
INVENTORY_SCREENS = ("world_map", "tavern", "character_room")
# Зоны, которые сохраняются в персонаже, чтобы вернуть героя туда же после входа
SAVED_ZONES = ("tavern", "character_room", "backyard")


class KalodaWorld:
    def __init__(self, session):
        self.session = session
        self.name = "character"
        self.scene = CharacterScene(session)
        self.transition = SceneTransition()
        self.inventory = InventoryWindow()
        self._queued = None

    @property
    def chat(self):
        """Чат текущего экрана: через него общий цикл понимает, что клавиатура занята вводом."""
        return getattr(self.scene, "chat", None)

    # ------------------------------------------------------------------ переходы

    def go(self, name, **options):
        """Ставит переход в очередь: он начнётся при следующей отрисовке, когда есть кадр для затемнения."""
        if self._queued is None and not self.transition.active:
            self._queued = (name, options)

    def _build(self, name, options):
        session = self.session
        if name == "character":
            return CharacterScene(session)
        if name == "create":
            return CreateCharacterScene(session)
        if name == "world_map":
            return WorldMapScene(session, spawn_pos=options.get("spawn_pos"))
        if name == "tavern":
            return TavernScene(session)
        if name == "character_room":
            return CharacterRoom(session)
        if name == "backyard":
            return BackyardScene(session)
        if name == "duel":
            scene_class = MageBattleScene if is_mage_profession(session.character.get("type")) else DuelScene
            return scene_class(session, options["opponent"])
        raise ValueError(f"Неизвестный экран Колоды: {name}")

    def _switch(self, name, options):
        self._close_scene()
        self.scene = self._build(name, options)
        self.name = name
        self._sync_checkpoint()
        return self.scene

    def _saved_screen(self):
        """Куда вернуть выбранного персонажа: туда, где он вышел из игры, а новичка — на карту."""
        character = self.session.character or {}
        zone = character.get("zone")
        if zone in SAVED_ZONES:
            return zone, {}
        position = (character.get("position_x"), character.get("position_y"))
        if zone == "world_map" and all(value is not None for value in position):
            return "world_map", {"spawn_pos": (*position, character.get("position_direction") or "s")}
        return "world_map", {}

    def _after_scene(self):
        scene = self.scene
        if not scene.finished:
            return
        name = self.name
        if name == "character":
            if scene.create_new_character:
                self.go("create")
            elif scene.cancelled:
                scene.finished = scene.cancelled = False
            else:
                name, options = self._saved_screen()
                self.go(name, **options)
        elif name == "create":
            if scene.cancelled:
                self.go("character")
            else:
                self.go("world_map")
        elif name == "world_map":
            if scene.navigate == "tavern":
                self.go("tavern")
            else:
                scene.finished = False
        elif name == "tavern":
            self._after_tavern(scene)
        elif name == "character_room":
            self.go("tavern")
        elif name == "backyard":
            self._after_backyard(scene)

    def _after_tavern(self, scene):
        target, cancelled = scene.navigate, scene.cancelled
        scene.finished = scene.cancelled = False
        scene.navigate = None
        if cancelled:
            return
        if target == "world_map":
            x, y = TAVERN_EXIT_POS
            self.go("world_map", spawn_pos=(x, y, "s"))
        elif target in ("character_room", "backyard"):
            self.go(target)

    def _after_backyard(self, scene):
        opponent = scene.opponent
        if opponent is not None and not scene.cancelled:
            self.go("duel", opponent=opponent)
        else:
            self.go("tavern")

    def _after_duel(self):
        scene = self.scene
        if not scene.return_to_tavern:
            return
        scene.return_to_tavern = False
        character = self.session.character
        if getattr(getattr(scene, "player", None), "hp", 1) <= 0 and character:
            # Проигравший не остаётся с нулевым здоровьем: возвращается в таверну полным сил.
            character["hp"] = int(character.get("max_hp", 100))
            self._save_character()
        self.go("tavern")

    def _save_character(self):
        try:
            self.session.client.save_character(self.session.character)
        except (ServerError, AttributeError, OSError):
            pass

    # ------------------------------------------------------------------ цикл сцены

    def handle_event(self, event):
        if self.transition.active or self._queued is not None:
            return
        if self.inventory.handle_event(event):
            return
        if (event.type == pygame.KEYDOWN and event.key == pygame.K_i
                and self._inventory_allowed() and not self._typing()):
            self._toggle_profile()
            return
        self.scene.handle_event(event)
        overlay = getattr(self.scene, "profile_overlay", None)
        if getattr(overlay, "inventory_requested", False):
            overlay.inventory_requested = False
            if self._inventory_allowed():
                self.inventory.open(self.session)

    def update(self, dt):
        if self.transition.active:
            self.transition.update(dt)
            return
        if self._queued is not None:
            return
        self.scene.update(dt)
        self._sync_checkpoint()
        if self.name == "duel":
            self._after_duel()
        else:
            self._after_scene()
        self._load_equipment_for_profile()

    def draw(self, screen):
        if self.transition.active:
            self.transition.draw(screen)
            return
        self.scene.draw(screen)
        self.inventory.draw(screen)
        if self._queued is not None:
            name, options = self._queued
            self._queued = None
            self.transition.start(screen, lambda: self._switch(name, options))

    def close(self):
        self.inventory.close()
        self._close_scene()

    def _close_scene(self):
        if self.scene is not None:
            self.scene.close()
            self.scene = None

    # ------------------------------------------------------------------ рюкзак и профиль

    def _inventory_allowed(self):
        return self.name in INVENTORY_SCREENS and bool(getattr(self.session, "character", None))

    def _typing(self):
        chat = self.chat
        return chat is not None and chat.captures_keyboard()

    def _toggle_profile(self):
        overlay = getattr(self.scene, "profile_overlay", None)
        if overlay is None:
            return
        if overlay.is_open:
            overlay.close()
        else:
            overlay.open(self.session.character, None)

    def _load_equipment_for_profile(self):
        """Один раз подгружает надетые предметы, чтобы слоты на карточке профиля не были пустыми."""
        overlay = getattr(self.scene, "profile_overlay", None)
        if not getattr(overlay, "is_open", False) or not self._inventory_allowed():
            return
        if "equipment" not in self.session.character and self.session.refresh_equipment_state() is None:
            self.session.character["equipment"] = {}

    # ------------------------------------------------------------------ сохранение места

    def _sync_checkpoint(self):
        """Общий цикл сохраняет `session.character` при выходе, поэтому место героя пишем в него заранее."""
        character = self.session.character
        scene = self.scene
        if not character or scene is None:
            return
        if self.name == "world_map":
            x, y, direction = scene.checkpoint_position()
            character.update({
                "zone": "world_map",
                "position_x": x,
                "position_y": y,
                "position_direction": direction,
            })
        elif self.name in SAVED_ZONES:
            character["zone"] = self.name
        elif self.name == "duel":
            character["zone"] = "backyard"
            player = getattr(scene, "player", None)
            if player is not None:
                character.update(KalodaSession._fighter_payload(player))
