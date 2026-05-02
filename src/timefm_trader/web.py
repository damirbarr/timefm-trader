"""FastAPI web server and control API for TimeFM Trader."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.timefm_trader import config

app = FastAPI(title="TimeFM Trader")
logger = logging.getLogger(__name__)


def _normalize(value: Any) -> Any:
    """Convert dataclasses, enums, and datetimes into JSON-safe values."""
    if is_dataclass(value):
        data = {key: _normalize(item) for key, item in asdict(value).items()}
        if hasattr(value, "portfolio_value"):
            data["portfolio_value"] = _normalize(getattr(value, "portfolio_value"))
        if hasattr(value, "total_return_pct"):
            data["total_return_pct"] = _normalize(getattr(value, "total_return_pct"))
        if hasattr(value, "realized_pnl"):
            data["realized_pnl"] = _normalize(getattr(value, "realized_pnl"))
        if hasattr(value, "positions"):
            data["position_count"] = len(getattr(value, "positions", {}) or {})
        return data
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_normalize(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _snapshot_state() -> dict[str, Any]:
    provider = getattr(app.state, "state_provider", None)
    if provider is None:
        raise RuntimeError("app.state.state_provider is not configured")

    state = provider()
    if hasattr(state, "get_state_snapshot"):
        snapshot = state.get_state_snapshot()
    else:
        snapshot = state

    normalized = _normalize(snapshot)
    if isinstance(normalized, dict):
        return normalized
    return {"state": normalized}


async def require_auth(request: Request) -> None:
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if token != config.CONTROL_API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: str) -> None:
        dead: list[WebSocket] = []
        for ws in list(self.active):
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await manager.connect(ws)
    try:
        while True:
            payload = json.dumps(_snapshot_state())
            await ws.send_text(payload)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        logger.exception("WebSocket stream failed")
        manager.disconnect(ws)


async def dispatch(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
    handler = getattr(app.state, "command_handler", None)
    if handler is None:
        raise HTTPException(status_code=503, detail="Command handler is not configured")

    result = await handler(payload)
    app.state.command_log.append(
        {"time": datetime.utcnow().isoformat(), "payload": _normalize(payload)}
    )
    return _normalize(result)


@app.get("/control/state", dependencies=[Depends(require_auth)])
async def get_state(request: Request) -> dict[str, Any]:
    return _snapshot_state()


@app.post("/control/risk", dependencies=[Depends(require_auth)])
async def control_risk(request: Request) -> dict[str, Any]:
    body = await request.json()
    return await dispatch(request, {"type": "risk", **body})


@app.post("/control/position", dependencies=[Depends(require_auth)])
async def control_position(request: Request) -> dict[str, Any]:
    body = await request.json()
    return await dispatch(request, {"type": "position", **body})


@app.post("/control/trading", dependencies=[Depends(require_auth)])
async def control_trading(request: Request) -> dict[str, Any]:
    body = await request.json()
    return await dispatch(request, {"type": "trading", **body})


@app.post("/control/watchlist", dependencies=[Depends(require_auth)])
async def control_watchlist(request: Request) -> dict[str, Any]:
    body = await request.json()
    return await dispatch(request, {"type": "watchlist", **body})


@app.post("/control/insight", dependencies=[Depends(require_auth)])
async def control_insight(request: Request) -> dict[str, Any]:
    body = await request.json()
    return await dispatch(request, {"type": "insight", **body})


@app.post("/control/config", dependencies=[Depends(require_auth)])
async def control_config(request: Request) -> dict[str, Any]:
    body = await request.json()
    return await dispatch(request, {"type": "config", **body})


@app.on_event("startup")
async def startup() -> None:
    if not hasattr(app.state, "command_log"):
        app.state.command_log = []


static_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "static")
)
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_model=None)
async def root() -> FileResponse | dict[str, str]:
    index = os.path.join(static_dir, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"status": "running"}
