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

WARRIOR_SPRITE_PATH = (
    BASE_DIR
    / "assets"
    / "fighters"
    / "warrior"
    / "Warior.png"
)


def fit_figure_to(image, reference):
    """Масштабирует фигуру на image до высоты фигуры на reference и ставит её на тот же уровень ног.

    Результат имеет размер reference, поэтому его можно рисовать тем же кодом, что и стандартный спрайт.
    """
    if reference is None:
        return image
    ref_rect = reference.get_bounding_rect()
    src_rect = image.get_bounding_rect()
    if ref_rect.height == 0 or src_rect.height == 0:
        return image
    scale = ref_rect.height / src_rect.height
    figure = image.subsurface(src_rect).copy()
    figure = pygame.transform.smoothscale(
        figure,
        (max(1, round(src_rect.width * scale)), ref_rect.height),
    )
    canvas = pygame.Surface(reference.get_size(), pygame.SRCALPHA)
    canvas.blit(figure, figure.get_rect(midbottom=(ref_rect.centerx, ref_rect.bottom)))
    return canvas


class FighterSprite:
    def __init__(self, path=FIGHTER_SPRITE_PATH, fit_to=None):
        self.path = Path(path)
        self.image = None
        self.fit_to = fit_to
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
            return

        if self.fit_to is not None:
            self.image = fit_figure_to(self.image, self.fit_to.image)

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
