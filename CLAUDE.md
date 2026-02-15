# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies (use venv to avoid system package conflicts)
python -m venv .venv
PYTHONPATH="" .venv/bin/pip install -r requirements.txt
PYTHONPATH="" .venv/bin/playwright install chromium

# Run server (hot-reload enabled, serves on http://localhost:8000)
PYTHONPATH="" .venv/bin/python -m src.server

# Run all tests
PYTHONPATH="" .venv/bin/python -m pytest tests/ -v

# Run a single test
PYTHONPATH="" .venv/bin/python -m pytest tests/test_loop.py::test_render_and_screenshot -v
```

`PYTHONPATH=""` is required on this system to avoid ROS package conflicts polluting the venv.

## Architecture

The system chains Claude in a feedback loop: **text prompt → generate SVG/HTML → render & screenshot → describe screenshot → repeat**.

Three layers with strict separation:

- **`src/claude_client.py`** — Shells out to `claude -p` (print mode) via subprocess. No API key needed; uses Claude Code subscription auth. Strips `CLAUDECODE` env var so the CLI runs outside the parent session. `describe_image` uses `--dangerously-skip-permissions` with the `Read` tool to let Claude read PNG files.

- **`src/loop_engine.py`** — Orchestrates the loop. Global `_active_run` / `_stop_flag` enforce one loop at a time. CLI calls are wrapped in `asyncio.to_thread()` since they're blocking subprocess calls. Each run persists to `runs/{run_id}/` as JSON + PNG + HTML files. The `on_iteration` callback is how the server layer gets notified.

- **`src/server.py`** — FastAPI app. The `/api/start` endpoint fires the loop as an `asyncio.ensure_future` task. The `on_iteration` callback broadcasts to WebSocket clients via `_ws_clients` set. Static files served from `static/`, run screenshots mounted at `/runs/`.

## Key Details

- Only one loop can run at a time (global state in `loop_engine.py`)
- Playwright launches a fresh Chromium instance per screenshot (800x600 viewport)
- Tests mock `subprocess.run` for Claude CLI calls; the Playwright render test is a real integration test requiring Chromium
- The `runs/` directory is gitignored
