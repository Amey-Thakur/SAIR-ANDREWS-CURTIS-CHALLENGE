"""Run the repo's detour shortening over paths the beam produced.

`jit_tieband.py` has always passed its finds through `engine.shorten`; the beam
in `policy_solve.py` never did, so every path it has reported is unshortened.
That matters at the margin the beam now sits on: several single-holder
challenges came back one move over the record, and shortening has measured
about 2 percent on paths of this length, which is one move on forty.

Each shortened path is replayed through src.ac.verify before it is kept, and
only paths at or under the record are written out, in the campaign schema so
`submit.py` can read them.

Usage (from the repo root):
  python runs/pool/policy_shorten.py runs/pool/policy/k1_len16k.jsonl \
      runs/pool/policy/resp_256k.jsonl --max-gap 8 --depth 4 \
      --out runs/pool/policy/shortened
"""
import argparse
import datetime as dt
import json
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--max-gap", type=int, default=8,
                    help="only try paths this many moves or fewer over the "
                         "record; shortening gains a couple of percent, so a "
                         "path thirty moves over is not a candidate")
    ap.add_argument("--depth", type=int, default=4)
    ap.add_argument("--out", default="runs/pool/policy/shortened")
    args = ap.parse_args()

    rows = {r["ac_id"]: r for r in
            (json.loads(l) for l in
             open(REPO / "runs/pool/pool.jsonl", encoding="utf-8"))}

    best = {}
    for f in args.files:
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

    cand = []
    for c, r in best.items():
        rec = rows[c]["ac_best"]
        if rec is None:
            continue
        gap = r["length"] - rec
        if 0 < gap <= args.max_gap:
            cand.append((gap, c, rec, r))
    cand.sort()
    print(f"{len(cand)} paths within {args.max_gap} of the record, "
          f"shorten depth {args.depth}", flush=True)

    out = REPO / args.out
    out.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    won = 0
    with (out / "solutions.jsonl").open("a", encoding="utf-8") as log:
        for gap, c, rec, r in cand:
            pool = rows[c]
            start = tuple(tuple(w) for w in pool["relators"])
            ids = list(r["moves"])
            t0 = time.time()
            for d in range(2, args.depth + 1):
                try:
                    cut = E.shorten(start, ids, depth=d)
                except Exception as exc:
                    print(f"  {c}: shorten depth {d} failed: {exc}", flush=True)
                    continue
                if len(cut) < len(ids):
                    ids = cut
            el = time.time() - t0
            ac = [E.to_move(m) for m in ids]
            stable = ac + [Destabilize(1), Destabilize(0)]
            begin = Presentation(2, start)
            ok = verify(begin, ac, stable=False) and verify(begin, stable,
                                                            stable=True)
            scores = ok and len(ac) <= rec
            won += scores
            print(f"  {c} record {rec} (k {pool['ac_k']}): {r['length']} -> "
                  f"{len(ac)} verify={ok} ({el:.0f}s)"
                  f"{'  <-- SCORES' if scores else ''}", flush=True)
            if not scores:
                continue
            for problem, moves in (("ac", ac), ("stable_ac", stable)):
                log.write(json.dumps(
                    {"id": pool["id"], "problem": problem,
                     "length": len(moves),
                     "moves": [move_to_json(m) for m in moves],
                     "relators": pool["relators"], "found_at": stamp,
                     "cfg": {"method": "beam-length+shorten",
                             "depth": args.depth}}) + "\n")
            log.flush()
    print(f"\n{won} of {len(cand)} now at or under the record", flush=True)


if __name__ == "__main__":
    main()
