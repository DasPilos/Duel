"""Миры из карт редактора Колоды: карта сохраняется заготовкой или становится миром Колоды.

Мир не запускается из редактора: сервер мира Колоды поднимается отдельным процессом с KALODA_WORLD_ID этого мира.
Опубликованную карту сервер читает из базы на каждом запросе рельефа, перезапуск не нужен.
"""
from core.map_catalog import DEFAULT_MAP_SIZE
from kaloda.game_modes import DEFAULT_MODE


def save_map(database, moderator_id, body):
    """Сохраняет карту на сервере как заготовку. Мир не создаётся: его создаёт админ."""
    saved_id = database.save_saved_map(
        int(body.get("saved_id") or 0), body.get("name", ""), str(body.get("mode", DEFAULT_MODE)),
        int(body.get("map_w", DEFAULT_MAP_SIZE)), int(body.get("map_h", DEFAULT_MAP_SIZE)),
        body.get("cells", []), body.get("mobs", []), moderator_id, spawns=body.get("spawns", []),
    )
    stored = database.get_saved_map(saved_id)
    world_errors = _republish_linked_worlds(database, moderator_id, stored)
    return {"saved_id": saved_id, "name": stored["name"], "mode": stored["mode"], "world_errors": world_errors}


def _republish_linked_worlds(database, moderator_id, saved):
    """Миры, где опубликована эта заготовка, получают новую версию: сервер мира прочитает её при следующем запросе рельефа."""
    errors = []
    for world_id in database.linked_world_ids(saved["id"]):
        try:
            database.publish_map(
                saved["cells"], world_id, saved["name"], saved["map_w"], saved["map_h"], moderator_id,
                mobs=saved["mobs"], mode=saved["mode"], spawns=saved["spawns"], saved_id=saved["id"],
            )
        except ValueError as error:
            errors.append({"world_id": world_id, "error": str(error)})
    return errors


def create_test_world(database, admin_id, body):
    """Мир Колоды из сохранённой карты. test=True (по умолчанию) — тестовый: его видят только модераторы и админы.

    Создаёт только админ, независимо от флага test.
    """
    if not database.is_admin(admin_id):
        raise ValueError("Создавать миры может только админ")
    saved = database.get_saved_map(int(body.get("saved_id") or 0))
    name = str(body.get("name", "")).strip() or saved["name"]
    test = bool(body.get("test", True))
    world = database.create_map_world(name, saved["mode"], admin_id, test_only=test)
    try:
        database.publish_map(
            saved["cells"], world["id"], name, saved["map_w"], saved["map_h"], admin_id,
            mobs=saved["mobs"], mode=saved["mode"], spawns=saved["spawns"], saved_id=saved["id"],
        )
    except ValueError:
        database.delete_map_world(world["id"])
        raise
    return {"world_id": world["id"], "name": name, "mode": saved["mode"], "test": test,
            "status": world_status(database, world["id"])}


def world_status(database, world_id):
    """Адрес мира и то, обслуживает ли его этот сервер. Сервер мира Колоды редактор не запускает: адрес пуст, пока мир не поднят."""
    info = database.world_info(world_id)
    return {"world_id": world_id, "server_url": info["server_url"], "served_here": world_id == database.world_id}
