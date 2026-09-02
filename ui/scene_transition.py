import pygame

from ui.music import fade_out_all_music

# Скорость перехода сокращена в 2 раза для более быстрого переключения между сценами
TRANSITION_SECONDS = 1.0 / 1.3 / 1.5


class SceneTransition:
    """Плавный переход между сценами: экран темнеет, музыка плавно затухает, затем создаётся новая сцена."""

    def __init__(self, duration=TRANSITION_SECONDS):
        self.duration = duration
        self.elapsed = 0.0
        self.factory = None
        self.frozen_frame = None

    @property
    def active(self):
        return self.factory is not None

    def start(self, screen, factory):
        """Замораживает текущий кадр и запускает переход к сцене, создаваемой factory()."""
        if self.active:
            return
        self.factory = factory
        self.elapsed = 0.0
        self.frozen_frame = screen.copy()
        fade_out_all_music(int(self.duration * 1000))

    def update(self, dt):
        """Возвращает новую сцену, когда переход завершён, иначе None."""
        if not self.active:
            return None
        self.elapsed += dt
        if self.elapsed >= self.duration:
            factory = self.factory
            self.factory = None
            self.frozen_frame = None
            return factory()
        return None

    def draw(self, screen):
        """Рисует замороженный кадр прошлой сцены с нарастающим затемнением."""
        if not self.active or self.frozen_frame is None:
            return False
        screen.blit(self.frozen_frame, (0, 0))
        progress = min(1.0, self.elapsed / self.duration)
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, int(255 * progress)))
        screen.blit(overlay, (0, 0))
        return True
