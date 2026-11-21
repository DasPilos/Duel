"""Build the downloadable source package for the Pygame client."""

import argparse
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


CLIENT_DIRS = ("client", "combat", "core", "deck", "scenes", "ui", "assets")
ROOT_FILES = ("main.py", "requirements.txt")
EXCLUDED_CLIENT_FILES = {
    "combat/arena_battle.py",
    "combat/card_battle.py",
    "combat/card_database.py",
    "combat/mechanics.py",
    "combat/physical_effects.py",
    "scenes/duel_input.py",
    "scenes/duel_resolver.py",
    "scenes/duel_scene.py",
    "scenes/mage_battle_scene.py",
    "ui/card_tooltip.py",
    "ui/collection_panel.py",
    "ui/deck_selection_panel.py",
    "ui/dungeon_window.py",
    "ui/duel_renderer.py",
    "ui/library_window.py",
    "ui/mage_card.py",
    "ui/renderers/card_area.py",
}
EXCLUDED_PARTS = {"__pycache__", ".git"}
DISABLED_MESSAGE = (
    "Сборка Python-клиента отключена. Клиент разрабатывается на Godot: godot_client/."
)
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def build_client_package(output_path=None):
    raise RuntimeError(DISABLED_MESSAGE)
    # Ниже код архивной сборки Python-клиента; не выполняется, пока сборка отключена.
    project = Path(__file__).resolve().parent.parent
    destination = Path(output_path).resolve() if output_path else project / "client_package.zip"
    temporary = destination.with_name(destination.name + ".tmp")
    destination.parent.mkdir(parents=True, exist_ok=True)
    written = 0

    with ZipFile(temporary, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for directory in CLIENT_DIRS:
            for path in sorted((project / directory).rglob("*")):
                if not path.is_file() or EXCLUDED_PARTS.intersection(path.parts):
                    continue
                if path.suffix in EXCLUDED_SUFFIXES:
                    continue
                relative_path = path.relative_to(project).as_posix()
                if relative_path in EXCLUDED_CLIENT_FILES:
                    continue
                archive.write(path, relative_path)
                written += 1

        for name in ROOT_FILES:
            path = project / name
            if path.is_file():
                archive.write(path, name)
                written += 1

        archive.writestr(
            "RUN_CLIENT.txt",
            "Multiverse of Games client (Python source package)\n\n"
            "Requires Python 3.13. From this extracted folder run:\n"
            "  py -3.13 -m pip install -r requirements.txt\n"
            "  py -3.13 main.py --online --server http://192.168.1.230:8765\n\n"
            "This is a source package, not a standalone executable.\n",
        )

    temporary.replace(destination)
    print(f"Created {destination} ({destination.stat().st_size:,} bytes; {written} files)")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="Output ZIP path (default: project/client_package.zip)")
    args = parser.parse_args()
    try:
        build_client_package(args.output)
    except RuntimeError as error:
        print(error, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
