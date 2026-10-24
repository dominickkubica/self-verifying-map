"""The `lean-agents` command: one entry point for each tool in the kit.

lean-agents carry-cost [...]   # what costs tokens in your transcripts, per source
lean-agents stats [...]        # per-request tokens, tool calls and re-reads
lean-agents slim CLAUDE.md     # split an instruction file into a core and sections
lean-agents prefetch           # the UserPromptSubmit hook (reads the prompt on stdin)
lean-agents map check          # the self-verifying map: generate, check, stamp
"""

from __future__ import annotations

import sys

from . import __version__

COMMANDS = {
    "carry-cost": (
        "carry_cost",
        "Rank what costs tokens in your transcripts, weighted by re-reads",
    ),
    "stats": ("transcript_stats", "Per-request tokens, tool calls, searches and re-reads"),
    "slim": ("slim_claude_md", "Split CLAUDE.md into a small core and sections read on demand"),
    "prefetch": ("map_prefetch", "UserPromptSubmit hook: inject map facts the prompt names"),
    "map": ("repomap.cli", "Generate the wiring map, check it against the code, stamp notes"),
}


def usage() -> str:
    width = max(map(len, COMMANDS))
    lines = [f"  {name:<{width}}  {summary}" for name, (_, summary) in COMMANDS.items()]
    return "usage: lean-agents <command> [args]\n\ncommands:\n" + "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] in ("-h", "--help"):
        print(usage(), end="")
        return 0
    if args[0] == "--version":
        print(f"lean-agent-kit {__version__}")
        return 0
    if args[0] not in COMMANDS:
        print(f"lean-agents: unknown command {args[0]!r}\n\n{usage()}", end="", file=sys.stderr)
        return 2
    module_name, _ = COMMANDS[args[0]]
    module = __import__(f"{__package__}.{module_name}", fromlist=["main"])
    sys.argv[0] = f"lean-agents {args[0]}"  # argparse takes the program name from here
    return module.main(args[1:])


if __name__ == "__main__":
    raise SystemExit(main())
