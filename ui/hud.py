import pygame


def draw_text(screen, font, text, x, y, color=(230, 230, 230)):
    # x — положение текста по горизонтали:
    # увеличьте x — текст переместится вправо.
    # уменьшите x — текст переместится влево.
    #
    # y — положение текста по вертикали:
    # увеличьте y — текст опустится ниже.
    # уменьшите y — текст поднимется выше.
    surface = font.render(str(text), True, color)
    screen.blit(surface, (x, y))


def draw_bar(
    screen,
    x,
    y,
    width,
    height,
    value,
    max_value,
    bg=(60, 60, 60),
    fg=(80, 200, 120),
):
    # width — ширина полосы HP или MP.
    # height — высота полосы HP или MP.
    pygame.draw.rect(
        screen,
        bg,
        (x, y, width, height),
        border_radius=6,
    )

    ratio = 0 if max_value <= 0 else max(0, min(1, value / max_value))

    pygame.draw.rect(
        screen,
        fg,
        (x, y, int(width * ratio), height),
        border_radius=6,
    )


def draw_button(
    screen,
    rect,
    text,
    font,
    color=(80, 160, 255),
    hover_color=(110, 190, 255),
    text_color=(255, 255, 255),
):
    # rect имеет формат:
    # (X, Y, ШИРИНА, ВЫСОТА)
    #
    # X — положение кнопки влево/вправо.
    # Y — положение кнопки вверх/вниз.
    # ШИРИНА — размер кнопки по горизонтали.
    # ВЫСОТА — размер кнопки по вертикали.
    rect = pygame.Rect(rect)
    hovered = rect.collidepoint(pygame.mouse.get_pos())

    pygame.draw.rect(
        screen,
        hover_color if hovered else color,
        rect,
        border_radius=10,
    )

    surface = font.render(str(text), True, text_color)
    text_rect = surface.get_rect(center=rect.center)
    screen.blit(surface, text_rect)

    return hovered


def draw_silhouette(screen, x, y, color):
    # x — центр силуэта по горизонтали.
    # y — нижняя точка ног силуэта.
    #
    # Изменяйте x, чтобы передвинуть силуэт влево или вправо.
    # Изменяйте y, чтобы передвинуть силуэт вверх или вниз.
    dark = (45, 48, 62)

    # Размер головы — 48.
    pygame.draw.circle(screen, dark, (x, y - 125), 48)
    pygame.draw.circle(screen, color, (x, y - 125), 48, 4)

    # Размер туловища: ширина 130, высота 190.
    pygame.draw.rect(
        screen,
        dark,
        (x - 65, y - 70, 130, 190),
        border_radius=30,
    )
    pygame.draw.rect(
        screen,
        color,
        (x - 65, y - 70, 130, 190),
        width=4,
        border_radius=30,
    )

    # Последнее число в каждой линии — её толщина.
    pygame.draw.line(screen, color, (x - 55, y - 40), (x - 125, y + 100), 24)
    pygame.draw.line(screen, color, (x + 55, y - 40), (x + 125, y + 100), 24)
    pygame.draw.line(screen, color, (x - 30, y + 115), (x - 45, y + 270), 30)
    pygame.draw.line(screen, color, (x + 30, y + 115), (x + 45, y + 270), 30)


class FloatingText:
    def __init__(
        self,
        x,
        y,
        text,
        font,
        color=(255, 60, 60),
        duration=60,
        velocity=-1.5,
    ):
        # x и y — начальная позиция всплывающего текста.
        self.x = x
        self.y = y
        self.text = str(text)
        self.font = font
        self.color = color
        self.duration = duration
        self.max_duration = duration

        # Скорость движения текста вверх.
        # Сделайте число более отрицательным — текст будет двигаться быстрее.
        self.vy = velocity

    def update(self):
        self.y += self.vy
        self.duration -= 1

    def draw(self, screen):
        if self.duration <= 0:
            return

        surface = self.font.render(self.text, True, self.color)

        if self.duration < self.max_duration // 2:
            alpha = int(
                255 * self.duration / (self.max_duration // 2)
            )
            surface.set_alpha(alpha)

        rect = surface.get_rect(
            center=(int(self.x), int(self.y))
        )
        screen.blit(surface, rect)


class FloatingImage:
    def __init__(self, x, y, image, label, font, color, duration=360, velocity=-1.5):
        self.x = x
        self.y = y
        self.image = image
        self.label = label
        self.font = font
        self.color = color
        self.duration = duration
        self.max_duration = duration
        self.vy = velocity

    def update(self):
        self.y += self.vy
        self.duration -= 1

    def draw(self, screen):
        if self.duration <= 0:
            return
        image = self.image.copy()
        if self.duration < self.max_duration // 2:
            image.set_alpha(int(255 * self.duration / (self.max_duration // 2)))
        rect = image.get_rect(center=(int(self.x), int(self.y)))
        screen.blit(image, rect)
        label = self.font.render(self.label, True, self.color)
        screen.blit(label, label.get_rect(center=(rect.centerx, rect.bottom - 28)))


def update_and_draw_floating_texts(screen, floating_texts):
    for floating_text in floating_texts[:]:
        floating_text.update()
        floating_text.draw(screen)

        if floating_text.duration <= 0:
            floating_texts.remove(floating_text)
