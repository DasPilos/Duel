# Менеджер управления звуками и музыкой
import pygame
import os
from pathlib import Path


class AudioManager:
    """
    Менеджер для управления звуками и музыкой в игре.
    Загружает и воспроизводит звуковые эффекты и фоновую музыку.
    """

    # Пути к папкам со звуками
    SOUNDS_DIR = Path(__file__).parent.parent / "assets" / "sound"
    MUSIC_DIR = SOUNDS_DIR / "music"
    EFFECTS_DIR = SOUNDS_DIR / "effects"

    # Типы музыки
    MUSIC_TAVERN = "tavern"
    MUSIC_BATTLE = "battle"
    MUSIC_DRAFT = "draft"

    # Типы звуковых эффектов
    EFFECT_DAMAGE = "damage"
    EFFECT_CRITICAL = "critical_hit"
    EFFECT_DODGE = "dodge_hit"
    EFFECT_WHOOSH = "dodge_whoosh"
    EFFECT_CARD_MOVE = "card_move"
    EFFECT_CARDS_DEAL = "draft_cards_deal"

    def __init__(self):
        """Инициализируем менеджер аудио"""
        self.current_music = None
        self.music_volume = 0.5  # Громкость музыки (0.0 - 1.0)
        self.sfx_volume = 0.7    # Громкость эффектов
        self.music_enabled = True
        self.sfx_enabled = True
        
        # Кэш загруженных звуков
        self.sounds_cache = {}
        self.music_cache = {}

    def load_music_track(self, track_type: str) -> str:
        """
        Загружает путь до музыкального трека
        
        Args:
            track_type: тип музыки (MUSIC_TAVERN, MUSIC_BATTLE, MUSIC_DRAFT)
            
        Returns:
            Путь к файлу музыки
        """
        if track_type == self.MUSIC_TAVERN:
            # Выбираем случайную музыку таверны из 4 доступных
            import random
            track_num = random.randint(1, 4)
            return self.MUSIC_DIR / f"tavern_theme_{track_num}.mp3"
        elif track_type == self.MUSIC_BATTLE:
            import random
            track_num = random.randint(1, 2)
            return self.MUSIC_DIR / f"battle_theme_{track_num}.mp3"
        elif track_type == self.MUSIC_DRAFT:
            return self.MUSIC_DIR / "draft_theme.mp3"
        return None

    def load_effect_sound(self, effect_type: str):
        """
        Загружает звуковой эффект
        
        Args:
            effect_type: тип эффекта
            
        Returns:
            pygame.mixer.Sound объект или None
        """
        if not self.sfx_enabled:
            return None

        # Кэшируем уже загруженные звуки
        if effect_type in self.sounds_cache:
            return self.sounds_cache[effect_type]

        sound_path = None
        
        if effect_type == self.EFFECT_DAMAGE:
            import random
            damage_num = random.randint(1, 5)
            sound_path = self.EFFECTS_DIR / f"damage_{damage_num}.mp3"
        elif effect_type == self.EFFECT_CRITICAL:
            sound_path = self.EFFECTS_DIR / "critical_hit.mp3"
        elif effect_type == self.EFFECT_DODGE:
            sound_path = self.EFFECTS_DIR / "dodge_hit.mp3"
        elif effect_type == self.EFFECT_WHOOSH:
            sound_path = self.EFFECTS_DIR / "dodge_whoosh.mp3"
        elif effect_type == self.EFFECT_CARD_MOVE:
            sound_path = self.EFFECTS_DIR / "card_move.mp3"
        elif effect_type == self.EFFECT_CARDS_DEAL:
            sound_path = self.EFFECTS_DIR / "draft_cards_deal.mp3"

        if sound_path and sound_path.exists():
            try:
                sound = pygame.mixer.Sound(str(sound_path))
                sound.set_volume(self.sfx_volume)
                self.sounds_cache[effect_type] = sound
                return sound
            except pygame.error as e:
                print(f"Ошибка загрузки звука {sound_path}: {e}")
                return None
        
        return None

    def play_music(self, track_type: str, loops: int = -1):
        """
        Воспроизводит фоновую музыку
        
        Args:
            track_type: тип музыки
            loops: количество повторений (-1 = бесконечно)
        """
        if not self.music_enabled:
            return

        track_path = self.load_music_track(track_type)
        if track_path and track_path.exists():
            try:
                pygame.mixer.music.load(str(track_path))
                pygame.mixer.music.set_volume(self.music_volume)
                pygame.mixer.music.play(loops)
                self.current_music = track_type
            except pygame.error as e:
                print(f"Ошибка воспроизведения музыки {track_path}: {e}")

    def stop_music(self):
        """Останавливает текущую музыку"""
        pygame.mixer.music.stop()
        self.current_music = None

    def play_sound(self, effect_type: str):
        """
        Воспроизводит звуковой эффект
        
        Args:
            effect_type: тип эффекта
        """
        if not self.sfx_enabled:
            return

        sound = self.load_effect_sound(effect_type)
        if sound:
            sound.play()

    def set_music_volume(self, volume: float):
        """Устанавливает громкость музыки (0.0 - 1.0)"""
        self.music_volume = max(0.0, min(1.0, volume))
        pygame.mixer.music.set_volume(self.music_volume)

    def set_sfx_volume(self, volume: float):
        """Устанавливает громкость звуковых эффектов (0.0 - 1.0)"""
        self.sfx_volume = max(0.0, min(1.0, volume))

    def toggle_music(self):
        """Включает/выключает музыку"""
        self.music_enabled = not self.music_enabled
        if not self.music_enabled:
            self.stop_music()

    def toggle_sfx(self):
        """Включает/выключает звуковые эффекты"""
        self.sfx_enabled = not self.sfx_enabled

    def cleanup(self):
        """Очищает память от кэшированных звуков"""
        self.sounds_cache.clear()
        self.music_cache.clear()
        self.stop_music()


# Глобальный экземпляр менеджера аудио
_audio_manager = None


def get_audio_manager() -> AudioManager:
    """Получить глобальный экземпляр менеджера аудио"""
    global _audio_manager
    if _audio_manager is None:
        _audio_manager = AudioManager()
    return _audio_manager


def play_sound(effect_type: str):
    """Быстрая функция для воспроизведения звука"""
    get_audio_manager().play_sound(effect_type)


def play_music(track_type: str):
    """Быстрая функция для воспроизведения музыки"""
    get_audio_manager().play_music(track_type)


def stop_music():
    """Быстрая функция для остановки музыки"""
    get_audio_manager().stop_music()
