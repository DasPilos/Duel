from pathlib import Path
import pygame


BASE_DIR = Path(__file__).resolve().parent.parent

FIGHTER_SPRITE_PATH = (
    BASE_DIR
    / "assets"
    / "fighters"
    / "base"
    / "fighter.png"
)


class FighterSprite:
    def __init__(self, path=FIGHTER_SPRITE_PATH):
        self.path = Path(path)
        self.image = None
        self.load()

    def load(self):
        if not self.path.exists():
            return

        try:
            self.image = pygame.image.load(
                str(self.path)
            ).convert_alpha()
        except (pygame.error, OSError):
            self.image = None

    def draw(self, screen, x, feet_y, scale=1.0):
        if self.image is None:
            return False

        image = self.image

        if scale != 1.0:
            width = int(image.get_width() * scale)
            height = int(image.get_height() * scale)

            image = pygame.transform.smoothscale(
                image,
                (width, height),
            )

        rect = image.get_rect()
        rect.midbottom = (int(x), int(feet_y))

        screen.blit(image, rect)

        return True
