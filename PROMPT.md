# Semantic Feedback Loop — Build Instructions

## What This Is

A system that chains Claude in a feedback loop:

1. Start with a text prompt
2. Claude generates SVG/HTML visual code from the prompt
3. Render the code in a headless browser and take a screenshot
4. Claude describes the screenshot
5. That description becomes the next prompt
6. Repeat for N iterations

The goal: observe how visual meaning drifts, persists, or transforms over many iterations.

## How to Run

```bash
pip install -r requirements.txt
playwright install chromium
python -m src.server
```

Open http://localhost:8000 — enter a seed prompt, click START, watch iterations appear live.

**Note:** No API key needed — uses the `claude` CLI (Claude Code) which authenticates via your subscription.

## Architecture

- `src/claude_client.py` — Claude CLI wrapper (generate code, describe images via `claude -p`)
- `src/loop_engine.py` — Core loop: prompt → code → render → screenshot → describe → repeat
- `src/server.py` — FastAPI server with WebSocket push for live updates
- `static/index.html` — Dashboard showing timeline of iterations
- `runs/` — Each run saved as JSON + PNG files

## Quality Gates

1. `pytest tests/` — all tests pass
2. `python -m src.server` — server starts without errors
3. Dashboard loads at http://localhost:8000
4. Starting a loop produces iterations with images and descriptions
5. Data is saved to `runs/` directory
