"""Claude CLI wrapper for generating visual code and describing images.

Uses the `claude` CLI (Claude Code) in print mode instead of the Anthropic API
directly, so it works with a Claude Code subscription — no API key needed.
"""

import logging
import os
import subprocess
import tempfile

logger = logging.getLogger(__name__)

# Strip CLAUDECODE env var so the CLI doesn't refuse to run inside Claude Code
_CLEAN_ENV = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}


def _run_claude(prompt: str, model: str = "sonnet", timeout: int = 120) -> str:
    """Run the claude CLI in print mode and return the text output."""
    cmd = [
        "claude",
        "-p",
        "--model", model,
        "--no-session-persistence",
        prompt,
    ]
    logger.info("Running claude CLI: %.120s...", prompt[:120])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_CLEAN_ENV,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed (exit {result.returncode}): {result.stderr[:500]}")
    return result.stdout.strip()


def generate_visual_code(prompt: str, model: str = "sonnet") -> str:
    """Ask Claude to generate SVG/HTML from a text prompt.

    Returns the raw SVG or HTML string.
    """
    full_prompt = (
        "Generate a single self-contained SVG or HTML document that visually represents "
        "the following description. Output ONLY the raw code — no markdown fences, no "
        "explanation, no commentary. The code must be valid and renderable in a browser.\n\n"
        f"Description: {prompt}"
    )
    return _run_claude(full_prompt, model=model)


def describe_image(image_path: str, model: str = "sonnet") -> str:
    """Ask Claude to describe a screenshot image.

    Uses the claude CLI with the image file piped via a prompt that references it.
    Since the CLI doesn't directly support image input in -p mode, we use a
    workaround: call claude with --allowedTools and have it read the file.

    Returns a text description of what's in the image.
    """
    full_prompt = (
        f"Read the image file at {image_path} using the Read tool, then describe it in rich detail. "
        "Focus on shapes, colors, spatial relationships, text content, and overall composition. "
        "Be vivid and specific so that someone could recreate the visual from your description alone. "
        "Output ONLY the description text — no preamble, no tool calls explanation."
    )
    cmd = [
        "claude",
        "-p",
        "--model", model,
        "--no-session-persistence",
        "--allowedTools", "Read",
        "--dangerously-skip-permissions",
        full_prompt,
    ]
    logger.info("Running claude CLI for image description: %s", image_path)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=180,
        env=_CLEAN_ENV,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed (exit {result.returncode}): {result.stderr[:500]}")
    return result.stdout.strip()
