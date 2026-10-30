import unittest

from client.map_editor_state import MapEditorState
from core.map_catalog import catalog_definitions

CATALOG = catalog_definitions()


def key_of(kind, category, blocks=None):
    return next(
        item["item_key"] for item in CATALOG
        if item["kind"] == kind and item["category"] == category and (blocks is None or item["blocks"] == blocks)
    )


class ObjectsAndMobsSurviveLayerPaintTests(unittest.TestCase):
    """Нанесение слоя (кисть, заливка, накладка, вставка) не уничтожает объекты и бесов на клетке."""

    def setUp(self):
        self.grass = key_of("ground", "grass", blocks=False)
        self.road = key_of("ground", "road")
        self.tree = key_of("object", "tree")
        self.state = MapEditorState(CATALOG, [], 16, 16)
        self.assertIsNone(self.state.place(self.tree, 3, 3))
        self.assertIsNone(self.state.place_mob("imp_sword", 3, 3))

    def assert_kept(self):
        self.assertEqual(self.state.objects, {(3, 3): self.tree})
        self.assertEqual(self.state.mobs, {(3, 3): "imp_sword"})

    def test_brush_keeps_objects_and_mobs(self):
        self.state.paint(self.grass, 3, 3, 1)
        self.assert_kept()

    def test_larger_brush_keeps_objects_and_mobs(self):
        self.state.paint(self.grass, 3, 3, 3)
        self.assert_kept()

    def test_overlay_keeps_objects_and_mobs(self):
        self.state.paint(self.road, 3, 3, 1)
        self.assert_kept()

    def test_fill_keeps_objects_and_mobs(self):
        self.state.fill(self.grass, 2, 2)
        self.assert_kept()

    def test_pasting_ground_keeps_objects_and_mobs(self):
        stamp = {"w": 1, "h": 1, "ground": [(0, 0, self.grass)], "overlay": [], "objects": []}
        self.state.paste(stamp, 3, 3)
        self.assert_kept()

    def test_erase_with_the_right_button_is_the_only_destruction(self):
        self.state.erase(3, 3)
        self.assertEqual(self.state.objects, {})


if __name__ == "__main__":
    unittest.main()
