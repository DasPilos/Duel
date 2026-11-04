"""Интерфейс боя на арене: подсветка арены, кнопки хода, рука и подсказки."""

import math
import re
from types import SimpleNamespace

import pygame

from client.network import ServerError
from kaloda import settings
from kaloda.combat.arena_battle import (
    ENEMY_CARDS_PER_TURN,
    ANCIENT_ENT_DECK,
    ANCIENT_ENT_NAME,
    FOREST_SPIRIT_RANGE,
    NECROMANCER_DECK,
    SKELETON_GUARD_DECK,
    SKELETON_KING_DECK,
    SKELETON_DECK,
    KOBOLD_DECK,
    MAX_CARDS_PER_TURN,
    MOVE_RANGE,
    SUMMON_RANGE,
    WOLF_MAX_HP,
    ArenaBattle,
    arena_center_for_tiles,
    arena_layout,
    card_role,
    create_ally_archer,
    create_ancient_ent,
    create_necromancer,
    create_kobold,
    create_skeleton,
    create_skeleton_guard,
    create_skeleton_king,
    hex_distance,
    hex_distance_to_center,
    hex_neighbors,
    spread_positions,
)
from kaloda.map_config import DUNGEON_ROOM_ORIGIN
from kaloda.ui.hud import draw_button


RESOURCE_NAMES = {
    "rage": "Ярость",
    "accuracy": "Меткость",
    "concentration": "Концентрация",
    "mana": "Мана",
    "necrotism": "Некротизм",
}

RESULT_TEXT = {
    "win": ("ПОБЕДА!", "Противник повержен.", (120, 235, 140)),
    "loss": ("ПОРАЖЕНИЕ", "Вы вернётесь в зал с полным здоровьем.", (245, 110, 100)),
    "teleport": ("ТЕЛЕПОРТ", "Вы покинули арену.", (110, 210, 255)),
}


def draw_kobold(screen, cx, cy, tile_size, outline=None):
    """Процедурный кобольд: ноги стоят у нижнего края тайла с центром (cx, cy)."""
    k = tile_size / 48
    foot_y = cy + int(tile_size * 0.42)
    pygame.draw.ellipse(screen, (10, 12, 14), (cx - int(16 * k), foot_y - int(5 * k), int(32 * k), int(10 * k)))
    body = pygame.Rect(0, 0, int(22 * k), int(24 * k))
    body.midbottom = (cx, foot_y - int(3 * k))
    pygame.draw.rect(screen, (120, 74, 46), (cx - int(9 * k), foot_y - int(8 * k), int(6 * k), int(8 * k)))
    pygame.draw.rect(screen, (120, 74, 46), (cx + int(3 * k), foot_y - int(8 * k), int(6 * k), int(8 * k)))
    pygame.draw.ellipse(screen, (150, 92, 52), body)
    pygame.draw.ellipse(screen, (95, 58, 34), body, 2)
    head_center = (cx, body.top - int(7 * k))
    head_r = int(11 * k)
    ear = int(12 * k)
    pygame.draw.polygon(screen, (165, 102, 58), [
        (cx - head_r + 2, head_center[1] - 2), (cx - head_r - ear, head_center[1] - ear), (cx - 3, head_center[1] - head_r + 2)])
    pygame.draw.polygon(screen, (165, 102, 58), [
        (cx + head_r - 2, head_center[1] - 2), (cx + head_r + ear, head_center[1] - ear), (cx + 3, head_center[1] - head_r + 2)])
    pygame.draw.circle(screen, (172, 108, 62), head_center, head_r)
    pygame.draw.circle(screen, (95, 58, 34), head_center, head_r, 2)
    for side in (-1, 1):
        pygame.draw.circle(screen, (255, 220, 60), (cx + side * int(4 * k), head_center[1] - 1), max(2, int(2.5 * k)))
    pygame.draw.line(screen, (240, 235, 220), (cx - int(3 * k), head_center[1] + int(5 * k)),
                     (cx + int(3 * k), head_center[1] + int(5 * k)), 2)
    # Дубина-сук в правой руке
    pygame.draw.line(screen, (92, 64, 36), (cx + int(11 * k), body.centery),
                     (cx + int(20 * k), body.top - int(10 * k)), max(3, int(4 * k)))
    if outline is not None:
        pygame.draw.rect(screen, outline, (cx - tile_size // 2 + 2, cy - tile_size // 2 + 2, tile_size - 4, tile_size - 4), 2, border_radius=6)


def draw_archer(screen, cx, cy, tile_size):
    """Процедурный лучник-союзник в зелёном плаще с луком."""
    k = tile_size / 48
    foot_y = cy + int(tile_size * 0.42)
    pygame.draw.ellipse(screen, (10, 12, 14), (cx - int(14 * k), foot_y - int(5 * k), int(28 * k), int(10 * k)))
    pygame.draw.rect(screen, (70, 52, 34), (cx - int(7 * k), foot_y - int(10 * k), int(5 * k), int(10 * k)))
    pygame.draw.rect(screen, (70, 52, 34), (cx + int(2 * k), foot_y - int(10 * k), int(5 * k), int(10 * k)))
    body = pygame.Rect(0, 0, int(20 * k), int(28 * k))
    body.midbottom = (cx, foot_y - int(8 * k))
    pygame.draw.polygon(screen, (46, 110, 58), [
        (body.left - int(3 * k), body.bottom), (body.centerx, body.top - int(2 * k)), (body.right + int(3 * k), body.bottom)])
    pygame.draw.rect(screen, (60, 140, 72), body.inflate(-int(6 * k), 0), border_radius=4)
    head = (cx, body.top - int(7 * k))
    pygame.draw.circle(screen, (232, 196, 160), head, int(8 * k))
    pygame.draw.polygon(screen, (40, 96, 50), [
        (cx - int(10 * k), head[1] - int(1 * k)), (cx, head[1] - int(16 * k)), (cx + int(10 * k), head[1] - int(1 * k))])
    bow_rect = pygame.Rect(cx + int(6 * k), body.top - int(6 * k), int(16 * k), int(36 * k))
    pygame.draw.arc(screen, (130, 88, 40), bow_rect, -1.4, 1.4, max(2, int(3 * k)))
    pygame.draw.line(screen, (225, 225, 225), (bow_rect.centerx, bow_rect.top + 2), (bow_rect.centerx, bow_rect.bottom - 2), 1)


def draw_skeleton(screen, cx, cy, tile_size, outline=None):
    k = tile_size / 48
    foot_y = cy + int(tile_size * 0.42)
    bone = (218, 214, 190)
    shadow = (10, 12, 14)
    pygame.draw.ellipse(screen, shadow, (cx - int(15 * k), foot_y - int(5 * k),
                                         int(30 * k), int(10 * k)))
    for side in (-1, 1):
        hip = (cx + int(side * 6 * k), foot_y - int(18 * k))
        knee = (cx + int(side * 8 * k), foot_y - int(9 * k))
        pygame.draw.line(screen, bone, hip, knee, max(2, int(3 * k)))
        pygame.draw.circle(screen, (105, 104, 94), knee, max(1, int(2 * k)))
        pygame.draw.line(screen, bone, knee, (cx + int(side * 9 * k), foot_y), max(2, int(3 * k)))
        shoulder = (cx + int(side * 8 * k), foot_y - int(34 * k))
        hand = (cx + int(side * 15 * k), foot_y - int(20 * k))
        pygame.draw.line(screen, bone, shoulder, hand, max(2, int(3 * k)))
    pygame.draw.line(screen, bone, (cx, foot_y - int(35 * k)),
                     (cx, foot_y - int(17 * k)), max(3, int(4 * k)))
    pygame.draw.line(screen, bone, (cx - int(8 * k), foot_y - int(32 * k)),
                     (cx + int(8 * k), foot_y - int(32 * k)), max(2, int(3 * k)))
    for rib_y in (foot_y - 29 * k, foot_y - 25 * k, foot_y - 21 * k):
        pygame.draw.arc(
            screen, bone,
            pygame.Rect(cx - int(8 * k), int(rib_y - 2 * k), int(16 * k), int(6 * k)),
            0, math.pi, max(1, int(2 * k)),
        )
    skull = pygame.Rect(0, 0, max(8, int(16 * k)), max(8, int(13 * k)))
    skull.midbottom = (cx, foot_y - int(35 * k))
    pygame.draw.ellipse(screen, bone, skull)
    pygame.draw.ellipse(screen, (105, 104, 94), skull, max(1, int(2 * k)))
    for side in (-1, 1):
        pygame.draw.circle(screen, (110, 45, 40),
                           (cx + int(side * 4 * k), skull.centery), max(1, int(2 * k)))
    pygame.draw.line(screen, (105, 104, 94), (cx - int(4 * k), skull.bottom - int(2 * k)),
                     (cx + int(4 * k), skull.bottom - int(2 * k)), max(1, int(2 * k)))
    if outline is not None:
        pygame.draw.rect(screen, outline, (cx - tile_size // 2 + 2, cy - tile_size // 2 + 2,
                                           tile_size - 4, tile_size - 4), 2, border_radius=6)


def draw_skeleton_king(screen, cx, cy, tile_size, outline=None):
    draw_skeleton(screen, cx, cy, tile_size, outline)
    k = tile_size / 48
    crown_y = cy - int(tile_size * 0.36)
    crown = [
        (cx - int(11 * k), crown_y + int(5 * k)),
        (cx - int(10 * k), crown_y - int(4 * k)),
        (cx - int(4 * k), crown_y + int(1 * k)),
        (cx, crown_y - int(7 * k)),
        (cx + int(4 * k), crown_y + int(1 * k)),
        (cx + int(10 * k), crown_y - int(4 * k)),
        (cx + int(11 * k), crown_y + int(5 * k)),
    ]
    pygame.draw.polygon(screen, (205, 164, 46), crown)
    pygame.draw.polygon(screen, (91, 64, 22), crown, max(1, int(2 * k)))


def draw_necromancer(screen, cx, cy, tile_size, outline=None):
    k = tile_size / 48
    foot_y = cy + int(tile_size * 0.42)
    robe = (75, 47, 91)
    trim = (151, 103, 177)
    pygame.draw.ellipse(screen, (10, 12, 14), (cx - int(16 * k), foot_y - int(5 * k),
                                                int(32 * k), int(10 * k)))
    pygame.draw.polygon(screen, robe, [
        (cx, foot_y - int(40 * k)),
        (cx - int(10 * k), foot_y - int(29 * k)),
        (cx - int(15 * k), foot_y - int(3 * k)),
        (cx + int(15 * k), foot_y - int(3 * k)),
        (cx + int(10 * k), foot_y - int(29 * k)),
    ])
    pygame.draw.polygon(screen, trim, [
        (cx, foot_y - int(39 * k)),
        (cx - int(6 * k), foot_y - int(27 * k)),
        (cx, foot_y - int(30 * k)),
        (cx + int(6 * k), foot_y - int(27 * k)),
    ])
    hood = [(cx, foot_y - int(48 * k)), (cx - int(12 * k), foot_y - int(35 * k)),
            (cx + int(12 * k), foot_y - int(35 * k))]
    pygame.draw.polygon(screen, (46, 34, 59), hood)
    pygame.draw.circle(screen, (183, 169, 164), (cx, foot_y - int(36 * k)), max(3, int(7 * k)))
    for side in (-1, 1):
        pygame.draw.circle(screen, (242, 65, 83),
                           (cx + int(side * 3 * k), foot_y - int(37 * k)), max(1, int(2 * k)))
    staff_x = cx + int(18 * k)
    pygame.draw.line(screen, (99, 68, 45), (staff_x, foot_y - int(4 * k)),
                     (staff_x, foot_y - int(47 * k)), max(2, int(3 * k)))
    pygame.draw.circle(screen, (190, 93, 220), (staff_x, foot_y - int(47 * k)),
                       max(2, int(5 * k)))
    pygame.draw.circle(screen, (244, 176, 255), (staff_x, foot_y - int(47 * k)),
                       max(1, int(2 * k)))
    if outline is not None:
        pygame.draw.rect(screen, outline, (cx - tile_size // 2 + 2, cy - tile_size // 2 + 2,
                                           tile_size - 4, tile_size - 4), 2, border_radius=6)


def draw_golem(screen, cx, cy, tile_size):
    k = tile_size / 48
    foot_y = cy + int(tile_size * 0.42)
    pygame.draw.ellipse(screen, (10, 12, 14), (cx - int(18 * k), foot_y - int(5 * k), int(36 * k), int(10 * k)))
    for side in (-1, 1):
        pygame.draw.rect(screen, (96, 88, 78), (cx + side * int(9 * k) - int(5 * k), foot_y - int(12 * k), int(10 * k), int(12 * k)), border_radius=3)
        pygame.draw.rect(screen, (110, 100, 88), (cx + side * int(17 * k) - int(5 * k), foot_y - int(36 * k), int(10 * k), int(22 * k)), border_radius=4)
    body = pygame.Rect(0, 0, int(28 * k), int(28 * k))
    body.midbottom = (cx, foot_y - int(10 * k))
    pygame.draw.rect(screen, (128, 118, 102), body, border_radius=6)
    pygame.draw.rect(screen, (74, 68, 60), body, 2, border_radius=6)
    pygame.draw.line(screen, (90, 200, 110), (body.left + int(6 * k), body.centery), (body.right - int(8 * k), body.centery + int(5 * k)), 2)
    head = pygame.Rect(0, 0, int(16 * k), int(13 * k))
    head.midbottom = (cx, body.top + 2)
    pygame.draw.rect(screen, (140, 130, 112), head, border_radius=4)
    for side in (-1, 1):
        pygame.draw.circle(screen, (120, 255, 140), (cx + side * int(4 * k), head.centery), max(2, int(2 * k)))


def draw_cloud(screen, cx, cy, tile_size, ticks=0):
    k = tile_size / 48
    base_y = cy - int(10 * k)
    pygame.draw.ellipse(screen, (10, 12, 14), (cx - int(14 * k), cy + int(14 * k), int(28 * k), int(8 * k)))
    for dx, dy, r in ((-12, 2, 10), (0, -4, 13), (12, 2, 10), (0, 6, 11)):
        pygame.draw.circle(screen, (92, 98, 120), (cx + int(dx * k), base_y + int(dy * k)), int(r * k))
    pygame.draw.circle(screen, (128, 136, 160), (cx - int(2 * k), base_y - int(6 * k)), int(8 * k))
    if (ticks // 250) % 2 == 0:
        bolt = [(cx + int(2 * k), base_y + int(12 * k)), (cx - int(4 * k), base_y + int(22 * k)),
                (cx + int(2 * k), base_y + int(22 * k)), (cx - int(3 * k), base_y + int(32 * k))]
        pygame.draw.lines(screen, (255, 235, 90), False, bolt, max(2, int(3 * k)))


def draw_forest_spirit(screen, cx, cy, tile_size):
    k = tile_size / 48
    pygame.draw.ellipse(screen, (10, 12, 14), (cx - int(15 * k), cy + int(14 * k),
                                                int(30 * k), int(8 * k)))
    pygame.draw.circle(screen, (97, 205, 125), (cx, cy), int(16 * k))
    pygame.draw.circle(screen, (47, 123, 73), (cx, cy), int(16 * k), max(1, int(2 * k)))
    pygame.draw.polygon(screen, (137, 226, 153), [
        (cx, cy - int(24 * k)), (cx - int(6 * k), cy - int(7 * k)),
        (cx + int(5 * k), cy - int(4 * k)),
    ])
    pygame.draw.circle(screen, (238, 247, 172), (cx - int(5 * k), cy - int(2 * k)),
                       max(1, int(2 * k)))
    pygame.draw.circle(screen, (238, 247, 172), (cx + int(5 * k), cy - int(2 * k)),
                       max(1, int(2 * k)))


def draw_ancient_ent(screen, cx, cy, tile_size):
    k = tile_size / 48
    pygame.draw.ellipse(screen, (10, 12, 14), (cx - int(25 * k), cy + int(14 * k),
                                                int(50 * k), int(12 * k)))
    trunk = pygame.Rect(cx - int(16 * k), cy - int(28 * k), int(32 * k), int(48 * k))
    pygame.draw.rect(screen, (94, 63, 38), trunk, border_radius=max(3, int(10 * k)))
    pygame.draw.rect(screen, (54, 42, 28), trunk, max(1, int(3 * k)), border_radius=max(3, int(10 * k)))
    for dx, dy, radius in ((-19, -30, 18), (0, -41, 22), (19, -27, 18), (0, -21, 17)):
        pygame.draw.circle(screen, (45, 111, 57), (cx + int(dx * k), cy + int(dy * k)),
                           int(radius * k))
        pygame.draw.circle(screen, (28, 75, 39), (cx + int(dx * k), cy + int(dy * k)),
                           int(radius * k), max(1, int(2 * k)))
    for dx in (-6, 6):
        pygame.draw.circle(screen, (255, 190, 65), (cx + int(dx * k), cy - int(7 * k)),
                           max(2, int(3 * k)))


def draw_wolf(screen, cx, cy, tile_size):
    k = tile_size / 48
    pygame.draw.ellipse(screen, (12, 14, 17), (cx - int(18 * k), cy + int(12 * k),
                                                int(36 * k), int(9 * k)))
    body = pygame.Rect(cx - int(15 * k), cy - int(8 * k), int(31 * k), int(20 * k))
    pygame.draw.ellipse(screen, (115, 119, 124), body)
    pygame.draw.circle(screen, (142, 147, 151), (cx + int(12 * k), cy - int(11 * k)),
                       int(9 * k))
    pygame.draw.polygon(screen, (115, 119, 124), [
        (cx + int(5 * k), cy - int(16 * k)), (cx + int(5 * k), cy - int(29 * k)),
        (cx + int(13 * k), cy - int(19 * k)),
    ])
    pygame.draw.polygon(screen, (115, 119, 124), [
        (cx + int(15 * k), cy - int(17 * k)), (cx + int(23 * k), cy - int(27 * k)),
        (cx + int(22 * k), cy - int(12 * k)),
    ])
    for dx in (-9, 10):
        pygame.draw.line(screen, (82, 86, 91), (cx + int(dx * k), cy + int(5 * k)),
                         (cx + int(dx * k), cy + int(15 * k)), max(2, int(4 * k)))
    pygame.draw.circle(screen, (246, 206, 80), (cx + int(15 * k), cy - int(12 * k)),
                       max(1, int(2 * k)))


def draw_skull(screen, cx, cy, tile_size):
    k = tile_size / 48
    hover_y = cy - int(4 * k)
    pygame.draw.ellipse(screen, (10, 12, 14), (cx - int(13 * k), cy + int(14 * k),
                                                int(26 * k), int(7 * k)))
    pygame.draw.circle(screen, (100, 56, 132), (cx, hover_y), max(1, int(19 * k)))
    skull = pygame.Rect(cx - int(13 * k), hover_y - int(13 * k),
                        max(8, int(26 * k)), max(8, int(22 * k)))
    pygame.draw.ellipse(screen, (204, 204, 181), skull)
    pygame.draw.ellipse(screen, (81, 76, 77), skull, max(1, int(2 * k)))
    jaw = pygame.Rect(cx - int(9 * k), hover_y + int(5 * k),
                      max(6, int(18 * k)), max(4, int(7 * k)))
    pygame.draw.rect(screen, (177, 177, 157), jaw, border_radius=max(1, int(2 * k)))
    pygame.draw.rect(screen, (81, 76, 77), jaw, max(1, int(1 * k)),
                     border_radius=max(1, int(2 * k)))
    for side in (-1, 1):
        pygame.draw.ellipse(screen, (42, 25, 49),
                            (cx + int(side * 7 * k) - int(3 * k),
                             hover_y - int(3 * k), max(3, int(6 * k)), max(4, int(8 * k))))
    pygame.draw.polygon(screen, (76, 61, 67), [
        (cx, hover_y + int(2 * k)),
        (cx - int(2 * k), hover_y + int(6 * k)),
        (cx + int(2 * k), hover_y + int(6 * k)),
    ])
    for tooth_x in (-5, 0, 5):
        pygame.draw.line(screen, (81, 76, 77),
                         (cx + int(tooth_x * k), jaw.top + int(k)),
                         (cx + int(tooth_x * k), jaw.bottom - int(k)),
                         max(1, int(k)))


def draw_bone_dog(screen, cx, cy, tile_size):
    k = tile_size / 48
    foot_y = cy + int(tile_size * 0.38)
    bone, shadow = (207, 205, 180), (10, 12, 14)
    pygame.draw.ellipse(screen, shadow, (cx - int(19 * k), foot_y - int(4 * k),
                                         int(38 * k), int(8 * k)))
    body = pygame.Rect(cx - int(13 * k), cy - int(9 * k),
                       max(8, int(27 * k)), max(8, int(17 * k)))
    pygame.draw.ellipse(screen, (125, 124, 109), body)
    pygame.draw.ellipse(screen, bone, body, max(1, int(2 * k)))
    for rib_x in (-7, -1, 5):
        pygame.draw.arc(
            screen, bone,
            pygame.Rect(cx + int(rib_x * k), body.top + int(2 * k),
                        max(5, int(10 * k)), max(8, int(14 * k))),
            -math.pi / 2, math.pi / 2, max(1, int(2 * k)),
        )
    spine_y = cy - int(8 * k)
    pygame.draw.line(screen, bone, (cx - int(12 * k), spine_y),
                     (cx + int(12 * k), spine_y), max(2, int(3 * k)))
    head = pygame.Rect(cx + int(9 * k), cy - int(17 * k),
                       max(8, int(16 * k)), max(7, int(13 * k)))
    pygame.draw.ellipse(screen, bone, head)
    pygame.draw.ellipse(screen, (82, 77, 73), head, max(1, int(2 * k)))
    snout = pygame.Rect(head.right - int(2 * k), head.centery - int(2 * k),
                        max(5, int(8 * k)), max(4, int(6 * k)))
    pygame.draw.ellipse(screen, (185, 183, 162), snout)
    pygame.draw.circle(screen, (46, 28, 48),
                       (head.centerx + int(2 * k), head.centery - int(2 * k)),
                       max(1, int(2 * k)))
    for leg_x in (-9, 9):
        hip = (cx + int(leg_x * k), body.bottom - int(2 * k))
        knee = (cx + int((leg_x + (2 if leg_x < 0 else -2)) * k),
                foot_y - int(7 * k))
        pygame.draw.line(screen, bone, hip, knee, max(2, int(3 * k)))
        pygame.draw.circle(screen, (100, 96, 85), knee, max(1, int(2 * k)))
        pygame.draw.line(screen, bone, knee,
                         (knee[0], foot_y), max(2, int(3 * k)))
    tail_base = (body.left + int(k), body.centery)
    tail_mid = (body.left - int(7 * k), body.centery - int(6 * k))
    tail_tip = (body.left - int(12 * k), body.centery - int(12 * k))
    pygame.draw.line(screen, bone, tail_base, tail_mid, max(2, int(3 * k)))
    pygame.draw.line(screen, bone, tail_mid, tail_tip, max(2, int(3 * k)))


def build_player_fighter(session):
    """Боец и колода игрока по профилю персонажа и выбранной колоде."""
    from kaloda.combat.fighter import Fighter
    from kaloda.scenes.duel_scene import DuelScene, _side_deck

    character = getattr(session, "character", None) or {}
    fighter = Fighter(character.get("name", "Герой"), int(character.get("level", 1) or 1),
                      character.get("type", "warrior"))
    if "stats" in character:
        try:
            DuelScene._apply_fighter_profile(fighter, character)
        except (KeyError, TypeError, ValueError):
            pass
    fighter.hp = max(1, min(int(character.get("hp", fighter.max_hp) or fighter.max_hp), fighter.max_hp))
    if character.get("mp") is not None:
        fighter.mp = max(0, min(int(character["mp"]), fighter.max_mp))
    fighter.equipment = dict(getattr(session, "equipment", None) or {})
    selected = getattr(session, "selected_deck", None) or {}
    return fighter, _side_deck(selected.get("cards"), fighter.profession_type)


class ArenaController:
    CARD_W = 150
    CARD_H = 200
    CARD_GAP = 14
    ENEMY_DELAY = 0.7
    STUN_DELAY = 1.3
    RESULT_DELAY = 2.2
    WALK_STEP_SECONDS = 0.12
    BUTTONS = (
        ("teleport", "ТЕЛЕПОРТ"),
        ("inventory", "ИНВЕНТАРЬ"),
        ("move", "ПОХОДИТЬ"),
        ("cards", "РАЗЫГРАТЬ КАРТЫ"),
        ("end", "ЗАВЕРШИТЬ ХОД"),
    )

    def __init__(self, scene, battle, center_world=None):
        self.scene = scene
        self.battle = battle
        self.center_world = center_world or (scene.player_x, scene.player_y)
        self.mode = None
        self.selected_card = None
        self.burn_mode = False
        self.targeting = False
        self.transfer_target = None
        self.walk_path = []
        self.walk_step_timer = 0.0
        self.actor_movement_queue = []
        self.actor_visual_positions = {}
        self.actor_movement = None
        self.pending = None
        self.pending_timer = 0.0
        self.teleport_confirmation = False
        self.inventory_open = False
        self.inventory_items = []
        self.inventory_selected = 0
        self.pending_battle_item = None
        self.result_timer = None
        self.done = False
        self.notice = None
        self.notice_timer = 0.0
        self.draw_toasts = []
        self._seen_draw_events = []
        self.title_font = pygame.font.SysFont(settings.FONT_NAME, 26, bold=True)
        self.big_font = pygame.font.SysFont(settings.FONT_NAME, 54, bold=True)
        self.font = pygame.font.SysFont(settings.FONT_NAME, 20)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 16)
        self.effect_font = pygame.font.SysFont(settings.FONT_NAME, 11, bold=True)
        self._attack_overlay = pygame.Surface(
            (settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA
        )
        self._card_renderer = None
        dialog_width, dialog_height = 560, 220
        self.teleport_dialog_rect = pygame.Rect(
            (settings.WIDTH - dialog_width) // 2,
            (settings.HEIGHT - dialog_height) // 2,
            dialog_width,
            dialog_height,
        )
        button_y = self.teleport_dialog_rect.bottom - 58
        self.teleport_cancel_rect = pygame.Rect(self.teleport_dialog_rect.left + 36, button_y, 224, 38)
        self.teleport_confirm_rect = pygame.Rect(self.teleport_dialog_rect.right - 260, button_y, 224, 38)
        self.inventory_rect = pygame.Rect(24, settings.HEIGHT - 354, 500, 320)
        self.inventory_close_rect = pygame.Rect(self.inventory_rect.right - 38, self.inventory_rect.top + 8, 28, 28)
        self.inventory_use_rect = pygame.Rect(self.inventory_rect.right - 154, self.inventory_rect.bottom - 48, 130, 34)
        width, height, gap = 240, 48, 10
        top = settings.HEIGHT - len(self.BUTTONS) * (height + gap) - 40
        self.buttons = {
            key: pygame.Rect(settings.WIDTH - width - 24, top + index * (height + gap), width, height)
            for index, (key, _) in enumerate(self.BUTTONS)
        }

    @classmethod
    def start(cls, scene, enemy_tile, enemy_count=1, ally=False, boss=None, dungeon_room=None):
        from kaloda.combat.card_database import is_mage_profession
        from kaloda.scenes.duel_scene import _side_deck

        player_tile = (int(scene.player_x // scene.tile_size), int(scene.player_y // scene.tile_size))
        center = arena_center_for_tiles(player_tile, tuple(enemy_tile))
        rect, player_pos, enemy_pos, center = arena_layout(
            player_tile, tuple(enemy_tile), scene.grid_w, scene.grid_h,
            extra_fighters=enemy_count - 1 + int(ally),
            arena_center=center,
        )
        enemy_world = ((enemy_tile[0] + 0.5) * scene.tile_size, (enemy_tile[1] + 0.5) * scene.tile_size)
        center_world = ((scene.player_x + enemy_world[0]) / 2, (scene.player_y + enemy_world[1]) / 2)
        fighter, cards = build_player_fighter(scene.session)
        if dungeon_room == 1:
            enemies = [create_skeleton("Скелет"), create_skeleton("Скелет")]
            enemy_deck = SKELETON_DECK
            enemy_pos = spread_positions(rect, player_pos, enemy_pos, 2, arena_center=center)
        elif dungeon_room == 3:
            enemies = [
                create_skeleton("Скелет"),
                create_skeleton("Скелет"),
                create_necromancer(),
            ]
            enemy_deck = SKELETON_DECK
            enemy_pos = spread_positions(rect, player_pos, enemy_pos, 3, arena_center=center)
        elif dungeon_room == 5:
            enemies = [
                create_skeleton_guard(),
                create_skeleton_guard(),
                create_skeleton_king(),
            ]
            enemy_deck = SKELETON_GUARD_DECK
            enemy_pos = spread_positions(rect, player_pos, enemy_pos, 3, arena_center=center)
        elif boss == "ancient_ent":
            enemies = create_ancient_ent()
            enemy_deck = ANCIENT_ENT_DECK
        elif boss == "skeleton":
            enemies = create_skeleton()
            enemy_deck = SKELETON_DECK
        elif boss == "necromancer":
            enemies = create_necromancer()
            enemy_deck = NECROMANCER_DECK
        elif enemy_count > 1:
            enemies = [create_kobold(name=f"Кобольд {index}") for index in range(1, enemy_count + 1)]
            enemy_pos = spread_positions(rect, player_pos, enemy_pos, enemy_count, arena_center=center)
            enemy_deck = KOBOLD_DECK
        else:
            enemies = create_kobold()
            enemy_deck = KOBOLD_DECK
        allies = []
        if ally:
            archer = create_ally_archer(fighter.level)
            taken = {tuple(player_pos), *(tuple(pos) for pos in (enemy_pos if enemy_count > 1 else [enemy_pos]))}
            allies.append((archer, _side_deck(None, "archer"),
                           cls._ally_start(rect, player_pos, taken, center)))
        battle = ArenaBattle(
            fighter, enemies, cards, rect, player_pos, enemy_pos,
            enemy_deck=enemy_deck,
            mage_mode=is_mage_profession(fighter.profession_type),
            allies=allies,
            arena_center=center,
            blocked_tiles=getattr(scene, "arena_obstacles", ()),
            player_draft=True,
        )
        if dungeon_room == 3:
            battle.enemy_decks[battle.enemy_ids[2]] = NECROMANCER_DECK
        elif dungeon_room == 5:
            battle.enemy_decks[battle.enemy_ids[0]] = SKELETON_GUARD_DECK
            battle.enemy_decks[battle.enemy_ids[1]] = SKELETON_GUARD_DECK
            battle.enemy_decks[battle.enemy_ids[2]] = SKELETON_KING_DECK
        controller = cls(scene, battle, center_world)
        controller._collect_draw_toasts(0.0)
        return controller

    @classmethod
    def start_dungeon(cls, scene, room):
        enemy_count = {1: 2, 3: 3, 5: 3}[int(room)]
        x, y = DUNGEON_ROOM_ORIGIN
        return cls.start(
            scene,
            (x + 8, y + 5),
            enemy_count=enemy_count,
            dungeon_room=int(room),
        )

    @staticmethod
    def _ally_start(rect, player_pos, taken, arena_center):
        """Свободная клетка рядом с игроком внутри арены."""
        left, top, width, height = rect
        px, py = player_pos
        radius = (min(width, height) - 1) / 2
        for dx, dy in ((0, 2), (0, -2), (2, 0), (-2, 0), (1, 1), (1, -1), (-1, 1), (-1, -1), (0, 1), (0, -1), (1, 0), (-1, 0)):
            tile = (px + dx, py + dy)
            if (left <= tile[0] < left + width and top <= tile[1] < top + height
                    and tile not in taken and hex_distance(player_pos, tile) <= SUMMON_RANGE
                    and hex_distance_to_center(tile, arena_center) <= radius + 1e-9):
                return tile
        raise ValueError("Нет свободной клетки рядом с игроком для союзника")

    # ------------------------------------------------------------------ геометрия

    def tile_center(self, tile):
        q, r = tile[0] - (tile[1] - (tile[1] & 1)) // 2, tile[1]
        center_q, center_r = self.battle.arena_center
        size = self.scene.tile_size
        return (self.center_world[0] + (q - center_q + (r - center_r) / 2) * size,
                self.center_world[1] + (r - center_r) * size * math.sqrt(3) / 2)

    def tile_polygon(self, tile, scale=1.0):
        cx, cy = self.tile_center(tile)
        radius = self.scene.tile_size / math.sqrt(3) * scale
        half_width = self.scene.tile_size / 2 * scale
        return [(cx, cy - radius), (cx + half_width, cy - radius / 2),
                (cx + half_width, cy + radius / 2), (cx, cy + radius),
                (cx - half_width, cy + radius / 2), (cx - half_width, cy - radius / 2)]

    def mouse_tile(self, pos):
        wx, wy = self.scene.screen_to_world(*pos)
        center_q, center_r = self.battle.arena_center
        size = self.scene.tile_size
        row = center_r + (wy - self.center_world[1]) / (size * math.sqrt(3) / 2)
        col_q = center_q + (wx - self.center_world[0]) / size - (row - center_r) / 2
        candidates = []
        for y in range(math.floor(row) - 1, math.floor(row) + 3):
            q = round(col_q + (row - y) / 2)
            col = q + (y - (y & 1)) // 2
            candidates.extend((x, y) for x in range(col - 1, col + 2))
        return min(candidates, key=lambda tile: (
            (self.tile_center(tile)[0] - wx) ** 2 + (self.tile_center(tile)[1] - wy) ** 2
        ))

    def arena_center_world(self):
        return self.center_world

    def hand_rects(self):
        hand = self.battle.engine.hands["player"]
        total = len(hand) * self.CARD_W + max(0, len(hand) - 1) * self.CARD_GAP
        left = (settings.WIDTH - total) // 2
        top = settings.HEIGHT - self.CARD_H - 30
        rects = []
        for index, card in enumerate(hand):
            rect = pygame.Rect(left + index * (self.CARD_W + self.CARD_GAP), top, self.CARD_W, self.CARD_H)
            if card is self.selected_card:
                rect.y -= 26
            rects.append((card, rect))
        return rects

    def _draft_rects(self):
        cards = self.battle.engine.table_for("player")
        columns = min(6, max(1, len(cards)))
        gap = 10
        width = min(280, (settings.WIDTH - 100 - (columns - 1) * gap) // columns)
        height = 76 if len(cards) > 6 else 112
        rows = (len(cards) + columns - 1) // columns
        left = (settings.WIDTH - columns * width - (columns - 1) * gap) // 2
        top = (settings.HEIGHT - rows * height - (rows - 1) * gap) // 2
        return [
            (card, pygame.Rect(
                left + (index % columns) * (width + gap),
                top + (index // columns) * (height + gap),
                width, height,
            ))
            for index, card in enumerate(cards)
        ]

    def _draw_choice_rects(self):
        cards = self.battle.engine.draw_choices["player"]
        width, height, gap = 300, 130, 20
        left = (settings.WIDTH - 2 * width - gap) // 2
        top = (settings.HEIGHT - height) // 2
        return [
            (card, pygame.Rect(left + index * (width + gap), top, width, height))
            for index, card in enumerate(cards)
        ]

    def unit_at(self, pos):
        tile = self.mouse_tile(pos)
        size = max(1, round(self.scene.tile_size * self.scene.zoom))
        battle = self.battle
        units = ("player", *battle.alive_allies(), *battle.alive_enemies(), *battle.summons)
        for side in units:
            if (
                side not in self.actor_visual_positions
                and tile == battle.positions[side]
            ):
                return side
        for side in units:
            cx, cy = self._unit_world_position(side)
            sx, sy = self.scene.world_to_screen(cx, cy)
            sprite = pygame.Rect(sx - size // 2, sy - int(size * 1.3), size, int(size * 1.8))
            if sprite.collidepoint(pos):
                return side
        return None

    def _player_turn_ready(self):
        return (
            not self.walk_path and self.pending is None
            and not self._actor_movement_pending()
            and self.result_timer is None and self.battle.player_can_act()
        )

    def _button_enabled(self, key):
        if self.teleport_confirmation:
            return False
        if key == "inventory":
            return self.result_timer is None
        if not self._player_turn_ready():
            return False
        if key == "move":
            return not self.battle.moved
        if key == "cards":
            return self.battle.cards_played < MAX_CARDS_PER_TURN
        return True

    # ------------------------------------------------------------------ ввод

    def handle_event(self, event):
        if self.teleport_confirmation:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.teleport_confirmation = False
                return True
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.teleport_confirm_rect.collidepoint(event.pos):
                    self.teleport_confirmation = False
                    self._schedule("teleport", self.ENEMY_DELAY)
                    self._notice("Телепорт к кристаллу сработает в начале вашего следующего хода")
                elif self.teleport_cancel_rect.collidepoint(event.pos):
                    self.teleport_confirmation = False
                return True
            return True
        if self._actor_movement_pending():
            return True
        if self.battle.player_draft:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for card, rect in self._draft_rects():
                    if rect.collidepoint(event.pos):
                        self.battle.choose_starting_card(card.key)
                        return True
            return True
        draw_choices = self.battle.engine.draw_choices["player"]
        if draw_choices:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for card, rect in self._draw_choice_rects():
                    if rect.collidepoint(event.pos):
                        self.battle.choose_draw_card(card.key)
                        self._collect_draw_toasts(0.0)
                        return True
            return True
        if self.inventory_open:
            return self._handle_inventory_event(event)
        if self.walk_path:
            return True
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_b and self._player_turn_ready():
                if self.battle.engine.burned_this_turn["player"]:
                    self._notice("За ход можно сжечь только одну карту")
                elif self.burn_mode and self.selected_card is not None:
                    self._burn_card(self.selected_card)
                else:
                    self.burn_mode = not self.burn_mode
                    self.mode = "cards" if self.burn_mode else None
                    self.selected_card = None
                    self.targeting = False
                    self.transfer_target = None
                    if self.burn_mode:
                        self._notice("Выберите карту и нажмите B, чтобы сжечь её")
                return True
            if event.key == pygame.K_s and self.targeting:
                self._cancel_targeting("Розыгрыш отменён")
                return True
            if event.key in (pygame.K_s, pygame.K_ESCAPE) and self.pending_battle_item is not None:
                self.pending_battle_item = None
                self._notice("Выбор цели для предмета отменён")
                return True
            if event.key == pygame.K_ESCAPE and (self.mode or self.selected_card):
                self.mode = None
                self._cancel_targeting()
                return True
        if event.type not in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL):
            return False
        if event.type != pygame.MOUSEBUTTONDOWN:
            return True
        if event.button == 3:
            if self.pending_battle_item is not None:
                self.pending_battle_item = None
                self._notice("Выбор цели для предмета отменён")
                return True
            if self.targeting:
                self._cancel_targeting("Розыгрыш отменён")
            else:
                self.mode = None
                self.selected_card = None
            return True
        if event.button != 1 or self.result_timer is not None:
            return True
        for key, rect in self.buttons.items():
            if rect.collidepoint(event.pos):
                if self._button_enabled(key):
                    self._press(key)
                return True
        if self.mode == "cards" and self._player_turn_ready():
            for card, rect in reversed(self.hand_rects()):
                if rect.collidepoint(event.pos):
                    self._click_card(card)
                    return True
            if self.targeting:
                self._click_target(event.pos)
                return True
        if self.pending_battle_item is not None:
            unit = self.unit_at(event.pos)
            if unit in self.battle.enemy_ids:
                self._use_battle_item(self.pending_battle_item, unit)
            else:
                self._notice("Выберите врага для метательного кинжала")
            return True
        unit = self.unit_at(event.pos)
        if self.mode != "move" and unit in self.battle.enemy_ids:
            if self.battle.target != unit:
                self.battle.select_target(unit)
                self._notice(f"Цель: {self.battle.enemy.name}", 1.5)
            return True
        if self.mode == "move" and self._player_turn_ready():
            tile = self.mouse_tile(event.pos)
            path = self.battle.begin_player_movement(tile)
            if path:
                self.walk_path = path
                self.walk_step_timer = self.WALK_STEP_SECONDS
            elif tile != self.battle.positions["player"]:
                self._notice(f"Сюда не дойти: до {MOVE_RANGE} клеток по свободным клеткам арены")
        return True

    def _click_card(self, card):
        """1-й клик выбирает карту, 2-й клик по ней же начинает выбор цели."""
        if self.burn_mode:
            self.selected_card = card
            self.transfer_target = None
            self._notice(f"Выбрана карта «{card.name}». Нажмите B, чтобы сжечь её")
            return
        if card is self.selected_card:
            if not self.targeting:
                self.targeting = True
                self.transfer_target = None
                self._notice(self._targeting_hint(card), 3.0)
            return
        self.targeting = False
        self.transfer_target = None
        if self.battle.can_play_card(card):
            self.selected_card = card
        else:
            self.selected_card = None
            self._notice(self._cannot_play_reason(card))

    def _burn_card(self, card):
        if self.battle.engine.burn_card("player", card.key):
            self.battle._log(f"{self.battle.player.name} сжигает карту «{card.name}»")
            self.burn_mode = False
            self.selected_card = None
            self.targeting = False
            self.mode = "cards"
            self._notice("Карта сожжена: восстановлено 15% максимального ресурса")
        else:
            self._notice("Не удалось сжечь карту")

    def _click_target(self, pos):
        card = self.selected_card
        if card is None:
            self._cancel_targeting("Выбор карты сброшен — выберите карту снова")
            return
        if card.effect_type == "necromancer_transfer":
            if self.transfer_target is None:
                unit = self.unit_at(pos)
                if unit in self.valid_targets():
                    self.transfer_target = unit
                    self._notice("Выберите свободный гекс для перемещения существа")
                else:
                    self._notice(self._targeting_hint(card))
            else:
                tile = self.mouse_tile(pos)
                if tile in self.valid_tiles():
                    self._play(card, self.transfer_target, tile)
                else:
                    self._notice(self._targeting_hint(card))
            return
        if card_role(card) == "enemy":
            tile = self.mouse_tile(pos)
            if tile in self.valid_tiles():
                self._play(card, None, aim_tile=tile)
                return
            unit = self.unit_at(pos)
            if unit in self.battle.alive_enemies():
                aim_tile = self.battle.aoe_aim_tile_for_target(
                    card, self.battle.positions[unit]
                )
                if aim_tile is not None:
                    self._play(card, None, aim_tile=aim_tile)
                    return
            self._notice(self._targeting_hint(card))
            return
        if card_role(card) in {"summon", "tile"}:
            tile = self.mouse_tile(pos)
            if tile in self.valid_tiles():
                self._play(card, tile)
            else:
                self._notice(self._targeting_hint(card))
            return
        unit = self.unit_at(pos)
        if unit is not None and unit in self.valid_targets():
            self._play(card, unit)
        else:
            self._notice(self._targeting_hint(card))

    def _cancel_targeting(self, text=None):
        self.targeting = False
        self.selected_card = None
        self.transfer_target = None
        if text:
            self._notice(text, 1.5)

    def valid_targets(self):
        if not self.targeting or self.selected_card is None:
            return []
        if card_role(self.selected_card) == "enemy":
            return []
        if self.selected_card.effect_type == "necromancer_transfer" and self.transfer_target is not None:
            return [self.transfer_target]
        return self.battle.card_targets(self.selected_card)

    def valid_tiles(self):
        if not self.targeting or self.selected_card is None:
            return []
        card = self.selected_card
        if card_role(card) == "enemy":
            return self.battle.card_aim_tiles(card)
        if card.effect_type == "necromancer_transfer" and self.transfer_target is not None:
            return self.battle.transfer_tiles(self.transfer_target, card)
        if card_role(card) not in {"summon", "tile"}:
            return []
        return (
            self.battle.card_tiles(card)
            if card.effect_type == "arena_wolf" or card_role(card) == "tile"
            else self.battle.summon_tiles()
        )

    def _targeting_hint(self, card):
        if card.effect_type == "necromancer_transfer":
            if self.transfer_target is not None:
                return "Выберите свободный гекс для перемещения существа — S отменяет розыгрыш"
            return "Выберите существо-союзника для переноса — S отменяет розыгрыш"
        role = card_role(card)
        text = {
            "enemy": "Выберите гекс для атаки",
            "ally": "Выберите себя или союзника",
            "self": "Нажмите на себя",
            "summon": f"Выберите клетку для призыва (радиус {SUMMON_RANGE})",
            "tile": "Выберите свободный гекс в пределах дальности карты",
        }[role]
        return f"{text} — S отменяет розыгрыш"

    def _press(self, key):
        if key != "end":
            self._cancel_targeting()
        if key == "cards":
            self.mode = None if self.mode == "cards" else "cards"
            self.selected_card = None
            self.transfer_target = None
        elif key == "move":
            self.mode = None if self.mode == "move" else "move"
            self.selected_card = None
            self.transfer_target = None
        elif key == "inventory":
            self.mode = None
            self.selected_card = None
            self.transfer_target = None
            self._open_inventory()
        elif key == "teleport":
            self.mode = None
            self.selected_card = None
            self.transfer_target = None
            self.targeting = False
            self.teleport_confirmation = True
        elif key == "end":
            self._schedule("end", self.ENEMY_DELAY)

    def _open_inventory(self):
        character = getattr(self.scene.session, "character", None)
        client = getattr(self.scene.session, "client", None)
        if not isinstance(character, dict) or character.get("id") is None:
            self._notice("Персонаж не загружен")
            return
        try:
            state = client.get_inventory(character["id"])
        except (ServerError, AttributeError, OSError) as error:
            self._notice(f"Не удалось загрузить инвентарь: {error}")
            return
        self.inventory_items = [
            item for item in state.get("inventory", [])
            if item.get("item_id") in (4, 5, 6, 52)
        ]
        self.inventory_selected = min(self.inventory_selected, max(0, len(self.inventory_items) - 1))
        self.inventory_open = True

    def _inventory_rows(self):
        return [
            pygame.Rect(self.inventory_rect.left + 14, self.inventory_rect.top + 48 + index * 34,
                        self.inventory_rect.width - 28, 30)
            for index in range(min(len(self.inventory_items), 7))
        ]

    def _handle_inventory_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.inventory_open = False
            return True
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL, pygame.KEYDOWN)
        if self.inventory_close_rect.collidepoint(event.pos):
            self.inventory_open = False
            return True
        for index, rect in enumerate(self._inventory_rows()):
            if rect.collidepoint(event.pos):
                self.inventory_selected = index
                return True
        if self.inventory_use_rect.collidepoint(event.pos) and self.inventory_items:
            item = self.inventory_items[self.inventory_selected]
            if item.get("item_id") == 6:
                self.pending_battle_item = item
                self.inventory_open = False
                self._notice("Выберите врага для метательного кинжала (S — отмена)")
            else:
                self._use_battle_item(item)
            return True
        return True

    def _use_battle_item(self, item, target=None):
        item_id = int(item["item_id"])
        available, message = self.battle.can_use_battle_item(item_id, target)
        if not available:
            self.pending_battle_item = None
            self._notice(message)
            return
        character = getattr(self.scene.session, "character", None) or {}
        try:
            self.scene.session.client.remove_inventory_item(
                character["id"], item_id, 1
            )
        except (ServerError, AttributeError, KeyError, OSError) as error:
            self.pending_battle_item = None
            self._notice(f"Не удалось использовать предмет: {error}")
            return
        before = self._team_hp()
        success, message = self.battle.use_battle_item(item_id, target)
        self.pending_battle_item = None
        if not success:
            self._notice(message)
            return
        quantity = int(item.get("quantity", 1))
        if quantity <= 1:
            self.inventory_items = [entry for entry in self.inventory_items if entry is not item]
            self.inventory_selected = min(self.inventory_selected, max(0, len(self.inventory_items) - 1))
        else:
            item["quantity"] = quantity - 1
        self._float_changes(before)
        self._notice(message)

    def _schedule(self, action, delay):
        self.mode = None
        self.selected_card = None
        self.targeting = False
        self.pending = action
        self.pending_timer = delay

    def _cannot_play_reason(self, card):
        if self.battle.cards_played >= MAX_CARDS_PER_TURN:
            return f"За ход можно разыграть не больше {MAX_CARDS_PER_TURN} карт"
        role = card_role(card)
        if role == "summon" and not self.battle.summon_tiles():
            return f"Нет свободных тайлов в радиусе {SUMMON_RANGE} для призыва"
        card_range = (card.effect_data or {}).get("range")
        if role == "enemy" and card_range is not None and not self.battle.card_targets(card):
            return f"Все враги слишком далеко (дальность {card_range})"
        return "Не хватает ресурса для этой карты"

    def _team_hp(self):
        battle = self.battle
        return {uid: battle.fighters[uid].hp for uid in ("player", *battle.ally_ids, *battle.enemy_ids)}

    def _float_changes(self, before):
        for uid, hp in before.items():
            if uid in self.battle.positions:
                self._float_damage(uid, int(hp - self.battle.fighters[uid].hp))

    def _play(self, card, target, destination=None, aim_tile=None):
        before = self._team_hp()
        event = self.battle.play_card(
            card, target, destination=destination, aim_tile=aim_tile
        )
        self.selected_card = None
        self.targeting = False
        self.transfer_target = None
        if event is None:
            self._notice(self._cannot_play_reason(card))
            return
        self._float_changes(before)
        self._float_combat_outcome(event)
        if self.battle.cards_played >= MAX_CARDS_PER_TURN:
            self.mode = None

    def _notice(self, text, seconds=2.5):
        self.notice = text
        self.notice_timer = seconds

    def _float_damage(self, side, amount):
        if amount == 0:
            return
        x, y = self.tile_center(self.battle.positions[side])
        text, color = (f"-{amount}", (255, 95, 80)) if amount > 0 else (f"+{-amount}", (110, 235, 130))
        self.scene._add_floating_message(text, x, y - self.scene.tile_size, color)

    def _float_combat_outcome(self, event):
        target = event.get("target")
        if target not in self.battle.positions:
            return
        x, y = self.tile_center(self.battle.positions[target])
        hits = event.get("hit_results")
        outcomes = hits or [event]
        offset = 0
        for hit in outcomes:
            if hit.get("dodged"):
                self.scene._add_floating_message(
                    "ПРОМАХ", x, y - self.scene.tile_size - offset, (180, 205, 225)
                )
                offset += 22
            if hit.get("critical") and int(hit.get("damage", event.get("damage", 0))) > 0:
                self.scene._add_floating_message(
                    "КРИТ!", x, y - self.scene.tile_size - offset, (255, 220, 75)
                )
                offset += 22

    # ------------------------------------------------------------------ сообщения о доборе карт

    TOAST_SECONDS = 6.0

    def _draw_event_text(self, event):
        if event.get("start"):
            return f"Стартовая рука: {', '.join(event['cards'])}"
        if event["cards"]:
            names = ", ".join(f"«{name}»" for name in event["cards"])
            return f"Ход {event['round']}: добрана карта {names}"
        if event.get("hand_full"):
            return f"Ход {event['round']}: рука полна ({self.battle.hand_limit}/{self.battle.hand_limit}) — карта не добрана"
        return f"Ход {event['round']}: колода пуста — карта не добрана"

    def _collect_draw_toasts(self, dt):
        for event in self.battle.draw_events:
            if not any(event is seen for seen in self._seen_draw_events):
                self._seen_draw_events.append(event)
                self.draw_toasts.append([self._draw_event_text(event), self.TOAST_SECONDS])
        del self._seen_draw_events[:-12]
        for toast in self.draw_toasts:
            toast[1] -= dt
        self.draw_toasts = [toast for toast in self.draw_toasts if toast[1] > 0][-4:]

    def _draw_draw_toasts(self, screen):
        toasts = self.draw_toasts
        # Над рукой, когда она открыта, чтобы не перекрывать карты
        bottom = settings.HEIGHT - (self.CARD_H + 90 if self.mode == "cards" else 40)
        for text, remaining in reversed(toasts):
            surf = self.small_font.render(text, True, (225, 235, 255))
            rect = surf.get_rect(bottomleft=(32, bottom))
            panel = rect.inflate(20, 12)
            alpha = int(220 * min(1.0, remaining / 1.0))
            box = pygame.Surface(panel.size, pygame.SRCALPHA)
            box.fill((16, 24, 38, alpha))
            screen.blit(box, panel)
            pygame.draw.rect(screen, (90, 140, 210), panel, 1, border_radius=6)
            surf.set_alpha(min(255, alpha + 35))
            screen.blit(surf, rect)
            bottom = panel.top - 6

    # ------------------------------------------------------------------ обновление

    def update(self, dt):
        self._collect_draw_toasts(dt)
        self._advance_player_walk(dt)
        self._collect_actor_movement_events()
        self._advance_actor_movement(dt)
        if self.notice_timer > 0:
            self.notice_timer -= dt
            if self.notice_timer <= 0:
                self.notice = None
        if self.pending is not None:
            self.pending_timer -= dt
            if self.pending_timer <= 0:
                action, self.pending = self.pending, None
                before = self._team_hp()
                if action == "teleport":
                    self.battle.teleport()
                else:
                    self.battle.end_player_turn()
                self._float_changes(before)
        elif (self.result_timer is None and not self.battle.is_over()
              and self.battle.active_side == "player" and self.battle.stunned("player")):
            self._schedule("end", self.STUN_DELAY)
        if self.battle.is_over() and self.result_timer is None and self.pending is None:
            self.result_timer = self.RESULT_DELAY
        if self.result_timer is not None:
            self.result_timer -= dt
            if self.result_timer <= 0:
                self.done = True
        self._collect_actor_movement_events()
        self._sync_scene()

    def _advance_player_walk(self, dt):
        if not self.walk_path:
            return
        self.walk_step_timer -= dt
        while self.walk_path and self.walk_step_timer <= 0:
            step = self.walk_path[0]
            if not self.battle.move_player_step(step):
                self.walk_path.clear()
                self.battle.player_movement_path.clear()
                self._notice("Перемещение остановлено")
                break
            self.walk_path.pop(0)
            if self.battle.last_move_interrupted:
                self.walk_path.clear()
                self.battle.player_movement_path.clear()
                self._notice("Перемещение прервано эффектом ловушки")
                break
            self.walk_step_timer += self.WALK_STEP_SECONDS
        if not self.walk_path:
            self.battle.player_movement_path.clear()
            self.mode = None

    def _collect_actor_movement_events(self):
        for event in self.battle.movement_events:
            unit = event["unit"]
            start = self.tile_center(event["start"])
            self.actor_visual_positions.setdefault(unit, start)
            self.actor_movement_queue.append({
                "unit": unit,
                "start": tuple(event["start"]),
                "path": list(event["path"]),
                "step": 0,
            })
        self.battle.movement_events.clear()

    def _actor_movement_pending(self):
        return self.actor_movement is not None or bool(self.actor_movement_queue)

    def _advance_actor_movement(self, dt):
        remaining = max(0.0, float(dt))
        while True:
            if self.actor_movement is None:
                if not self.actor_movement_queue:
                    return
                queued = self.actor_movement_queue.pop(0)
                unit = queued["unit"]
                start = self.tile_center(queued["start"])
                self.actor_visual_positions[unit] = start
                self.actor_movement = {
                    **queued,
                    "elapsed": 0.0,
                    "from": start,
                    "to": self.tile_center(queued["path"][0]),
                }
            if remaining <= 0:
                return

            movement = self.actor_movement
            elapsed = min(
                self.WALK_STEP_SECONDS,
                movement["elapsed"] + remaining,
            )
            remaining -= elapsed - movement["elapsed"]
            movement["elapsed"] = elapsed
            progress = elapsed / self.WALK_STEP_SECONDS
            start_x, start_y = movement["from"]
            end_x, end_y = movement["to"]
            self.actor_visual_positions[movement["unit"]] = (
                start_x + (end_x - start_x) * progress,
                start_y + (end_y - start_y) * progress,
            )

            if progress >= 1:
                movement["step"] += 1
                if movement["step"] == len(movement["path"]):
                    unit = movement["unit"]
                    self.actor_movement = None
                    if not any(
                        queued["unit"] == unit
                        for queued in self.actor_movement_queue
                    ):
                        self.actor_visual_positions.pop(unit, None)
                    continue
                movement["from"] = movement["to"]
                movement["to"] = self.tile_center(
                    movement["path"][movement["step"]]
                )
                movement["elapsed"] = 0.0
            if remaining <= 0:
                return

    def _unit_world_position(self, unit):
        position = self.actor_visual_positions.get(unit)
        if position is None:
            return self.tile_center(self.battle.positions[unit])
        x, y = position
        if self.actor_movement and self.actor_movement["unit"] == unit:
            progress = self.actor_movement["elapsed"] / self.WALK_STEP_SECONDS
            y -= math.sin(math.pi * progress) * self.scene.tile_size * 0.08
        return x, y

    def _unit_screen_polygon(self, unit, scale=0.9):
        logical_center = self.tile_center(self.battle.positions[unit])
        visual_center = self._unit_world_position(unit)
        logical_screen = self.scene.world_to_screen(*logical_center)
        visual_screen = self.scene.world_to_screen(*visual_center)
        dx = visual_screen[0] - logical_screen[0]
        dy = visual_screen[1] - logical_screen[1]
        return [
            (x + dx, y + dy)
            for x, y in (
                self.scene.world_to_screen(*point)
                for point in self.tile_polygon(self.battle.positions[unit], scale=scale)
            )
        ]

    def _sync_scene(self):
        scene = self.scene
        px, py = self._unit_world_position("player")
        ex, ey = self.tile_center(self.battle.positions[self.battle.target])
        scene.player_x, scene.player_y = float(px), float(py)
        scene.player_target = None
        scene.player_state = "idle"
        if (ex, ey) != (px, py):
            scene.player_direction = scene._vector_to_direction(ex - px, ey - py)
            scene.player_facing_right = ex >= px
        if self.actor_movement and self.actor_movement["unit"] == "player":
            start_x, start_y = self.actor_movement["from"]
            end_x, end_y = self.actor_movement["to"]
            scene.player_state = "walk"
            scene.player_direction = scene._vector_to_direction(
                end_x - start_x, end_y - start_y
            )
            scene.player_facing_right = end_x >= start_x

    # ------------------------------------------------------------------ отрисовка в мире

    def draw_world(self, screen):
        scene = self.scene
        size = max(1, round(scene.tile_size * scene.zoom))
        left, top, width, height = self.battle.arena_rect
        hover = self.mouse_tile(pygame.mouse.get_pos())
        hovered_unit = self.unit_at(pygame.mouse.get_pos())
        reachable = (set(self.battle.reachable_tiles("player"))
                     if self.mode == "move" and self._player_turn_ready() else set())
        summon_tiles = set(self.valid_tiles())
        targets = set(self.valid_targets())
        target_tiles = {self.battle.positions[uid]: uid for uid in targets}
        attack_aim_tiles = (
            set(self.battle.card_aim_tiles(self.selected_card))
            if self.targeting and self.selected_card is not None
            and card_role(self.selected_card) == "enemy"
            else set()
        )
        aoe_radius = (
            int((self.selected_card.effect_data or {}).get("aoe_radius", 0))
            if attack_aim_tiles else 0
        )
        attack_preview = set()
        attack_preview_center = hover if hover in attack_aim_tiles else None
        if (
            attack_preview_center is None
            and attack_aim_tiles
            and hovered_unit in self.battle.alive_enemies()
        ):
            attack_preview_center = self.battle.aoe_aim_tile_for_target(
                self.selected_card, self.battle.positions[hovered_unit]
            )
        if attack_preview_center is not None:
            attack_preview = {
                tile for y in range(top, top + height)
                for x in range(left, left + width)
                if self.battle.in_arena(tile := (x, y))
                if hex_distance(tile, attack_preview_center) <= aoe_radius
            }
            if not attack_preview:
                attack_preview.add(attack_preview_center)
        max_range_tiles = set()
        if attack_aim_tiles:
            card_range = (self.selected_card.effect_data or {}).get("range")
            origin = self.battle.positions["player"]
            max_range_tiles = {
                (x, y)
                for y in range(top, top + height)
                for x in range(left, left + width)
                if self.battle.in_arena((x, y))
                and (
                    card_range is None
                    or hex_distance(origin, (x, y)) <= int(card_range)
                )
            }
        if attack_preview:
            self._attack_overlay.fill((0, 0, 0, 0))
        for y in range(top, top + height):
            for x in range(left, left + width):
                tile = (x, y)
                if not self.battle.in_arena(tile):
                    continue
                polygon = [scene.world_to_screen(*point) for point in self.tile_polygon(tile)]
                color = (48, 65, 37) if (x + y) % 2 else (53, 70, 40)
                if tile in self.battle.grave_soil:
                    color = (108, 108, 114)
                if tile in reachable:
                    color = (70, 155, 85) if tile == hover else (48, 105, 60)
                if tile in summon_tiles:
                    color = (80, 165, 210) if tile == hover else (45, 105, 135)
                if tile in self.battle.barriers:
                    color = (105, 105, 115)
                if any(trap["tile"] == tile for trap in self.battle.traps):
                    color = (118, 118, 122)
                if tile in target_tiles:
                    color = ((135, 60, 50) if target_tiles[tile] in self.battle.enemy_ids
                             else (50, 135, 65))
                if tile in self.battle.grave_soil:
                    color = (108, 108, 114)
                pygame.draw.polygon(screen, color, polygon)
                if tile in attack_preview:
                    pygame.draw.polygon(self._attack_overlay, (255, 35, 35, 92), polygon)
                pygame.draw.polygon(screen, (150, 150, 80), polygon, 1)
                for edge, neighbor in enumerate(hex_neighbors(tile)):
                    if tile in max_range_tiles and neighbor not in max_range_tiles:
                        pygame.draw.line(
                            screen, (245, 245, 255), polygon[edge],
                            polygon[(edge + 1) % 6], 3,
                        )
                    elif not self.battle.in_arena(neighbor):
                        pygame.draw.line(screen, (235, 200, 90), polygon[edge], polygon[(edge + 1) % 6], 3)
        if attack_preview:
            screen.blit(self._attack_overlay, (0, 0))
        alive = self.battle.alive_enemies()
        units = ([("player", (90, 170, 255))]
                 + [(aid, (90, 225, 120)) for aid in self.battle.alive_allies()]
                 + [(sid, (110, 200, 255)) for sid in self.battle.summons]
                 + [(eid, (240, 90, 80)) for eid in alive])
        for side, color in units:
            polygon = self._unit_screen_polygon(side)
            pygame.draw.polygon(screen, color, polygon, 3)

        for aid in self.battle.alive_allies():
            ax, ay = scene.world_to_screen(*self._unit_world_position(aid))
            draw_archer(screen, ax, ay, size)
            fighter = self.battle.fighters[aid]
            scene._draw_badge(screen, ax, ay - int(size * 0.85),
                              f"{fighter.name} {max(0, int(fighter.hp))}/{fighter.max_hp}", (90, 200, 110))
        ticks = pygame.time.get_ticks()
        for sid, summon in self.battle.summons.items():
            ux, uy = scene.world_to_screen(*self._unit_world_position(sid))
            if summon["kind"] == "golem":
                draw_golem(screen, ux, uy, size)
                label = f"{summon['name']} {max(0, summon['hp'])}/{summon['max_hp']}"
            elif summon["kind"] == "forest_spirit":
                draw_forest_spirit(screen, ux, uy, size)
                label = f"{summon['name']} {max(0, summon['hp'])}/{summon['max_hp']}"
            elif summon["kind"] == "wolf":
                draw_wolf(screen, ux, uy, size)
                label = f"{summon['name']} {max(0, summon['hp'])}/{summon['max_hp']}"
            elif summon["kind"].startswith("necromancer_"):
                colors = {
                    "necromancer_familiar": (105, 235, 155),
                    "necromancer_lokrif": (75, 170, 90),
                    "necromancer_bone_hero": (215, 205, 155),
                    "necromancer_spirit": (175, 225, 235),
                    "necromancer_lyrk": (90, 210, 105),
                    "necromancer_grave_zink": (200, 220, 235),
                    "necromancer_bone_dragon": (190, 220, 160),
                }
                color = colors.get(summon["kind"], (160, 220, 170))
                pygame.draw.circle(screen, (230, 250, 225), (ux, uy), max(3, size // 3 + 2))
                pygame.draw.circle(screen, color, (ux, uy), max(2, size // 3))
                label = f"{summon['name']} {max(0, summon['hp'])}/{summon['max_hp']}"
            else:
                draw_cloud(screen, ux, uy, size, ticks)
                label = f"{summon['name']} ({summon['remaining']} х.)"
            scene._draw_badge(screen, ux, uy - int(size * 0.85), label, (110, 190, 240))
        for eid in alive:
            ex, ey = scene.world_to_screen(*self._unit_world_position(eid))
            hovered = hovered_unit == eid
            targeted = eid in targets
            outline = (255, 215, 60) if targeted and hovered else (240, 110, 90) if hovered or targeted else None
            fighter = self.battle.fighters[eid]
            if eid in self.battle.enemy_summons:
                summon_kind = self.battle.enemy_summon_kinds.get(eid)
                if summon_kind == "skull":
                    draw_skull(screen, ex, ey, size)
                elif summon_kind == "skeleton":
                    draw_skeleton(screen, ex, ey, size)
                elif summon_kind == "bone_dog":
                    draw_bone_dog(screen, ex, ey, size)
                else:
                    draw_wolf(screen, ex, ey, size)
            elif fighter.name == ANCIENT_ENT_NAME:
                draw_ancient_ent(screen, ex, ey, size)
            elif fighter.name == "Король скелетов":
                draw_skeleton_king(screen, ex, ey, size)
            elif fighter.name.startswith("Скелет"):
                draw_skeleton(screen, ex, ey, size)
            elif fighter.name.startswith("Некромансер"):
                draw_necromancer(screen, ex, ey, size)
            else:
                draw_kobold(screen, ex, ey, size)
            if outline is not None:
                polygon = self._unit_screen_polygon(eid)
                pygame.draw.polygon(screen, outline, polygon, 3)
            if (len(self.battle.enemy_ids) > 1 or fighter.name == ANCIENT_ENT_NAME
                    or eid in self.battle.enemy_summons):
                label = f"{fighter.name} {max(0, int(fighter.hp))}/{fighter.max_hp}"
                color = (255, 215, 60) if eid == self.battle.target else (220, 90, 70)
                scene._draw_badge(screen, ex, ey - int(size * 0.85), label, color)

    # ------------------------------------------------------------------ интерфейс

    def draw_ui(self, screen):
        self._draw_unit_effects(screen)
        self._draw_banner(screen)
        self._draw_log(screen)
        self._draw_buttons(screen)
        self._draw_draw_toasts(screen)
        if self.mode == "cards":
            self._draw_hand(screen)
        if self.inventory_open:
            self._draw_inventory(screen)
        side = self.unit_at(pygame.mouse.get_pos())
        if side is not None:
            self._draw_unit_tooltip(screen, side, pygame.mouse.get_pos())
        if self.notice:
            surf = self.font.render(self.notice, True, (255, 225, 140))
            rect = surf.get_rect(midbottom=(settings.WIDTH // 2, settings.HEIGHT - (self.CARD_H + 80 if self.mode == "cards" else 40)))
            pygame.draw.rect(screen, (20, 22, 28), rect.inflate(24, 12), border_radius=6)
            pygame.draw.rect(screen, (190, 160, 80), rect.inflate(24, 12), 1, border_radius=6)
            screen.blit(surf, rect)
        if self.result_timer is not None and self.battle.result in RESULT_TEXT:
            self._draw_result(screen)
        if self.teleport_confirmation:
            self._draw_teleport_confirmation(screen)
        if self.battle.player_draft:
            self._draw_card_choice_panel(screen, self._draft_rects(), "Выберите 2 карты; ещё 3 будут выданы случайно")
        elif self.battle.engine.draw_choices["player"]:
            self._draw_card_choice_panel(screen, self._draw_choice_rects(), "Выберите 1 из 2 карт")

    def _draw_card_choice_panel(self, screen, choices, title):
        shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 175))
        screen.blit(shade, (0, 0))
        title_surface = self.title_font.render(title, True, (245, 230, 190))
        title_y = 90 if len(choices) > 6 else settings.HEIGHT // 2 - 145
        screen.blit(title_surface, title_surface.get_rect(center=(settings.WIDTH // 2, title_y)))
        selected = len(self.battle.engine.hands["player"])
        for card, rect in choices:
            pygame.draw.rect(screen, (35, 48, 65), rect, border_radius=8)
            pygame.draw.rect(screen, (150, 190, 220), rect, 2, border_radius=8)
            name = self.font.render(card.name, True, (245, 245, 250))
            name_y = rect.top + (22 if rect.height < 100 else 34)
            screen.blit(name, name.get_rect(center=(rect.centerx, name_y)))
            resource = RESOURCE_NAMES.get(card.resource_type, card.resource_type)
            cost = self.small_font.render(f"{resource}: {card.resource_cost}", True, (215, 210, 180))
            cost_y = rect.top + (50 if rect.height < 100 else 68)
            screen.blit(cost, cost.get_rect(center=(rect.centerx, cost_y)))
        if self.battle.player_draft:
            hint = self.small_font.render(f"Выбрано: {min(selected, 2)}/2", True, (220, 225, 235))
            hint_y = max((rect.bottom for _, rect in choices), default=settings.HEIGHT // 2) + 32
            screen.blit(hint, hint.get_rect(center=(settings.WIDTH // 2, hint_y)))

    def _draw_inventory(self, screen):
        panel = self.inventory_rect
        pygame.draw.rect(screen, (20, 29, 40), panel, border_radius=8)
        pygame.draw.rect(screen, (100, 160, 210), panel, 2, border_radius=8)
        title = self.font.render("Боевые предметы", True, (220, 235, 250))
        screen.blit(title, (panel.left + 14, panel.top + 12))
        pygame.draw.rect(screen, (100, 60, 55), self.inventory_close_rect, border_radius=4)
        cross = self.small_font.render("×", True, (255, 255, 255))
        screen.blit(cross, cross.get_rect(center=self.inventory_close_rect.center))
        if not self.inventory_items:
            screen.blit(self.small_font.render("Подходящих предметов нет", True, (190, 195, 205)),
                        (panel.left + 14, panel.top + 58))
        for index, (item, rect) in enumerate(zip(self.inventory_items, self._inventory_rows())):
            selected = index == self.inventory_selected
            pygame.draw.rect(screen, (48, 75, 98) if selected else (34, 45, 58), rect, border_radius=4)
            name = f"{item['name']} ×{item.get('quantity', 1)}"
            screen.blit(self.small_font.render(name, True, (235, 240, 245)),
                        (rect.left + 8, rect.top + 6))
        if self.inventory_items:
            draw_button(screen, self.inventory_use_rect, "ИСПОЛЬЗОВАТЬ", self.small_font,
                        color=(55, 115, 155), hover_color=(70, 145, 190))

    def _draw_teleport_confirmation(self, screen):
        shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 155))
        screen.blit(shade, (0, 0))
        panel = self.teleport_dialog_rect
        pygame.draw.rect(screen, (24, 29, 39), panel, border_radius=10)
        pygame.draw.rect(screen, (230, 180, 75), panel, 2, border_radius=10)
        title = self.title_font.render("Подтвердите телепорт", True, (255, 220, 135))
        screen.blit(title, title.get_rect(center=(panel.centerx, panel.top + 46)))
        message = self.font.render(
            "Персонаж покинет арену и вернётся в зал. Продолжить?",
            True,
            (235, 235, 240),
        )
        screen.blit(message, message.get_rect(center=(panel.centerx, panel.top + 100)))
        draw_button(screen, self.teleport_cancel_rect, "ОСТАТЬСЯ", self.font,
                    color=(75, 85, 100), hover_color=(95, 105, 120), text_color=(245, 245, 245))
        draw_button(screen, self.teleport_confirm_rect, "ДА, ТЕЛЕПОРТИРОВАТЬ", self.font,
                    color=(145, 75, 60), hover_color=(180, 85, 65), text_color=(255, 245, 235))

    def _status_line(self):
        battle = self.battle
        many = len(battle.enemy_ids) > 1
        if battle.is_over() or self.result_timer is not None:
            return "Бой окончен"
        if self._actor_movement_pending():
            return "Существа перемещаются..."
        if self.pending == "teleport":
            return "Телепорт... ход кобольдов" if many else "Телепорт... ход кобольда"
        if self.pending == "end" and battle.stunned("player"):
            return "Вы оглушены — ход пропущен"
        if self.pending is not None or battle.active_side != "player":
            return "Ход кобольдов..." if many else "Ход кобольда..."
        return "Ваш ход"

    def _draw_banner(self, screen):
        battle = self.battle
        alive = len(battle.alive_enemies())
        opponent = (f"лагеря кобольдов ({alive}/{len(battle.enemy_ids)})"
                    if len(battle.enemy_ids) > 1 else battle.enemy.name)
        _, _, width, height = battle.arena_rect
        title = (f"БОЙ: {battle.player.name} против {opponent} — {width}×{height} — "
                 f"раунд {battle.round} — {self._status_line()}")
        details = (
            f"Перемещение: {'использовано' if battle.moved else f'доступно (до {MOVE_RANGE} клеток)'}   |   "
            f"Карты: {battle.cards_played}/{MAX_CARDS_PER_TURN}   |   "
            f"В руке: {len(battle.engine.hands['player'])}/{battle.hand_limit}   |   B — сжечь карту   |   "
            f"Цель: {battle.enemy.name}, дистанция {battle.distance()}"
        )
        title_surf = self.title_font.render(title, True, (255, 225, 140))
        details_surf = self.small_font.render(details, True, (210, 215, 225))
        width = max(title_surf.get_width(), details_surf.get_width()) + 40
        panel = pygame.Rect(0, 0, width, 70)
        panel.midtop = (settings.WIDTH // 2, 88)
        surface = pygame.Surface(panel.size, pygame.SRCALPHA)
        surface.fill((14, 16, 22, 225))
        screen.blit(surface, panel)
        pygame.draw.rect(screen, (190, 160, 80), panel, 2, border_radius=6)
        screen.blit(title_surf, title_surf.get_rect(midtop=(panel.centerx, panel.top + 8)))
        screen.blit(details_surf, details_surf.get_rect(midtop=(panel.centerx, panel.top + 44)))

    def _draw_log(self, screen):
        if not self.battle.log:
            return
        lines = self.battle.log[-7:]
        panel = pygame.Rect(20, 88, 470, 30 + len(lines) * 22)
        surface = pygame.Surface(panel.size, pygame.SRCALPHA)
        surface.fill((14, 16, 22, 200))
        screen.blit(surface, panel)
        pygame.draw.rect(screen, (90, 100, 120), panel, 1, border_radius=6)
        screen.blit(self.small_font.render("Журнал боя", True, (230, 210, 150)), (panel.left + 10, panel.top + 6))
        for index, line in enumerate(lines):
            screen.blit(self.small_font.render(line, True, (215, 220, 230)), (panel.left + 10, panel.top + 28 + index * 22))

    def _draw_buttons(self, screen):
        mouse = pygame.mouse.get_pos()
        for key, label in self.BUTTONS:
            rect = self.buttons[key]
            enabled = self._button_enabled(key)
            if not enabled:
                color, text = (52, 54, 60), (140, 140, 145)
            elif self.mode == key:
                color, text = (190, 145, 55), (255, 255, 255)
            elif rect.collidepoint(mouse):
                color, text = (85, 125, 175), (255, 255, 255)
            else:
                color, text = {
                    "teleport": (60, 120, 160), "end": (150, 95, 55),
                }.get(key, (65, 95, 135)), (240, 240, 240)
            draw_button(screen, rect, label, self.font, color=color, hover_color=color, text_color=text)

    def _renderer(self):
        if self._card_renderer is None:
            from kaloda.ui.renderers.card_area import CardAreaRenderer

            shim = SimpleNamespace(
                battle=self.battle.engine, player=self.battle.player, enemy=self.battle.enemy,
                small_font=self.small_font, font=self.font, phase="battle", burn_mode=False,
                burn_card_key=None, card_transfer=None, enemy_card_transfer=None, draw_transfer=None,
                draft_cleanup_started=False, draft_reveal_started=False, turn_deadline=None,
            )
            self._card_renderer = CardAreaRenderer(shim, None)
        return self._card_renderer

    def _draw_hand(self, screen):
        renderer = self._renderer()
        mouse = pygame.mouse.get_pos()
        hovered = None
        for card, rect in self.hand_rects():
            selected = card is self.selected_card
            if selected:
                glow = pygame.Surface((rect.width + 20, rect.height + 20), pygame.SRCALPHA)
                pygame.draw.rect(glow, (255, 215, 60, 110), glow.get_rect(), border_radius=12)
                screen.blit(glow, rect.move(-10, -10))
            renderer._draw_card_in_rect(screen, card, rect, is_selected=selected)
            if selected:
                pygame.draw.rect(screen, (255, 225, 80), rect.inflate(6, 6), 3, border_radius=8)
            elif not self.battle.can_play_card(card):
                dim = pygame.Surface(rect.size, pygame.SRCALPHA)
                dim.fill((5, 7, 12, 120))
                screen.blit(dim, rect)
            if rect.collidepoint(mouse):
                hovered = (card, rect)
        if self.targeting and self.selected_card is not None:
            hint = self._targeting_hint(self.selected_card)
        elif self.selected_card is not None:
            hint = "Нажмите на выбранную карту ещё раз, чтобы выбрать цель"
        else:
            hint = "Выберите карту для розыгрыша"
        surf = self.small_font.render(hint, True, (235, 230, 200))
        screen.blit(surf, surf.get_rect(midbottom=(settings.WIDTH // 2, settings.HEIGHT - self.CARD_H - 62)))
        if hovered is not None:
            try:
                renderer._draw_card_tooltip(screen, *hovered)
            except (AttributeError, KeyError, TypeError, ValueError):
                pass

    def _unit_lines(self, side):
        battle = self.battle
        if side in battle.summons:
            summon = battle.summons[side]
            lines = [(f"{summon['name']} (призыв {battle.fighters[summon['owner']].name})", (150, 210, 255))]
            if summon["kind"].startswith("necromancer_"):
                lines.append((f"Здоровье: {max(0, summon['hp'])}/{summon['max_hp']}", (235, 120, 110)))
                lines.append((f"Мана: {summon.get('mana', 0)}/{summon.get('max_mana', 0)}; "
                              f"перемещение: {summon.get('movement', 0)} гекса", (210, 215, 225)))
                if summon["kind"] == "necromancer_familiar":
                    lines.append(("Усиливает урон союзников в радиусе 2 гексов на 20%.", (150, 225, 160)))
                elif summon["kind"] == "necromancer_spirit":
                    lines.append(("Получает на 50% меньше урона; оглушение и отбрасывание.", (150, 225, 160)))
                else:
                    lines.append((f"Атака: {summon.get('damage', 0)} урона.", (240, 200, 120)))
            elif summon["kind"] == "golem":
                lines.append((f"Здоровье: {max(0, summon['hp'])}/{summon['max_hp']}", (235, 120, 110)))
                lines.append((f"Удар: {summon['damage']} (дальность 1), каждый {summon['stun_every']}-й "
                              f"+{summon['stun_damage']}", (240, 200, 120)))
                lines.append((f"Идёт к ближайшему врагу до {MOVE_RANGE} клеток за ход", (210, 215, 225)))
            elif summon["kind"] == "forest_spirit":
                lines.append((f"Здоровье: {max(0, summon['hp'])}/{summon['max_hp']}", (235, 120, 110)))
                lines.append((f"Поддержка союзников в радиусе {FOREST_SPIRIT_RANGE} гексов:", (210, 215, 225)))
                lines.append(("Лечение: 5% максимального HP; усиление урона: +10% на 2 хода; "
                              "щит: 8% текущего HP.", (150, 225, 160)))
            elif summon["kind"] == "wolf":
                lines.append((f"Здоровье: {max(0, summon['hp'])}/{summon['max_hp']}", (235, 120, 110)))
                lines.append((f"Укус: {summon['damage']} урона, дальность 1", (240, 200, 120)))
                lines.append(("Перемещение: до 4 гексов за ход", (210, 215, 225)))
            else:
                lines.append((f"Молния: {summon['damage']} урона + «электро» (дальность 1)", (240, 200, 120)))
                lines.append(("Парит над ареной и не занимает тайл для врагов", (210, 215, 225)))
            lines.append((f"Урон за бой: {battle.damage_dealt[side]}", (240, 200, 120)))
            lines.extend((f"  • {text}", (150, 225, 160)) for text in battle.effects_for(side))
            return lines
        fighter = battle.fighters[side]
        lines = [(f"{fighter.name} (ур. {fighter.level})", (255, 225, 140))]
        if side in battle.enemy_summons:
            lines[0] = ("Волк (призыв босса)", (220, 225, 230))
        if side in battle.ally_ids:
            lines[0] = (f"{fighter.name} (союзник-лучник, ур. {fighter.level})", (140, 230, 150))
        lines.append((f"Здоровье: {max(0, int(fighter.hp))}/{fighter.max_hp}", (235, 120, 110)))
        if side in battle.enemy_ids:
            lines.append((f"Мана: {int(fighter.mp)}/{fighter.max_mp}"
                          if fighter.name == ANCIENT_ENT_NAME
                          else "Мана: не использует", (130, 180, 235)))
            lines.append(("Уникальный ресурс: не нужен", (200, 170, 235)))
            lines.append((f"Урон за бой: {battle.damage_dealt[side]}", (240, 200, 120)))
            lines.append((f"Карты (случайно по {ENEMY_CARDS_PER_TURN} за ход):", (210, 215, 225)))
            for card in battle.enemy_decks[side]:
                description = card.description or f"Дальность {card.range}"
                if card.damage:
                    description = f"{card.damage} урона, дальность {card.range}"
                if card.aoe_radius:
                    description += f", радиус области {card.aoe_radius}"
                if card.heal_percent:
                    description = (
                        f"Лечение {int(card.heal_percent * 100)}% максимального HP при HP <= "
                        f"{int(card.heal_threshold * 100)}%, раз в {card.cooldown_turns} хода"
                    )
                if card.root_turns:
                    description = f"Корни на {card.root_turns} хода, дальность {card.range}"
                if card.summon_wolf:
                    description = f"Волк: {WOLF_MAX_HP} HP, передвижение 4 гекса"
                lines.append((f"  • {card.name}: {description}", (190, 195, 205)))
            if side in battle.enemy_summons:
                lines.append(("Атака: укус, 5 урона, дальность 1", (235, 180, 130)))
                lines.append(("Передвижение: до 4 гексов за ход", (210, 215, 225)))
        else:
            lines.append((f"Мана: {int(fighter.mp)}/{fighter.max_mp}", (130, 180, 235)))
            resource = getattr(fighter, "unique_resource_type", None)
            if resource and resource != "mana":
                lines.append((
                    f"{RESOURCE_NAMES.get(resource, resource)}: "
                    f"{int(fighter.unique_resource_current)}/{fighter.unique_resource_max}",
                    (200, 170, 235),
                ))
            lines.append((f"Урон за бой: {battle.damage_dealt[side]}", (240, 200, 120)))
            if side in battle.ally_ids:
                lines.append((f"Карт в руке: {len(battle.ally_cards[side]['hand'])}", (210, 215, 225)))
        effects = battle.effect_entries_for(side)
        lines.append(("Эффекты:" if effects else "Эффекты: нет", (210, 215, 225)))
        lines.extend((f"  • {text}", color) for text, color in effects)
        return lines

    def _draw_unit_effects(self, screen):
        battle = self.battle
        for uid in ("player", *battle.alive_allies(), *battle.alive_enemies(), *battle.summons):
            entries = battle.effect_entries_for(uid)
            if not entries:
                continue
            x, y = self.scene.world_to_screen(*self._unit_world_position(uid))
            columns = min(5, len(entries))
            rows = math.ceil(len(entries) / columns)
            width, height = 22, 17
            left = int(x - columns * width / 2)
            top = int(y + self.scene.tile_size * 0.45)
            for index, (text, color) in enumerate(entries):
                row, column = divmod(index, columns)
                rect = pygame.Rect(left + column * width, top + row * height, 20, 15)
                rect.clamp_ip(screen.get_rect())
                pygame.draw.rect(screen, (15, 20, 26), rect, border_radius=3)
                pygame.draw.rect(screen, color, rect, 1, border_radius=3)
                self._draw_effect_icon(screen, rect, text, color)
                duration = re.search(r"(\d+)\s*х\.", text)
                count = re.search(r"\bx(\d+)\b", text)
                value = duration.group(1) if duration else count.group(1) if count else ""
                if value:
                    label = self.effect_font.render(value, True, (245, 245, 245))
                    screen.blit(label, label.get_rect(midright=(rect.right - 2, rect.centery)))

    @staticmethod
    def _draw_effect_icon(screen, rect, text, color):
        label = text.lower()
        if "яд" in label or "кровотеч" in label:
            center = (rect.left + 7, rect.centery - 1)
            pygame.draw.circle(screen, color, center, 4)
            pygame.draw.polygon(screen, color, [
                (center[0] - 3, center[1] + 2), (center[0] + 3, center[1] + 2),
                (center[0], center[1] + 7),
            ])
        elif "корн" in label or "оплет" in label:
            pygame.draw.line(screen, color, (rect.left + 4, rect.bottom - 3),
                             (rect.left + 7, rect.top + 3), 2)
            pygame.draw.line(screen, color, (rect.left + 7, rect.centery),
                             (rect.left + 11, rect.top + 5), 2)
            pygame.draw.line(screen, color, (rect.left + 6, rect.centery + 1),
                             (rect.left + 3, rect.centery - 2), 2)
        elif "щит" in label or "сопротив" in label:
            points = [(rect.left + 7, rect.top + 2), (rect.left + 11, rect.top + 4),
                      (rect.left + 10, rect.bottom - 5), (rect.left + 7, rect.bottom - 2),
                      (rect.left + 4, rect.bottom - 5), (rect.left + 3, rect.top + 4)]
            pygame.draw.polygon(screen, color, points, 2)
        elif "лечен" in label or "восст." in label:
            pygame.draw.line(screen, color, (rect.left + 7, rect.top + 3),
                             (rect.left + 7, rect.bottom - 3), 2)
            pygame.draw.line(screen, color, (rect.left + 4, rect.centery),
                             (rect.left + 10, rect.centery), 2)
        elif "оглуш" in label or "замороз" in label or "пропуск" in label:
            pygame.draw.lines(screen, color, False, [
                (rect.left + 9, rect.top + 2), (rect.left + 5, rect.centery),
                (rect.left + 8, rect.centery), (rect.left + 5, rect.bottom - 2),
            ], 2)
        elif "электро" in label or "молни" in label:
            pygame.draw.lines(screen, color, False, [
                (rect.left + 8, rect.top + 2), (rect.left + 4, rect.centery),
                (rect.left + 7, rect.centery), (rect.left + 5, rect.bottom - 2),
                (rect.left + 11, rect.centery - 1), (rect.left + 8, rect.centery - 1),
            ], 2)
        elif any(word in label for word in ("урон", "меткость", "ловкость", "уворот", "крит")):
            pygame.draw.polygon(screen, color, [
                (rect.left + 7, rect.top + 2), (rect.left + 3, rect.centery),
                (rect.left + 6, rect.centery), (rect.left + 6, rect.bottom - 2),
                (rect.left + 8, rect.bottom - 2), (rect.left + 8, rect.centery),
                (rect.left + 11, rect.centery),
            ])
        else:
            pygame.draw.circle(screen, color, (rect.left + 7, rect.centery), 4, 2)

    def _draw_unit_tooltip(self, screen, side, pos):
        lines = self._unit_lines(side)
        surfaces = [self.small_font.render(text, True, color) for text, color in lines]
        width = max(surface.get_width() for surface in surfaces) + 24
        height = len(surfaces) * 21 + 16
        panel = pygame.Rect(pos[0] + 20, pos[1] + 12, width, height)
        panel.clamp_ip(pygame.Rect(0, 80, settings.WIDTH, settings.HEIGHT - 80))
        surface = pygame.Surface(panel.size, pygame.SRCALPHA)
        surface.fill((14, 16, 22, 235))
        screen.blit(surface, panel)
        border = ((240, 110, 90) if side in self.battle.enemy_ids
                  else (90, 225, 120) if side in self.battle.ally_ids
                  else (110, 200, 255) if side in self.battle.summons else (90, 170, 255))
        pygame.draw.rect(screen, border, panel, 2, border_radius=6)
        for index, surf in enumerate(surfaces):
            screen.blit(surf, (panel.left + 12, panel.top + 8 + index * 21))

    def _draw_result(self, screen):
        title, subtitle, color = RESULT_TEXT[self.battle.result]
        if self.battle.result == "win" and len(self.battle.enemy_ids) > 1:
            subtitle = "Лагерь кобольдов разгромлен."
        shade = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 120))
        screen.blit(shade, (0, 0))
        title_surf = self.big_font.render(title, True, color)
        subtitle_surf = self.font.render(subtitle, True, (235, 235, 235))
        center = (settings.WIDTH // 2, settings.HEIGHT // 2)
        screen.blit(title_surf, title_surf.get_rect(center=(center[0], center[1] - 24)))
        screen.blit(subtitle_surf, subtitle_surf.get_rect(center=(center[0], center[1] + 30)))
