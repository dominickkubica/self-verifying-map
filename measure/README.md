# Measuring what the map saves

`transcript_stats.py` reads Claude Code's local session transcripts
(`~/.claude/projects/*/*.jsonl`) and reports per-request cost and navigation effort:
weighted tokens, context per call, API and tool calls, searches, reads, searches and
reads before the first edit, and re-reads. With `--split` it compares requests before
and after a date; `--match` keeps only requests that touched a path; `--edits-only`
keeps only requests that changed code. It outputs numbers only, never message content.

```
python measure/transcript_stats.py --split 2026-10-22T15:26:55Z --match options-scanner --edits-only
```

A before/after split on real work mixes the change with the task mix. A controlled
benchmark (fixed tasks, repeated runs, map on and off) is the next step.
