import io
import json
import struct
import unittest

from server import websocket
from server.world_stream import WorldStream


def _client_frame(opcode, payload):
    """Кадр клиента: всегда маскируется (RFC 6455, раздел 5.3)."""
    mask = b"\x12\x34\x56\x78"
    header = bytearray([0x80 | opcode])
    length = len(payload)
    if length < 126:
        header.append(0x80 | length)
    elif length < 65536:
        header.append(0x80 | 126)
        header += struct.pack("!H", length)
    else:
        header.append(0x80 | 127)
        header += struct.pack("!Q", length)
    masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return bytes(header) + mask + masked


class _Stream:
    def __init__(self, incoming=b""):
        self.rfile = io.BytesIO(incoming)
        self.wfile = io.BytesIO()


class _Database:
    def __init__(self, tokens):
        self.tokens = tokens

    def user_id_by_token(self, token):
        if token not in self.tokens:
            raise ValueError("Требуется авторизация")
        return self.tokens[token]

    def character_belongs_to_user(self, user_id, character_id):
        return character_id == 7 and user_id == 1


class _World:
    def __init__(self):
        self.commands = []

    def command(self, user_id, character_id, payload):
        self.commands.append((user_id, character_id, payload))
        return {"ok": True}


def _decode_server_messages(data):
    messages = []
    stream = io.BytesIO(data)
    while stream.tell() < len(data):
        opcode, payload = websocket.read_frame(_UnmaskedReader(stream))
        messages.append((opcode, json.loads(payload.decode("utf-8")) if payload else None))
    return messages


class _UnmaskedReader:
    """Серверные кадры не маскируются, а read_frame принимает оба варианта: читаем как есть."""

    def __init__(self, stream):
        self.stream = stream

    def read(self, count):
        return self.stream.read(count)


class WebSocketFramingTests(unittest.TestCase):
    def test_accept_key_matches_rfc_example(self):
        self.assertEqual(
            websocket.accept_key("dGhlIHNhbXBsZSBub25jZQ=="),
            "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=",
        )

    def test_masked_client_frame_is_decoded(self):
        opcode, payload = websocket.read_frame(io.BytesIO(_client_frame(websocket.OP_TEXT, b'{"type":"ready"}')))
        self.assertEqual((opcode, payload), (websocket.OP_TEXT, b'{"type":"ready"}'))

    def test_server_frame_length_forms(self):
        for size in (5, 300, 70000):
            payload = b"x" * size
            opcode, decoded = websocket.read_frame(io.BytesIO(websocket.encode_frame(websocket.OP_TEXT, payload)))
            self.assertEqual((opcode, len(decoded)), (websocket.OP_TEXT, size))

    def test_oversized_frame_is_rejected(self):
        header = bytes([0x81, 127]) + struct.pack("!Q", websocket.MAX_PAYLOAD + 1)
        with self.assertRaises(websocket.WebSocketError):
            websocket.read_frame(io.BytesIO(header))


class WorldStreamTests(unittest.TestCase):
    def _session(self):
        stream = _Stream()
        world = _World()
        session = WorldStream(stream, world, _Database({"token-1": 1}))
        return session, stream, world

    def test_auth_then_command_is_acked_and_forwarded(self):
        session, stream, world = self._session()
        session._pusher = object()  # не запускаем поток снимков в тесте
        session.handle_message({"type": "auth", "token": "token-1", "character_id": 7})
        session.handle_message({"type": "command", "id": 5, "payload": {"order_id": 2, "attack_target": None}})
        self.assertEqual(world.commands, [(1, 7, {"order_id": 2, "attack_target": None})])
        messages = _decode_server_messages(stream.wfile.getvalue())
        self.assertEqual([message for _, message in messages], [{"type": "ready"}, {"type": "ack", "id": 5}])

    def test_wrong_token_is_refused(self):
        session, stream, world = self._session()
        session.handle_message({"type": "auth", "token": "bad", "character_id": 7})
        self.assertTrue(session.closed)
        self.assertIsNone(session.user_id)

    def test_sync_before_auth_is_refused(self):
        session, stream, world = self._session()
        session.handle_message({"type": "sync", "payload": {"x": 1.0, "y": 2.0}})
        messages = [message for _, message in _decode_server_messages(stream.wfile.getvalue())]
        self.assertEqual(messages, [{"type": "error", "error": "Сначала авторизуйтесь (auth)"}])
        self.assertIsNone(session.user_id)

    def test_dash_is_kept_until_the_next_push_and_position_follows_latest_sync(self):
        session, stream, world = self._session()
        session._store_sync({"x": 10.0, "y": 20.0, "dash_target": {"x": 5.0, "y": 5.0}})
        session._store_sync({"x": 12.0, "y": 22.0})
        self.assertEqual(session.pending_dash, {"x": 5.0, "y": 5.0})
        self.assertEqual((session.sync_payload["x"], session.sync_payload["y"]), (12.0, 22.0))
        self.assertNotIn("dash_target", session.sync_payload)


if __name__ == "__main__":
    unittest.main()
