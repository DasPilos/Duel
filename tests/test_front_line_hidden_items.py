import unittest

from server.items_database import BASE_STARTER_EQUIPMENT, _item_id_of, hidden_items_for_mode


class HiddenStarterItemsTests(unittest.TestCase):
    def test_front_line_hides_the_economy_starter_tools(self):
        self.assertEqual(hidden_items_for_mode("front_line"), frozenset(BASE_STARTER_EQUIPMENT))

    def test_other_modes_keep_the_starter_tools(self):
        self.assertEqual(hidden_items_for_mode("economy"), frozenset())
        self.assertEqual(hidden_items_for_mode("tower"), frozenset())

    def test_item_id_is_read_from_either_field(self):
        self.assertEqual(_item_id_of({"item_id": 91}), 91)
        self.assertEqual(_item_id_of({"id": 90}), 90)
        self.assertEqual(_item_id_of({}), -1)


if __name__ == "__main__":
    unittest.main()
