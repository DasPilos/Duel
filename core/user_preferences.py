import json
import logging
import math
import os
from pathlib import Path

import pygame


LOGGER = logging.getLogger(__name__)
DEFAULT_KEY_BINDINGS = {
    "profile": pygame.K_TAB,
    "interact": pygame.K_e,
    "grid": pygame.K_g,
    "center": pygame.K_SPACE,
    "move_left": pygame.K_a,
    "move_right": pygame.K_d,
    "move_up": pygame.K_w,
    "move_down": pygame.K_s,
}
DEFAULT_PREFERENCES = {
    "tab_toggle": False,
    "music_volume": 0.5,
    "sfx_volume": 0.7,
    "key_bindings": DEFAULT_KEY_BINDINGS,
}


def _preferences_path():
    if os.getenv("APPDATA"):
        root = Path(os.environ["APPDATA"])
    elif os.getenv("XDG_CONFIG_HOME"):
        root = Path(os.environ["XDG_CONFIG_HOME"])
    else:
        root = Path.home() / ".config"
    return root / "Duel" / "settings.json"


class UserPreferences:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else _preferences_path()
        self.values = {
            **DEFAULT_PREFERENCES,
            "key_bindings": dict(DEFAULT_KEY_BINDINGS),
        }
        self.load_error = None
        self._load()

    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            self.load_error = str(error)
            LOGGER.warning("Не удалось загрузить настройки %s: %s", self.path, error)
            return
        if not isinstance(data, dict):
            self.load_error = "Файл настроек должен содержать объект"
            LOGGER.warning("Некорректный формат настроек: %s", self.path)
            return

        if isinstance(data.get("tab_toggle"), bool):
            self.values["tab_toggle"] = data["tab_toggle"]
        for key in ("music_volume", "sfx_volume"):
            value = data.get(key)
            if (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
            ):
                self.values[key] = max(0.0, min(1.0, float(value)))
        bindings = data.get("key_bindings")
        if isinstance(bindings, dict):
            for name in DEFAULT_KEY_BINDINGS:
                value = bindings.get(name)
                if type(value) is int and value != pygame.K_UNKNOWN:
                    self.values["key_bindings"][name] = value

    def get(self, key, default=None):
        return self.values.get(key, default)

    @property
    def key_bindings(self):
        return self.values["key_bindings"]

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(self.values, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary_path, self.path)


_user_preferences = None


def get_user_preferences():
    global _user_preferences
    if _user_preferences is None:
        _user_preferences = UserPreferences()
    return _user_preferences
