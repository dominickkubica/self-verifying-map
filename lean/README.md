# Lean agent settings

Measured context per turn on Claude Code, stacking each change (one-word reply, same
repository):

| Setting | Context per turn |
|---|---|
| Default | 47.0k tokens |
| `--tools` listing only the tools the task needs, plus `--disable-slash-commands`, `--exclude-dynamic-system-prompt-sections`, `--setting-sources project` | 17.5k |
| Instruction file slimmed (`tools/slim_claude_md.py`) | 8.8k |
| Read-only questions: `--tools Read Grep Glob` | 7.5k |
| `--system-prompt` with a short prompt (below) | 4.5k |

## Headless agents (`claude -p`)

Questions:

```
claude -p --output-format json --model sonnet --effort low \
  --tools Read Grep Glob --allowedTools Read Grep Glob \
  --disable-slash-commands --exclude-dynamic-system-prompt-sections \
  --setting-sources project --system-prompt "$(cat lean/system-prompt.txt)"
```

Code changes: the same with `--tools Read Grep Glob Edit Bash` (and matching
`--allowedTools`). Pass the prompt on stdin: on Windows `claude` is a `.cmd` wrapper and a
newline inside an argument silently drops every flag after it.

Measured on a four-change benchmark: $0.09 to $0.43 per change at this setting against
$2.05 to $3.57 for the default agent, every change passing its hidden tests; questions at
$0.01 to $0.04 against about $0.31.

## Interactive sessions

- Slim `CLAUDE.md` with `tools/slim_claude_md.py`.
- Turn off connectors and plugins a project does not use: their tool definitions ride in
  every turn.
- Add the prefetch hook (`settings.json` here, `benchmark/hooks/map_prefetch.py`) if the
  repository has a generated, verified map.
- Start a fresh session when the topic changes: everything in context is re-read by every
  later call; run `measure/carry_cost.py` to see the multiplier in your own sessions.
