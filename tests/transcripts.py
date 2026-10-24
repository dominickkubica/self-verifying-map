"""Build synthetic Claude Code transcripts (JSONL) for tests.

Never use real transcripts as fixtures: they hold private prompts, code and answers.
Every message text here contains `SECRET`, so a test can assert no output repeats it.
"""

from __future__ import annotations

import json
from pathlib import Path

SECRET = "SECRET-7f3a"


class Transcript:
    """Append entries in the shape Claude Code logs them, then `write` to a folder."""

    def __init__(self) -> None:
        self.entries: list[dict] = []
        self._ids = 0

    def _next(self, prefix: str) -> str:
        self._ids += 1
        return f"{prefix}{self._ids}"

    def prompt(self, text: str, at: str = "2026-10-01T10:00:00Z") -> Transcript:
        self.entries.append(
            {"type": "user", "timestamp": at, "message": {"role": "user", "content": text}}
        )
        return self

    def injected(self, text: str) -> Transcript:
        """Content in a user turn that the person did not type (a reminder, a hook)."""
        self.entries.append(
            {"type": "user", "isMeta": True, "message": {"role": "user", "content": text}}
        )
        return self

    def call(
        self,
        *,
        text: str | None = None,
        tools: list[tuple[str, dict, str]] = (),
        usage: dict | None = None,
        split_lines: bool = False,
    ) -> Transcript:
        """One API call: optional text, then tool uses, each with its result.

        `tools` is [(name, input, result text)]. With `split_lines`, each content block
        is logged as its own line carrying the same message id and usage, as Claude Code
        does; the call must still count once.
        """
        message_id = self._next("msg_")
        usage = usage or {
            "input_tokens": 10,
            "cache_creation_input_tokens": 100,
            "cache_read_input_tokens": 1000,
            "output_tokens": 20,
        }
        blocks: list[dict] = []
        if text is not None:
            blocks.append({"type": "text", "text": text})
        uses = []
        for name, tool_input, result in tools:
            use_id = self._next("toolu_")
            blocks.append({"type": "tool_use", "id": use_id, "name": name, "input": tool_input})
            uses.append((use_id, result))
        groups = [[b] for b in blocks] if split_lines else [blocks]
        for group in groups:
            self.entries.append(
                {
                    "type": "assistant",
                    "message": {
                        "id": message_id,
                        "role": "assistant",
                        "usage": usage,
                        "content": group,
                    },
                }
            )
        for use_id, result in uses:
            self.entries.append(
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": [
                            {"type": "tool_result", "tool_use_id": use_id, "content": result}
                        ],
                    },
                }
            )
        return self

    def attachment(self, kind: str, payload: str) -> Transcript:
        self.entries.append(
            {"type": "attachment", "attachment": {"type": kind, "content": payload}}
        )
        return self

    def compact(self, summary: str) -> Transcript:
        self.entries.append(
            {
                "type": "user",
                "isCompactSummary": True,
                "message": {"role": "user", "content": summary},
            }
        )
        return self

    def write(self, folder: Path, session: str = "session-1") -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{session}.jsonl"
        lines = [json.dumps(entry) for entry in self.entries]
        path.write_text(
            "\n".join(lines) + "\nnot json, as a truncated last line can be\n", encoding="utf-8"
        )
        return path
