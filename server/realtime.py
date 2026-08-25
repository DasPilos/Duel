"""Optional WebSocket chat gateway.

Run separately with: python -m server.realtime
"""
import asyncio
import json

from server import config
from server.database import Database

try:
    import websockets
except ImportError as error:
    websockets = None
    WEBSOCKETS_IMPORT_ERROR = error


class ChatGateway:
    def __init__(self):
        self.database = Database()
        self.connections = set()

    async def handle(self, websocket):
        self.connections.add(websocket)
        try:
            async for raw in websocket:
                event = json.loads(raw)
                response = await self.dispatch(event)
                if response is not None:
                    await websocket.send(json.dumps(response, ensure_ascii=False))
        finally:
            self.connections.discard(websocket)

    async def dispatch(self, event):
        event_type = event.get("type")
        payload = event.get("payload", {})
        token = payload.get("token")
        if event_type == "chat:history":
            user_id = self.database.user_id_by_token(token)
            character = self.database.get_character(user_id, int(payload["character_id"]))
            if character is None:
                raise ValueError("Персонаж не найден")
            messages = self.database.get_chat_history(
                character["id"],
                payload.get("location", "tavern"),
                payload.get("before_id"),
                payload.get("limit", 50),
            )
            return {"type": "chat:history", "request_id": event.get("request_id"), "payload": {"messages": messages}}
        if event_type == "chat:send":
            user_id = self.database.user_id_by_token(token)
            character = self.database.get_character(user_id, int(payload["character_id"]))
            if character is None:
                raise ValueError("Персонаж не найден")
            text = str(payload.get("text", "")).strip()
            if not text or len(text) > config.CHAT_MAX_LENGTH:
                raise ValueError("Сообщение должно содержать от 1 до 300 символов")
            message = self.database.add_chat_message(
                character["id"],
                payload.get("location", "tavern"),
                text,
                payload.get("recipient_id"),
            )
            event = {"type": "chat:message", "payload": message}
            await self.broadcast(event)
            return None
        raise ValueError("Неизвестное событие")

    async def broadcast(self, event):
        if not self.connections:
            return
        raw = json.dumps(event, ensure_ascii=False)
        await asyncio.gather(*(connection.send(raw) for connection in self.connections), return_exceptions=True)


async def run():
    if websockets is None:
        raise SystemExit(f"Установите зависимость websockets: {WEBSOCKETS_IMPORT_ERROR}")
    gateway = ChatGateway()
    async with websockets.serve(gateway.handle, config.HOST, 8766):
        print(f"WebSocket chat: ws://{config.HOST}:8766")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(run())
