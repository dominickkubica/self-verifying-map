# Measuring what the map saves

`lean-agents stats` reads Claude Code's local session transcripts
(`~/.claude/projects/*/*.jsonl`) and reports per-request cost and navigation effort:
weighted tokens, context per call, API and tool calls, searches, reads, searches and
reads before the first edit, and re-reads. With `--split` it compares requests before
and after a date; `--match` keeps only requests that touched a path; `--edits-only`
keeps only requests that changed code. It outputs numbers only, never message content.

Neither `lean-agents stats` nor `lean-agents carry-cost` prints or writes message
content. `stats` outputs numbers (its CSV adds the session file and project folder
names); `carry-cost` labels each source by tool name, attachment type or the program a
shell command runs, and a label that does not look like a name prints as `?`.
`tests/test_privacy.py` runs both with every option over a transcript whose every
message carries a marker, and fails if the marker appears in any output.

```
lean-agents stats --split 2026-10-22T15:26:55Z --match options-scanner --edits-only
```

A before/after split on real work mixes the change with the task mix. A controlled
benchmark (fixed tasks, repeated runs, map on and off) is the next step.
