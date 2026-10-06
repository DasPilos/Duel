"""Build the downloadable source package for the Pygame client."""

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


CLIENT_DIRS = ("client", "combat", "core", "scenes", "ui", "assets")
ROOT_FILES = ("main.py", "requirements.txt", "cards.sqlite3")
EXCLUDED_PARTS = {"__pycache__", ".git"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def build_client_package(output_path=None):
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
                archive.write(path, path.relative_to(project).as_posix())
                written += 1

        for name in ROOT_FILES:
            path = project / name
            if path.is_file():
                archive.write(path, name)
                written += 1

        archive.writestr(
            "RUN_CLIENT.txt",
            "Duel client (Python source package)\n\n"
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
    build_client_package(args.output)


if __name__ == "__main__":
    main()
