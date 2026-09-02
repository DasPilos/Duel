from pathlib import Path
import random
import time

import pygame


DRAFT_MUSIC_PATH = Path(__file__).resolve().parent.parent / "assets" / "sound" / "music" / "draft_theme.mp3"
BATTLE_MUSIC_PATHS = (
    Path(__file__).resolve().parent.parent / "assets" / "sound" / "music" / "battle_theme_1.mp3",
    Path(__file__).resolve().parent.parent / "assets" / "sound" / "music" / "battle_theme_2.mp3",
)
TAVERN_MUSIC_PATHS = (
    Path(__file__).resolve().parent.parent / "assets" / "sound" / "music" / "tavern_theme_1.mp3",
    Path(__file__).resolve().parent.parent / "assets" / "sound" / "music" / "tavern_theme_2.mp3",
    Path(__file__).resolve().parent.parent / "assets" / "sound" / "music" / "tavern_theme_3.mp3",
    Path(__file__).resolve().parent.parent / "assets" / "sound" / "music" / "tavern_theme_4.mp3",
)
_tavern_music_active = False


def _reset_music_volume():
    global _duck_state
    _duck_state = "idle"
    try:
        pygame.mixer.music.set_volume(1.0)
    except pygame.error:
        pass


def fade_out_all_music(duration_ms=2000):
    """Плавно затухает любую текущую музыку при переходе между сценами."""
    global _tavern_music_active, _duck_state
    _tavern_music_active = False
    _duck_state = "idle"
    try:
        pygame.mixer.music.set_volume(1.0)
        pygame.mixer.music.fadeout(int(duration_ms))
    except pygame.error:
        pass


_music_base_volume = 1.0
_duck_state = "idle"  # "idle" | "down" | "held" | "up"
_duck_phase_elapsed = 0.0
_duck_start_volume = 1.0
_duck_target_volume = 0.5
_duck_release_at = 0.0
DUCK_FADE_DOWN_SECONDS = 0.020
DUCK_FADE_UP_SECONDS = 0.030


def duck_battle_music(duration=1.2, volume=0.5):
    """Плавно приглушает боевую музыку (обмен картами/удары) за 20мс, держит и за 30мс возвращает громкость."""
    global _duck_state, _duck_phase_elapsed, _duck_start_volume, _duck_target_volume, _duck_release_at
    now = time.monotonic()
    if _duck_state == "idle":
        try:
            _duck_start_volume = pygame.mixer.music.get_volume()
        except pygame.error:
            _duck_start_volume = _music_base_volume
        _duck_state = "down"
        _duck_phase_elapsed = 0.0
        _duck_release_at = now + duration
    elif _duck_state == "up":
        try:
            _duck_start_volume = pygame.mixer.music.get_volume()
        except pygame.error:
            _duck_start_volume = _duck_target_volume
        _duck_state = "down"
        _duck_phase_elapsed = 0.0
        _duck_release_at = now + duration
    else:
        # Уже приглушено (fade down/held) — просто продлеваем время удержания.
        _duck_release_at = max(_duck_release_at, now + duration)
    _duck_target_volume = volume


def update_music_ducking(dt):
    """Вызывать каждый кадр во время боя с реальным dt, чтобы плавно вести приглушение/восстановление."""
    global _duck_state, _duck_phase_elapsed, _duck_start_volume
    if _duck_state == "idle":
        return
    if _duck_state == "down":
        _duck_phase_elapsed += dt
        progress = min(1.0, _duck_phase_elapsed / DUCK_FADE_DOWN_SECONDS)
        volume = _duck_start_volume + (_duck_target_volume - _duck_start_volume) * progress
        try:
            pygame.mixer.music.set_volume(volume)
        except pygame.error:
            pass
        if progress >= 1.0:
            _duck_state = "held"
        return
    if _duck_state == "held":
        if time.monotonic() >= _duck_release_at:
            _duck_state = "up"
            _duck_phase_elapsed = 0.0
            _duck_start_volume = _duck_target_volume
        return
    if _duck_state == "up":
        _duck_phase_elapsed += dt
        progress = min(1.0, _duck_phase_elapsed / DUCK_FADE_UP_SECONDS)
        volume = _duck_start_volume + (_music_base_volume - _duck_start_volume) * progress
        try:
            pygame.mixer.music.set_volume(volume)
        except pygame.error:
            pass
        if progress >= 1.0:
            _duck_state = "idle"


def play_draft_music():
    """Запускает фоновую музыку драфта по кругу; тихо игнорирует отсутствие звука."""
    _reset_music_volume()
    try:
        pygame.mixer.music.load(str(DRAFT_MUSIC_PATH))
        pygame.mixer.music.play(loops=-1)
    except (pygame.error, OSError):
        pass


def stop_draft_music():
    try:
        pygame.mixer.music.stop()
    except pygame.error:
        pass


def play_battle_music():
    """Запускает случайный боевой трек по кругу, пока бой не завершится."""
    _reset_music_volume()
    try:
        pygame.mixer.music.load(str(random.choice(BATTLE_MUSIC_PATHS)))
        pygame.mixer.music.play(loops=-1)
    except (pygame.error, OSError):
        pass


def stop_battle_music():
    try:
        pygame.mixer.music.stop()
    except pygame.error:
        pass


def _play_random_tavern_track():
    try:
        pygame.mixer.music.load(str(random.choice(TAVERN_MUSIC_PATHS)))
        pygame.mixer.music.play()
    except (pygame.error, OSError):
        pass


def play_tavern_music():
    """Запускает случайный трек таверны; следующий случайный трек подхватывается в update_tavern_music."""
    global _tavern_music_active
    _tavern_music_active = True
    _reset_music_volume()
    _play_random_tavern_track()


def update_tavern_music():
    """Вызывается каждый кадр, пока игрок в таверне: подхватывает новый случайный трек, когда текущий закончился."""
    if not _tavern_music_active:
        return
    try:
        busy = pygame.mixer.music.get_busy()
    except pygame.error:
        return
    if not busy:
        _play_random_tavern_track()


def stop_tavern_music():
    global _tavern_music_active
    _tavern_music_active = False
    try:
        pygame.mixer.music.stop()
    except pygame.error:
        pass


DRAFT_CARDS_DEAL_SOUND_PATH = Path(__file__).resolve().parent.parent / "assets" / "sound" / "effects" / "draft_cards_deal.mp3"
_draft_cards_deal_sound = None
_draft_cards_deal_sound_loaded = False


def play_draft_cards_deal_sound():
    """Проигрывает звук раздачи 10 карт драфта из колоды, один раз за вылет всей пачки."""
    global _draft_cards_deal_sound, _draft_cards_deal_sound_loaded
    if not _draft_cards_deal_sound_loaded:
        _draft_cards_deal_sound_loaded = True
        try:
            _draft_cards_deal_sound = pygame.mixer.Sound(str(DRAFT_CARDS_DEAL_SOUND_PATH))
        except (pygame.error, OSError):
            _draft_cards_deal_sound = None
    if _draft_cards_deal_sound is not None:
        try:
            _draft_cards_deal_sound.play()
        except pygame.error:
            pass


CRITICAL_HIT_SOUND_PATH = Path(__file__).resolve().parent.parent / "assets" / "sound" / "effects" / "critical_hit.mp3"
_critical_hit_sound = None
_critical_hit_sound_loaded = False


def play_critical_hit_sound():
    """Проигрывает звук критического удара отдельным каналом, не трогая фоновую музыку."""
    global _critical_hit_sound, _critical_hit_sound_loaded
    if not _critical_hit_sound_loaded:
        _critical_hit_sound_loaded = True
        try:
            _critical_hit_sound = pygame.mixer.Sound(str(CRITICAL_HIT_SOUND_PATH))
        except (pygame.error, OSError):
            _critical_hit_sound = None
    if _critical_hit_sound is not None:
        try:
            _critical_hit_sound.play()
            duck_battle_music()
        except pygame.error:
            pass


DODGE_SOUND_PATHS = (
    Path(__file__).resolve().parent.parent / "assets" / "sound" / "effects" / "dodge_hit.mp3",
    Path(__file__).resolve().parent.parent / "assets" / "sound" / "effects" / "dodge_whoosh.mp3",
)
_dodge_sounds = None
_dodge_sounds_loaded = False


def play_dodge_sound():
    """Проигрывает оба звука уворота одновременно отдельными каналами."""
    global _dodge_sounds, _dodge_sounds_loaded
    if not _dodge_sounds_loaded:
        _dodge_sounds_loaded = True
        try:
            _dodge_sounds = [pygame.mixer.Sound(str(path)) for path in DODGE_SOUND_PATHS]
        except (pygame.error, OSError):
            _dodge_sounds = []
    for sound in _dodge_sounds or []:
        try:
            sound.play()
            duck_battle_music()
        except pygame.error:
            pass


CARD_MOVE_SOUND_PATH = Path(__file__).resolve().parent.parent / "assets" / "sound" / "effects" / "card_move.mp3"
_card_move_sound = None
_card_move_sound_loaded = False


def play_card_move_sound():
    """Проигрывает звук перемещения карты (стол/рука в любую сторону) отдельным каналом."""
    global _card_move_sound, _card_move_sound_loaded
    if not _card_move_sound_loaded:
        _card_move_sound_loaded = True
        try:
            _card_move_sound = pygame.mixer.Sound(str(CARD_MOVE_SOUND_PATH))
        except (pygame.error, OSError):
            _card_move_sound = None
    if _card_move_sound is not None:
        try:
            _card_move_sound.play()
        except pygame.error:
            pass


DAMAGE_SOUND_PATHS = tuple(
    Path(__file__).resolve().parent.parent / "assets" / "sound" / "effects" / f"damage_{index}.mp3"
    for index in range(1, 6)
)
_damage_sounds = None
_damage_sounds_loaded = False


def play_damage_sound():
    """Проигрывает один случайный звук броска урона отдельным каналом."""
    global _damage_sounds, _damage_sounds_loaded
    if not _damage_sounds_loaded:
        _damage_sounds_loaded = True
        try:
            _damage_sounds = [pygame.mixer.Sound(str(path)) for path in DAMAGE_SOUND_PATHS]
        except (pygame.error, OSError):
            _damage_sounds = []
    if _damage_sounds:
        try:
            random.choice(_damage_sounds).play()
            duck_battle_music()
        except pygame.error:
            pass
