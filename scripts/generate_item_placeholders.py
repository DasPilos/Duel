"""Generate transparent inventory placeholder icons for catalog materials and missing items."""

from pathlib import Path
import sys

import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.items_database import CATALOG


OUTPUT_DIR = Path(__file__).resolve().parents[1] / "assets" / "fighters" / "equipment" / "placeholders"
SIZE = 128
OUTLINE = (41, 31, 28)
BUILDING_IDS = (
    "crystal_of_life", "main_castle", "tavern_building", "barn_building",
    "warehouse_building", "forge_building", "workshop_building", "barracks_building",
    "engineering_building", "university_building", "military_academy", "mage_school_building",
    "stable_building", "lumber_camp", "town_radburg", "wheat_farm", "mountain_rift",
    "barnyard", "black_pit",
)
EXTRA_ICON_KEYS = (
    "weapon_club", "weapon_bow", "weapon_staff", "shield_wooden",
    *(f"building_{building_id}" for building_id in BUILDING_IDS),
)


def draw_icon(key):
    image = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    pygame.draw.ellipse(image, (10, 8, 8, 85), (25, 103, 78, 14))

    if key.startswith("potion_"):
        liquid = {"potion_blue": (60, 151, 224), "potion_red": (204, 61, 69), "potion_orange": (228, 139, 47)}[key]
        pygame.draw.rect(image, (183, 207, 210), (48, 22, 32, 24), border_radius=5)
        pygame.draw.rect(image, (143, 96, 57), (43, 16, 42, 12), border_radius=5)
        pygame.draw.ellipse(image, (218, 227, 215), (32, 37, 64, 66))
        pygame.draw.ellipse(image, liquid, (39, 51, 50, 44))
        pygame.draw.ellipse(image, (246, 224, 187), (32, 37, 64, 66), 4)
        pygame.draw.ellipse(image, (247, 247, 221), (45, 49, 9, 18))
        pygame.draw.arc(image, (255, 255, 255), (40, 42, 42, 54), 3.4, 5.0, 3)
    elif key == "scroll":
        pygame.draw.rect(image, (216, 190, 142), (31, 25, 66, 76), border_radius=8)
        pygame.draw.rect(image, (247, 226, 180), (39, 31, 51, 64), border_radius=4)
        pygame.draw.ellipse(image, (155, 104, 60), (25, 19, 78, 19))
        pygame.draw.ellipse(image, (205, 157, 99), (29, 22, 70, 12))
        pygame.draw.ellipse(image, (155, 104, 60), (25, 91, 78, 19))
        pygame.draw.ellipse(image, (205, 157, 99), (29, 94, 70, 12))
        for y in (48, 60, 72, 84):
            pygame.draw.line(image, (123, 87, 61), (49, y), (84, y), 3)
        pygame.draw.circle(image, (161, 51, 45), (91, 60), 8)
    elif key == "bone":
        pygame.draw.line(image, (223, 211, 176), (38, 89), (88, 39), 17)
        pygame.draw.line(image, (249, 239, 207), (40, 86), (86, 42), 8)
        for x, y in ((31, 84), (42, 96), (83, 29), (96, 42)):
            pygame.draw.circle(image, (226, 215, 184), (x, y), 13)
            pygame.draw.circle(image, (249, 239, 208), (x - 2, y - 3), 6)
    elif key == "crystal":
        points = [(62, 12), (91, 44), (82, 100), (48, 108), (31, 53)]
        pygame.draw.polygon(image, (50, 132, 171), points)
        pygame.draw.polygon(image, (125, 220, 239), [(62, 12), (67, 53), (48, 108), (31, 53)])
        pygame.draw.polygon(image, (28, 78, 113), [(62, 12), (91, 44), (67, 53)])
        pygame.draw.polygon(image, OUTLINE, points, 4)
        pygame.draw.line(image, (228, 249, 245), (53, 38), (44, 61), 4)
    elif key == "herb":
        pygame.draw.line(image, (88, 112, 54), (63, 106), (63, 31), 6)
        for cx, cy, side in ((50, 78, -1), (75, 66, 1), (49, 54, -1), (74, 43, 1)):
            leaf = [(63, cy + 8), (cx, cy), (cx + side * 8, cy + 18), (63, cy + 20)]
            pygame.draw.polygon(image, (67, 135, 59), leaf)
            pygame.draw.line(image, (151, 190, 83), (63, cy + 15), (cx + side * 4, cy + 8), 2)
    elif key == "weapon_club":
        pygame.draw.line(image, (97, 58, 37), (48, 108), (83, 26), 18)
        pygame.draw.line(image, (159, 103, 57), (49, 104), (81, 31), 8)
        pygame.draw.ellipse(image, (113, 69, 42), (64, 13, 37, 43))
        pygame.draw.ellipse(image, (180, 122, 68), (70, 17, 19, 19))
        pygame.draw.line(image, (60, 42, 31), (69, 43), (90, 47), 4)
    elif key == "weapon_bow":
        pygame.draw.arc(image, (138, 83, 45), (23, 12, 82, 104), 1.15, 5.13, 9)
        pygame.draw.arc(image, (208, 147, 84), (27, 16, 74, 96), 1.2, 5.08, 3)
        pygame.draw.line(image, (221, 210, 179), (53, 17), (53, 111), 2)
        pygame.draw.line(image, (181, 187, 183), (37, 63), (99, 63), 3)
        pygame.draw.polygon(image, (220, 218, 195), [(100, 63), (88, 56), (89, 70)])
        pygame.draw.polygon(image, OUTLINE, [(37, 63), (99, 63)], 1)
    elif key == "weapon_staff":
        pygame.draw.line(image, (95, 61, 42), (49, 111), (77, 29), 11)
        pygame.draw.line(image, (174, 124, 75), (51, 107), (76, 32), 4)
        pygame.draw.circle(image, (67, 170, 204), (80, 22), 15)
        pygame.draw.polygon(image, (173, 239, 235), [(80, 6), (87, 22), (80, 36), (73, 22)])
        pygame.draw.circle(image, (222, 238, 223), (80, 22), 16, 3)
    elif key == "shield_wooden":
        points = [(28, 20), (100, 20), (94, 74), (64, 108), (34, 74)]
        pygame.draw.polygon(image, (132, 79, 45), points)
        pygame.draw.polygon(image, (183, 119, 65), [(34, 27), (60, 27), (60, 94), (40, 72)])
        pygame.draw.polygon(image, (151, 91, 51), [(67, 27), (94, 27), (88, 72), (67, 95)])
        pygame.draw.line(image, (219, 171, 99), (64, 25), (64, 96), 5)
        pygame.draw.polygon(image, (196, 163, 111), points, 5)
    elif key.startswith("building_"):
        building_id = key.removeprefix("building_")
        wall, roof, trim = {
            "crystal_of_life": ((83, 111, 117), (70, 145, 164), (164, 233, 237)),
            "main_castle": ((139, 135, 117), (78, 90, 108), (224, 194, 126)),
            "tavern_building": ((155, 95, 54), (120, 59, 43), (237, 180, 84)),
            "barn_building": ((148, 84, 52), (124, 56, 43), (221, 172, 88)),
            "warehouse_building": ((108, 113, 111), (72, 78, 82), (199, 174, 125)),
            "forge_building": ((104, 80, 67), (63, 54, 54), (242, 111, 48)),
            "workshop_building": ((94, 111, 114), (62, 80, 91), (119, 202, 213)),
            "barracks_building": ((118, 97, 75), (78, 68, 62), (186, 72, 54)),
            "engineering_building": ((100, 120, 120), (67, 87, 94), (221, 185, 86)),
            "university_building": ((133, 116, 96), (70, 81, 107), (228, 202, 136)),
            "military_academy": ((125, 104, 78), (79, 71, 64), (222, 177, 88)),
            "mage_school_building": ((101, 90, 127), (70, 72, 116), (147, 208, 241)),
            "stable_building": ((148, 105, 61), (95, 65, 45), (216, 176, 105)),
            "lumber_camp": ((135, 89, 51), (77, 105, 57), (206, 164, 94)),
            "town_radburg": ((147, 133, 101), (77, 92, 99), (216, 187, 124)),
            "wheat_farm": ((163, 136, 76), (145, 93, 51), (235, 204, 104)),
            "mountain_rift": ((77, 76, 81), (45, 43, 50), (143, 183, 191)),
            "barnyard": ((146, 105, 67), (109, 64, 46), (221, 184, 114)),
            "black_pit": ((78, 69, 65), (42, 39, 40), (163, 129, 96)),
        }[building_id]
        if building_id == "crystal_of_life":
            points = [(64, 12), (91, 51), (81, 91), (47, 91), (37, 51)]
            pygame.draw.polygon(image, wall, [(24, 101), (37, 84), (91, 84), (104, 101)])
            pygame.draw.polygon(image, roof, points)
            pygame.draw.polygon(image, trim, [(64, 12), (66, 53), (47, 91), (37, 51)])
            pygame.draw.polygon(image, (230, 247, 231), [(64, 12), (78, 45), (64, 70), (52, 45)])
            pygame.draw.polygon(image, OUTLINE, points, 4)
        elif building_id in ("mountain_rift", "black_pit"):
            points = [(16, 102), (27, 59), (47, 25), (63, 53), (83, 21), (112, 102)]
            pygame.draw.polygon(image, wall, points)
            pygame.draw.ellipse(image, (22, 21, 23), (40, 54, 49, 52))
            pygame.draw.rect(image, (22, 21, 23), (40, 79, 49, 28))
            pygame.draw.arc(image, trim, (39, 52, 51, 53), 3.14, 6.28, 6)
            pygame.draw.polygon(image, OUTLINE, points, 4)
        else:
            pygame.draw.rect(image, wall, (28, 51, 72, 50), border_radius=4)
            pygame.draw.polygon(image, roof, [(20, 54), (64, 22), (108, 54)])
            pygame.draw.rect(image, OUTLINE, (28, 51, 72, 50), 3, border_radius=4)
            pygame.draw.polygon(image, OUTLINE, [(20, 54), (64, 22), (108, 54)], 3)
            pygame.draw.rect(image, (55, 42, 34), (57, 72, 17, 29), border_radius=3)
            pygame.draw.rect(image, trim, (37, 61, 12, 13), border_radius=2)
            pygame.draw.rect(image, trim, (79, 61, 12, 13), border_radius=2)
            if building_id in ("main_castle", "town_radburg", "barracks_building", "university_building", "military_academy", "mage_school_building"):
                pygame.draw.rect(image, wall, (22, 37, 19, 47), border_radius=3)
                pygame.draw.rect(image, wall, (87, 37, 19, 47), border_radius=3)
                pygame.draw.polygon(image, roof, [(19, 39), (31, 20), (44, 39)])
                pygame.draw.polygon(image, roof, [(84, 39), (97, 20), (109, 39)])
            if building_id == "forge_building":
                pygame.draw.rect(image, (64, 59, 55), (82, 7, 16, 36))
                pygame.draw.polygon(image, trim, [(61, 92), (69, 68), (78, 92)])
            elif building_id in ("barn_building", "wheat_farm"):
                for x in (43, 54, 78, 89):
                    pygame.draw.line(image, trim, (x, 98), (x - 5, 76), 3)
            elif building_id == "lumber_camp":
                for y in (91, 98):
                    pygame.draw.line(image, trim, (40, y), (87, y), 5)
            elif building_id in ("warehouse_building", "stable_building", "barnyard"):
                pygame.draw.rect(image, trim, (44, 67, 40, 30), 3)
            elif building_id in ("engineering_building", "workshop_building"):
                pygame.draw.circle(image, trim, (65, 75), 13, 4)
                pygame.draw.circle(image, trim, (65, 75), 4)
            elif building_id == "tavern_building":
                pygame.draw.rect(image, trim, (82, 60, 10, 25), border_radius=3)
                pygame.draw.line(image, (244, 221, 159), (87, 54), (87, 60), 3)
    elif key.startswith("tool_"):
        pygame.draw.line(image, (105, 65, 39), (52, 104), (82, 32), 12)
        pygame.draw.line(image, (176, 117, 67), (52, 101), (80, 36), 5)
        if key == "tool_sickle":
            pygame.draw.arc(image, (150, 164, 166), (34, 9, 66, 60), 3.7, 6.1, 11)
            pygame.draw.arc(image, (228, 229, 202), (36, 10, 64, 58), 3.8, 6.0, 4)
        elif key == "tool_axe":
            pygame.draw.polygon(image, (135, 146, 150), [(68, 42), (83, 14), (108, 17), (111, 49), (94, 59)])
            pygame.draw.polygon(image, (213, 218, 202), [(83, 14), (108, 17), (100, 32), (74, 34)])
            pygame.draw.polygon(image, OUTLINE, [(68, 42), (83, 14), (108, 17), (111, 49), (94, 59)], 3)
        elif key == "tool_pickaxe":
            pygame.draw.polygon(image, (129, 143, 151), [(31, 37), (44, 18), (75, 24), (98, 12), (105, 24), (78, 40), (48, 33), (36, 51)])
            pygame.draw.polygon(image, (222, 227, 213), [(44, 18), (75, 24), (98, 12), (78, 33), (48, 28)])
            pygame.draw.polygon(image, OUTLINE, [(31, 37), (44, 18), (75, 24), (98, 12), (105, 24), (78, 40), (48, 33)], 3)
        else:
            pygame.draw.polygon(image, (177, 184, 184), [(40, 53), (92, 20), (103, 27), (58, 68)])
            pygame.draw.polygon(image, (232, 231, 216), [(92, 20), (103, 27), (58, 68), (52, 61)])
            pygame.draw.polygon(image, OUTLINE, [(40, 53), (92, 20), (103, 27), (58, 68)], 3)
    elif key.startswith("material_"):
        name = key.removeprefix("material_")
        gems = {
            "jet": (43, 47, 57), "malachite": (37, 154, 103), "topaz": (237, 174, 57),
            "garnet": (159, 42, 66), "emerald": (32, 151, 88), "ruby": (210, 48, 65),
            "sapphire": (51, 108, 211), "diamond": (193, 231, 244),
        }
        if name in gems:
            color = gems[name]
            points = [(64, 13), (91, 33), (83, 79), (64, 108), (39, 80), (32, 39)]
            pygame.draw.polygon(image, color, points)
            pygame.draw.polygon(image, tuple(min(255, c + 62) for c in color), [(64, 13), (64, 70), (32, 39)])
            pygame.draw.polygon(image, tuple(max(0, c - 35) for c in color), [(64, 70), (91, 33), (83, 79), (64, 108)])
            pygame.draw.polygon(image, (213, 222, 205), points, 3)
        elif name in ("iron_ore", "mithril_ore", "obsidian_ore", "coal", "stone"):
            base = {"iron_ore": (104, 91, 78), "mithril_ore": (69, 100, 111),
                    "obsidian_ore": (73, 61, 86), "coal": (53, 52, 54), "stone": (133, 132, 123)}[name]
            points = [(24, 78), (32, 42), (55, 22), (82, 28), (104, 52), (94, 89), (62, 104), (34, 99)]
            pygame.draw.polygon(image, base, points)
            pygame.draw.polygon(image, tuple(min(255, c + 42) for c in base), [(32, 42), (55, 22), (70, 51), (48, 72)])
            pygame.draw.polygon(image, tuple(max(0, c - 28) for c in base), [(70, 51), (104, 52), (94, 89), (62, 104)])
            vein = {"iron_ore": (203, 124, 71), "mithril_ore": (92, 220, 231),
                    "obsidian_ore": (186, 105, 227), "coal": (119, 113, 112), "stone": (178, 173, 154)}[name]
            pygame.draw.line(image, vein, (45, 77), (71, 46), 7)
            pygame.draw.line(image, tuple(min(255, c + 36) for c in vein), (71, 46), (87, 69), 5)
            pygame.draw.polygon(image, OUTLINE, points, 4)
        elif name in ("wood", "board"):
            if name == "wood":
                for y, color in ((39, (127, 75, 42)), (59, (151, 94, 50)), (79, (112, 66, 39))):
                    pygame.draw.rect(image, color, (26, y, 72, 20), border_radius=9)
                    pygame.draw.ellipse(image, (205, 155, 91), (79, y + 2, 18, 16))
                    pygame.draw.ellipse(image, (106, 62, 38), (83, y + 6, 8, 8), 2)
                    pygame.draw.line(image, (224, 171, 96), (35, y + 5), (71, y + 5), 2)
            else:
                pygame.draw.polygon(image, (153, 99, 55), [(28, 43), (82, 25), (103, 38), (49, 57)])
                pygame.draw.polygon(image, (116, 69, 42), [(49, 57), (103, 38), (103, 71), (49, 91)])
                pygame.draw.polygon(image, (190, 131, 73), [(28, 43), (49, 57), (49, 91), (28, 75)])
                for y in (56, 67, 78):
                    pygame.draw.line(image, (226, 174, 101), (55, y), (92, y - 14), 2)
        elif name in ("iron", "steel"):
            top = (186, 190, 183) if name == "iron" else (186, 207, 216)
            side = (93, 103, 108) if name == "iron" else (91, 126, 144)
            pygame.draw.polygon(image, side, [(28, 55), (99, 55), (89, 91), (38, 91)])
            pygame.draw.polygon(image, top, [(28, 55), (42, 36), (99, 36), (99, 55)])
            pygame.draw.line(image, (245, 245, 221), (44, 42), (88, 42), 4)
            pygame.draw.polygon(image, OUTLINE, [(28, 55), (42, 36), (99, 36), (99, 55), (89, 91), (38, 91)], 3)
        elif name in ("leather", "tough_leather", "thick_leather"):
            color = {"leather": (163, 112, 69), "tough_leather": (128, 78, 49), "thick_leather": (97, 59, 42)}[name]
            points = [(36, 24), (80, 28), (100, 47), (91, 91), (65, 103), (32, 82), (25, 51)]
            pygame.draw.polygon(image, color, points)
            pygame.draw.polygon(image, (213, 169, 111), [(36, 24), (80, 28), (62, 49), (25, 51)])
            pygame.draw.polygon(image, (66, 43, 34), points, 4)
            for pos in ((40, 43), (82, 43), (83, 78), (43, 81)):
                pygame.draw.circle(image, (230, 201, 151), pos, 2)
        elif name == "meat":
            pygame.draw.line(image, (224, 215, 184), (75, 68), (102, 43), 14)
            pygame.draw.circle(image, (234, 224, 194), (105, 39), 11)
            pygame.draw.circle(image, (234, 224, 194), (99, 47), 10)
            pygame.draw.ellipse(image, (134, 43, 48), (22, 39, 67, 55))
            pygame.draw.ellipse(image, (204, 72, 67), (31, 45, 52, 39))
            pygame.draw.arc(image, (243, 175, 139), (31, 47, 47, 35), 0.4, 2.5, 5)
            pygame.draw.ellipse(image, OUTLINE, (22, 39, 67, 55), 4)
        elif name in ("cloth", "flax", "cotton", "wheat", "berry"):
            if name == "cloth":
                pygame.draw.polygon(image, (93, 137, 161), [(35, 31), (88, 27), (100, 44), (87, 56), (99, 82), (48, 96), (29, 75), (41, 57)])
                pygame.draw.polygon(image, (153, 196, 203), [(35, 31), (88, 27), (81, 42), (41, 57)])
                for y in (64, 73, 82):
                    pygame.draw.line(image, (208, 224, 212), (48, y), (82, y - 7), 2)
            elif name == "flax":
                pygame.draw.line(image, (82, 132, 69), (63, 104), (65, 30), 5)
                for x, y in ((47, 48), (78, 59), (48, 73), (79, 85)):
                    pygame.draw.ellipse(image, (109, 160, 77), (x - 13, y - 6, 25, 12))
                for x, y in ((60, 31), (46, 40), (75, 43)):
                    pygame.draw.circle(image, (121, 126, 195), (x, y), 8)
                    pygame.draw.circle(image, (245, 210, 98), (x, y), 3)
            elif name == "cotton":
                pygame.draw.line(image, (91, 128, 63), (64, 105), (64, 45), 5)
                for x, y in ((49, 54), (77, 58), (54, 79), (73, 82)):
                    pygame.draw.circle(image, (236, 232, 210), (x, y), 14)
                    pygame.draw.circle(image, (255, 251, 230), (x - 4, y - 4), 7)
                pygame.draw.polygon(image, (89, 127, 67), [(50, 59), (42, 46), (55, 51)])
                pygame.draw.polygon(image, (89, 127, 67), [(78, 64), (90, 52), (85, 69)])
            elif name == "wheat":
                pygame.draw.line(image, (165, 130, 55), (63, 108), (66, 21), 5)
                for i, y in enumerate((34, 46, 58, 70, 82)):
                    side = -1 if i % 2 else 1
                    pygame.draw.ellipse(image, (221, 184, 82), (64 if side > 0 else 45, y, 20, 9))
                pygame.draw.line(image, (239, 209, 127), (63, 29), (66, 12), 3)
            else:
                pygame.draw.line(image, (77, 130, 63), (64, 105), (61, 36), 5)
                for x, y, color in ((43, 55, (159, 54, 82)), (76, 47, (186, 54, 74)), (51, 79, (116, 51, 110)), (79, 76, (147, 59, 127))):
                    pygame.draw.circle(image, color, (x, y), 13)
                    pygame.draw.circle(image, (246, 192, 173), (x - 4, y - 4), 4)
                pygame.draw.ellipse(image, (82, 143, 61), (39, 41, 15, 8))
                pygame.draw.ellipse(image, (82, 143, 61), (68, 65, 16, 8))
        elif name == "stone_block":
            pygame.draw.polygon(image, (105, 111, 110), [(26, 43), (69, 26), (101, 43), (58, 61)])
            pygame.draw.polygon(image, (137, 141, 133), [(26, 43), (58, 61), (58, 98), (26, 78)])
            pygame.draw.polygon(image, (82, 88, 91), [(58, 61), (101, 43), (101, 79), (58, 98)])
            pygame.draw.line(image, (190, 190, 171), (36, 47), (62, 58), 3)
            pygame.draw.polygon(image, OUTLINE, [(26, 43), (69, 26), (101, 43), (101, 79), (58, 98), (26, 78)], 3)
        else:
            raise ValueError(f"No placeholder drawing for catalog icon: {key}")

    return image


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    keys = sorted({entry[10] for entry in CATALOG if entry[10]} | set(EXTRA_ICON_KEYS))
    generated = []
    for key in keys:
        path = OUTPUT_DIR / f"{key}.png"
        if path.exists() and not key.startswith("material_"):
            continue
        pygame.image.save(draw_icon(key), path)
        generated.append(key)
    print(f"Generated {len(generated)} item placeholders: {', '.join(generated)}")


if __name__ == "__main__":
    main()