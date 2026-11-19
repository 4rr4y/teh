#!/usr/bin/env python3
"""When would compacting earlier pay? Replays recorded runs as if teh had compacted at a lower context size.

usage: bench/simulate.py RESULTS_DIR [--config baseline] [--thresholds 16000,32000,...] [--reread 0,5000,15000]

Each recorded call (from the traces) says how big the context was and how much the reply added. The replay keeps
that growth, but whenever the context would pass a threshold it pays for a compaction instead, as teh does it:
- the summary call: the whole conversation read from the cache, the summary request written, the summary output
- then a fresh conversation (the setup prompt, the summary, the user's requests): written to the cache again
- and what the model reads again afterwards to pick up the thread (--reread tokens: unknown, so several are tried;
  they arrive in calls of about 3,000 tokens each, and each of those calls rereads the context)
Everything else costs what it did: cache reads for what was there before, cache writes for what's new, the output.

It measures cost only. Whether results suffer from compacting earlier needs real runs: run.py with
--config compact64k TEH_CONTEXT_WINDOW=64000 and so on (see bench/README.md). Runs that compacted on their own are
left out, as their traces don't show the uncompacted growth."""
import argparse, json, math, sys
from pathlib import Path

SUMMARY_OUT = 600     # tokens: the summary (at most about 400 words)
SUMMARY_REQUEST = 200  # tokens: the request for it
REREAD_CALL = 3000    # tokens read again per extra call, after a compaction

def traces(results, config):
    runs = [json.loads(line) for line in (results / "results.jsonl").read_text().splitlines() if line.strip()]
    for r in runs:
        if r["config"] != config or r.get("compactions"):
            continue
        path = results / "traces" / config / f"{r['task']}-{r['rep']}.jsonl"
        calls = [c["usage"] for c in map(json.loads, path.read_text().splitlines()) if "usage" in c]
        if len(calls) >= 2:
            yield r, calls

def cost_of(uncached, write, read, out, p):
    return uncached + write * p.write + read * p.read + out * p.output

def replay(calls, threshold, reread, p):  # -> (cost, compactions); threshold None: as it happened
    base = calls[0]["in"]  # the system prompt, the tool and the task: what a compacted conversation starts from
    ctx, cost, compactions = base, cost_of(0, base, 0, calls[0]["out"], p), 0
    for before, call in zip(calls, calls[1:]):
        growth = max(0, call["in"] - before["in"])
        if threshold and ctx + growth >= threshold:
            cost += cost_of(0, SUMMARY_REQUEST, ctx, SUMMARY_OUT, p)               # the summary call
            ctx = base + SUMMARY_OUT
            extra = math.ceil(reread / REREAD_CALL)                                # picking up the thread
            for _ in range(extra):
                cost += cost_of(0, REREAD_CALL, ctx, 100, p)
                ctx += REREAD_CALL
            cost += cost_of(0, ctx, 0, call["out"], p)                             # this call: all new
            compactions += 1
        else:
            cost += cost_of(0, growth, ctx, call["out"], p)
            ctx += growth
    return cost, compactions

def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("results", type=Path)
    parser.add_argument("--config", default="baseline")
    parser.add_argument("--thresholds", default="16000,24000,32000,48000,64000,96000,128000")
    parser.add_argument("--reread", default="0,5000,15000", help="tokens read again after each compaction")
    parser.add_argument("--write", type=float, default=1.25)
    parser.add_argument("--read", type=float, default=0.1)
    parser.add_argument("--output", type=float, default=5.0)
    p = parser.parse_args()
    thresholds = [int(t) for t in p.thresholds.split(",")]
    rereads = [int(r) for r in p.reread.split(",")]
    runs = list(traces(p.results, p.config))
    if not runs:
        sys.exit(f"no usable traces for config {p.config} in {p.results}")

    # How well the replay's cost model matches what the provider reported, uncompacted
    actual = sum(sum(cost_of(c["uncached"], c["write"], c["read"], c["out"], p) for c in calls) for _, calls in runs)
    modelled = sum(replay(calls, None, 0, p)[0] for _, calls in runs)
    print(f"{len(runs)} runs; peak context: median {sorted(max(c['in'] for c in cs) for _, cs in runs)[len(runs) // 2]:,}"
          f", largest {max(max(c['in'] for c in cs) for _, cs in runs):,} tokens")
    print(f"cost model check: replayed without compaction {modelled:,.0f}, as reported {actual:,.0f} "
          f"({modelled / actual - 1:+.1%}; the difference is cache misses the replay doesn't model)\n")

    print("cost of all runs if teh compacted at each threshold, against not compacting (negative: cheaper)")
    header = ["threshold", "runs compacted", "compactions"] + [f"reread {r:,}" for r in rereads]
    rows = []
    for t in thresholds:
        affected = [calls for _, calls in runs if max(c["in"] for c in calls) >= t]
        if not affected:
            rows.append([f"{t:,}", "0", "0"] + ["-"] * len(rereads))
            continue
        row = [f"{t:,}", f"{len(affected)}/{len(runs)}",
               str(sum(replay(calls, t, 0, p)[1] for calls in affected))]
        for r in rereads:
            if max(cs[0]["in"] for _, cs in runs) + SUMMARY_OUT + r >= t / 2:  # it would compact again at once
                row.append("n/a")
                continue
            new = sum(replay(calls, t, r, p)[0] for _, calls in runs)
            row.append(f"{new / modelled - 1:+.1%}")
        rows.append(row)
    widths = [max(len(str(x)) for x in col) for col in zip(header, *rows)]
    for row in [header, *rows]:
        print("  ".join(str(x).rjust(w) for x, w in zip(row, widths)))
    print("(n/a: a compacted conversation would be over half the threshold, so it would soon compact again)")

    print("\nper long and xl run, at the threshold that would have been cheapest (reread 5,000):")
    for r, calls in runs:
        if r["size"] not in ("long", "xl"):
            continue
        none, peak = replay(calls, None, 0, p)[0], max(c["in"] for c in calls)
        below = [t for t in thresholds if t <= peak]  # a threshold above the peak means not compacting
        best = min(below + [None], key=lambda t: replay(calls, t, 5000, p)[0] if t else none)
        saving = (replay(calls, best, 5000, p)[0] / none - 1) if best else 0
        print(f"  {r['task']:<18} #{r['rep']}  {len(calls):>3} calls, peak {max(c['in'] for c in calls):>8,}: "
              + (f"{best:,} ({saving:+.1%})" if best else "not compacting"))

    print("\nbreak-even: calls after a compaction at context C before it has paid for itself (reread 5,000), when "
          "each call reads the whole context from the cache:")
    for c in (32_000, 64_000, 128_000):
        after = 2_000 + SUMMARY_OUT + 5_000  # roughly: setup prompt, summary, what's read again
        spend = (c * p.read + SUMMARY_REQUEST * p.write + SUMMARY_OUT * p.output + after * p.write
                 + 2 * (after * p.read))
        print(f"  C = {c:>7,}: about {spend / ((c - after) * p.read):.1f} calls")


if __name__ == "__main__":
    main()
