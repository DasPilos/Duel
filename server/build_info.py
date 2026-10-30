"""Идентификатор сборки сервера: меняется только при изменении исходного кода серверной части."""

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIRS = ("server", "core", "combat")


def compute_build_id(root=ROOT):
    digest = hashlib.sha256()
    for name in SOURCE_DIRS:
        for path in sorted((root / name).rglob("*.py")):
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


SERVER_BUILD_ID = compute_build_id()
