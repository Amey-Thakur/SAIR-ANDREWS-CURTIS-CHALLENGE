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
from src.ac.moves import Destabilize                             # noqa: E402
from src.ac.presentation import Presentation                     # noqa: E402
from src.ac.verify import verify                                 # noqa: E402
from src.search.campaign import move_to_json                     # noqa: E402
from src.search.engine import (FINISH_AC, FINISH_STABLE,         # noqa: E402
                               replay, to_move)


def pick(count, rec_lo, rec_hi, max_k, unsolved, skip, arb=False):
    """Targets, widest tolerance first.

    `unsolved` takes the challenges nobody has solved, where ANY verified path
    is worth a full point. `arb` takes the cross-problem arbitrage set, where
    `sac_best - ac_best >= 3` and so an ac path of `sac_best - 3` or less gives
    a stable path of `ac + 2` that BEATS the stable record outright - no ac beat
    required. Otherwise it takes single-holder challenges inside a record band.
    """
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
        if arb:
            if r["sac_best"] is None or r["sac_best"] - b < 3:
                continue
            if rec_lo <= b <= rec_hi:
                rows.append(r)
            continue
        if k <= max_k and rec_lo <= b <= rec_hi:
            rows.append(r)
    if unsolved:
        # STRATIFIED by presentation size, not smallest-first. The unsolved
        # pool runs size 13 to 40 with a median of 24, and taking the smallest
        # `count` would measure the easy tail and call it a find rate.
        rows.sort(key=lambda r: sum(len(x) for x in r["relators"]))
        if count and count < len(rows):
            by_size = {}
            for r in rows:
                by_size.setdefault(sum(len(x) for x in r["relators"]),
                                   []).append(r)
            out, i = [], 0
            while len(out) < count:
                took = False
                for s in sorted(by_size):
                    bucket = by_size[s]
                    if i < len(bucket) and len(out) < count:
                        out.append(bucket[i])
                        took = True
                if not took:
                    break
                i += 1
            rows = out
    elif arb:
        # most generous first: the biggest allowance over the ac record
        rows.sort(key=lambda r: -((r["sac_best"] - 3) / r["ac_best"]))
    else:
        rows.sort(key=lambda r: -r["ac_best"])
    n = len(rows)
    rows = rows[skip:]
    step = 1 if (unsolved or arb) else max(1, len(rows) // count)
    return rows[::step][:count], n


def shard_of(rows, shard, nshards):
    """One worker's slice. Taking every nth of a size-sorted list keeps each
    shard spread evenly across presentation sizes, which `--skip` would not:
    skip-based sharding interacts with the stratifier above and would hand
    every worker the same challenges."""
    if nshards <= 1:
        return rows
    return rows[shard::nshards]


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
    ap.add_argument("--arb", action="store_true",
                    help="the cross-problem arbitrage set: sac_best - ac_best "
                         ">= 3, where an ac path of sac_best - 3 or less is an "
                         "outright stable beat with no ac beat required")
    ap.add_argument("--skip", type=int, default=0)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--out", default="runs/pool/fresh")
    args = ap.parse_args()
    rows, pool_n = pick(args.count, args.rec_lo, args.rec_hi, args.max_k,
                        args.unsolved, args.skip, arb=args.arb)
    rows = shard_of(rows, args.shard, args.nshards)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sol = open(out / "solutions.jsonl", "a", encoding="utf-8")
    modes = [int(x) for x in args.modes.split(",")]
    what = ("the arbitrage set, sac_best - ac_best >= 3, ac records "
            f"{args.rec_lo}-{args.rec_hi}" if args.arb else
            "unsolved by anyone" if args.unsolved else
            f"k <= {args.max_k}, record {args.rec_lo}-{args.rec_hi}")
    tag = (f", shard {args.shard} of {args.nshards}"
           if args.nshards > 1 else "")
    print(f"  freshbeat: {len(rows)} of {pool_n} challenges, {what}{tag}, "
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
            sb = r["sac_best"]
            # the arbitrage threshold: our stable path is ac + 2, so an ac path
            # of sac_best - 3 or less takes the stable point outright, with no
            # ac beat at all
            arb_need = (sb - 3) if sb is not None else None
            mark = "   AC BEAT" if total < rec else (
                "   AC TIE" if total == rec else "")
            if arb_need is not None and total <= arb_need:
                mark += "   STABLE BEAT"
            req = f", required <= {arb_need} (ratio {arb_need / rec:.2f})" \
                if arb_need is not None and rec < 10 ** 9 else ""
            print(f"      mode {mode}: found {raw} -> shortened {len(short)} "
                  f"-> with finish {total} vs record {rec} "
                  f"(ratio {total / rec:.2f}){req}, {nodes:,} nodes, "
                  f"{dt:.0f}s + shorten {passes} passes{mark}", flush=True)

            moves = [to_move(m) for m in ac]
            chk = verify(Presentation(2, tuple(rels)), moves, stable=False)
            if not chk:
                print(f"      VERIFIER REJECTED: {chk.reason}", flush=True)
                continue
            wrote = False
            if total <= rec:
                stat[mode]["beat"] += total < rec
                sol.write(json.dumps(
                    {"id": r["id"], "problem": "ac", "length": total,
                     "moves": [move_to_json(m) for m in moves],
                     "record_at_find": rec, "mode": mode}) + "\n")
                wrote = True
            # the stable twin, both constructions, shortest that scores
            cands = [[to_move(m) for m in short] + FINISH_STABLE[end],
                     moves + [Destabilize(1), Destabilize(0)]]
            cands = [c for c in cands
                     if verify(Presentation(2, tuple(rels)), c, stable=True)]
            # sb is None exactly when nobody has solved the stable problem
            # either, and then ANY verified path is a full point - all 2,672
            # unsolved challenges are unsolved on both boards, so a single find
            # is worth 1.0 twice over
            if cands and (sb is None or len(min(cands, key=len)) <= sb):
                st = min(cands, key=len)
                stat[mode]["beat"] += sb is None or len(st) < sb
                sol.write(json.dumps(
                    {"id": r["id"], "problem": "stable_ac",
                     "length": len(st),
                     "moves": [move_to_json(m) for m in st],
                     "record_at_find": sb, "mode": mode}) + "\n")
                wrote = True
            if wrote:
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
