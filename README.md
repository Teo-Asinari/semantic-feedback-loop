# semantic-feedback-loop

Feed Claude a text prompt. It generates a visual (SVG/HTML). Screenshot it. Claude describes the screenshot. That description becomes the next prompt. Repeat.

The question: what happens to meaning over many iterations? Where does it drift, where does it lock in, and is there a regime where structure emerges on its own?

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

No API key. Uses the `claude` CLI — just need a Claude Code subscription.

## Run

```bash
python -m src.server
```

Open http://localhost:8000. Type a seed prompt. Hit start. Each iteration shows up live — prompt, rendered image, description feeding into the next round.

Data saves to `runs/` as JSON + PNG.

## How it works

Three files do the work:

- `src/claude_client.py` — talks to Claude via `claude -p` (CLI print mode)
- `src/loop_engine.py` — runs the loop: generate → render → screenshot → describe → repeat
- `src/server.py` — FastAPI + WebSocket, pushes iterations to the dashboard in real time
