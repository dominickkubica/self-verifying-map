"""Summarise a benchmark run: accuracy, cost and effort per arm, and map/no-map ratios.

    python benchmark/analyze.py bench-out/runs.jsonl

Per task, each metric is the median over repetitions; the ratio is map (B) over no map
(A). Across tasks of a kind, the median ratio with a 95% bootstrap interval that
resamples tasks. A ratio below 1 means the map arm spent less.
"""

from __future__ import annotations

import json
import random
import statistics
import sys
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


def main(path: str) -> int:
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]
    by = defaultdict(list)
    for row in rows:
        by[(row["task"], row["arm"])].append(row)
    kinds = {row["task"]: row["kind"] for row in rows}

    print(f"{len(rows)} runs, {len(kinds)} tasks\n")
    print(f"{'kind':9} {'arm':4} {'correct':>8} {'partial':>8}")
    for kind in sorted(set(kinds.values())):
        for arm in ("A", "B"):
            chosen = [r for r in rows if r["kind"] == kind and r["arm"] == arm]
            if not chosen:
                continue
            correct = sum(r["grade"] == "correct" for r in chosen) / len(chosen)
            partial = sum(r["grade"] == "partial" for r in chosen) / len(chosen)
            print(f"{kind:9} {arm:4} {correct:>8.0%} {partial:>8.0%}")

    for name in ("weighted_tokens", "cost_usd", "tool_calls", "searches", "orientation"):
        print(f"\n{name}: median ratio, map / no map (95% interval over tasks)")
        for kind in sorted(set(kinds.values())):
            ratios = []
            for task in sorted(t for t, k in kinds.items() if k == kind):
                a = median(metric(r, name) for r in by[(task, "A")])
                b = median(metric(r, name) for r in by[(task, "B")])
                if a and b is not None:
                    ratios.append(b / a)
            if not ratios:
                continue
            interval = bootstrap(ratios)
            span = f"[{interval[0]:.2f}, {interval[1]:.2f}]" if interval else "(one task)"
            print(f"  {kind:9} {statistics.median(ratios):.2f}  {span}  ({len(ratios)} tasks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
