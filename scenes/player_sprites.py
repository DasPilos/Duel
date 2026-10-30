"""Загрузка 8-направленных спрайтов персонажа (Idle и Run) для сцен мира и города."""
import math
from pathlib import Path

import pygame

from core.carry_weight import is_overloaded

PLAYER_SPRITE_ROOT = Path(__file__).resolve().parent.parent / "assets"
PLAYER_SPRITE_HEIGHT = 90
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
# Две атаки героя: при каждом ударе сцена случайно выбирает одну (индекс в WARRIOR_ATTACK_ANIMATIONS).
WARRIOR_ATTACK_ANIMATIONS = ("attack1", "attack2")
# Реакции: получение удара и смерть играют один раз по прогрессу 0..1 (смерть держит последний кадр)
WARRIOR_REACTION_ANIMATIONS = ("gothit", "death")
WARRIOR_ANIMATIONS = ("idle", "run", "walking") + WARRIOR_ATTACK_ANIMATIONS + WARRIOR_REACTION_ANIMATIONS
# Папка кадров в assets/warrior для каждой анимации. Отдельных Run в спрайте героя нет: бег и ходьба с грузом
# играют кадры Walk (темп задаёт run_fps в player_frame); покой — один кадр ходьбы с сомкнутыми ногами.
WARRIOR_ANIMATION_SOURCE = {
    "idle": "idle", "run": "walk", "walking": "walk", "attack1": "attack1", "attack2": "attack2",
    "gothit": "gothit", "death": "death",
}
WARRIOR_BASE_FOLDERS = ("idle", "walk")
# Атаки и реакции шире и выше фигуры (меч, падение, тень): им общий большой холст
WARRIOR_WIDE_FOLDERS = ("attack1", "attack2", "gothit", "death")
# Герой при ударе и падении сдвигается, поэтому ноги берём по первому, стоячему кадру, а не по медиане
ANCHOR_FIRST_FRAME_FOLDERS = ("gothit", "death")
# Герой — 3D-рендер с запечённой полупрозрачной тенью: фигуру измеряем по плотным пикселям, а тень остаётся на кадре.
BODY_MIN_ALPHA = 201
# Запас под ногами для тени и шага: герой «парит» над точкой мира ровно на столько, всё, что ниже, обрезается
FEET_MARGIN = 3
FEET_BAND_SHARE = 0.25
WARRIOR_DIRECTION_RING = ("n", "ne", "e", "se", "s", "sw", "w", "nw")
WARRIOR_MIRROR_PARTNER = {"n": "n", "s": "s", "e": "w", "w": "e", "ne": "nw", "nw": "ne", "se": "sw", "sw": "se"}
_warrior_frames = None
_warrior_base_height = 0


def player_profession(character):
    return (character or {}).get("type")


def _solid_rect(surface):
    """Габарит плотных пикселей фигуры: полупрозрачная тень и мягкие края не в счёт."""
    return surface.get_bounding_rect(min_alpha=BODY_MIN_ALPHA)


def _feet_anchor(surface):
    """Точка ног на исходном кадре: центр нижней полосы фигуры по x и низ фигуры по y."""
    body = _solid_rect(surface)
    band_height = max(2, int(body.height * FEET_BAND_SHARE))
    band = surface.subsurface(pygame.Rect(body.x, body.bottom - band_height, body.width, band_height))
    return body.x + _solid_rect(band).centerx, body.bottom


def _median(values):
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def _load_raw_frames(folder):
    """{направление: [кадры]} исходного размера из assets/warrior/<папка>."""
    result = {}
    for d in PLAYER_DIRECTIONS:
        files = _frame_files(WARRIOR_SPRITE_ROOT / folder / d)
        if files:
            result[d] = [pygame.image.load(str(f)).convert_alpha() for f in files]
    return result


def _scale_folder(raw, scale, first_frame_anchor=False):
    """{направление: (кадры, (x, y) ног, габарит содержимого)} после масштаба. Ноги — медиана по кадрам направления:
    корень персонажа в кадрах одной анимации не двигается, а ноги и меч в отдельных кадрах могут выдаваться.
    Габарит — объединение непрозрачных областей всех кадров (с тенью и мечом), без прозрачных полей исходника."""
    scaled = {}
    for d, surfaces in raw.items():
        anchors = [_feet_anchor(surface) for surface in surfaces]
        if first_frame_anchor:
            anchor = (anchors[0][0] * scale, anchors[0][1] * scale)
        else:
            anchor = (_median(a[0] for a in anchors) * scale, _median(a[1] for a in anchors) * scale)
        frames = [
            pygame.transform.smoothscale(
                surface, (max(1, round(surface.get_width() * scale)), max(1, round(surface.get_height() * scale)))
            )
            for surface in surfaces
        ]
        content = frames[0].get_bounding_rect()
        for frame in frames[1:]:
            content = content.union(frame.get_bounding_rect())
        scaled[d] = (frames, anchor, content)
    return scaled


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


def load_warrior_directional_frames():
    """{состояние: {направление: [кадры]}} для воина.

    Один масштаб на все анимации и направления (рост ходьбы приводится к PLAYER_SPRITE_HEIGHT), иначе фигура
    «усаживалась» бы при взмахе мечом. Ноги персонажа всегда в нижнем центре кадра (сцены рисуют кадр по midbottom),
    запас снизу под тень одинаков во всех кадрах. Покой, бег и ходьба лежат на одном холсте по размеру фигуры,
    атаки, получение удара и смерть на другом, шире и выше: в них меч, падение и тень выходят за фигуру.
    Недостающие направления берутся из соседних.
    """
    global _warrior_frames, _warrior_base_height
    if _warrior_frames is None:
        raw = {folder: _load_raw_frames(folder) for folder in set(WARRIOR_ANIMATION_SOURCE.values())}
        walk_heights = [_solid_rect(surface).height for frames in raw["walk"].values() for surface in frames]
        scale = PLAYER_SPRITE_HEIGHT / float(_median(walk_heights))
        scaled = {
            folder: _scale_folder(frames, scale, folder in ANCHOR_FIRST_FRAME_FOLDERS) for folder, frames in raw.items()
        }

        def extents(folders):
            entries = [entry for folder in folders for entry in scaled[folder].values()]
            half = 1 + math.ceil(max(max(ax - box.left, box.right - ax) for _, (ax, _), box in entries))
            above = math.ceil(max(ay - box.top for _, (_, ay), box in entries))
            below = math.ceil(max(box.bottom - ay for _, (_, ay), box in entries))
            return half, above, below

        base_half, base_above, measured_below = extents(WARRIOR_BASE_FOLDERS)
        below = min(measured_below, FEET_MARGIN)
        wide_half, wide_above, _ = extents(WARRIOR_WIDE_FOLDERS)
        canvases = {folder: (base_half, base_above) for folder in WARRIOR_BASE_FOLDERS}
        canvases.update({folder: (wide_half, wide_above) for folder in WARRIOR_WIDE_FOLDERS})
        _warrior_base_height = base_above + below

        def place(surface, anchor, half, above):
            canvas = pygame.Surface((2 * half, above + below), pygame.SRCALPHA)
            canvas.blit(surface, (round(half - anchor[0]), round(above - anchor[1])))
            return canvas

        placed = {
            folder: {
                d: [place(frame, anchor, *canvases[folder]) for frame in frames]
                for d, (frames, anchor, _) in per_direction.items()
            }
            for folder, per_direction in scaled.items()
        }
        frames = {}
        for anim, folder in WARRIOR_ANIMATION_SOURCE.items():
            anim_frames = dict(placed[folder])
            for d in PLAYER_DIRECTIONS:
                if d in anim_frames:
                    continue
                source, mirrored = _warrior_source_direction(d, anim_frames)
                if source is None:
                    continue
                anim_frames[d] = (
                    [pygame.transform.flip(f, True, False) for f in anim_frames[source]] if mirrored else anim_frames[source]
                )
            frames[anim] = anim_frames
        _warrior_frames = frames
    return _warrior_frames


def player_label_top(character, frame_rect):
    """Верх надписи над героем: у воина считается по росту фигуры, а не по кадру, иначе подписи прыгали бы при взмахе меча."""
    if player_profession(character) == WARRIOR_PROFESSION:
        load_warrior_directional_frames()
        return frame_rect.bottom - _warrior_base_height
    return frame_rect.top


def player_frames_for(scene, character, state, attack_variant=0):
    """Набор {направление: [кадры]} для состояния idle, run, walking или attack (вид атаки — индекс attack_variant)."""
    if player_profession(character) == WARRIOR_PROFESSION:
        frames = load_warrior_directional_frames()
        if state == "attack":
            state = WARRIOR_ATTACK_ANIMATIONS[int(attack_variant) % len(WARRIOR_ATTACK_ANIMATIONS)]
        return frames[state]
    if state in ("run", "walking"):
        run_frames = getattr(scene, "player_run_directional_frames", None)
        if run_frames:
            return run_frames
    return getattr(scene, "player_directional_frames", {})


def player_anim_state(character, moving, attacking=False, hit=False, dead=False):
    if player_profession(character) != WARRIOR_PROFESSION:
        return "run" if moving else "idle"
    if dead:
        return "death"
    if hit:
        return "gothit"
    if attacking:
        return "attack"
    if not moving:
        return "idle"
    return "walking" if is_overloaded(character) else "run"


def player_frame(scene, character, direction, anim_time, moving, attacking=False, attack_progress=0.0, run_fps=10.0, idle_fps=4.0, attack_variant=0, hit_progress=None, death_progress=None):
    """Текущий кадр персонажа. Замах воина показывает кадр по прогрессу замаха (0..1) выбранной атакой.

    hit_progress (0..1) включает получение удара, death_progress (0..1) — смерть; None — анимация не идёт.
    Смерть важнее удара, удар важнее атаки; у не-воинов этих состояний нет.
    """
    state = player_anim_state(character, moving, attacking, hit_progress is not None, death_progress is not None)
    frames_dict = player_frames_for(scene, character, state, attack_variant)
    if not frames_dict:
        return None
    frames = frames_dict.get(direction) or next(iter(frames_dict.values()))
    if not frames:
        return None
    progress = {"attack": attack_progress, "gothit": hit_progress, "death": death_progress}.get(state)
    if progress is not None:
        index = int(max(0.0, min(1.0, progress)) * len(frames))
        return frames[min(len(frames) - 1, index)]
    fps = run_fps if state in ("run", "walking") else idle_fps
    return frames[int(anim_time * fps) % len(frames)]
