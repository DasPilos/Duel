import pygame

from core import settings


def active_player_entities(scene, location):
    chat = getattr(scene, "chat", None)
    if chat is None:
        return []
    character = getattr(getattr(scene, "session", None), "character", {}) or {}
    own_id = str(character.get("id", ""))
    return [
        occupant for occupant in chat.occupants
        if not occupant.get("afk") and occupant.get("location") == location
        and occupant.get("position_x") is not None and occupant.get("position_y") is not None
        and str(occupant.get("character_id")) != own_id
    ]


def draw_active_players(scene, screen, location):
    for occupant in active_player_entities(scene, location):
        sx, sy = scene.world_to_screen(occupant["position_x"], occupant["position_y"])
        if not (-80 <= sx <= settings.WIDTH + 80 and -100 <= sy <= settings.HEIGHT + 20):
            continue

        direction = occupant.get("position_direction") or "s"
        frames = getattr(scene, "player_directional_frames", {}).get(direction, [])
        if frames:
            sprite = frames[0]
            sprite_rect = sprite.get_rect(midbottom=(sx, sy))
            screen.blit(sprite, sprite_rect)
            name_y = sprite_rect.top - 4
        else:
            pygame.draw.ellipse(screen, (16, 17, 20), (sx - 14, sy - 4, 28, 10))
            pygame.draw.circle(screen, (218, 190, 153), (sx, sy - 28), 7)
            pygame.draw.rect(screen, (74, 126, 102), (sx - 6, sy - 21, 12, 17), border_radius=3)
            name_y = sy - 44

        label = scene.grid_font.render(occupant.get("name", "Игрок"), True, (184, 224, 255))
        label_rect = label.get_rect(midbottom=(sx, name_y))
        background = label_rect.inflate(8, 4)
        pygame.draw.rect(screen, (17, 23, 29), background, border_radius=3)
        pygame.draw.rect(screen, (79, 139, 179), background, 1, border_radius=3)
        screen.blit(label, label_rect)


def draw_afk_players(scene, screen, location):
    chat = getattr(scene, "chat", None)
    if chat is None:
        return
    for occupant in chat.occupants:
        if (not occupant.get("afk") or occupant.get("location") != location
                or occupant.get("position_x") is None or occupant.get("position_y") is None):
            continue
        sx, sy = scene.world_to_screen(occupant["position_x"], occupant["position_y"])
        if not (-80 <= sx <= settings.WIDTH + 80 and -100 <= sy <= settings.HEIGHT + 20):
            continue

        direction = occupant.get("position_direction") or "s"
        frames = getattr(scene, "player_directional_frames", {}).get(direction, [])
        if frames:
            sprite = frames[0].copy()
            sprite.fill((135, 139, 145, 255), special_flags=pygame.BLEND_RGBA_MULT)
            sprite_rect = sprite.get_rect(midbottom=(sx, sy))
            screen.blit(sprite, sprite_rect)
            name_y = sprite_rect.top - 4
        else:
            pygame.draw.ellipse(screen, (16, 17, 20), (sx - 14, sy - 4, 28, 10))
            pygame.draw.circle(screen, (145, 149, 153), (sx, sy - 28), 7)
            pygame.draw.rect(screen, (100, 105, 112), (sx - 6, sy - 21, 12, 17), border_radius=3)
            name_y = sy - 44

        label = scene.grid_font.render(f"{occupant.get('name', 'Игрок')} (АФК)", True, (153, 157, 163))
        label_rect = label.get_rect(midbottom=(sx, name_y))
        background = label_rect.inflate(8, 4)
        pygame.draw.rect(screen, (20, 22, 26), background, border_radius=3)
        pygame.draw.rect(screen, (105, 109, 115), background, 1, border_radius=3)
        screen.blit(label, label_rect)