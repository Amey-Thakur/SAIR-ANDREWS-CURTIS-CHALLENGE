"""Re-solve every SUFFIX of a known path with the exact search.

The exact bidirectional search settles a challenge when the true minimum fits
inside cap = size + a small slack, and its reach is governed by the SIZE of the
presentation it starts from. Everything this campaign has tried applies it to the
start presentation: the cap walk re-solves from move 0, where ac-00678 has total
relator length 35 and the box is hopeless. But a path descends. Thirty moves
along, the same path sits at total length 11, and there cap = 11 + 4 is a box the
exact search settles completely.

So walk the path and re-solve each suffix exactly. At position i the state is
s_i, the tail we hold costs len(path) - i moves, and the exact search returns the
TRUE MINIMUM from s_i to (x, y) inside cap = size(s_i) + slack. If that is
shorter than the tail we hold, splice it in and the total drops.

This is not `engine.shorten`, which replaces a stretch between two states already
on the path using detours of radius at most `depth` and measured 0 of 6 on beam
paths. It is not the cap walk, which re-solves from move 0 only. It is the exact
solver applied where its own constraint is weakest: at the small states a long
path passes through on its way down.

Validated with a planted control before being trusted: take a path we know is
optimal, splice a detour into its tail, and check that this recovers the original
length.

Usage (from the repo root):
  python runs/pool/suffix_opt.py --paths runs/pool/policy/k1_close_64k.jsonl \\
      --ids runs/pool/policy/two_resp.txt --nodes 4000000 --max-slack 4
"""
import argparse
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


def improve(start, mids, nodes, bits, max_slack, verbose=True):
    """Best path found by re-solving every suffix of `mids` exactly."""
    best = list(mids)
    states = E.replay(start, best)
    i = 0
    tried = hits = 0
    while i < len(best):
        st = states[i]
        size = len(st[0]) + len(st[1])
        tail = len(best) - i
        if tail < 2:
            break
        got = None
        for slack in range(0, max_slack + 1):
            cap = size + slack
            if cap + 2 > MAXLEN:
                break
            tried += 1
            ids, _ = solve_bidir([list(st[0]), list(st[1])], cap, nodes, bits)
            if ids is not None and len(ids) < tail and (got is None
                                                        or len(ids) < len(got)):
                got = list(ids)
        if got is not None:
            hits += 1
            if verbose:
                print(f"    position {i:>3} (size {size:>3}): tail {tail} -> "
                      f"{len(got)}", flush=True)
            best = best[:i] + got
            states = E.replay(start, best)
            # the splice changed everything after i, so continue from here
            continue
        i += 1
    return best, tried, hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", nargs="+",
                    default=["runs/pool/policy/k1_close_64k.jsonl"])
    ap.add_argument("--ids", default="runs/pool/policy/two_resp.txt")
    ap.add_argument("--nodes", type=int, default=4_000_000)
    ap.add_argument("--bits", type=int, default=22)
    ap.add_argument("--max-slack", type=int, default=4)
    ap.add_argument("--check", action="store_true",
                    help="planted control: splice a detour into an optimal "
                         "path and confirm this recovers the original length")
    ap.add_argument("--out", default="runs/pool/policy/suffix")
    args = ap.parse_args()

    rows = {r["ac_id"]: r for r in
            (json.loads(l) for l in
             open(REPO / "runs/pool/pool.jsonl", encoding="utf-8"))}

    if args.check:
        # A challenge whose record we reproduce exactly, so its path is optimal.
        cand = [r for r in rows.values() if r["ac_best"] is not None
                and 10 <= r["ac_best"] <= 13]
        cand.sort(key=lambda r: r["ac_best"])
        ok = bad = 0
        for r in cand[:4]:
            start = tuple(tuple(w) for w in r["relators"])
            base, _ = solve_bidir(r["relators"],
                                  len(start[0]) + len(start[1]) + 6,
                                  2_000_000, 21)
            if base is None:
                continue
            base = list(base)
            # plant a detour in the TAIL: move 0 is an involution, so 0,0 is a
            # two-move cycle that lengthens the path without changing where it
            # ends. Two of them, six moves in, gives four wasted moves.
            k = max(1, len(base) - 3)
            spoilt = base[:k] + [0, 0, 0, 0] + base[k:]
            got, tried, hits = improve(start, spoilt, 2_000_000, 21, 4,
                                       verbose=False)
            good = len(got) <= len(base)
            ok += good
            bad += not good
            print(f"  {r['ac_id']} record {r['ac_best']}: optimal {len(base)}, "
                  f"spoilt {len(spoilt)}, recovered {len(got)} "
                  f"({hits} splices from {tried} searches)"
                  f"{'' if good else '   FAILED'}", flush=True)
        print(f"\ncontrol: {ok} recovered, {bad} failed", flush=True)
        os._exit(0)

    best = {}
    for f in args.paths:
        p = REPO / f
        if not p.exists():
            continue
        for line in open(p, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            if not r.get("verified"):
                continue
            c = r["challenge_id"]
            if c not in best or r["length"] < best[c]["length"]:
                best[c] = r
    want = [l.split()[0] for l in
            open(REPO / args.ids, encoding="utf-8") if l.strip()]

    out = REPO / args.out
    out.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    scored = 0
    with (out / "solutions.jsonl").open("a", encoding="utf-8") as log:
        for c in want:
            if c not in best:
                print(f"  {c}: no stored path", flush=True)
                continue
            pool = rows[c]
            rec = pool["ac_best"]
            start = tuple(tuple(w) for w in pool["relators"])
            t0 = time.time()
            print(f"  {c} record {rec} (k {pool['ac_k']}), from "
                  f"{best[c]['length']} moves:", flush=True)
            got, tried, hits = improve(start, best[c]["moves"], args.nodes,
                                       args.bits, args.max_slack)
            el = time.time() - t0
            ac = [E.to_move(m) for m in got]
            stable = ac + [Destabilize(1), Destabilize(0)]
            begin = Presentation(2, start)
            vok = (verify(begin, ac, stable=False).ok
                   and verify(begin, stable, stable=True).ok)
            sc = vok and rec is not None and len(ac) <= rec
            scored += sc
            print(f"    -> {len(ac)} against record {rec}, verify={vok}, "
                  f"{hits} splices from {tried} exact searches, {el:.0f}s"
                  f"{'   <-- SCORES' if sc else ''}", flush=True)
            if not sc:
                continue
            for problem, moves in (("ac", ac), ("stable_ac", stable)):
                log.write(json.dumps(
                    {"id": pool["id"], "problem": problem,
                     "length": len(moves),
                     "moves": [move_to_json(m) for m in moves],
                     "relators": pool["relators"], "found_at": stamp,
                     "cfg": {"method": "beam+suffix-exact"}}) + "\n")
            log.flush()
    print(f"\n{scored} at or under the record", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()
