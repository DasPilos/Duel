"""Мобы Колоды для редактора карт: виды, которые можно расставить на карте.

Ключи совпадают с видами, которые принимает сервер Колоды при сохранении карты (kaloda/server/map_editor.py).
members — кто выходит в бой с этой клетки, как в kaloda/rewards.py: лагерь кобольдов — это три кобольда.
Картинки рисуются процедурно (previews.py), файлов спрайтов у мобов Колоды нет.
"""

MOB_CATALOG = (
    {
        "key": "kobold",
        "name": "Кобольд",
        "members": ("kobold",),
        "hint": "Кобольд в лесу; после поражения возрождается через минуту",
    },
    {
        "key": "kobold_camp",
        "name": "Лагерь кобольдов",
        "members": ("kobold", "kobold", "kobold"),
        "hint": "Три кобольда в одном бою на арене",
    },
    {
        "key": "ancient_ent",
        "name": "Древний энт",
        "members": ("ancient_ent",),
        "hint": "Древний энт в лесу",
    },
    {
        "key": "skeleton",
        "name": "Скелет",
        "members": ("skeleton",),
        "hint": "Скелет из подземелья",
    },
    {
        "key": "necromancer",
        "name": "Некромансер",
        "members": ("necromancer",),
        "hint": "Некромансер из подземелья",
    },
)

MOB_KINDS = frozenset(mob["key"] for mob in MOB_CATALOG)


def mob_catalog():
    """Копия каталога мобов в порядке показа в редакторе."""
    return [dict(mob) for mob in MOB_CATALOG]
