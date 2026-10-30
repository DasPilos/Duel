import random
from pathlib import Path

import pygame

SFX_DIR = Path(__file__).resolve().parent.parent / "assets" / "sound" / "effects"
SWORD_SWING_SOUNDS = ("sword_swing_1.mp3", "sword_swing_2.mp3", "sword_swing_3.mp3")
CLUB_SWING_SOUNDS = ("club_swing.mp3",)
KNIFE_SWING_SOUNDS = ("knife_swing_1.mp3", "knife_swing_2.mp3")
RUN_SOUND = "run_grass.mp3"
DASH_SOUND = "dash_slice.mp3"
DASH_WHIRL_SOUND = "dash_whirl_strike.mp3"

_sound_cache = {}
_run_channel = None


def swing_sounds_for_weapon(weapon):
    """Набор звуков замаха по названию оружия: меч, дубина или молот, нож или кинжал."""
    name = str((weapon or {}).get("name", "")).lower()
    if "меч" in name:
        return SWORD_SWING_SOUNDS
    if "дубин" in name or "молот" in name:
        return CLUB_SWING_SOUNDS
    if "нож" in name or "кинжал" in name:
        return KNIFE_SWING_SOUNDS
    return ()


def _load(name):
    """Загружает звук один раз; без инициализированного микшера возвращает None и не кэширует."""
    if not pygame.mixer.get_init():
        return None
    if name not in _sound_cache:
        try:
            _sound_cache[name] = pygame.mixer.Sound(str(SFX_DIR / name))
        except pygame.error:
            _sound_cache[name] = None
    return _sound_cache[name]


def play_random_sound(names):
    """Проигрывает один случайный файл из набора."""
    if not names:
        return
    sound = _load(random.choice(names))
    if sound is not None:
        sound.play()


def play_dash_sound():
    """Разовый звук активации рывка."""
    sound = _load(DASH_SOUND)
    if sound is not None:
        sound.play()


def play_dash_whirl_sound():
    """Разовый звук кругового удара в конце рывка."""
    sound = _load(DASH_WHIRL_SOUND)
    if sound is not None:
        sound.play()


def set_run_sound(running):
    """Зацикленный звук бега: включается пока персонаж идёт, выключается при остановке."""
    global _run_channel
    if not running:
        stop_run_sound()
        return
    if _run_channel is not None and _run_channel.get_busy():
        return
    sound = _load(RUN_SOUND)
    _run_channel = sound.play(loops=-1) if sound is not None else None


def stop_run_sound():
    global _run_channel
    if _run_channel is not None:
        _run_channel.stop()
    _run_channel = None
