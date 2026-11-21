"""Сессия WebSocket мира: сервер сам шлёт снимки с фиксированной частотой, команды и положение приходят по тому же соединению.

Клиент: auth -> ready; затем sync (положение, добыча, рывок) и command (приказы). Сервер: snapshot и ack.
"""

import json
import threading
import time

from server import websocket

PUSH_INTERVAL_SECONDS = 0.05  # 20 снимков в секунду
MAX_MESSAGE_BYTES = 64 * 1024


class WorldStream:
    def __init__(self, stream, world, database):
        self.stream = stream  # объект с rfile/wfile (обработчик HTTP после рукопожатия)
        self.world = world
        self.database = database
        self.write_lock = threading.Lock()
        self.user_id = None
        self.character_id = None
        self.sync_payload = {}
        self.pending_dash = None
        self.last_seq = 0
        self.closed = False
        self._pusher = None

    def send(self, message):
        data = json.dumps(message, ensure_ascii=False).encode("utf-8")
        with self.write_lock:
            self.stream.wfile.write(websocket.encode_frame(websocket.OP_TEXT, data))
            self.stream.wfile.flush()

    def run(self):
        """Читает сообщения клиента, пока соединение открыто."""
        try:
            while not self.closed:
                opcode, data = websocket.read_frame(self.stream.rfile)
                if opcode == websocket.OP_CLOSE:
                    self._send_close()
                    return
                if opcode == websocket.OP_PING:
                    with self.write_lock:
                        self.stream.wfile.write(websocket.encode_frame(websocket.OP_PONG, data))
                        self.stream.wfile.flush()
                    continue
                if opcode != websocket.OP_TEXT:
                    continue
                if len(data) > MAX_MESSAGE_BYTES:
                    raise websocket.WebSocketError("сообщение слишком большое")
                self.handle_message(json.loads(data.decode("utf-8")))
        except (websocket.WebSocketError, OSError, ValueError):
            pass
        finally:
            self.closed = True

    def _send_close(self):
        with self.write_lock:
            try:
                self.stream.wfile.write(websocket.encode_frame(websocket.OP_CLOSE, b""))
                self.stream.wfile.flush()
            except OSError:
                pass

    def handle_message(self, message):
        if not isinstance(message, dict):
            return
        kind = message.get("type")
        if kind == "auth":
            self._auth(message)
        elif self.user_id is None:
            self.send({"type": "error", "error": "Сначала авторизуйтесь (auth)"})
        elif kind == "sync":
            self._store_sync(message.get("payload") or {})
        elif kind == "command":
            self._command(message)

    def _auth(self, message):
        try:
            user_id = self.database.user_id_by_token(str(message.get("token", "")))
            character_id = int(message.get("character_id", 0))
            if not self.database.character_belongs_to_user(user_id, character_id):
                raise ValueError("Персонаж не найден")
        except (ValueError, TypeError) as error:
            self.send({"type": "error", "error": str(error)})
            self.closed = True
            return
        self.user_id = user_id
        self.character_id = character_id
        self.sync_payload = {"resync": True}
        self.send({"type": "ready"})
        if self._pusher is None:
            self._pusher = threading.Thread(target=self._push_loop, daemon=True)
            self._pusher.start()

    def _store_sync(self, payload):
        if not isinstance(payload, dict):
            return
        # Разовые действия (рывок) не теряются между кадрами: берём их отдельно и отдаём один раз.
        if payload.get("dash_target") is not None:
            self.pending_dash = payload.get("dash_target")
        resync = bool(payload.get("resync")) or bool(self.sync_payload.get("resync"))
        self.sync_payload = {key: value for key, value in payload.items() if key != "dash_target"}
        self.sync_payload["resync"] = resync

    def _command(self, message):
        command_id = message.get("id")
        try:
            self.world.command(self.user_id, self.character_id, message.get("payload") or {})
            self.send({"type": "ack", "id": command_id})
        except (ValueError, TypeError) as error:
            self.send({"type": "error", "id": command_id, "error": str(error)})

    def _push_loop(self):
        while not self.closed:
            time.sleep(PUSH_INTERVAL_SECONDS)
            try:
                payload = dict(self.sync_payload)
                payload["since"] = self.last_seq
                payload["dash_target"] = self.pending_dash
                snapshot = self.world.sync(self.user_id, self.character_id, payload)
                self.pending_dash = None
                self.sync_payload.pop("resync", None)
                self.last_seq = snapshot.get("seq", self.last_seq)
                self.send({"type": "snapshot", "data": snapshot})
            except (OSError, ValueError, TypeError):
                self.closed = True
                return
