from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from collections import defaultdict
import json

router = APIRouter()


class WebSocketManager:
    def __init__(self):
        # facility_id → list of connected WebSockets
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, facility_id: str):
        await websocket.accept()
        self._connections[facility_id].append(websocket)

    def disconnect(self, websocket: WebSocket, facility_id: str):
        self._connections[facility_id].discard(websocket) if hasattr(
            self._connections[facility_id], "discard"
        ) else None
        try:
            self._connections[facility_id].remove(websocket)
        except ValueError:
            pass

    async def broadcast_to_facility(self, facility_id: str, message: dict):
        dead = []
        for ws in self._connections.get(facility_id, []):
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, facility_id)

    async def broadcast_all(self, message: dict):
        for facility_id in list(self._connections.keys()):
            await self.broadcast_to_facility(facility_id, message)


ws_manager = WebSocketManager()


@router.websocket("/facility/{facility_id}")
async def facility_ws(
    websocket: WebSocket,
    facility_id: str,
    token: str = Query(...),
):
    # Basic token check — in production validate JWT here
    await ws_manager.connect(websocket, facility_id)
    try:
        while True:
            await websocket.receive_text()  # keep alive / ping
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, facility_id)
