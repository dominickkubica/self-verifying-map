# Findings: Making AI Coding Agents Cheaper Without Making Them Worse

| | |
|---|---|
| Status | Measurement in progress; numbers below are pilot-sized and marked as such |
| Owner | Dominick |
| Repository | github.com/dominickkubica/self-verifying-map |
| Model | Claude Opus 5 via Claude Code (CLI 2.1.258), on a 124-module Python and React codebase |

## Summary

An AI coding agent pays for its entire working context again on every turn of a task. Most
of that context is fixed overhead (the agent's built-in instructions, the definitions of
every tool it could use, and the project's instruction file), not the work itself. Two
kinds of change reduce cost: giving the agent a reliable map of the codebase so it takes
fewer turns, and shrinking the fixed context each turn carries. In pilot runs, the map
cuts wiring questions by about 20%, and trimming the fixed context cuts questions by about
two thirds and code changes by about a third. Stacking a tighter tool set, a short system
prompt, low reasoning effort and a mid-sized model reaches about 90% to 96% below the
default on questions and about 90% on the one code change with a measured baseline, with
every answer correct and every code change passing its hidden test. These are small
samples; a larger, pre-registered benchmark is set up to confirm or correct them.

## The cost model

Cost per task is approximately

```
turns × context per turn × 0.1   (re-reading cached context)
  + new context × 2              (writing it to the cache)
  + output × 5                   (the reply, including reasoning)
  × the model's price per token
```

which gives four independent levers: **context per turn, number of turns, output, and
model price**. The measurements below address each.

## What is built

| Component | Purpose |
|---|---|
| Self-verifying project map | Facts about the codebase's wiring generated from the code and checked on every commit; hand-written notes pinned to the facts they describe |
| Transcript analyzer | Reads the agent's local session logs and reports tokens, tool calls and searching per request |
| Benchmark runner | Runs fixed tasks as fresh agent sessions in isolated copies of the repository, alternating configurations, grading answers against frozen rubrics and code changes against hidden tests |
| Analysis | Accuracy per configuration, then per-task cost ratios with bootstrap intervals |

The benchmark's hypotheses, tasks, grading and pass criteria are published in the
repository before the full run.

## Finding 1: most of the cost is fixed context, not search

A question that needs no tools at all still carries 47,000 tokens of context per turn in
the default configuration. Measured by stacking changes on a one-word reply:

| Configuration | Context per turn |
|---|---|
| Default agent | 47.0k |
| Only the tools the task needs are defined; skills listing and per-session prompt sections off | 17.5k |
| Project instruction file cut from 26.8 KB to 2.6 KB, the rest moved to files read on demand | 8.8k |
| Three read-only tools for questions | 7.5k |
| A short custom system prompt in place of the default | 4.5k |

The default definitions cover every capability the agent has (notebooks, browsing,
subagents, scheduling) whether or not a task uses them, and the full instruction file is
loaded for every task even when a task needs one section of it.

## Finding 2: the map reduces turns on wiring questions

Pilot benchmark: 4 tasks, 2 configurations, 2 repetitions, 16 runs, all correct.

| Task type | Cost with map vs without | Tool calls | Searches |
|---|---|---|---|
| Wiring questions | −20% | −28% | −56% |
| Control question (map should not help) | no difference | no difference | no difference |
| Code change | +4% | +11% | +26% |

The control behaving as expected supports the wiring saving coming from the map. On the
code change the map costs slightly more, consistent with the agent spending turns keeping
the map current; whether harder changes recover that cost is part of the full benchmark.

## Finding 3: trimming fixed context saves more than the map

Optimizer round 1 (22 runs, every answer correct), median cost against the map
configuration:

| Configuration | Wiring questions | Control question | Code change |
|---|---|---|---|
| Lean harness (only needed tools; listing and dynamic sections off) | −26% | −36% | −15% |
| + slim instruction file | −65% | −70% | −32% |
| + a smaller model (Sonnet) for questions | −78% | −88% | −38% |

Ten further runs stopped at the account's session limit before the agent answered; they
are excluded and published separately, and the runner now halts on a limit instead of
recording it.

## Finding 4: stacking levers reaches about 90%

Iterations at one run per task (32 runs, every answer correct, every code change passing
its hidden test), stacking a tighter tool set, a short custom system prompt and a low
reasoning-effort setting on the slim configuration:

| Configuration | Cost per question | Cost per code change |
|---|---|---|
| Map configuration (default agent) | about $0.31 | $1.80 to $2.20 |
| Slim, tight tools, minimal prompt, low effort (Opus) | $0.05 to $0.12 | $0.47 |
| The same on Sonnet | **$0.01 to $0.04** | **$0.09 to $0.43** across four changes |

Questions on Sonnet at low effort answer in one to three tool calls. Haiku is cheapest
when it goes straight to the answer but wanders on some questions (45 tool calls on one),
so it is not recommended. Only one of the four code changes has a measured default-agent
baseline so far; the others are compared in the full benchmark.

## Implications for agent swarms

Each lever multiplies by the number of agents, and swarms add their own:

- **One stable shared prefix** (same system prompt, tools and instruction file) so the
  provider's prompt cache is written once and read by every agent, at a tenth of the cost.
- **Least tools per role:** explorers get read tools, editors get edit tools.
- **Model per role:** small models explore and summarise; the large model edits.
- **Briefs and structured results:** the coordinator passes facts such as paths, line
  ranges and decisions rather than whole files, and agents return results rather than
  transcripts.
- **One map as common ground,** so agents do not each rediscover the same wiring.

## Method and safeguards

- Fresh session per run, in an isolated git worktree at a fixed commit, reset between runs.
- Configurations interleaved in a seeded order, so prompt caching favours neither.
- Answers frozen from the code by script; code changes graded by tests the agent never sees.
- Accuracy is a guard: a configuration's saving counts only if accuracy holds.
- Every run is kept; a run that hits the turn limit counts as wrong, at full cost.
- Raw run data is published alongside the results.

## Limits

- Pilot sizes: two to four tasks per round and one or two repetitions per configuration.
  Intervals are not yet meaningful.
- One codebase and one model family.
- A custom system prompt removes the default's guidance; its effect on accuracy is measured
  before it is recommended.

## Next steps

1. Measure default-agent baselines for the remaining code changes, and repeat the best configuration to check its variance.
2. Run the full benchmark (20 tasks, 5 repetitions) on the best configuration against the
   default.
3. Test pre-loaded briefs, where the relevant map rows go into the prompt so a question
   needs little or no exploration.
4. Repeat on a second repository, and on a multi-agent setup.
