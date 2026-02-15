"""Tests for the semantic feedback loop components."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.loop_engine import Iteration, RunState, _render_and_screenshot


# --- Unit tests for claude_client ---

@patch("src.claude_client.subprocess.run")
def test_generate_visual_code(mock_run):
    """Test that generate_visual_code calls the claude CLI correctly."""
    from src.claude_client import generate_visual_code

    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="<svg><circle r='50'/></svg>",
        stderr="",
    )

    result = generate_visual_code("a red circle")
    assert "<svg>" in result
    mock_run.assert_called_once()

    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "claude"
    assert "-p" in cmd


@patch("src.claude_client.subprocess.run")
def test_describe_image(mock_run):
    """Test that describe_image calls the claude CLI with the image path."""
    from src.claude_client import describe_image

    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="A red circle on white background",
        stderr="",
    )

    result = describe_image("/tmp/test.png")
    assert "red circle" in result
    mock_run.assert_called_once()

    cmd = mock_run.call_args[0][0]
    assert "claude" in cmd[0]
    assert "--dangerously-skip-permissions" in cmd


# --- Unit tests for loop_engine data structures ---

def test_iteration_to_dict():
    it = Iteration(index=0, prompt="test", code="<svg/>", description="a thing")
    d = it.to_dict()
    assert d["index"] == 0
    assert d["prompt"] == "test"
    assert d["code"] == "<svg/>"
    assert d["description"] == "a thing"
    assert d["error"] is None


def test_run_state_to_dict():
    run = RunState(seed_prompt="hello", max_iterations=5)
    d = run.to_dict()
    assert d["seed_prompt"] == "hello"
    assert d["max_iterations"] == 5
    assert d["status"] == "idle"
    assert d["iteration_count"] == 0
    assert len(d["run_id"]) == 12


# --- Integration test for render (requires playwright) ---

@pytest.mark.asyncio
async def test_render_and_screenshot(tmp_path):
    """Test rendering HTML and taking a screenshot (requires playwright + chromium)."""
    html = "<html><body style='background:red'><h1>Hello</h1></body></html>"
    image_path = await _render_and_screenshot(html, tmp_path, 0)

    assert Path(image_path).exists()
    image_bytes = Path(image_path).read_bytes()
    # PNG magic bytes
    assert image_bytes[:4] == b"\x89PNG"


# --- Server tests ---

def test_server_routes():
    """Test that FastAPI routes are reachable."""
    from fastapi.testclient import TestClient
    from src.server import app

    client = TestClient(app)

    # Status endpoint
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "idle"

    # History endpoint
    resp = client.get("/api/history")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

    # Stop when nothing running
    resp = client.post("/api/stop")
    assert resp.status_code == 404
