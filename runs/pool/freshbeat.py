"""Find a path with the lossless canonical key, then shorten it: the two
backlog items pointed at the only targets worth a full point.

Why this combination and why these targets. The shortener measured on 512 held
paths lands exactly ON the record and never below, which is the right answer
where the record is already the true minimum - and a record shared by eight to
forty teams is. So shortening cannot produce a beat on the near-miss set. Where
a record CAN be soft is the opposite corner of the pool: a long record held by
ONE team, which nobody has had reason to polish. There we hold no path at all,
so the question is not shortening but finding - and the lossless canonical key
(the sixteen exact symmetries of the move graph) is what buys reach at a fixed
budget, +21 solved of 400 on the benchmark.

So: canonical-key search for a path, bidirectional shortener to polish it, and
compare with the record. Any result strictly under the record is a full point
and drops a single holder to zero. A path longer than the record scores nothing
and is recorded as a negative.

The control is the same search with the plain visited key at the same budget,
so the canonical key is credited only with what it actually adds.

Usage (from the repo root):
  python runs/pool/freshbeat.py --count 40 --rec-lo 61 --nodes 3000000
"""
import argparse
import json
import os
import pathlib
import statistics
import sys
import time

os.environ.setdefault("ACC_MAXLEN", "64")

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "runs" / "pool"))

import canonkey                                                  # noqa: E402
from bishorten import shorten as bishort                         # noqa: E402
from src.ac.presentation import Presentation                     # noqa: E402
from src.ac.verify import verify                                 # noqa: E402
from src.search.campaign import move_to_json                     # noqa: E402
from src.search.engine import (FINISH_AC, FINISH_STABLE,         # noqa: E402
                               replay, to_move)


def pick(count, rec_lo, rec_hi, max_k, unsolved, skip):
    """Targets, widest tolerance first.

    `unsolved` takes the challenges nobody has solved, where ANY verified path
    is worth a full point. Otherwise it takes single-holder challenges inside
    a record band, where any path under the record is worth a full point."""
    rows = []
    for line in open(REPO / "runs/pool/pool.jsonl", encoding="utf-8"):
        r = json.loads(line)
        b, k = r["ac_best"], r["ac_k"]
        if unsolved:
            if b is None:
                rows.append(r)
            continue
        if b is None or k is None:
            continue
        if k <= max_k and rec_lo <= b <= rec_hi:
            rows.append(r)
    if unsolved:
        # smallest first: size is the only lever we have on an unsolved case
        rows.sort(key=lambda r: sum(len(x) for x in r["relators"]))
    else:
        rows.sort(key=lambda r: -r["ac_best"])
    n = len(rows)
    rows = rows[skip:]
    step = max(1, len(rows) // count) if not unsolved else 1
    return rows[::step][:count], n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=40)
    ap.add_argument("--rec-lo", type=int, default=61)
    ap.add_argument("--rec-hi", type=int, default=100000)
    ap.add_argument("--max-k", type=int, default=1)
    ap.add_argument("--nodes", type=int, default=3_000_000)
    ap.add_argument("--slack", type=int, default=8)
    ap.add_argument("--depth", type=int, default=5)
    ap.add_argument("--modes", default="4,0")
    ap.add_argument("--unsolved", action="store_true")
    ap.add_argument("--skip", type=int, default=0)
    ap.add_argument("--out", default="runs/pool/fresh")
    args = ap.parse_args()
    rows, pool_n = pick(args.count, args.rec_lo, args.rec_hi, args.max_k,
                        args.unsolved, args.skip)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sol = open(out / "solutions.jsonl", "a", encoding="utf-8")
    modes = [int(x) for x in args.modes.split(",")]
    what = ("unsolved by anyone" if args.unsolved else
            f"k <= {args.max_k}, record {args.rec_lo}-{args.rec_hi}")
    print(f"  freshbeat: {len(rows)} of {pool_n} challenges, {what}, "
          f"budget {args.nodes:,}, modes {modes}", flush=True)
    canonkey.solve([(1, 2), (2, 1)], 8, 1000, 4)      # warm the compiler

    stat = {m: {"found": 0, "beat": 0, "ratios": []} for m in modes}
    for n, r in enumerate(rows, 1):
        rels = [tuple(x) for x in r["relators"]]
        size = sum(len(x) for x in rels)
        rec = r["ac_best"] if r["ac_best"] is not None else 10 ** 9
        print(f"\n  [{n}/{len(rows)}] {r['ac_id']} record "
              f"{r['ac_best']} (k {r['ac_k']}) size {size}", flush=True)
        for mode in modes:
            t0 = time.time()
            path, nodes = canonkey.solve(rels, size + args.slack,
                                         args.nodes, mode)
            dt = time.time() - t0
            if path is None:
                print(f"      mode {mode}: none, {nodes:,} nodes, {dt:.0f}s",
                      flush=True)
                continue
            raw = len(path)
            short, passes, saved, over = bishort(tuple(rels), path,
                                                 args.depth, args.slack)
            end = replay(tuple(rels), short)[-1]
            ac = short + FINISH_AC[end]
            total = len(ac)
            stat[mode]["found"] += 1
            stat[mode]["ratios"].append(total / rec)
            mark = "BEAT" if total < rec else ""
            print(f"      mode {mode}: found {raw} -> shortened {len(short)} "
                  f"-> with finish {total} vs record {rec} "
                  f"(ratio {total / rec:.2f}), {nodes:,} nodes, "
                  f"{dt:.0f}s + shorten {passes} passes {mark}", flush=True)
            if total >= rec:
                continue
            stat[mode]["beat"] += 1
            moves = [to_move(m) for m in ac]
            chk = verify(Presentation(2, tuple(rels)), moves, stable=False)
            if not chk:
                print(f"      VERIFIER REJECTED: {chk.reason}", flush=True)
                continue
            sol.write(json.dumps(
                {"id": r["id"], "problem": "ac", "length": total,
                 "moves": [move_to_json(m) for m in moves],
                 "record_at_find": rec, "mode": mode}) + "\n")
            stable = [to_move(m) for m in short] + FINISH_STABLE[end]
            chk = verify(Presentation(2, tuple(rels)), stable, stable=True)
            if chk and len(stable) < (r["sac_best"] or 10 ** 9):
                sol.write(json.dumps(
                    {"id": r["id"], "problem": "stable_ac",
                     "length": len(stable),
                     "moves": [move_to_json(m) for m in stable],
                     "record_at_find": r["sac_best"], "mode": mode}) + "\n")
            sol.flush()
    sol.close()
    print()
    for mode in modes:
        s = stat[mode]
        med = statistics.median(s["ratios"]) if s["ratios"] else 0
        mn = min(s["ratios"]) if s["ratios"] else 0
        print(f"  mode {mode}: found {s['found']}/{len(rows)}, "
              f"BEAT {s['beat']}, ratio min {mn:.2f} median {med:.2f}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
