import pygame

from ui.music import fade_out_all_music

# Скорость перехода между фазами боя
PHASE_TRANSITION_SECONDS = 0.75


class PhaseTransition:
    """Плавный переход между фазами боя: экран темнеет, музыка плавно затухает."""

    def __init__(self, duration=PHASE_TRANSITION_SECONDS):
        self.duration = duration
        self.elapsed = 0.0
        self.active_transition = False
        self.frozen_frame = None
        self.target_phase = None

    @property
    def active(self):
        return self.active_transition

    def start(self, screen, target_phase):
        """Замораживает текущий кадр и запускает переход к целевой фазе."""
        if self.active_transition:
            return
        self.active_transition = True
        self.target_phase = target_phase
        self.elapsed = 0.0
        self.frozen_frame = screen.copy()
        fade_out_all_music(int(self.duration * 1000))

    def update(self, dt):
        """Возвращает целевую фазу когда переход завершён, иначе None."""
        if not self.active_transition:
            return None
        self.elapsed += dt
        if self.elapsed >= self.duration:
            self.active_transition = False
            target = self.target_phase
            self.target_phase = None
            self.frozen_frame = None
            return target
        return None

    def draw(self, screen):
        """Рисует замороженный кадр с нарастающим затемнением."""
        if not self.active_transition or self.frozen_frame is None:
            return False
        screen.blit(self.frozen_frame, (0, 0))
        progress = min(1.0, self.elapsed / self.duration)
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, int(255 * progress)))
        screen.blit(overlay, (0, 0))
        return True
