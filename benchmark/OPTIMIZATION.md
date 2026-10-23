# Where an agent's tokens go, and the levers that cut them

A coding agent pays for the same context again on every turn. Cost per task is roughly

```
turns × (context per turn, mostly cache reads at 0.1×)
  + new context written to cache (2×)
  + output (5×, thinking included)
  × price per token of the model
```

so there are four independent levers: **context per turn, turns, output, and price**.
Each is measured below on Claude Code (CLI 2.1.258, Opus 5) against the options-scanner
repository.

## 1. Context per turn: the largest lever

Every turn re-reads the whole prompt prefix: system prompt, tool definitions, the
instruction file, injected session details. Measured on a one-word reply:

| Setup | Context per turn |
|---|---|
| Default Claude Code | 47.0k tokens |
| Only the task's tools defined (`--tools`), skills listing and dynamic prompt sections off | 17.5k |
| + instruction file cut from 26.8 KB to 2.6 KB, the rest moved to files read on demand | 8.8k |
| + three tools for read-only questions (no shell) | 7.5k |
| + a short custom system prompt in place of the default | 4.5k |

From 47k to 4.5k is a 90% cut on every turn of every session. On a 40-turn code change
that is the difference between ~1.9M and ~0.2M tokens read.

**Why it is large:** tool definitions and the default system prompt are written for every
possible task. A session that only reads code carries the full instructions for editing
notebooks, running subagents, browsing and scheduling, on every turn.

**Risk:** a custom system prompt drops the default's guidance on tool use and safety. It
is measured for accuracy on change tasks before it is trusted.

## 2. Turns

- **A wiring map** answers "what touches what" in one read instead of a search trail:
  wiring questions went from 7 turns to 5.5, with 56% fewer searches.
- **Parallel tool calls and stopping early,** asked for in the system prompt.
- **A brief with pointers** (untested): put the map rows relevant to a task into the
  prompt, so a question needs no exploration at all.

## 3. Output

Output is priced at five times input, and thinking counts as output. Code changes
produced 12-14k output tokens. Lower effort settings cut it; whether accuracy holds is
measured.

## 4. Price per token

Route by task: a lookup does not need the largest model. Smaller models for questions,
the large model for changes, with accuracy measured per kind.

## 5. Cache economics

A cache read costs a tenth of fresh input; a cache write costs about double. A prefix
that is identical across sessions is written once and read thereafter. Dynamic sections
(dates, git status, environment) break that, which is part of why excluding them pays.
For a swarm, every agent sharing one stable prefix (same system prompt, same tools,
same instruction file) turns N cache writes into one write and N-1 reads.

## For agent swarms

Every lever above multiplies by the number of agents, and swarms add their own:

- **Shared stable prefix** across agents, for cache reads instead of writes.
- **Least tools per role:** an explorer gets read tools, an editor gets edit tools.
- **Model per role:** small models explore and summarise; the large model edits.
- **Briefs and result schemas:** the coordinator passes facts (paths, line ranges,
  decisions), not files, and agents return structured results, not transcripts.
- **One map as common ground,** so N agents do not each rediscover the same wiring.

## Measured so far

See `results/` for the raw runs. Round 1 compares the map baseline (B) with the lean
harness (L), lean plus slim instructions (S), and S with a smaller model for questions
(R). Round 2 compares S with the tightest tools (T), a minimal system prompt (M), M with
the smallest model for questions (H), and M at low effort (E).
