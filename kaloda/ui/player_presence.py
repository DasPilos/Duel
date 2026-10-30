"""Другие игроки на карте: рисование, поиск под курсором и карточка при наведении."""

import pygame

from kaloda import settings
from kaloda.ui.character_card import CharacterCard
from kaloda.ui.class_identity import class_icon


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
        icon = class_icon(occupant.get("type", "warrior"))
        group_width = icon.get_width() + 4 + label.get_width()
        group_left = sx - group_width // 2
        label_rect = label.get_rect(
            midbottom=(group_left + icon.get_width() + 4 + label.get_width() // 2, name_y)
        )
        icon_y = name_y - label.get_height() + (label.get_height() - icon.get_height()) // 2
        icon_rect = pygame.Rect(group_left, icon_y, icon.get_width(), icon.get_height())
        background = label_rect.union(icon_rect).inflate(8, 4)
        pygame.draw.rect(screen, (20, 22, 26), background, border_radius=3)
        pygame.draw.rect(screen, (105, 109, 115), background, 1, border_radius=3)
        screen.blit(icon, icon_rect)
        screen.blit(label, label_rect)


def player_at(scene, screen_position, location):
    """Игрок под курсором (не AFK, не сам игрок) или None."""
    x, y = screen_position
    for occupant in active_player_entities(scene, location):
        sx, sy = scene.world_to_screen(occupant["position_x"], occupant["position_y"])
        if pygame.Rect(sx - 22, sy - 58, 44, 62).collidepoint(x, y):
            return dict(occupant)
    return None


def draw_player_hover_card(screen, player):
    profile = dict(player)
    profile["id"] = player.get("character_id", player.get("id"))
    profile["character_id"] = profile["id"]
    card = CharacterCard.get_or_create(profile["id"])
    card.draw(screen, pygame.Rect(settings.ENEMY_CARD_RECT), profile=profile,
              border_color=(95, 174, 225), title="ИГРОК РЯДОМ", editable=False)
