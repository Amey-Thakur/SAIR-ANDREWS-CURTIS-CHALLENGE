"""Does a wider cap buy a shorter path?

Our paths run about 10 percent longer than the records we are trying to beat.
Each is the true minimum inside cap = size + slack, so the only way to shorten
one is to widen the cap. This measures that trade directly on challenges we
have already solved, rather than guessing at it.
"""
import json
import os
import pathlib
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "runs" / "pool"))
from ball_search import Ball, solve  # noqa: E402

TARGETS = ["ac-03055", "ac-01216", "ac-03652", "ac-09747"]

rows = {r["ac_id"]: r for r in
        (json.loads(l) for l in open(REPO / "runs/pool/pool.jsonl", encoding="utf-8"))}

print("warming", flush=True)
w = Ball(20, 50_000, 18)
solve(rows[TARGETS[0]]["relators"], w, 20, 50_000, 18)

for tid in TARGETS:
    r = rows[tid]
    size = len(r["relators"][0]) + len(r["relators"][1])
    print(f"\n{tid}: record {r['ac_best']}, size {size}", flush=True)
    for slack in (2, 4, 6, 8):
        cap = size + slack
        if cap + 2 > 44:
            print(f"  slack {slack}: cap {cap} over the buffer", flush=True)
            continue
        t0 = time.time()
        ball = Ball(cap, 16_000_000, 25)
        ids, nodes = solve(r["relators"], ball, cap, 4_000_000, 23)
        got = "none" if ids is None else str(len(ids))
        beats = ids is not None and len(ids) <= r["ac_best"]
        print(f"  slack {slack} (cap {cap}): ours {got:>5}"
              f"  [ball {ball.count:,} {ball.secs:.0f}s, fwd {nodes:,},"
              f" {time.time()-t0:.0f}s total]{'   BEATS THE RECORD' if beats else ''}",
              flush=True)
os._exit(0)
