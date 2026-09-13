"""Retry the challenges we missed by a hair, at a wider cap.

Each of these was solved exactly inside cap = size + slack, so the answer is
the true minimum THERE. The record holder's shorter path simply leaves that
box. Widening the cap generally breaks the search, but on a challenge we have
already solved we know a path exists nearby, so it is worth walking the cap up
a step at a time and taking the first result that beats the record.

Every one of these is worth a full point on both boards: they are nearly all
single-holder, so beating one takes it outright.
"""
import datetime as dt
import json
import os
import pathlib
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "runs" / "pool"))
from src.ac.moves import Destabilize  # noqa: E402
from src.ac.presentation import Presentation  # noqa: E402
from src.ac.verify import move_to_json, verify  # noqa: E402
from src.search import engine as E  # noqa: E402
from jit_tieband import solve_bidir  # noqa: E402
from jit_engine import MAXLEN  # noqa: E402

SLACKS = (1, 2, 3, 4, 5, 6, 7, 8)
LIST = sys.argv[1] if len(sys.argv) > 1 else "runs/pool/nearmiss.txt"
NODES = int(sys.argv[2]) if len(sys.argv) > 2 else 8_000_000
OUTDIR = sys.argv[3] if len(sys.argv) > 3 else "runs/pool/nearmiss"
BITS = 24

targets = []
for line in open(REPO / LIST, encoding="utf-8"):
    if line.strip():
        cid, rec, ours, k = line.split()
        targets.append((cid, int(rec), int(ours), int(k)))

rows = {r["ac_id"]: r for r in
        (json.loads(l) for l in open(REPO / "runs/pool/pool.jsonl", encoding="utf-8"))}

out = REPO / OUTDIR
out.mkdir(parents=True, exist_ok=True)
print(f"{len(targets)} from {LIST}, slacks {SLACKS}, {NODES:,} nodes/side",
      flush=True)
solve_bidir(rows[targets[0][0]]["relators"], 40, 200_000, 20)   # warm the compiler

won = 0
with (out / "solutions.jsonl").open("a", encoding="utf-8") as log:
    for cid, rec, ours, k in targets:
        r = rows[cid]
        start = tuple(tuple(w) for w in r["relators"])
        size = len(start[0]) + len(start[1])
        best = None
        for slack in SLACKS:
            cap = size + slack
            if cap + 2 > MAXLEN:
                break
            t0 = time.time()
            ids, nodes = solve_bidir(r["relators"], cap, NODES, BITS)
            if ids is not None and (best is None or len(ids) < len(best)):
                best = ids
            mark = "none" if ids is None else str(len(ids))
            print(f"  {cid} record {rec} (was {ours}): slack {slack} -> {mark} "
                  f"({nodes:,} nodes, {time.time()-t0:.0f}s)", flush=True)
            # a tie pays 2^(1-k); a strictly shorter path pays a full 1.0 and
            # drops the holder to zero, so keep walking until we are under
            if best is not None and len(best) < rec:
                break
        if best is None or len(best) >= ours:
            continue
        ac = [E.to_move(m) for m in best]
        stable = ac + [Destabilize(1), Destabilize(0)]
        begin = Presentation(2, start)
        if not verify(begin, ac, stable=False) or \
                not verify(begin, stable, stable=True):
            raise AssertionError("near-miss retry produced an unverifiable path")
        scores = len(ac) <= rec
        won += scores
        stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        for problem, moves in (("ac", ac), ("stable_ac", stable)):
            log.write(json.dumps({"id": r["id"], "problem": problem,
                                  "length": len(moves),
                                  "moves": [move_to_json(m) for m in moves],
                                  "relators": r["relators"], "found_at": stamp,
                                  "cfg": {"method": "nearmiss-retry"}}) + "\n")
        log.flush()
        print(f"    {cid}: {ours} -> {len(ac)} against record {rec}"
              f"{'   TAKES IT' if scores else ''}", flush=True)
print(f"\n{won} of {len(targets)} now beat or match the record", flush=True)
os._exit(0)
