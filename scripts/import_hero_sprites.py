"""Импорт спрайта героя-мечника из архива художника (Hero.zip) в assets/warrior.

Архив: папки Walk, Attack_01, Attack_02, Block, Death, Got-Hit, кадры вида name_DNNNN.png, где D — направление 0–7,
NNNN — номер кадра. Покоя (Idle) и бега (Run) в архиве нет: покой берётся из кадра ходьбы с сомкнутыми ногами,
а бег и ходьба с грузом играют кадры Walk (см. scenes/player_sprites.py).

Пример: python scripts/import_hero_sprites.py "C:/Users/.../Downloads/Hero.zip"
Старые папки анимаций воина в assets/warrior заменяются целиком.
"""
import argparse
import io
import re
import shutil
import sys
import zipfile
from pathlib import Path

import pygame

WARRIOR_DIR = Path(__file__).resolve().parent.parent / "assets" / "warrior"
# Направление по первой цифре номера кадра, определено по повороту фигуры: 7 — лицом к зрителю, дальше против часовой стрелки на экране
DIRECTION_BY_INDEX = ("se", "e", "ne", "n", "nw", "w", "sw", "s")
# Папка архива -> папка в assets/warrior. Две атаки: при каждом ударе игра случайно берёт attack1 или attack2.
FOLDERS = {
    "Walk": "walk", "Attack_01": "attack1", "Attack_02": "attack2",
    "Block": "block", "Death": "death", "Got-Hit": "gothit",
}
# Папки, которые импорт пересоздаёт: новые и старые (run и walking заменены на walk, attack разделилась на два вида)
REPLACED = ("idle", "run", "walking", "walk", "attack", "attack1", "attack2", "block", "death", "gothit")
FRAME_RE = re.compile(r"^(?P<folder>[^/]+)/[A-Za-z-]+_(?P<direction>\d)(?P<frame>\d{4})\.png$", re.IGNORECASE)
BODY_ALPHA = 201  # плотные пиксели тела; полупрозрачная тень не считается
FEET_BAND_SHARE = 0.25


def direction_for_index(index):
    return DIRECTION_BY_INDEX[int(index)]


def leg_spread(surface):
    """Ширина ног: габарит плотных пикселей в нижней четверти фигуры. Чем меньше, тем теснее стоят ноги."""
    body = surface.get_bounding_rect(min_alpha=BODY_ALPHA)
    if body.height == 0:
        return 10 ** 6
    band_h = max(2, int(body.height * FEET_BAND_SHARE))
    band = surface.subsurface(pygame.Rect(body.x, body.bottom - band_h, body.width, band_h))
    return band.get_bounding_rect(min_alpha=BODY_ALPHA).width


def pick_idle_frame(surfaces):
    """Индекс кадра для покоя: ноги вместе; при равенстве — самый ранний."""
    spreads = [leg_spread(surface) for surface in surfaces]
    return spreads.index(min(spreads))


def read_archive(zip_path):
    """{папка в assets/warrior: {направление: [(номер кадра, байты PNG)]}} из архива."""
    result = {}
    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            match = FRAME_RE.match(name)
            if not match or match["folder"] not in FOLDERS:
                continue
            folder = FOLDERS[match["folder"]]
            direction = direction_for_index(match["direction"])
            result.setdefault(folder, {}).setdefault(direction, []).append((int(match["frame"]), archive.read(name)))
    for directions in result.values():
        for frames in directions.values():
            frames.sort()
    return result


def write_sprites(sprites, target=WARRIOR_DIR):
    """Пересоздаёт папки анимаций воина и дописывает idle из кадров ходьбы. Возвращает {папка: число кадров}."""
    for folder in REPLACED:
        shutil.rmtree(target / folder, ignore_errors=True)
    counts = {}
    for folder, directions in sprites.items():
        for direction, frames in directions.items():
            out = target / folder / direction
            out.mkdir(parents=True, exist_ok=True)
            for number, (_, data) in enumerate(frames, 1):
                (out / f"{number:02d}.png").write_bytes(data)
            counts[folder] = counts.get(folder, 0) + len(frames)
    for direction, frames in sprites.get("walk", {}).items():
        surfaces = [pygame.image.load(io.BytesIO(data)) for _, data in frames]
        out = target / "idle" / direction
        out.mkdir(parents=True, exist_ok=True)
        (out / "01.png").write_bytes(frames[pick_idle_frame(surfaces)][1])
        counts["idle"] = counts.get("idle", 0) + 1
    return counts


def main():
    parser = argparse.ArgumentParser(description="Импорт спрайта героя-мечника из архива художника")
    parser.add_argument("archive", type=Path, help="путь к Hero.zip")
    args = parser.parse_args()
    if not args.archive.is_file():
        sys.exit(f"Архив не найден: {args.archive}")
    sprites = read_archive(args.archive)
    missing = [folder for folder in FOLDERS.values() if folder not in sprites]
    if missing:
        sys.exit(f"В архиве нет анимаций: {', '.join(missing)}")
    counts = write_sprites(sprites)
    for folder, count in sorted(counts.items()):
        print(f"{folder}: {count} кадров")


if __name__ == "__main__":
    main()
