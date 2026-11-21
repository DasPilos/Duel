import base64
import json
import struct
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
import zlib

from server.central_main import CentralRequestHandler
from tests.fixtures import create_test_database, drop_test_database, running_server


def _png_chunk(chunk_type, data):
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def _tile_png_base64():
    header = struct.pack(">IIBBBBB", 16, 16, 8, 6, 0, 0, 0)
    pixels = b"".join(b"\x00" + bytes(16 * 4) for _ in range(16))
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(pixels))
        + _png_chunk(b"IEND", b"")
    )
    return base64.b64encode(png).decode("ascii")


def _group_payload(rows=5):
    tile = _tile_png_base64()
    return {
        "name": "Проверочная группа",
        "category": "mountain",
        "tile_rows": rows,
        "tiles": [
            {"x": x, "y": y, "png": tile}
            for y in range(rows)
            for x in range(3)
        ],
    }


class CustomMapTileGroupTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        self.user = self.database.register("custom-tile-user", "password")
        self.moderator = self.database.register("custom-tile-mod", "password")
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE users SET role = 'moderator' WHERE id = %s",
                (self.moderator["id"],),
            )

    def tearDown(self):
        drop_test_database(self.database)

    def test_published_group_is_shared_in_catalog_and_asset_api(self):
        result = self.database.save_custom_tile_group(self.moderator["id"], _group_payload())

        group = result["group"]
        keys = group["tile_keys"]
        self.assertEqual(len(keys), 5)
        self.assertTrue(all(len(row) == 3 for row in keys))
        self.assertEqual(keys[1][1], "custom_tile_%s_1_1" % group["group_id"])
        self.assertEqual(len(result["items"]), 15)

        catalog = {item["item_key"]: item for item in self.database.map_catalog()}
        self.assertEqual(catalog[keys[1][1]]["tile_group_id"], group["group_id"])
        self.assertEqual(catalog[keys[1][1]]["category"], "mountain")
        self.assertEqual(self.database.map_asset(keys[1][1]), base64.b64decode(_tile_png_base64()))
        self.assertEqual(self.database.custom_tile_groups(), [group])

    def test_regular_user_cannot_publish_group(self):
        with self.assertRaisesRegex(ValueError, "модератора"):
            self.database.save_custom_tile_group(self.user["id"], _group_payload(3))

    def test_rejects_missing_tiles_and_invalid_png(self):
        missing_tile = _group_payload(3)
        missing_tile["tiles"].pop()
        with self.assertRaisesRegex(ValueError, "все тайлы"):
            self.database.save_custom_tile_group(self.moderator["id"], missing_tile)

        invalid_png = _group_payload(3)
        invalid_png["tiles"][0]["png"] = base64.b64encode(b"not png").decode("ascii")
        with self.assertRaisesRegex(ValueError, "PNG"):
            self.database.save_custom_tile_group(self.moderator["id"], invalid_png)

    def test_rejects_duplicate_tile_coordinates(self):
        duplicate = _group_payload(3)
        duplicate["tiles"][-1] = duplicate["tiles"][0]
        with self.assertRaisesRegex(ValueError, "повторяющиеся"):
            self.database.save_custom_tile_group(self.moderator["id"], duplicate)

    def test_game_server_upload_catalog_and_asset_routes(self):
        token = self.database.login("custom-tile-mod", "password")["token"]
        with running_server(self.database) as client:
            upload = Request(
                f"{client.base_url}/api/map/tile-groups",
                data=json.dumps(_group_payload(3)).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                method="POST",
            )
            with urlopen(upload, timeout=5) as response:
                uploaded = json.loads(response.read().decode("utf-8"))
                self.assertEqual(response.status, 201)

            catalog_request = Request(
                f"{client.base_url}/api/map/catalog",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urlopen(catalog_request, timeout=5) as response:
                catalog = json.loads(response.read().decode("utf-8"))
            self.assertEqual(catalog["tile_groups"], [uploaded["group"]])
            self.assertIn(
                uploaded["group"]["tile_keys"][1][1],
                {item["item_key"] for item in catalog["items"]},
            )

            asset_request = Request(
                f"{client.base_url}/api/map/assets/{uploaded['group']['tile_keys'][1][1]}",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urlopen(asset_request, timeout=5) as response:
                self.assertEqual(response.read(), base64.b64decode(_tile_png_base64()))

    def test_central_server_accepts_group_upload(self):
        token = self.database.login("custom-tile-mod", "password")["token"]
        previous_database = CentralRequestHandler.database
        CentralRequestHandler.database = self.database
        http_server = ThreadingHTTPServer(("127.0.0.1", 0), CentralRequestHandler)
        thread = threading.Thread(target=http_server.serve_forever, daemon=True)
        thread.start()
        try:
            request = Request(
                f"http://127.0.0.1:{http_server.server_port}/api/map/tile-groups",
                data=json.dumps(_group_payload(3)).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                method="POST",
            )
            with urlopen(request, timeout=5) as response:
                uploaded = json.loads(response.read().decode("utf-8"))
                self.assertEqual(response.status, 201)
            self.assertEqual(len(uploaded["items"]), 9)
        finally:
            http_server.shutdown()
            thread.join(timeout=5)
            http_server.server_close()
            CentralRequestHandler.database = previous_database


if __name__ == "__main__":
    unittest.main()
