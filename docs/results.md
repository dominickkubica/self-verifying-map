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
| A2, C2, P2 | Sonnet, low effort | Default Claude Code harness (tools, system prompt, full instruction file); only the mapping tool differs: none (A2), CodeGraph (C2), the map with its prefetch hook (P2) |
| A3, C3, P3 | Opus, default effort | The same three on Opus |

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

## Three-way: no map, CodeGraph, the map

Same model, effort and harness in each comparison, so only the mapping tool differs:
none, [CodeGraph](https://github.com/colbymchenry/codegraph) 1.6.4 set up the way its own
installer sets it up for Claude Code (its MCP server, its `CLAUDE.md` block, its permission
rule and its prompt hook, on a built index), or the map with its prefetch hook on the full
instruction file. All 20 tasks, one run each, on Claude Code 2.1.332 on Linux. Runs were
parallel (`--workers`), so they share the provider's prompt cache: compare arms within a
table, not with the sequential tables above. The code-change prompt here asks for only the
tests that cover the change, and `python` is the repository's interpreter in every arm.

`three-way-sonnet-2026-11-26.jsonl`: 60 runs, Sonnet at low effort.

| | A2: no map | C2: CodeGraph | P2: the map |
|---|---|---|---|
| Correct | 19 of 20 (missed t13) | 19 of 20 (missed t12) | 19 of 20 (missed t13) |
| Total cost | $2.19 | $2.45 | $2.05 |
| Wiring questions, median cost ratio to A2 (95% interval over tasks) | 1 | 1.11 [0.94, 1.23] | 0.89 [0.64, 1.10] |
| Code changes, median cost ratio to A2 | 1 | 1.04 [0.96, 1.08] | 1.02 [0.97, 1.12] |

`three-way-opus-2026-11-26.jsonl`: 60 runs, Opus at its default effort.

| | A3: no map | C3: CodeGraph | P3: the map |
|---|---|---|---|
| Correct | 20 of 20 | 19 of 20 (missed t12) | 20 of 20 |
| Total cost | $5.71 | $6.23 | $5.59 |
| Wiring questions, median cost ratio to A3 (95% interval over tasks) | 1 | 1.06 [1.00, 1.12] | 0.80 [0.68, 0.95] |
| Code changes, median cost ratio to A3 | 1 | 1.19 [0.80, 1.41] | 1.06 [0.68, 1.45] |

With one run per task the intervals are rough (they resample 20 tasks, not repetitions).
On the same model the map lowers the cost of wiring questions (on Opus by a fifth, the one
interval here that excludes no change) and changes little else; CodeGraph costs a little more
in both. The large savings of the lean setup come from its harness and model, not the map.
`three-way-mixed-models-stopped-2026-11-26.jsonl` is a first attempt (17 runs) that compared
default and CodeGraph on Opus against P on Sonnet, stopped because the arms differed in
model; it is kept for the record and supports no comparison.

## The map plus codefactory's change prefetch

P4 (Sonnet, low effort) and P5 (Opus) are P2 and P3 plus a second prompt hook,
[codefactory](https://github.com/dominickkubica/codefactory)'s `prefetch --hook`. For each
function, command, route or module the prompt names, it adds the definition's file and
line range, its callers and calls, the tests that exercise it, where the name appears as a
string in code (an argparse command, a registry key) and the docs that mention it. It
answers from an index built at setup, in about 0.2 seconds. The instruction file is P2's,
so only the hook differs. The setup, the parallel runs and the prompts are those of the
three-way table above. Results are in `codefactory-prefetch-2026-11-26.jsonl`.

| | P2: the map | P4: plus prefetch | P3: the map | P5: plus prefetch |
|---|---|---|---|---|
| Model | Sonnet, low | Sonnet, low | Opus | Opus |
| All 20 tasks, one run each: correct | 19 of 20 | 20 of 20 | 20 of 20 | 20 of 20 |
| All 20 tasks, one run each: total cost | $2.05 | $1.97 | $5.59 | $4.98 |
| Code changes, runs | 4 | 4 | 12 | 12 |
| Code changes, total cost | $0.70 | $0.67 | $7.35 | $6.40 |
| Code changes, median cost ratio to the map (95% interval over tasks) | 1 | 0.93 [0.76, 1.20] | 1 | 0.88 [0.68, 1.04] |
| Code changes, median turns ratio | 1 | 0.89 [0.70, 1.67] | 1 | 0.84 [0.66, 1.54] |

The Opus code-change rows are three runs of each of the four change tasks per arm; every
other cell is one run per task. On questions P4's cost ratio to P2 is 1.00 [0.85, 1.02] for
wiring, 0.89 [0.81, 0.97] for control and 0.92 [0.90, 1.26] for traps.

The prefetch lowers the cost of code changes by about a tenth on both models, but every
interval includes no change. The agents use what it supplies: their first calls read the
exact line ranges it gives, rather than searching. Most of a change's turns come after
that, in editing, writing tests and updating docs, which locating code doesn't shorten.
Within a task, turns still vary a lot between runs (P3 on c16: 23 to 38).

## Bug fixes: the map against the map plus codefactory

Five fix tasks (f21 to f25), each a one-line bug planted in options-scanner and described
only by its symptom: a dropped `status=None` default one file away from the symptom, a
case-sensitive symbol filter, a cache the Refresh route no longer clears, a CLI command
wired to the wrong handler, and an off-by-one in a win rate. The repository's own tests
miss all five; a hidden test grades each. The bug is folded into the tree's commit, so
`git status` and `git diff` show nothing (`git show HEAD` would). The map and codefactory's
index are rebuilt from the buggy code, as a real repository's would be. P3 against P5 on
Opus, three runs per task, in `fix-tasks-2026-11-26.jsonl`.

| | P3: the map | P5: plus codefactory |
|---|---|---|
| Correct | 15 of 15 | 14 of 15 |
| Total cost | $6.74 | $6.95 |
| Median cost ratio to P3 (95% interval over tasks) | 1 | 1.01 [0.95, 1.25] |
| Median turns ratio | 1 | 0.90 [0.72, 1.25] |
| Median searches ratio | 1 | 0.73 [0.55, 1.21] |

The one miss judged a win by realized dollars rather than return. That is a valid fix, but
the hidden test's fake trades had a 50% return with $0 realized. The hidden test now gives
consistent figures; the run is reported as it was graded. On the wired-to-the-wrong-handler
bug, codefactory's prefetch names the cause outright (the handler is never called, and the
dispatch line points elsewhere), yet P5 took 8 to 13 turns against P3's 9 to 11: the map alone led there just as fast.
With the map alone the agent already finds every bug, so there is no accuracy left to gain
on these tasks. codefactory cuts searching by about a quarter, but not cost. One of P5's 15
runs used a later prefetch (the hook was edited during the run); the other 14 used the
version described above.

## A large codebase: Django

Django at `baa7a80` has 2,943 Python files and 1.15 million lines, about ten times
options-scanner. It has no map plugin, so the map trees get the generic map, which for Django
is a list of modules with their purposes. The facts about what a prompt names come from
codefactory's prefetch. Every tree shares the same short instruction file. The tasks are in
`tasks-django.json`: 10 wiring questions, 2 controls, 2 changes and 2 fixes with planted
bugs, all with hidden tests that were checked to fail and pass as they should. Sonnet at
low effort, one run per task, parallel runs. Results are in `django-four-way-2026-11-26.jsonl`;
the rerun after two fixes is in `django-rerun-2026-11-26.jsonl`.

| | A2: default | C2: CodeGraph | P4: map + codefactory | L4: lean | L5: lean, complete lists |
|---|---|---|---|---|---|
| Correct | 16 of 16 | 15 of 16 | 16 of 16 (rerun: 14) | 14 of 16 | 16 of 16 |
| Total cost | $1.55 | $2.06 | $1.62 (rerun: $1.58) | $0.60 | $0.51 |
| Wiring, median cost ratio to A2 (95% interval over tasks) | 1 | 1.28 [1.13, 1.44] | 1.02 [0.91, 1.06] | 0.23 [0.20, 0.30] | 0.24 [0.18, 0.34] |
| Changes (2 tasks) | 1 | 1.27 [1.14, 1.39] | 1.23 [1.04, 1.42] | 0.70 [0.45, 0.96] | 0.52 [0.47, 0.57] |
| Fixes (2 tasks) | 1 | 1.36 [1.21, 1.50] | 1.02 [1.01, 1.04] | 0.41 [0.38, 0.44] | 0.33 [0.31, 0.35] |

L4 is P4 in the lean harness. Both its misses left one item out of a "which" list. L5 adds one
sentence to its system prompt: "When asked which or what things do something, find every one
before answering." The P4 rerun matches only identifiers and backticked words, not plain
English. In the first run, "parallel" and "configured" from the prompt's test-command
instructions pulled unrelated functions into the context. The rerun's ratios to A2 are 0.94
[0.86, 1.04] for wiring, 1.18 [1.17, 1.20] for changes and 1.05 [0.85, 1.25] for fixes. Its
two misses are the same list questions L4 missed (w02, w06).

On the large codebase the harness is what pays. The lean setup costs a quarter of the
default on questions and a third to a half on changes and fixes. With the completeness
sentence it loses no accuracy. In the default harness, neither CodeGraph nor codefactory's
prefetch lowers cost: CodeGraph adds about a quarter, and the prefetch is level on questions
and fixes and above on the two changes. Two changes and two fixes are too few to say more
about those kinds.

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
