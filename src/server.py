"""FastAPI web server with WebSocket support for the semantic feedback loop."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.loop_engine import (
    get_active_run,
    get_iteration,
    get_run_history,
    run_loop,
    stop_loop,
    Iteration,
    RunState,
    RUNS_DIR,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Semantic Feedback Loop")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_ROOT / "static"

# Serve run screenshot images
app.mount("/runs", StaticFiles(directory=str(RUNS_DIR), check_dir=False), name="runs")

# Connected WebSocket clients
_ws_clients: set[WebSocket] = set()


async def _broadcast(data: dict):
    """Send a JSON message to all connected WebSocket clients."""
    message = json.dumps(data, default=str)
    disconnected = set()
    for ws in _ws_clients:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)
    _ws_clients -= disconnected


class StartRequest(BaseModel):
    prompt: str
    max_iterations: int = 20


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.post("/api/start")
async def start_loop(req: StartRequest):
    if get_active_run() is not None:
        return JSONResponse({"error": "A loop is already running"}, status_code=409)

    def on_iteration(iteration: Iteration, run: RunState):
        # Schedule broadcast on the event loop
        asyncio.get_event_loop().call_soon_threadsafe(
            asyncio.ensure_future,
            _broadcast({
                "type": "iteration",
                "run_id": run.run_id,
                "status": run.status,
                "iteration": iteration.to_dict(),
            }),
        )

    async def _run():
        try:
            result = await run_loop(
                seed_prompt=req.prompt,
                max_iterations=req.max_iterations,
                on_iteration=on_iteration,
            )
            await _broadcast({
                "type": "run_complete",
                "run_id": result.run_id,
                "status": result.status,
                "iteration_count": len(result.iterations),
            })
        except Exception as e:
            logger.error("Loop error: %s", e)
            await _broadcast({"type": "error", "message": str(e)})

    asyncio.ensure_future(_run())
    return {"status": "started"}


@app.post("/api/stop")
async def stop():
    if get_active_run() is None:
        return JSONResponse({"error": "No loop is running"}, status_code=404)
    stop_loop()
    return {"status": "stopping"}


@app.get("/api/status")
async def status():
    run = get_active_run()
    if run is None:
        return {"status": "idle", "run": None}
    return {"status": run.status, "run": run.to_dict()}


@app.get("/api/history")
async def history():
    return get_run_history()


@app.get("/api/runs/{run_id}/iterations/{index}")
async def get_iter(run_id: str, index: int):
    data = get_iteration(run_id, index)
    if data is None:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return data


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)
    logger.info("WebSocket client connected (%d total)", len(_ws_clients))
    try:
        while True:
            # Keep connection alive; we don't expect client messages
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(ws)
        logger.info("WebSocket client disconnected (%d total)", len(_ws_clients))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.server:app", host="0.0.0.0", port=8000, reload=True)
