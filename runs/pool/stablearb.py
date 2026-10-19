"""The ac-to-stable arbitrage: where EQUALLING an ac record is an outright
stable beat.

Our harness emits the stable path as the ordinary descent plus two
destabilisations, and that relationship is exact rather than assumed: over the
396 challenges solved on this machine, our stable length minus our ac length is
**2 on 393 of them** (3 on one, 4 on one, 285 on one, all three of which are
stale stable paths that the +2 construction would improve).

So on any challenge where `sac_best - ac_best >= 3`, an ac path of length L
yields a stable path of L + 2, and that BEATS the stable record outright - worth
1.0, not the 2^(1-k) a tie pays - whenever

    L + 2 < sac_best,  i.e.  L <= sac_best - 3.

That is strictly weaker than beating the ac record and often weaker than
equalling it: on a challenge where the two records are 29 apart, our ac path may
be 29 moves WORSE than the ac record and still take a full point on the stable
board.

252 challenges satisfy `sac_best - ac_best >= 3` at the current snapshot. The
catch, measured: 238 of them have `ac_best >= 61` and 201 have `ac_k == 1`, so
they are the same long-record single-holder band that a complete 108-challenge
bestfirst sweep failed to find a single path in. **Only two sit at an ac record
our solvers reach**, and this goes after those two with everything:

  ac-03060  ac record 27 (k 1), stable record 30 (k 3), size 22, need L <= 27
  ac-01876  ac record 40 (k 3), stable record 45 (k 4), size 29, need L <= 42

Both were attempted before and both returned "not found" - but at the records
they carried THEN, 34-35 and 47. ac-03060's record has since fallen from 35 to
27, which moves it out of the 31-60 band (slack 0) and into 23-30 (slack 2), so
it is no longer settled at its band's slack and `skip_exact.txt` is stale for
it. That is the runbook's "a refresh refills the productive band", and it is why
this is worth the compute.

The exact bidirectional search returns the TRUE MINIMUM inside cap = size +
slack, so the cap is walked upward: when the answer is longer than we need, the
route we want lies outside the box.

Usage (from the repo root):
  python runs/pool/stablearb.py --ids 03060,01876 --slacks 2,4,6,8,10,12
"""
import argparse
import json
import os
import pathlib
import sys
import time

os.environ.setdefault("ACC_MAXLEN", "56")

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "runs" / "pool"))

from jit_engine import MAXLEN                                    # noqa: E402
from jit_tieband import solve_bidir                              # noqa: E402
from src.ac.moves import Destabilize                             # noqa: E402
from src.ac.presentation import Presentation                     # noqa: E402
from src.ac.verify import verify                                 # noqa: E402
from src.search.campaign import move_to_json                     # noqa: E402
from src.search.engine import to_move                            # noqa: E402


def arbitrage(pool, max_ac):
    out = []
    for r in pool:
        if r["ac_best"] is None or r["sac_best"] is None:
            continue
        if r["sac_best"] - r["ac_best"] < 3:
            continue
        if r["ac_best"] > max_ac:
            continue
        out.append(r)
    out.sort(key=lambda r: r["ac_best"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="")
    ap.add_argument("--max-ac", type=int, default=45)
    ap.add_argument("--slacks", default="2,4,6,8,10,12")
    ap.add_argument("--nodes", type=int, default=4_000_000)
    ap.add_argument("--bits", type=int, default=23)
    ap.add_argument("--out", default="runs/pool/arb")
    args = ap.parse_args()

    pool = [json.loads(l) for l in
            open(REPO / "runs/pool/pool.jsonl", encoding="utf-8")]
    if args.ids:
        want = set(args.ids.split(","))
        rows = [r for r in pool if r["id"] in want]
    else:
        rows = arbitrage(pool, args.max_ac)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sol = open(out / "solutions.jsonl", "a", encoding="utf-8")
    print(f"  stablearb: {len(rows)} targets, MAXLEN {MAXLEN}, "
          f"{args.nodes:,} nodes/side", flush=True)
    solve_bidir([[1, 2], [2, 1]], 8, 1000, 12)         # warm the compiler

    wins = 0
    for r in rows:
        start = tuple(tuple(w) for w in r["relators"])
        size = len(start[0]) + len(start[1])
        need = r["sac_best"] - 3
        acrec = r["ac_best"]
        print(f"\n  ac-{r['id']}: size {size}, ac record {acrec} (k {r['ac_k']}), "
              f"stable record {r['sac_best']} (k {r['sac_k']}); an ac path of "
              f"{need} or less is a STABLE BEAT, {acrec - 1} or less also an "
              f"AC BEAT", flush=True)
        best = None
        for slack in [int(x) for x in args.slacks.split(",")]:
            cap = size + slack
            if cap + 2 > MAXLEN:
                print(f"      slack {slack}: cap {cap} needs MAXLEN "
                      f"{cap + 2}, have {MAXLEN}; stopping the walk",
                      flush=True)
                break
            t0 = time.time()
            ids, nodes = solve_bidir(r["relators"], cap, args.nodes, args.bits)
            dt = time.time() - t0
            if ids is None:
                print(f"      slack {slack} (cap {cap}): no path inside the "
                      f"box, {nodes:,} nodes, {dt:.0f}s", flush=True)
                continue
            L = len(ids)
            mark = ""
            if L <= need:
                mark = "  <-- STABLE BEAT"
            if L < acrec:
                mark += "  <-- AC BEAT"
            print(f"      slack {slack} (cap {cap}): true minimum {L} "
                  f"(need {need}), {nodes:,} nodes, {dt:.0f}s{mark}",
                  flush=True)
            if best is None or L < len(best):
                best = ids
            if L <= need:
                break
        if best is None:
            continue
        ac = [to_move(m) for m in best]
        stable = ac + [Destabilize(1), Destabilize(0)]
        begin = Presentation(2, start)
        ca = verify(begin, ac, stable=False)
        cs = verify(begin, stable, stable=True)
        if not ca or not cs:
            print(f"      VERIFIER REJECTED: "
                  f"{ca.reason if not ca else cs.reason}", flush=True)
            continue
        for problem, moves, rec in (("ac", ac, acrec),
                                    ("stable_ac", stable, r["sac_best"])):
            if len(moves) > rec:
                continue
            sol.write(json.dumps(
                {"id": r["id"], "problem": problem, "length": len(moves),
                 "moves": [move_to_json(m) for m in moves],
                 "record_at_find": rec}) + "\n")
            wins += len(moves) < rec
        sol.flush()
    sol.close()
    print(f"\n  {len(rows)} targets, {wins} outright beats written", flush=True)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
