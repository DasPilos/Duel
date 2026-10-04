"""Данные зданий города: геометрия, хитбоксы и описания (CityScene.objects/solid_rects)."""
import pygame
from client.network import ServerError
from client.structures import hydrate_structures


class CityBuildingsMixin:
    """Инициализация объектов города и крепостных стен. Требует self.tile_size (CityScene)."""

    def _init_city_objects(self):
        """Строения города и стены периметра живут на сервере; клиент только получает их и рисует."""
        try:
            city = self.session.client.get_city_structures()
        except (ServerError, AttributeError, KeyError, OSError):
            city = {"objects": [], "walls": []}
        self.objects = hydrate_structures(city.get("objects", []))
        self.solid_rects = [pygame.Rect(rect) for rect in city.get("walls", [])]

    def _build_city_walls(self):
        """Стены приходят с сервера вместе со строениями (см. _init_city_objects)."""
        self.solid_rects = getattr(self, "solid_rects", [])
