from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from lean_agent_kit import run_tool

SRC = Path(__file__).resolve().parent.parent / "src"


def test_lists_one_small_tool() -> None:
    reply = run_tool.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, Path.cwd())
    (tool,) = reply["result"]["tools"]
    assert tool["name"] == "run"
    assert len(json.dumps(tool)) < 400  # the point: a definition far smaller than Bash's


def test_runs_a_command_in_its_directory(tmp_path) -> None:
    (tmp_path / "marker.txt").write_text("here", encoding="utf-8")
    call = {
        "name": "run",
        "arguments": {"command": "python -c \"print(open('marker.txt').read())\""},
    }
    reply = run_tool.handle({"id": 2, "method": "tools/call", "params": call}, tmp_path)
    assert reply["result"]["isError"] is False
    assert reply["result"]["content"][0]["text"] == "exit 0\nhere\n"


def test_reports_failure_and_cuts_long_output(tmp_path) -> None:
    command = "python -c \"import sys; print('x' * 30000); sys.exit(3)\""
    text, failed = run_tool.run_command(command, tmp_path)
    assert failed and text.startswith("exit 3\n[first ")
    assert len(text) < run_tool.MAX_OUTPUT + 100


def test_unknown_methods_and_notifications(tmp_path) -> None:
    assert run_tool.handle({"method": "notifications/initialized"}, tmp_path) is None
    reply = run_tool.handle({"id": 3, "method": "resources/list"}, tmp_path)
    assert reply["error"]["code"] == -32601


def test_speaks_mcp_over_stdio(tmp_path) -> None:
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "x"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    done = subprocess.run(
        [sys.executable, "-m", "lean_agent_kit.run_tool", "--cwd", str(tmp_path)],
        input="".join(json.dumps(m) + "\n" for m in messages),
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(SRC)},
        check=True,
    )
    replies = [json.loads(line) for line in done.stdout.splitlines()]
    assert [r["id"] for r in replies] == [1, 2]
    assert replies[0]["result"]["protocolVersion"] == "x"


def test_a_timeout_kills_the_command_and_everything_it_started(tmp_path) -> None:
    import time

    child = "import time; time.sleep(60)"
    command = (
        f'python -c "import subprocess, sys, time; '
        f"subprocess.Popen([sys.executable, '-c', '{child}']); time.sleep(60)\""
    )
    started = time.monotonic()
    text, failed = run_tool.run_command(command, tmp_path, timeout=2)
    assert failed and text.startswith("killed after 2s")
    assert time.monotonic() - started < 20  # it returned, rather than waiting on the grandchild


def test_commands_get_no_stdin(tmp_path) -> None:
    text, failed = run_tool.run_command(
        'python -c "import sys; print(repr(sys.stdin.read()))"', tmp_path, timeout=10
    )
    assert not failed and text == "exit 0\n''\n"


def test_a_timeout_returns_even_when_the_shell_started_the_straggler(tmp_path) -> None:
    """Git Bash on Windows: a backgrounded `sleep` is not in the shell's process tree."""
    import shutil
    import time

    import pytest

    if not shutil.which("bash"):
        pytest.skip("needs bash")
    started = time.monotonic()
    text, failed = run_tool.run_command("sleep 60 & sleep 60", tmp_path, timeout=2)
    assert failed and text.startswith("killed after 2s")
    assert time.monotonic() - started < 15


def test_a_finished_command_leaves_nothing_running(tmp_path) -> None:
    import shutil
    import time

    import pytest

    if not shutil.which("bash"):
        pytest.skip("needs bash")
    started = time.monotonic()
    text, failed = run_tool.run_command("(sleep 60 &) ; echo done", tmp_path, timeout=30)
    assert not failed and "done" in text
    assert time.monotonic() - started < 15  # did not wait for the background sleep
