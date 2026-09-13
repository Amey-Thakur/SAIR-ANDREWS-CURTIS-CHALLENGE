"""Exact shortest paths for challenges whose held best is short.

Greedy finds paths that are too long to score. On a challenge already solved in
a handful of moves, the only way to score is to match the true minimum, so this
searches from both ends at once: forward from the presentation, backward from
the target using inverted moves, expanding whichever frontier is smaller, until
they meet. With a cap on total relator length the search is exhaustive inside
that cap, so a path it returns at length L proves nothing shorter exists inside
the cap, and L <= held best either ties or takes the challenge outright.

Every path is verified locally and written in the campaign format, so
`python -m src.harness.submit runs/pool/tieband` re-checks it with the official
verifier and sends it.

Usage (from the repo root):
  python runs/pool/tieband.py --max-held 24 --cap-slack 6 --limit 60 --workers 5
"""
import argparse
import datetime as dt
import json
import pathlib
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from src.ac.moves import Destabilize  # noqa: E402
from src.ac.presentation import Presentation  # noqa: E402
from src.ac.verify import move_to_json, verify  # noqa: E402
from src.search import engine as E  # noqa: E402

INV = (0, 1, 3, 2, 5, 4, 7, 6, 9, 8, 11, 10, 13, 12)


def bidirectional(start, target, cap, max_depth):
    """A shortest move sequence from start to target inside the length cap,
    or None. Expands the smaller frontier, so the work is about two balls of
    half the answer's depth rather than one of the whole."""
    if start == target:
        return []
    fwd = {start: []}
    bwd = {target: []}
    fwd_front, bwd_front = [start], [target]
    depth = 0
    while depth < max_depth:
        if len(fwd_front) <= len(bwd_front):
            nxt = []
            for s in fwd_front:
                base = fwd[s]
                for mid, t in E.expand(s):
                    if t in fwd:
                        continue
                    a, b = t
                    if not a or not b or len(a) + len(b) > cap:
                        continue
                    route = base + [mid]
                    hit = bwd.get(t)
                    if hit is not None:
                        return route + hit
                    fwd[t] = route
                    nxt.append(t)
            fwd_front = nxt
        else:
            nxt = []
            for s in bwd_front:
                base = bwd[s]
                for mid, t in E.expand(s):
                    if t in bwd:
                        continue
                    a, b = t
                    if not a or not b or len(a) + len(b) > cap:
                        continue
                    route = [INV[mid]] + base
                    hit = fwd.get(t)
                    if hit is not None:
                        return hit + route
                    bwd[t] = route
                    nxt.append(t)
            bwd_front = nxt
        if not fwd_front or not bwd_front:
            return None
        depth += 1
    return None


def work(task):
    r, cap_slack, max_depth, budget_s = task
    start = tuple(tuple(w) for w in r["relators"])
    cap = len(start[0]) + len(start[1]) + cap_slack
    t0 = time.time()
    try:
        ids = bidirectional(start, E.TARGET, cap, max_depth)
    except MemoryError:
        return r, None, None, time.time() - t0, "out of memory"
    if ids is None:
        return r, None, None, time.time() - t0, None
    ac = [E.to_move(m) for m in ids]
    stable = ac + [Destabilize(1), Destabilize(0)]
    begin = Presentation(2, start)
    if not verify(begin, ac, stable=False) or not verify(begin, stable, stable=True):
        raise AssertionError("tieband produced a path the verifier rejects")
    return r, [move_to_json(m) for m in ac], [move_to_json(m) for m in stable], \
        time.time() - t0, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-held", type=int, default=24)
    ap.add_argument("--min-held", type=int, default=0,
                    help="skip challenges already reachable at a lower setting")
    ap.add_argument("--cap-slack", type=int, default=6)
    ap.add_argument("--max-depth", type=int, default=13)
    ap.add_argument("--budget-s", type=float, default=120.0)
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--out", default="runs/pool/tieband")
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(REPO / "runs/pool/pool.jsonl", encoding="utf-8")]
    band = [r for r in rows if r["ac_best"] is not None
            and args.min_held <= r["ac_best"] <= args.max_held]
    # easiest first: shortest held best, then smallest presentation
    band.sort(key=lambda r: (r["ac_best"], len(r["relators"][0]) + len(r["relators"][1])))
    band = band[:args.limit]
    out = REPO / args.out
    out.mkdir(parents=True, exist_ok=True)
    print(f"{len(band)} challenges with held best {args.min_held}-{args.max_held}, "
          f"cap slack {args.cap_slack}, depth {args.max_depth}, {args.workers} workers",
          flush=True)

    found = scoring = 0
    with (out / "solutions.jsonl").open("a", encoding="utf-8") as log, \
            ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(work, (r, args.cap_slack, args.max_depth, args.budget_s))
                   for r in band]
        for fut in as_completed(futures):
            r, ac, stable, secs, note = fut.result()
            size = len(r["relators"][0]) + len(r["relators"][1])
            if ac is None:
                print(f"  {r['id']} held {r['ac_best']:>3} size {size:>2}: "
                      f"none inside the cap ({secs:.0f}s){' ' + note if note else ''}",
                      flush=True)
                continue
            found += 1
            scores = len(ac) <= r["ac_best"]
            scoring += scores
            stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            for problem, moves in (("ac", ac), ("stable_ac", stable)):
                log.write(json.dumps({"id": r["id"], "problem": problem,
                                      "length": len(moves), "moves": moves,
                                      "relators": r["relators"], "found_at": stamp,
                                      "cfg": {"method": "bidirectional"}}) + "\n")
            log.flush()
            print(f"  {r['id']} held ac {r['ac_best']:>3} (k {r['ac_k']}) sac "
                  f"{str(r['sac_best']):>3}: ours ac {len(ac):>3} sac {len(stable):>3} "
                  f"({secs:.0f}s){'  <-- SCORES' if scores else ''}", flush=True)
    print(f"\nsolved {found}/{len(band)}, scoring {scoring}", flush=True)


if __name__ == "__main__":
    main()
