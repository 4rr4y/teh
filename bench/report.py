#!/usr/bin/env python3
"""Summarises benchmark results, and compares configs: bench/report.py RESULTS_DIR ... [--baseline NAME] [--tasks]

Cost is in input-token equivalents, so providers and configs can be compared on one number: uncached input counts 1,
a cache write --write (default 1.25, as for Anthropic's 5-minute cache), a cache read --read (0.1) and output
--output (5). Set them to your model's price ratios. For OpenAI-format providers, input that isn't cached counts 1."""
import argparse, json, math, sys
from collections import defaultdict
from pathlib import Path

def load(dirs):
    runs = []
    for d in dirs:
        path = Path(d) / "results.jsonl"
        if not path.exists():
            sys.exit(f"no results in {d}")
        runs += [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return runs

def cost(r, prices):
    return r["uncached"] + r["write"] * prices.write + r["read"] * prices.read + r["out"] * prices.output

def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0

def interval(passes, n):  # a 90% Wilson interval for a pass rate: with few runs, differences are often noise
    if not n:
        return 0, 0
    p, z = passes / n, 1.645
    centre, half = (p + z * z / (2 * n)) / (1 + z * z / n), z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (
        1 + z * z / n)
    return max(0, centre - half), min(1, centre + half)

def table(rows, header):
    widths = [max(len(str(x)) for x in col) for col in zip(header, *rows)]
    for row in [header, *rows]:
        print("  ".join(str(x).rjust(w) if i else str(x).ljust(w) for i, (x, w) in enumerate(zip(row, widths))))

def summary(runs, prices, baseline):
    by = defaultdict(list)
    for r in runs:
        by[r["config"]].append(r)
    base_cost = mean([cost(r, prices) for r in by.get(baseline, [])])
    rows = []
    for config, rs in by.items():
        passes, c = sum(r["passed"] for r in rs), mean([cost(r, prices) for r in rs])
        low, high = interval(passes, len(rs))
        read_share = sum(r["read"] for r in rs) / max(1, sum(r["in"] for r in rs))
        rows.append([config, len(rs), f"{passes / len(rs):.0%}", f"{low:.0%}-{high:.0%}",
                     f"{mean([r['calls'] for r in rs]):.1f}", f"{mean([r['in'] for r in rs]):,.0f}",
                     f"{read_share:.0%}", f"{mean([r['out'] for r in rs]):,.0f}",
                     f"{mean([r['max_context'] for r in rs]):,.0f}", f"{c:,.0f}",
                     f"{(c / base_cost - 1):+.1%}" if base_cost and config != baseline else ""])
    table(rows, ["config", "runs", "pass", "90% range", "calls", "input/run", "cached", "output/run",
                 "peak ctx", "cost/run", f"vs {baseline}"])

def paired(runs, prices, baseline):  # each task under each config, against the baseline: where a change shows
    by = defaultdict(list)
    for r in runs:
        by[(r["task"], r["config"])].append(r)
    configs = sorted({r["config"] for r in runs} - {baseline})
    rows = []
    for task in sorted({r["task"] for r in runs}):
        base = by.get((task, baseline), [])
        row = [task, f"{sum(r['passed'] for r in base)}/{len(base)}", f"{mean([cost(r, prices) for r in base]):,.0f}"]
        for config in configs:
            rs = by.get((task, config), [])
            c = mean([cost(r, prices) for r in rs])
            b = mean([cost(r, prices) for r in base])
            row += [f"{sum(r['passed'] for r in rs)}/{len(rs)}", f"{(c / b - 1):+.0%}" if b and rs else ""]
        rows.append(row)
    header = ["task", f"{baseline} pass", "cost"]
    for config in configs:
        header += [f"{config} pass", "Δcost"]
    table(rows, header)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("dirs", nargs="+")
    parser.add_argument("--baseline", default="baseline")
    parser.add_argument("--tasks", action="store_true", help="also show each task, against the baseline")
    parser.add_argument("--write", type=float, default=1.25)
    parser.add_argument("--read", type=float, default=0.1)
    parser.add_argument("--output", type=float, default=5.0)
    args = parser.parse_args(argv)
    runs = load(args.dirs)
    print(f"\n== all tasks ({len({r['task'] for r in runs})})")
    summary(runs, args, args.baseline)
    for field, values in (("kind", ("dev", "everyday")), ("size", ("short", "slow", "long", "xl"))):
        for value in values:
            subset = [r for r in runs if r[field] == value]
            if subset:
                print(f"\n== {field} = {value} ({len({r['task'] for r in subset})} tasks)")
                summary(subset, args, args.baseline)
    if args.tasks or len({r["config"] for r in runs}) > 1:
        print("\n== each task")
        paired(runs, args, args.baseline)
    failures = [r for r in runs if not r["passed"]]
    if failures:
        print("\n== failures")
        for r in failures:
            print(f"  {r['config']:<12} {r['task']:<18} #{r['rep']}  {r['ended']}: {r['detail'][:100]}")


if __name__ == "__main__":
    main()
