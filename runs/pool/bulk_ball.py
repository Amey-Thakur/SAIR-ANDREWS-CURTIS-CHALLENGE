"""Solve the whole pool at once out of a single ball.

Every per-challenge search so far pays its own cost. But the ball built from the
trivial pair does not depend on the challenge at all, and a challenge that
appears inside it is solved exactly, by one hash lookup, with the true minimum
distance attached. So one big ball can settle many challenges at once.

A hit is optimal inside the cap, which means it ties or beats any record.
Reconstruction inverts the stored move chain: the ball stores moves that carry
the trivial pair outwards, and we need the path back in.

Usage (from the repo root):
  python runs/pool/bulk_ball.py --cap 40 --nodes 20000000 --bits 25
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import time

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "runs" / "pool"))
from ball_search import INV, build_ball  # noqa: E402
from jit_engine import MAXLEN, _hash  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=40)
    ap.add_argument("--nodes", type=int, default=20_000_000)
    ap.add_argument("--bits", type=int, default=25)
    ap.add_argument("--out", default="runs/pool/bulk")
    args = ap.parse_args()

    from src.ac.moves import Destabilize
    from src.ac.presentation import Presentation
    from src.ac.verify import move_to_json, verify
    from src.search import engine as E

    if args.cap + 2 > MAXLEN:
        raise SystemExit(f"cap {args.cap} needs MAXLEN >= {args.cap + 2}")

    rows = [json.loads(l) for l in
            open(REPO / "runs/pool/pool.jsonl", encoding="utf-8")]
    print(f"{len(rows)} challenges; building one ball at cap {args.cap}, "
          f"{args.nodes:,} states", flush=True)

    build_ball(8, 10_000, 16)                       # warm the compiler
    t0 = time.time()
    keys, slot, parent, move, depth, count, expanded = build_ball(
        args.cap, args.nodes, args.bits)
    print(f"ball: {count:,} states in {time.time() - t0:.0f}s"
          f"{', complete' if expanded >= count else ''}", flush=True)

    mask = np.uint64((1 << args.bits) - 1)
    out = REPO / args.out
    out.mkdir(parents=True, exist_ok=True)

    hits = beats = ties = 0
    with (out / "solutions.jsonl").open("a", encoding="utf-8") as log:
        for r in rows:
            a = np.array(r["relators"][0], dtype=np.int8)
            b = np.array(r["relators"][1], dtype=np.int8)
            if len(a) + len(b) > args.cap:
                continue
            h = _hash(a, len(a), b, len(b))
            j = h & mask
            node = -1
            while keys[j] != np.uint64(0):
                if keys[j] == h:
                    node = slot[j]
                    break
                j = (j + np.uint64(1)) & mask
            if node < 0:
                continue
            # the ball carries the trivial pair outwards; invert to come back
            ids = []
            while parent[node] != -1:
                ids.append(int(INV[move[node]]))
                node = int(parent[node])
            hits += 1
            start = tuple(tuple(w) for w in r["relators"])
            ac = [E.to_move(m) for m in ids]
            stable = ac + [Destabilize(1), Destabilize(0)]
            begin = Presentation(2, start)
            if not verify(begin, ac, stable=False) or \
                    not verify(begin, stable, stable=True):
                raise AssertionError(f"bulk ball produced a bad path for {r['ac_id']}")
            rec = r["ac_best"]
            if rec is not None and len(ac) < rec:
                beats += 1
            elif rec is not None and len(ac) == rec:
                ties += 1
            stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            for problem, moves in (("ac", ac), ("stable_ac", stable)):
                log.write(json.dumps({"id": r["id"], "problem": problem,
                                      "length": len(moves),
                                      "moves": [move_to_json(m) for m in moves],
                                      "relators": r["relators"], "found_at": stamp,
                                      "cfg": {"method": "bulk-ball"}}) + "\n")
            if hits % 50 == 0:
                log.flush()
                print(f"  {hits} hits, {beats} beat the record, {ties} match",
                      flush=True)
    print(f"\n{hits} challenges found in the ball: {beats} beat the record, "
          f"{ties} match it", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()
