"""A shell tool with a one-line definition, served over MCP, to stand in for Bash.

Claude Code's Bash tool definition is about 4.2k tokens, carried on every call of a
session. This serves one tool, `run`, that does the same job (run a command in the
repository and return its output) with a definition of about a hundred tokens. Standard
library only. Configure it in an MCP config file:

    {"mcpServers": {"lean": {"command": "lean-agents", "args": ["run-tool"]}}}

and allow it with `--allowedTools mcp__lean__run`. Commands run in the server's working
directory (or `--cwd`), through bash when it is installed, else the system shell.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path

from . import __version__

#: Output kept per call, in characters: the tail, where errors and test summaries are.
MAX_OUTPUT = 20_000
#: Seconds, as Claude Code's Bash tool: 2 minutes unless asked, at most 10.
DEFAULT_TIMEOUT = 120
MAX_TIMEOUT = 600
TOOL = {
    "name": "run",
    "description": "Run a shell command in the repository; returns exit code and output.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "timeout": {"type": "number", "description": "Seconds, default 120, max 600."},
        },
        "required": ["command"],
    },
}


class _Group:
    """Everything a command starts, so all of it can be ended together.

    On Windows a job object, which a process's children join however they were started
    (Git Bash's do not show up as a process tree); elsewhere a process group.
    """

    def __init__(self, process: subprocess.Popen) -> None:
        self.process = process
        self.job = None
        if os.name == "nt":
            import ctypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateJobObjectW.restype = ctypes.c_void_p
            kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            kernel32.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            job = kernel32.CreateJobObjectW(None, None)
            if job and kernel32.AssignProcessToJobObject(job, int(process._handle)):
                self.kernel32, self.job = kernel32, job

    def kill(self) -> None:
        if self.job:
            self.kernel32.TerminateJobObject(self.job, 1)
        elif os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"], check=False)
        else:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def close(self) -> None:
        if self.job:
            self.kernel32.CloseHandle(self.job)


def run_command(command: str, cwd: Path, timeout: float = DEFAULT_TIMEOUT) -> tuple[str, bool]:
    """(exit code and output, whether it failed).

    Returns within the timeout whatever the command does: output is read on its own
    thread, so a process that outlives the command and holds the pipe cannot block the
    call. Anything the command left running is ended when it returns.
    """
    timeout = max(1.0, min(float(timeout), MAX_TIMEOUT))
    shell = shutil.which("bash")
    process = subprocess.Popen(
        [shell, "-c", command] if shell else command,
        shell=shell is None,
        cwd=cwd,
        stdin=subprocess.DEVNULL,  # the server's stdin is the protocol; never share it
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=os.name != "nt",
    )
    group = _Group(process)
    chunks: list[str] = []
    reader = threading.Thread(target=lambda: chunks.extend(process.stdout), daemon=True)
    reader.start()
    try:
        process.wait(timeout=timeout)
        status = f"exit {process.returncode}"
        failed = process.returncode != 0
    except subprocess.TimeoutExpired:
        status, failed = f"killed after {timeout:g}s (timeout)", True
    group.kill()  # also ends anything a finished command left in the background
    group.close()
    reader.join(timeout=5)
    output = "".join(chunks)
    if len(output) > MAX_OUTPUT:
        output = f"[first {len(output) - MAX_OUTPUT} characters cut]\n" + output[-MAX_OUTPUT:]
    return f"{status}\n{output}", failed


def handle(message: dict, cwd: Path) -> dict | None:
    """The response to one JSON-RPC message, or None for a notification."""
    if "id" not in message:
        return None
    method, params = message.get("method"), message.get("params") or {}
    if method == "initialize":
        result = {
            "protocolVersion": params.get("protocolVersion", "2025-06-18"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "lean-agent-kit", "version": __version__},
        }
    elif method == "tools/list":
        result = {"tools": [TOOL]}
    elif method == "tools/call" and params.get("name") == "run":
        arguments = params.get("arguments") or {}
        text, failed = run_command(
            str(arguments.get("command", "")), cwd, arguments.get("timeout") or DEFAULT_TIMEOUT
        )
        result = {"content": [{"type": "text", "text": text}], "isError": failed}
    elif method == "ping":
        result = {}
    else:
        return {
            "jsonrpc": "2.0",
            "id": message["id"],
            "error": {"code": -32601, "message": f"unknown method {method}"},
        }
    return {"jsonrpc": "2.0", "id": message["id"], "result": result}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    lock = threading.Lock()

    def answer(message: dict) -> None:
        response = handle(message, args.cwd)
        if response is not None:
            with lock:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

    # Each request on its own thread: a long command never stops the server answering.
    threads = []
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        thread = threading.Thread(target=answer, args=(message,))
        thread.start()
        threads.append(thread)
    for thread in threads:  # every command has a timeout, so this ends
        thread.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
