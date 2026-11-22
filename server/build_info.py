"""Идентификатор сборки сервера: меняется только при изменении исходного кода серверной части."""

import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIRS = ("server", "economy", "deck", "core", "combat", "front_line")
SERVER_VERSION = "1.0.1"  # версия после перехода на тайл 16 px
PROTOCOL_VERSION = 1
MINIMUM_CLIENT_VERSION = "1.0.1"
MINIMUM_EDITOR_VERSION = "1.0.1"
_VERSION_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def compute_build_id(root=ROOT):
    digest = hashlib.sha256()
    for name in SOURCE_DIRS:
        for path in sorted((root / name).rglob("*.py")):
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def _version_parts(value):
    match = _VERSION_PATTERN.fullmatch(str(value))
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())


def public_version_info(app="", version="", protocol_version=None):
    result = {
        "server_version": SERVER_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "minimum_client_version": MINIMUM_CLIENT_VERSION,
        "minimum_editor_version": MINIMUM_EDITOR_VERSION,
        "build_id": SERVER_BUILD_ID,
    }
    if not app:
        return result

    minimum_version = {
        "client": MINIMUM_CLIENT_VERSION,
        "editor": MINIMUM_EDITOR_VERSION,
    }.get(str(app))
    client_parts = _version_parts(version)
    minimum_parts = _version_parts(minimum_version) if minimum_version else None
    compatible = (
        minimum_parts is not None
        and client_parts is not None
        and client_parts >= minimum_parts
        and protocol_version == PROTOCOL_VERSION
    )
    if minimum_version is None:
        reason = "Неизвестный тип приложения."
    elif client_parts is None:
        reason = "Некорректный формат версии приложения."
    elif client_parts < minimum_parts:
        reason = f"Требуется версия приложения {minimum_version} или новее."
    elif protocol_version != PROTOCOL_VERSION:
        reason = f"Требуется версия API-протокола {PROTOCOL_VERSION}."
    else:
        reason = ""
    result["compatibility"] = {
        "app": str(app),
        "compatible": compatible,
        "requires_update": not compatible,
        "reason": reason,
    }
    return result


SERVER_BUILD_ID = compute_build_id()
