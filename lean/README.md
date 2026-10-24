# Lean agent settings

Measured context per turn on Claude Code, stacking each change (one-word reply, same
repository):

| Setting | Context per turn |
|---|---|
| Default | 47.0k tokens |
| `--tools` listing only the tools the task needs, plus `--disable-slash-commands`, `--exclude-dynamic-system-prompt-sections`, `--setting-sources project` | 17.5k |
| Instruction file slimmed (`lean-agents slim`) | 8.8k |
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

Measured on a four-change benchmark, two runs per change: $0.08 to $0.43 per change at
this setting against $1.80 to $3.57 for the default agent (one run each; two of the four
stopped at the 40-turn limit), every lean change passing its hidden test; questions at
$0.01 to $0.04 against about $0.31. Every run: `docs/results.md`.

## Interactive sessions

- Slim `CLAUDE.md` with `lean-agents slim`.
- Turn off connectors and plugins a project does not use: their tool definitions ride in
  every turn.
- Add the prefetch hook (`settings.json` here runs `lean-agents prefetch`) if the
  repository has a generated, verified map.
- Start a fresh session when the topic changes: everything in context is re-read by every
  later call; run `lean-agents carry-cost` to see the multiplier in your own sessions.
