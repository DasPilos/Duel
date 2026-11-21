from pathlib import Path

from core.map_catalog import MAP_ASSETS


def read_catalog_asset(catalog, item_key):
    item = next((entry for entry in catalog if entry["item_key"] == item_key), None)
    if item is None:
        raise ValueError("Элемента нет в каталоге карт")
    root = MAP_ASSETS.resolve()
    asset_path = (root / str(item["asset"])).resolve()
    try:
        asset_path.relative_to(root)
    except ValueError:
        raise ValueError("Некорректный путь ресурса карты") from None
    if not asset_path.is_file():
        raise ValueError("Файл ресурса карты не найден")
    return asset_path.read_bytes()
