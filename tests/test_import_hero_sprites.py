import importlib.util
import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from scenes.player_sprites import PLAYER_DIRECTIONS

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "import_hero_sprites.py"
spec = importlib.util.spec_from_file_location("import_hero_sprites", SCRIPT)
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)


def png_bytes(color=(200, 50, 50, 255), size=(8, 8)):
    surface = pygame.Surface(size, pygame.SRCALPHA)
    surface.fill(color)
    buffer = io.BytesIO()
    pygame.image.save(surface, buffer, "frame.png")
    return buffer.getvalue()


def figure(feet):
    """Фигура 24×40: тело и ноги по заданным столбцам x."""
    surface = pygame.Surface((24, 40), pygame.SRCALPHA)
    pygame.draw.rect(surface, (200, 80, 80, 255), (6, 0, 12, 28))
    for x in feet:
        pygame.draw.rect(surface, (50, 50, 90, 255), (x, 28, 3, 12))
    return surface


class HeroImportTests(unittest.TestCase):
    def test_direction_indexes_cover_all_eight_directions(self):
        directions = [importer.direction_for_index(i) for i in range(8)]
        self.assertEqual(sorted(directions), sorted(PLAYER_DIRECTIONS))
        # 7 — лицом к зрителю, 3 — спиной, 1 и 5 — профили
        self.assertEqual([directions[7], directions[3], directions[1], directions[5]], ["s", "n", "e", "w"])

    def test_idle_frame_is_the_one_with_feet_together(self):
        apart = figure([4, 17])
        together = figure([10, 13])
        self.assertGreater(importer.leg_spread(apart), importer.leg_spread(together))
        self.assertEqual(importer.pick_idle_frame([apart, together, apart]), 1)
        self.assertEqual(importer.pick_idle_frame([together, together]), 0)

    def test_import_builds_folders_and_replaces_old_ones(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "Hero.zip"
            with zipfile.ZipFile(archive, "w") as zipped:
                for name in (
                    "Walk/walk_70001.png", "Walk/walk_70000.png", "Walk/walk_30000.png",
                    "Attack_01/attack_70000.png", "Attack_02/Attack_70000.png", "Attack_02/Attack_70001.png",
                    "Block/block_70000.png", "Death/death_70000.png", "Got-Hit/gothit_70000.png",
                ):
                    zipped.writestr(name, png_bytes())
                zipped.writestr("Readme.txt", "не кадр")
            target = root / "warrior"
            (target / "run" / "e").mkdir(parents=True)
            (target / "run" / "e" / "01.png").write_bytes(b"old")

            counts = importer.write_sprites(importer.read_archive(archive), target)

            self.assertFalse((target / "run").exists())
            self.assertEqual(sorted(p.name for p in (target / "walk").iterdir()), ["n", "s"])
            self.assertEqual(sorted(p.name for p in (target / "walk" / "s").iterdir()), ["01.png", "02.png"])
            self.assertEqual(len(list((target / "attack1" / "s").iterdir())), 1)
            self.assertEqual(len(list((target / "attack2" / "s").iterdir())), 2)
            for folder in ("block", "death", "gothit", "idle"):
                self.assertTrue((target / folder / "s" / "01.png").is_file(), folder)
            self.assertEqual(counts["walk"], 3)
            self.assertEqual(counts["idle"], 2)

    def test_frames_are_ordered_by_frame_number_not_by_archive_order(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "Hero.zip"
            first, second = png_bytes((10, 10, 10, 255)), png_bytes((250, 250, 250, 255))
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.writestr("Walk/walk_70001.png", second)
                zipped.writestr("Walk/walk_70000.png", first)
            frames = importer.read_archive(archive)["walk"]["s"]
            self.assertEqual([data for _, data in frames], [first, second])


class ShippedHeroSpriteTests(unittest.TestCase):
    def test_every_animation_has_all_eight_directions(self):
        root = importer.WARRIOR_DIR
        expected = {"idle": 1, "walk": 10, "attack1": 10, "attack2": 18, "block": 5, "death": 8, "gothit": 6}
        for folder, count in expected.items():
            for direction in PLAYER_DIRECTIONS:
                files = sorted((root / folder / direction).glob("*.png"))
                self.assertEqual(len(files), count, f"{folder}/{direction}")

    def test_old_pixel_art_folders_are_gone(self):
        for folder in ("run", "walking", "attack"):
            self.assertFalse((importer.WARRIOR_DIR / folder).exists(), folder)


if __name__ == "__main__":
    unittest.main()
