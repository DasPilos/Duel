import asyncio
import json

try:
    import websockets
except ImportError as error:
    websockets = None
    WEBSOCKETS_IMPORT_ERROR = error


class RealtimeChatClient:
    def __init__(self, url="ws://127.0.0.1:8766"):
        self.url = url
        self.websocket = None
        self.events = asyncio.Queue()

    async def connect(self):
        if websockets is None:
            raise RuntimeError(f"Установите зависимость websockets: {WEBSOCKETS_IMPORT_ERROR}")
        self.websocket = await websockets.connect(self.url)

    async def send(self, event):
        if self.websocket is None:
            raise RuntimeError("WebSocket-клиент не подключён")
        await self.websocket.send(json.dumps(event, ensure_ascii=False))

    async def receive_loop(self):
        if self.websocket is None:
            raise RuntimeError("WebSocket-клиент не подключён")
        async for raw in self.websocket:
            await self.events.put(json.loads(raw))

    async def close(self):
        if self.websocket is not None:
            await self.websocket.close()
            self.websocket = None
