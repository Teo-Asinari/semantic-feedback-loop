"""Core feedback loop engine.

text prompt -> Claude generates SVG/HTML -> render & screenshot -> Claude describes -> repeat
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable, Optional

from playwright.async_api import async_playwright

from src.claude_client import generate_visual_code, describe_image

logger = logging.getLogger(__name__)

RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"


@dataclass
class Iteration:
    index: int
    prompt: str
    code: str = ""
    image_path: str = ""
    description: str = ""
    timestamp: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RunState:
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    seed_prompt: str = ""
    iterations: list[Iteration] = field(default_factory=list)
    status: str = "idle"  # idle | running | stopped | finished | error
    max_iterations: int = 20

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "seed_prompt": self.seed_prompt,
            "status": self.status,
            "max_iterations": self.max_iterations,
            "iteration_count": len(self.iterations),
        }


# Global active run — only one loop at a time
_active_run: Optional[RunState] = None
_stop_flag = False


def get_active_run() -> Optional[RunState]:
    return _active_run


def get_run_history() -> list[dict]:
    """List completed runs from the runs/ directory."""
    if not RUNS_DIR.exists():
        return []
    runs = []
    for d in sorted(RUNS_DIR.iterdir()):
        meta = d / "meta.json"
        if meta.exists():
            runs.append(json.loads(meta.read_text()))
    return runs


def get_iteration(run_id: str, index: int) -> Optional[dict]:
    run_dir = RUNS_DIR / run_id
    iter_file = run_dir / f"iteration_{index:04d}.json"
    if iter_file.exists():
        return json.loads(iter_file.read_text())
    return None


async def _render_and_screenshot(html_content: str, run_dir: Path, index: int) -> str:
    """Write HTML/SVG to a temp file, open in Playwright, screenshot it.

    Returns the absolute path to the screenshot PNG.
    """
    tmp = run_dir / f"render_{index:04d}.html"
    tmp.write_text(html_content, encoding="utf-8")

    image_path = str(run_dir / f"screenshot_{index:04d}.png")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 800, "height": 600})
        await page.goto(f"file://{tmp.resolve()}")
        # Give the page a moment to render
        await page.wait_for_timeout(500)
        await page.screenshot(path=image_path, full_page=False)
        await browser.close()

    return image_path


def _save_iteration(run_dir: Path, iteration: Iteration):
    path = run_dir / f"iteration_{iteration.index:04d}.json"
    data = iteration.to_dict()
    # Don't store raw code in JSON if it's huge — it's also in the .html file
    path.write_text(json.dumps(data, indent=2))


def _save_meta(run_dir: Path, run: RunState):
    meta = run_dir / "meta.json"
    meta.write_text(json.dumps(run.to_dict(), indent=2))


async def run_loop(
    seed_prompt: str,
    max_iterations: int = 20,
    on_iteration: Optional[Callable[[Iteration, RunState], None]] = None,
) -> RunState:
    """Execute the feedback loop.

    Args:
        seed_prompt: The initial text prompt.
        max_iterations: How many iterations to run.
        on_iteration: Callback fired after each iteration completes.

    Returns:
        The final RunState.
    """
    global _active_run, _stop_flag
    _stop_flag = False

    run = RunState(seed_prompt=seed_prompt, max_iterations=max_iterations, status="running")
    _active_run = run

    run_dir = RUNS_DIR / run.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _save_meta(run_dir, run)

    current_prompt = seed_prompt

    try:
        for i in range(max_iterations):
            if _stop_flag:
                run.status = "stopped"
                logger.info("Loop stopped by user at iteration %d", i)
                break

            logger.info("Iteration %d — prompt: %.80s...", i, current_prompt)
            iteration = Iteration(index=i, prompt=current_prompt, timestamp=time.time())

            try:
                # Step 1: Generate visual code via claude CLI
                code = await asyncio.to_thread(generate_visual_code, current_prompt)
                iteration.code = code

                # Step 2: Render and screenshot
                image_path = await _render_and_screenshot(code, run_dir, i)
                iteration.image_path = image_path

                # Step 3: Describe the screenshot via claude CLI
                description = await asyncio.to_thread(describe_image, image_path)
                iteration.description = description

                # The description becomes the next prompt
                current_prompt = description

            except Exception as e:
                logger.error("Error in iteration %d: %s", i, e)
                iteration.error = str(e)
                # Still save partial iteration data
                run.iterations.append(iteration)
                _save_iteration(run_dir, iteration)
                _save_meta(run_dir, run)
                if on_iteration:
                    on_iteration(iteration, run)
                run.status = "error"
                break

            run.iterations.append(iteration)
            _save_iteration(run_dir, iteration)
            _save_meta(run_dir, run)

            if on_iteration:
                on_iteration(iteration, run)
        else:
            run.status = "finished"

    finally:
        _save_meta(run_dir, run)
        _active_run = None

    return run


def stop_loop():
    global _stop_flag
    _stop_flag = True
