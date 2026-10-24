# Results

Every benchmark number in this repository, run by run, with its sample size and the file it
comes from in `benchmark/results/`. Costs are the dollar cost Claude Code reported for each
session. All runs are on [options-scanner](https://github.com/dominickkubica/options-scanner)
at commit `90fe543` with Claude Code 2.1.258.

**Sample sizes are small.** Most cells are one or two runs. A cost that differs by a few
cents between two setups is within run-to-run noise; read the large gaps, not the small
ones. Intervals are not meaningful at these sizes. The pre-registered benchmark
(`benchmark/DESIGN.md`: 20 tasks, 5 repetitions) has not been run yet.

**†** marks a run that ended at the 40-turn limit. The hidden tests still passed on the
code it left, so the runner graded it correct, but the agent never finished.
`benchmark/DESIGN.md` counts a run that hits the turn limit as wrong, so under the
pre-registered rule these are failures, and their cost is a floor: the agent was stopped
before it was done. Every † run is a default-configuration run (A or B); no lean run hit
the limit.

Reproduce any ratio below with `python benchmark/analyze.py <file> --base <arm>`.

## Setups

| Arm | Model | Setup |
|---|---|---|
| A | Opus | Default Claude Code, repository with the map removed |
| B | Opus | Default Claude Code, repository with its map (the baseline for everything after the pilot) |
| L | Opus | Lean harness: only the task's tools defined, skills listing and dynamic prompt sections off |
| S | Opus | L with the instruction file slimmed from 26.8 KB to 2.6 KB |
| R | Sonnet for questions, Opus for changes | S with a smaller model for questions |
| T | Opus | S with the tightest tool set per task kind |
| M | Opus | T with a short custom system prompt in place of Claude Code's |
| H | Haiku for questions | M with the smallest model for questions |
| E | Opus | M at low reasoning effort |
| EH | Haiku for questions | E with the smallest model for questions |
| ES | Sonnet for questions | E with Sonnet for questions |
| ESC | Sonnet | E with Sonnet for everything, code changes included: **the lean setup** |
| G | Sonnet | ESC with an instruction to search the map before the code |
| P | Sonnet | ESC with the prefetch hook (`lean-agents prefetch`) |

Task ids are those in `benchmark/DESIGN.md`: `w` wiring questions, `t` trap questions, `k`
a control question the map should not help with, `c` code changes graded by hidden tests.

## Default agent against the lean setup

Default is arm B; lean is ES for questions and ESC for code changes (the same setup:
Sonnet, low effort, tight tools, short system prompt, slim instruction file). Every lean
run is correct.

| Task | Default (runs) | Lean (runs) | Saving per lean run |
|---|---|---|---|
| w01 wiring question | $0.27 (1) | $0.01, $0.02 (2) | 95%, 92% |
| w07 wiring question | $0.35 (1) | $0.03, $0.03 (2) | 92%, 92% |
| k18 control question | $0.28, $0.34 (2) | $0.02, $0.02 (2) | 93%, 92% |
| t11 trap question | not run | $0.04, $0.03 (2) | - |
| c14 add a CLI option | $1.80 (1) | $0.21, $0.31 (2) | 88%, 83% |
| c15 add an API parameter | $2.66† (1) | $0.19, $0.23 (2) | 93%, 91% |
| c16 add a scheduled job | $3.57† (1) | $0.43, $0.30 (2) | 88%, 91% |
| c17 change CLI output | $2.05 (1) | $0.09, $0.08 (2) | 96%, 96% |

Savings are against the default run, or the median of the two default runs for k18.
Sources: `optimizer-round1.jsonl` (B, questions and c14), `baselines-changes.jsonl` (B,
c15 to c17), `iterations-2026-10-23.jsonl` and `repeats-es-esc.jsonl` (lean).

## Pilot: the map against no map

`pilot-2026-10-23.jsonl`: 16 runs, 4 tasks, 2 arms, 2 repetitions each. All correct.

| task | kind | A (no map) | B (map) |
|---|---|---|---|
| w01 | wiring | $0.38, $0.38 | $0.27, $0.36 |
| w07 | wiring | $0.40, $0.44 | $0.35, $0.31 |
| k18 | control | $0.34, $0.32 | $0.34, $0.34 |
| c14 | change | $2.13†, $2.08† | $2.21†, $2.18† |

Median ratio, map over no map:

| Kind | Cost | Tool calls | Searches |
|---|---|---|---|
| Wiring (2 tasks) | 0.80 | 0.72 | 0.44 |
| Control (1 task) | 1.04 | 1.00 | 1.00 |
| Change (1 task) | 1.04 | 1.11 | 1.26 |

All four change runs hit the turn limit, so the change row compares two unfinished runs.

## Round 1: trimming fixed context

`optimizer-round1.jsonl`: 22 runs, 4 tasks, 1 or 2 runs per cell. All correct. Ten more
runs stopped at the account's session limit before the agent answered; they are in
`optimizer-round1-excluded-limit-errors.jsonl` and not counted, and the runner now halts on
a session limit instead of recording it.

| task | kind | B | L | S | R |
|---|---|---|---|---|---|
| w01 | wiring | $0.27 | $0.26, $0.18 | $0.08, $0.10 | $0.04 |
| w07 | wiring | $0.35 | $0.23 | $0.13 | $0.11 |
| k18 | control | $0.28, $0.34 | $0.20, $0.19 | $0.09, $0.09 | $0.04, $0.04 |
| c14 | change | $1.80 | $1.54 | $1.22 | $1.12 |

Median cost ratio against B:

| Arm | Wiring (2 tasks) | Control (1 task) | Change (1 task) |
|---|---|---|---|
| L | 0.74 | 0.64 | 0.85 |
| S | 0.35 | 0.30 | 0.68 |
| R | 0.22 | 0.12 | 0.62 |

## Round 2: tools, system prompt, effort and model

`iterations-2026-10-23.jsonl`: 32 runs, one or two per cell, and
`repeats-es-esc.jsonl`: 8 runs, a second run of every ES and ESC cell. All correct, and
every code change passed its hidden test.

| task | kind | T | M | H | E | EH | ES | ESC |
|---|---|---|---|---|---|---|---|---|
| w01 | wiring | $0.11 | $0.10 | $0.02 | $0.07, $0.04 | $0.02 | $0.01, $0.02 | - |
| w07 | wiring | $0.14 | $0.11 | $0.12 | $0.08, $0.09 | $0.30 | $0.03, $0.03 | - |
| t11 | trap | - | - | - | $0.12 | $0.03 | $0.04, $0.03 | - |
| k18 | control | $0.10 | $0.08 | $0.02 | $0.08, $0.08 | $0.02 | $0.02, $0.02 | - |
| c14 | change | - | - | - | $0.47 | - | - | $0.21, $0.31 |
| c15 | change | - | - | - | - | - | - | $0.19, $0.23 |
| c16 | change | - | - | - | - | - | - | $0.43, $0.30 |
| c17 | change | - | - | - | - | - | - | $0.09, $0.08 |

Haiku (H, EH) is cheapest when it goes straight to the answer, but on w07 it made 24 tool
calls under H and 45 under EH, so it is not recommended.

## Prefetch

`prefetch-iteration.jsonl`: 21 runs, 7 questions, 3 arms, one run each.

| task | kind | ESC | G | P |
|---|---|---|---|---|
| w01 | wiring | $0.02 | $0.02 | $0.01 |
| w02 | wiring | $0.01 | $0.01 | $0.01 |
| w05 | wiring | $0.03 | $0.02 | $0.01 |
| w07 | wiring | $0.03 | $0.03 | $0.05 |
| w09 | wiring | $0.02 | $0.02 | $0.01 |
| t11 | trap | $0.04 | $0.04 | $0.06 |
| t12 | trap | $0.02 (wrong) | $0.02 | $0.01 |

| | ESC | G | P |
|---|---|---|---|
| Median cost per question | $0.021 | $0.021 | $0.011 |
| Answered with no tool calls | 0 of 7 | 0 of 7 | 5 of 7 |
| Correct | 6 of 7 | 7 of 7 | 7 of 7 |

On w07 and t11 the agent under P still searched, and cost more than under ESC.

## Measurements outside the benchmark

These come from the kit's own tools rather than from benchmark runs, so `benchmark/results/`
does not hold them.

- **Context per turn** (47.0k tokens for default Claude Code down to 4.5k for the lean
  setup; `docs/findings.md`, Finding 1). Measured from the usage Claude Code reported for a
  one-word reply under each setup. Those sessions are not published.
- **Where tokens go in long sessions** (98% re-reads, 32% from the agent's own tool inputs;
  Finding 6). Measured with `lean-agents carry-cost` on 14 of the owner's development
  sessions. The transcripts are private and not published; run the same command on your
  own.
