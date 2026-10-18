"""Widen the box on the twenty targets where a beat is still arithmetically
possible, using the TRUE minimum between two states on a path we hold.

Why these twenty and no others. Cross-tabulating the 247 `ac` and 265
`stable_ac` near misses by (k, gap) says where a beat can come from at all:

         k   gap<=3    4-6   7-12    13+          (ac)
      k<=3        1      0      0      5
     k 4-7        2      2      3     18
      k>=8       45     39     73     59

A high k means many teams independently found that length, so the record is
almost certainly the true minimum and no amount of box is going to get under
it - which is exactly what `bishorten` measured: it landed ON the record
fourteen times across both boards and never once below. A large gap means no
local reoptimisation can close it. So the only cell that can pay is low k AND
small gap, and it holds 5 challenges on `ac` and 15 on `stable_ac`.

What widening means here. `shortcut.py` asked the exact search for the minimum
between s_i and s_j, but only over spans 6 to 22 and inside a box of (the
longest state IN THAT WINDOW) + 2. Both limits are lifted: every span up to the
whole path, and a box of (the longest state on the WHOLE path) + a slack that is
walked upward, so a shortcut is allowed to pass through states longer than
anything the window itself contains.

The stop condition is `total < rec`, strictly. Landing on a record pays
2^(1-k); passing it pays 1.0 and drops the holder to zero.

Usage (from the repo root):
  python runs/pool/widen.py --problem ac --out runs/pool/wid_ac
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

from bishorten import (replay, split_path, _as_json, _rebuild)   # noqa: E402
from jit_engine import MAXLEN                                    # noqa: E402
from shortcut import between                                     # noqa: E402
from src.ac.presentation import Presentation                     # noqa: E402
from src.ac.verify import verify                                 # noqa: E402
from src.search.engine import to_move                            # noqa: E402


def targets(problem, max_k, max_gap):
    rows = [json.loads(l) for l in
            open(REPO / f"runs/pool/work/near_{problem}.jsonl",
                 encoding="utf-8")]
    sel = [r for r in rows if r["k"] <= max_k and r["gap"] <= max_gap]
    sel.sort(key=lambda r: -r["record"])
    return sel


def seed(rows, problem, files):
    """Replace each stored path with the shortest one any earlier run wrote."""
    shorter = {}
    for f in files:
        p = pathlib.Path(f)
        if not p.exists():
            continue
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if not line or line[0] != "{":
                continue
            r = json.loads(line)
            if r.get("problem") != problem or not r.get("moves"):
                continue
            k = str(r["id"])
            ln = r.get("length") or len(r["moves"])
            if k not in shorter or ln < shorter[k][0]:
                shorter[k] = (ln, r["moves"])
    n = 0
    for row in rows:
        s = shorter.get(row["id"])
        if s and s[0] < row["ours"]:
            row["ours"], row["moves"] = s[0], s[1]
            n += 1
    return n


def sweep(start, mids, slack, span_min, span_max, nodes, bits, budget, rec,
          tail, log):
    """Splice in exact-minimum routes, widest span first, until the clock or
    the strict beat condition stops it.

    Returns (mids, moves saved, windows tried, windows the search could not
    reach, True when it beat the record)."""
    best = list(mids)
    saved = tried = unreached = 0
    t0 = time.time()
    changed = True
    while changed:
        changed = False
        states = replay(start, best)
        n = len(best)
        gmax = max(len(a) + len(b) for a, b in states)
        cap = gmax + slack
        if cap + 2 > MAXLEN:
            log(f"      cap {cap} needs ACC_MAXLEN above {MAXLEN}; skipped")
            return best, saved, tried, unreached, False
        # Spans ASCENDING. A wider box is harder to exhaust, not easier, so
        # the exact search has a reach frontier in span; once a whole span is
        # unreachable every wider one is too, and the sweep stops there rather
        # than spending the budget proving it again. Spans below span_min are
        # skipped because the ball shortener already searched them completely.
        for span in range(span_min, min(n, span_max) + 1):
            hit = 0
            for i in range(0, n - span + 1):
                if time.time() - t0 > budget:
                    log(f"      budget spent at span {span}")
                    return best, saved, tried, unreached, False
                j = i + span
                tried += 1
                seg, _ = between(states[i], states[j], cap, nodes, bits)
                if seg is None:
                    unreached += 1
                    continue
                hit += 1
                if len(seg) >= span:
                    continue
                if replay(states[i], seg)[-1] != states[j]:
                    log(f"      ({i},{j}) hash collision, rejected")
                    continue
                log(f"      ({i},{j}) span {span} -> {len(seg)} at cap {cap}")
                best = best[:i] + seg + best[j:]
                saved += span - len(seg)
                changed = True
                break
            if changed:
                break
            if hit == 0:
                log(f"      reach frontier: span {span} wholly unreachable "
                    f"at cap {cap}, {n - span + 1} windows")
                break
        if len(best) + len(tail) < rec:
            return best, saved, tried, unreached, True
    return best, saved, tried, unreached, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--problem", default="ac", choices=("ac", "stable_ac"))
    ap.add_argument("--max-k", type=int, default=7)
    ap.add_argument("--max-gap", type=int, default=6)
    ap.add_argument("--slacks", default="2,4,6")
    ap.add_argument("--span-max", type=int, default=40)
    ap.add_argument("--span-min", type=int, default=6)
    ap.add_argument("--nodes", type=int, default=1_200_000)
    ap.add_argument("--bits", type=int, default=21)
    ap.add_argument("--budget", type=float, default=600.0,
                    help="seconds per target per slack")
    ap.add_argument("--out", default="runs/pool/wid")
    args = ap.parse_args()

    def log(s):
        print(s, flush=True)

    rows = targets(args.problem, args.max_k, args.max_gap)
    n = seed(rows, args.problem,
             [REPO / "runs/pool/bs5_ac/solutions.jsonl",
              REPO / "runs/pool/bs5_stable_ac/solutions.jsonl",
              REPO / "runs/pool/bslow/solutions.jsonl"])
    log(f"  widen {args.problem}: {len(rows)} targets, {n} seeded shorter, "
        f"MAXLEN {MAXLEN}")
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sol = open(out / "solutions.jsonl", "a", encoding="utf-8")
    stable = args.problem == "stable_ac"
    between(((1,), (2,)), ((1,), (2,)), 8, 1000, 12)     # warm the compiler

    beats = 0
    for idx, row in enumerate(rows, 1):
        start = tuple(tuple(r) for r in row["relators"])
        mids, tail = split_path(row["moves"])
        rec = row["record"]
        cur = list(mids)
        total0 = len(cur) + len(tail)
        log(f"\n  [{idx}/{len(rows)}] {args.problem} {row['id']} record {rec} "
            f"(k {row['k']}) holding {total0}, needs "
            f"{total0 - rec + 1} moves for a beat")
        won = False
        for slack in [int(x) for x in args.slacks.split(",")]:
            t0 = time.time()
            cur, saved, tried, unreached, won = sweep(
                start, cur, slack, args.span_min, args.span_max, args.nodes,
                args.bits, args.budget, rec, tail, log)
            total = len(cur) + len(tail)
            log(f"      slack {slack}: {total0} -> {total}, saved {saved}, "
                f"{tried} windows, {unreached} unreached, "
                f"{time.time() - t0:.0f}s"
                f"{'   BEAT' if won else ''}")
            if won:
                break
        total = len(cur) + len(tail)
        if total >= total0:
            continue
        moves = [to_move(m) for m in cur] + [_rebuild(m) for m in tail]
        chk = verify(Presentation(2, start), moves, stable=stable)
        if not chk:
            log(f"      VERIFIER REJECTED: {chk.reason}")
            continue
        sol.write(json.dumps({"id": row["id"], "problem": args.problem,
                              "length": total,
                              "moves": [_as_json(m) for m in moves],
                              "record_at_find": rec, "was": total0}) + "\n")
        sol.flush()
        beats += total < rec
    sol.close()
    log(f"\n  {len(rows)} targets, {beats} BEAT a record")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
