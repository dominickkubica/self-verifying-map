"""Summarise a benchmark run: accuracy, cost and effort per arm, and ratios to a base arm.

    python benchmark/analyze.py bench-out/runs.jsonl            # base arm A if present
    python benchmark/analyze.py bench-opt/runs.jsonl --base B   # optimizer arms against B

Per task, each metric is the median over repetitions; the ratio is arm over base. Across
tasks of a kind, the median ratio with a 95% bootstrap interval that resamples tasks. A
ratio below 1 means the arm spent less than the base.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

DRAWS = 2000
SEED = 20261023
WEIGHTS = {
    "input_tokens": 1.0,
    "cache_read_input_tokens": 0.1,
    "cache_creation_input_tokens": 2.0,
    "output_tokens": 5.0,
}
METRICS = ("cost_usd", "weighted_tokens", "num_turns", "tool_calls", "searches")


def weighted(usage: dict | None) -> float | None:
    if not usage:
        return None
    return sum(weight * (usage.get(key) or 0) for key, weight in WEIGHTS.items())


def metric(row: dict, name: str) -> float | None:
    if name == "weighted_tokens":
        return weighted(row.get("usage"))
    value = row.get(name)
    return float(value) if isinstance(value, int | float) else None


def median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def bootstrap(ratios: list[float]) -> tuple[float, float] | None:
    if len(ratios) < 2:
        return None
    rng = random.Random(SEED)
    draws = sorted(statistics.median(rng.choices(ratios, k=len(ratios))) for _ in range(DRAWS))
    return draws[int(0.025 * DRAWS)], draws[int(0.975 * DRAWS) - 1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("runs", type=Path)
    parser.add_argument("--base", default=None)
    args = parser.parse_args(argv)

    rows = [json.loads(line) for line in args.runs.read_text(encoding="utf-8").splitlines()]
    arms = sorted({r["arm"] for r in rows})
    base = args.base or ("A" if "A" in arms else arms[0])
    kinds = {r["task"]: r["kind"] for r in rows}
    by = defaultdict(list)
    for row in rows:
        by[(row["task"], row["arm"])].append(row)

    print(f"{len(rows)} runs, {len(kinds)} tasks, arms {', '.join(arms)}, base {base}\n")
    head = ("arm", "kind", "runs", "correct", "median $", "turns", "tools")
    print("{:4} {:8} {:>5} {:>8} {:>9} {:>6} {:>6}".format(*head))
    for arm in arms:
        for kind in sorted(set(kinds.values())):
            chosen = [r for r in rows if r["arm"] == arm and r["kind"] == kind]
            if not chosen:
                continue
            correct = sum(r["grade"] == "correct" for r in chosen) / len(chosen)
            cost = median(metric(r, "cost_usd") for r in chosen)
            turns = median(metric(r, "num_turns") for r in chosen)
            tools = median(metric(r, "tool_calls") for r in chosen)
            print(
                f"{arm:4} {kind:8} {len(chosen):>5} {correct:>8.0%} {cost or 0:>9.3f} "
                f"{turns or 0:>6.1f} {tools or 0:>6.1f}"
            )
        total = sum(metric(r, "cost_usd") or 0 for r in rows if r["arm"] == arm)
        print(f"{arm:4} {'total':8} {'':>5} {'':>8} {total:>9.2f}")

    for name in METRICS:
        print(f"\n{name}: median ratio to {base} (95% interval over tasks)")
        for arm in arms:
            if arm == base:
                continue
            for kind in sorted(set(kinds.values())):
                ratios = []
                for task in sorted(t for t, k in kinds.items() if k == kind):
                    b = median(metric(r, name) for r in by[(task, base)])
                    a = median(metric(r, name) for r in by[(task, arm)])
                    if b and a is not None:
                        ratios.append(a / b)
                if not ratios:
                    continue
                interval = bootstrap(ratios)
                span = f"[{interval[0]:.2f}, {interval[1]:.2f}]" if interval else ""
                print(f"  {arm:4} {kind:8} {statistics.median(ratios):.2f}  {span}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
