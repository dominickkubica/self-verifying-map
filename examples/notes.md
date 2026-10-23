# Notes: what the code cannot say about itself

One entry per item, keyed the way `map/generated/` names it. Every table and every
scheduled job has one; anything else gets one only when its purpose or a trap is not
obvious from the generated facts.

Each entry is pinned. `fact:` is a hash of the item's generated facts, so when its
writers, readers, calls or schedule change, `tests/test_map.py` fails until someone
re-reads the note and runs `optscan map stamp <key>`. A trap is pinned to the test that
guards it (`test: <file>::<name>`), or to `test: none` when no test can.

Present tense only. Why something came to be lives in `DECISIONS.md`.

(A sample of the entries.)

### table:opportunity_log
fact: 38b3bcf340cc
Every candidate the screen scored, as scored, for the validation study. Cannot be
re-logged after the fact, which is why the backup job exists.

### table:daily_condition
fact: 65799ccff487
Per-symbol daily gamma regime and indicators, recorded forward by `optscan conditions`.
No vendor sells historical per-strike open interest, so this record is the only gamma
history there will ever be. Written by the `conditions` job once the user installs it.

### job:snapshot
fact: b9ea98179c67
Captures the watchlist's chains. The IV history has exactly one writer, this job, and a
missed day is permanent.

### job:conditions
fact: a0939e1837bf
Records the forward gamma history into `daily_condition` at 16:25. Off by default
(chain fetches against a vendor that throttles silently); installed with
`optscan schedule --install conditions`, which the user runs themselves.

### route:/gaps
fact: 27c4f34889f9
Served, but no dashboard file calls it; reachable from the API only.

### trap:iv-history-source
test: tests/test_traps.py::test_iv_history_is_never_read_through_the_price_source
A symbol's IV history comes from `jobs/backtest.load_implied`. `preferred_source` names
the price source, which is Alpaca for most symbols, and Alpaca has no IV30.

### trap:scorer-without-iv-history
test: tests/test_traps.py::test_every_scorer_call_states_its_iv_history
`screener/context.analyze_snapshot` without `iv_history` scores with no IV rank and
says nothing. Every caller passes it, or passes `iv_history=None` deliberately.

### trap:study-symbol-loss
test: tests/test_traps.py::test_a_study_refuses_to_run_on_a_fraction_of_its_symbols
A study that silently loses most of its symbols produces a table that looks like any
other. `scripts/studies/harness.py` raises when more than half are lost.

### trap:two-servers-one-port
test: none
One server on 127.0.0.1 and another on 0.0.0.0 can share port 8000, and localhost then
reaches the old build. Check with `Get-NetTCPConnection -LocalPort 8000`.
