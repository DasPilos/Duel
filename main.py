import pygame

from core.settings import FPS, HEIGHT, WIDTH
from scenes.duel_scene import DuelScene


def main():
    pygame.init()

    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Мини-дуэль")

    clock = pygame.time.Clock()
    scene = DuelScene()

    running = True

    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            else:
                scene.handle_event(event)

        scene.update(dt)
        scene.draw(screen)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
