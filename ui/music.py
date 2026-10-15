from pathlib import Path
import random

import pygame


_MUSIC_DIR = Path(__file__).resolve().parent.parent / "assets" / "sound" / "music"
TAVERN_MUSIC_PATHS = tuple(_MUSIC_DIR / f"tavern_theme_{index}.mp3" for index in range(1, 5))
_tavern_music_active = False


def _reset_music_volume():
    try:
        pygame.mixer.music.set_volume(1.0)
    except pygame.error:
        pass


def fade_out_all_music(duration_ms=2000):
    """Плавно затухает любую текущую музыку при переходе между сценами."""
    global _tavern_music_active
    _tavern_music_active = False
    try:
        pygame.mixer.music.set_volume(1.0)
        pygame.mixer.music.fadeout(int(duration_ms))
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
