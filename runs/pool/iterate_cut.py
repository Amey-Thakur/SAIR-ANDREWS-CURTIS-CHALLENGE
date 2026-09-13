"""Does shortening keep paying if you run it again?

One pass cut a 3,742-move path to 963, a 74 percent reduction, where the same
pass on a 30-move path gained 2 percent. Long paths carry far more slack. If
repeated passes keep converging, the long-record bands open up, because
best-first can reach them and nothing else can.
"""
import json
import os
import pathlib
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "runs" / "pool"))
from bestfirst import solve  # noqa: E402
from src.ac.presentation import Presentation  # noqa: E402
from src.ac.verify import verify  # noqa: E402
from src.search import engine as E  # noqa: E402

rows = {r["ac_id"]: r for r in
        (json.loads(l) for l in open(REPO / "runs/pool/pool.jsonl", encoding="utf-8"))}
TARGETS = ["ac-04353", "ac-09331"]

solve(rows[TARGETS[0]]["relators"], 100_000, 18)      # warm
for tid in TARGETS:
    r = rows.get(tid)
    if r is None:
        continue
    start = tuple(tuple(w) for w in r["relators"])
    ids, nodes = solve(r["relators"], 4_000_000, 23)
    if ids is None:
        print(f"{tid}: no path", flush=True)
        continue
    print(f"\n{tid}: record {r['ac_best']}, raw {len(ids)}", flush=True)
    for it in range(1, 9):
        t0 = time.time()
        try:
            cut = E.shorten(start, ids, depth=3)
        except Exception as exc:
            print(f"   pass {it}: failed {exc}", flush=True)
            break
        gain = len(ids) - len(cut)
        ids = cut
        ok = verify(Presentation(2, start), [E.to_move(m) for m in ids],
                    stable=False)
        beats = len(ids) <= r["ac_best"]
        print(f"   pass {it}: -> {len(ids)} (cut {gain}, {time.time()-t0:.0f}s, "
              f"verified {bool(ok)}){'   BEATS THE RECORD' if beats else ''}",
              flush=True)
        if gain == 0 or beats:
            break
os._exit(0)
