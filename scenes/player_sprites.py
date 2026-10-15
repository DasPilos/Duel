"""Загрузка 8-направленных спрайтов персонажа (Idle и Run) для сцен мира и города."""
from pathlib import Path

import pygame

from core.carry_weight import is_overloaded

PLAYER_SPRITE_ROOT = Path(__file__).resolve().parent.parent / "assets"
PLAYER_SPRITE_HEIGHT = 120
PLAYER_DIRECTIONS = ["n", "ne", "e", "se", "s", "sw", "w", "nw"]


def _frame_files(folder):
    return sorted([
        f for f in folder.glob("*.png")
        if not f.name.endswith("apng.png") and not f.name.endswith("spritesheet.png")
    ])


def _load_directional_frames(sprite_dir, label, target_h):
    """Возвращает {направление: [кадры]} для папки спрайтов; пропускает пустые."""
    result = {}
    if not sprite_dir.is_dir():
        return result
    for d in PLAYER_DIRECTIONS:
        d_folder = sprite_dir / d
        if not d_folder.is_dir():
            continue
        frame_files = _frame_files(d_folder)
        if not frame_files:
            continue
        sample = pygame.image.load(str(frame_files[0])).convert_alpha()
        crop_rect = sample.get_bounding_rect()
        if crop_rect.height <= 0:
            continue
        ratio = target_h / float(crop_rect.height)
        target_w = max(1, int(crop_rect.width * ratio))
        frames = []
        for ff in frame_files:
            try:
                raw = pygame.image.load(str(ff)).convert_alpha()
                cropped = raw.subsurface(crop_rect).copy()
                frames.append(pygame.transform.smoothscale(cropped, (target_w, target_h)))
            except Exception as error:
                print(f"[PlayerSprites] Error loading {label} {ff}: {error}")
        if frames:
            result[d] = frames
    return result


def load_player_directional_sprites(scene):
    """Заполняет scene.player_directional_frames (idle) и scene.player_run_directional_frames (run)."""
    scene.player_directional_frames = _load_directional_frames(
        PLAYER_SPRITE_ROOT / "2Idle", "idle", PLAYER_SPRITE_HEIGHT,
    )
    scene.player_run_directional_frames = _load_directional_frames(
        PLAYER_SPRITE_ROOT / "3run", "run", PLAYER_SPRITE_HEIGHT,
    )
    load_warrior_directional_frames()


WARRIOR_PROFESSION = "warrior"
WARRIOR_SPRITE_ROOT = PLAYER_SPRITE_ROOT / "warrior"
WARRIOR_ANIMATIONS = ("idle", "run", "walking", "attack")
WARRIOR_DIRECTION_RING = ("n", "ne", "e", "se", "s", "sw", "w", "nw")
WARRIOR_MIRROR_PARTNER = {"n": "n", "s": "s", "e": "w", "w": "e", "ne": "nw", "nw": "ne", "se": "sw", "sw": "se"}
_warrior_frames = None


def player_profession(character):
    return (character or {}).get("type")


def _warrior_anim_frames(anim):
    """Кадры всех направлений одной анимации, обрезанные и масштабированные.

    Каждое направление масштабируется своим коэффициентом: в исходниках одна и та же анимация
    нарисована разного размера по направлениям (например, покой «вниз» мельче остальных), и общий
    коэффициент давал бы усадку при повороте. Медиана высоты направления приводится к PLAYER_SPRITE_HEIGHT.
    """
    result = {}
    for d in PLAYER_DIRECTIONS:
        files = _frame_files(WARRIOR_SPRITE_ROOT / anim / d)
        if not files:
            continue
        surfaces = [pygame.image.load(str(f)).convert_alpha() for f in files]
        rects = [surface.get_bounding_rect() for surface in surfaces]
        crop = rects[0]
        for rect in rects[1:]:
            crop = crop.union(rect)
        heights = sorted(rect.height for rect in rects)
        scale = PLAYER_SPRITE_HEIGHT / float(heights[len(heights) // 2])
        target = (max(1, round(crop.width * scale)), max(1, round(crop.height * scale)))
        result[d] = [pygame.transform.smoothscale(surface.subsurface(crop).copy(), target) for surface in surfaces]
    return result


def _warrior_source_direction(direction, available):
    """Чем заменить отсутствующее направление: (направление, нужно ли зеркалить).

    Сначала берётся зеркальная пара (w из e, nw из ne), иначе ближайшее направление по кругу.
    """
    partner = WARRIOR_MIRROR_PARTNER[direction]
    if partner in available:
        return partner, True
    index = WARRIOR_DIRECTION_RING.index(direction)
    for step in range(1, len(WARRIOR_DIRECTION_RING)):
        for candidate in (WARRIOR_DIRECTION_RING[(index - step) % len(WARRIOR_DIRECTION_RING)],
                          WARRIOR_DIRECTION_RING[(index + step) % len(WARRIOR_DIRECTION_RING)]):
            if candidate in available:
                return candidate, False
    return None, False


def _place_on_canvas(surface, width, height):
    canvas = pygame.Surface((width, height), pygame.SRCALPHA)
    canvas.blit(surface, surface.get_rect(midbottom=(width // 2, height)))
    return canvas


def load_warrior_directional_frames():
    """{состояние: {направление: [кадры]}} для воина. Недостающие направления берутся из соседних."""
    global _warrior_frames
    if _warrior_frames is None:
        by_anim = {anim: _warrior_anim_frames(anim) for anim in WARRIOR_ANIMATIONS}
        all_frames = [frame for raw in by_anim.values() for frames in raw.values() for frame in frames]
        canvas_w = max(frame.get_width() for frame in all_frames)
        canvas_h = max(frame.get_height() for frame in all_frames)
        frames = {}
        for anim, raw in by_anim.items():
            placed = {d: [_place_on_canvas(s, canvas_w, canvas_h) for s in surfaces] for d, surfaces in raw.items()}
            anim_frames = dict(placed)
            for d in PLAYER_DIRECTIONS:
                if d in placed:
                    continue
                source, mirrored = _warrior_source_direction(d, placed)
                if source is None:
                    continue
                anim_frames[d] = (
                    [pygame.transform.flip(f, True, False) for f in placed[source]] if mirrored else placed[source]
                )
            frames[anim] = anim_frames
        _warrior_frames = frames
    return _warrior_frames


def player_frames_for(scene, character, state):
    """Набор {направление: [кадры]} для состояния idle, run, walking или attack."""
    if player_profession(character) == WARRIOR_PROFESSION:
        return load_warrior_directional_frames()[state]
    if state in ("run", "walking"):
        run_frames = getattr(scene, "player_run_directional_frames", None)
        if run_frames:
            return run_frames
    return getattr(scene, "player_directional_frames", {})


def player_anim_state(character, moving, attacking=False):
    if player_profession(character) != WARRIOR_PROFESSION:
        return "run" if moving else "idle"
    if attacking:
        return "attack"
    if not moving:
        return "idle"
    return "walking" if is_overloaded(character) else "run"


def player_frame(scene, character, direction, anim_time, moving, attacking=False, attack_progress=0.0, run_fps=10.0, idle_fps=4.0):
    """Текущий кадр персонажа. Замах воина показывает кадр по прогрессу замаха (0..1)."""
    state = player_anim_state(character, moving, attacking)
    frames_dict = player_frames_for(scene, character, state)
    if not frames_dict:
        return None
    frames = frames_dict.get(direction) or next(iter(frames_dict.values()))
    if not frames:
        return None
    if state == "attack":
        index = int(max(0.0, min(1.0, attack_progress)) * len(frames))
        return frames[min(len(frames) - 1, index)]
    fps = run_fps if state in ("run", "walking") else idle_fps
    return frames[int(anim_time * fps) % len(frames)]
