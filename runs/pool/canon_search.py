"""Search over canonical presentations instead of exact ones.

Plain greedy keys its visited set on the exact pair of words, so it re-explores
presentations that differ only by a conjugation, and the budget drains into
duplicates. This collapses each state to a canonical representative first:
every relator is cyclically reduced, and each is replaced by its inverse when
that is smaller. Both steps are performed with real moves, conjugations and
inversions, so the path this returns still replays under the official verifier.

Canonicalising costs moves, so paths come out longer than greedy's. That is the
right trade for the 3,505 challenges nobody has solved, where any verified path
is a full point and length is irrelevant.

Usage (from the repo root):
  python runs/pool/canon_search.py --count 12 --nodes 300000 --workers 4
  python runs/pool/canon_search.py --count 12 --nodes 300000 --workers 4 --plain
"""
import argparse
import datetime as dt
import heapq
import itertools
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

CONJ_INDEX = {c: i for i, c in enumerate(E.CONJ)}


def cyclically_reduce(state):
    """Conjugate each relator until no letter cancels across its ends.

    r = a w a^-1 becomes w by conjugating with a^-1, which is one move."""
    moves = []
    for i in (0, 1):
        while True:
            r = state[i]
            if len(r) < 2 or r[0] != -r[-1]:
                break
            c = -r[0]
            mid = (6 if i == 0 else 10) + CONJ_INDEX[c]
            state = E.step(state, mid)
            moves.append(mid)
            if not state[i]:
                break
    return state, moves


def canonical(state):
    """A canonical representative, with the moves that reach it."""
    state, moves = cyclically_reduce(state)
    for i in (0, 1):
        r = state[i]
        if r and E.invert(r) < r:
            state = E.step(state, i)
            moves.append(i)
    return state, moves


def search(start, max_nodes, cap, plain=False):
    """Best first on total relator length over canonical states.

    Returns the move ids to a trivial state, or None."""
    pre = []
    s0 = start
    if not plain:
        s0, pre = canonical(start)
    if s0 in E.FINISH_AC:
        return pre
    parent = {s0: None}
    counter = itertools.count()
    heap = [(len(s0[0]) + len(s0[1]), 0, next(counter), s0)]
    while heap and len(parent) < max_nodes:
        _, depth, _, s = heapq.heappop(heap)
        for mid, t in E.expand(s):
            a, b = t
            if not a or not b:
                continue
            edge = [mid]
            if not plain:
                t, extra = canonical(t)
                a, b = t
                if not a or not b:
                    continue
                edge += extra
            if t in parent:
                continue
            if cap and (len(a) > cap or len(b) > cap):
                continue
            parent[t] = (s, edge)
            if t in E.FINISH_AC:
                out = []
                node = t
                while parent[node] is not None:
                    prev, moves = parent[node]
                    out = moves + out
                    node = prev
                return pre + out
            heapq.heappush(heap, (len(a) + len(b), depth + 1, next(counter), t))
    return None


def work(task):
    r, nodes, plain = task
    start = tuple(tuple(w) for w in r["relators"])
    cap = 3 * max(len(start[0]), len(start[1])) + 8
    t0 = time.time()
    ids = search(start, nodes, cap, plain=plain)
    if ids is None:
        return r, None, None, time.time() - t0
    end = E.replay(start, ids)[-1]
    core = E.shorten(start, ids) if len(ids) <= 4000 else ids
    ac = [E.to_move(m) for m in E.shorten(start, core + E.FINISH_AC[end])]
    stable = min([E.to_move(m) for m in core] + E.FINISH_STABLE[end],
                 ac + [Destabilize(1), Destabilize(0)], key=len)
    begin = Presentation(2, start)
    if not verify(begin, ac, stable=False) or not verify(begin, stable, stable=True):
        raise AssertionError("canonical search produced an unverifiable path")
    return (r, [move_to_json(m) for m in ac],
            [move_to_json(m) for m in stable], time.time() - t0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=12)
    ap.add_argument("--skip", type=int, default=0)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--nodes", type=int, default=300_000)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--plain", action="store_true",
                    help="exact states, for the side-by-side comparison")
    ap.add_argument("--out", default="runs/pool/canon")
    args = ap.parse_args()

    import random
    rows = [json.loads(l) for l in open(REPO / "runs/pool/pool.jsonl", encoding="utf-8")]
    unsolved = [r for r in rows if r["ac_best"] is None]
    random.Random(args.seed).shuffle(unsolved)
    chosen = unsolved[args.skip:args.skip + args.count]
    out = REPO / args.out
    out.mkdir(parents=True, exist_ok=True)
    mode = "plain (exact states)" if args.plain else "canonical"
    print(f"{mode}: {len(chosen)} unsolved challenges, {args.nodes:,} nodes, "
          f"{args.workers} workers", flush=True)

    found = 0
    with (out / "solutions.jsonl").open("a", encoding="utf-8") as log, \
            ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(work, (r, args.nodes, args.plain)) for r in chosen]
        for fut in as_completed(futures):
            r, ac, stable, secs = fut.result()
            size = len(r["relators"][0]) + len(r["relators"][1])
            if ac is None:
                print(f"  {r['id']} size {size:>2}: not found ({secs:.0f}s)", flush=True)
                continue
            found += 1
            stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            if not args.plain:
                for problem, moves in (("ac", ac), ("stable_ac", stable)):
                    log.write(json.dumps({"id": r["id"], "problem": problem,
                                          "length": len(moves), "moves": moves,
                                          "relators": r["relators"], "found_at": stamp,
                                          "cfg": {"method": "canonical"}}) + "\n")
                log.flush()
            print(f"  {r['id']} size {size:>2}: FOUND ac {len(ac)} stable {len(stable)} "
                  f"({secs:.0f}s)", flush=True)
    print(f"\n{mode}: found {found} of {len(chosen)}", flush=True)


if __name__ == "__main__":
    main()
