"""Convert beam-search results into the campaign's solutions.jsonl.

policy_solve.py records a path as bare move ids, because that is all the beam
needs.  The submit harness reads the campaign schema and refuses anything the
repo verifier does not replay, so every path is replayed here through
src.ac.verify before it is written, on both boards, exactly as jit_tieband does.

Only paths at or under the current record are exported: a longer path cannot
score and submit would drop it anyway.

Usage (from the repo root):
  python runs/pool/policy_export.py runs/pool/policy/k1_len16k.jsonl \
      --out runs/pool/policy/send
"""
import argparse
import datetime as dt
import json
import pathlib
import sys

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
    ap.add_argument("--out", default="runs/pool/policy/send")
    args = ap.parse_args()

    rows = {r["ac_id"]: r for r in
            (json.loads(l) for l in
             open(REPO / "runs/pool/pool.jsonl", encoding="utf-8"))}

    best = {}
    for f in args.files:
        for line in open(REPO / f, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            if not r.get("verified"):
                continue
            cid = r["challenge_id"]
            pool = rows.get(cid)
            if pool is None or pool["ac_best"] is None:
                continue
            if r["length"] > pool["ac_best"]:
                continue
            if cid not in best or r["length"] < best[cid]["length"]:
                best[cid] = r

    out = REPO / args.out
    out.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    n = 0
    with (out / "solutions.jsonl").open("a", encoding="utf-8") as log:
        for cid, r in sorted(best.items()):
            pool = rows[cid]
            start = tuple(tuple(w) for w in pool["relators"])
            ac = [E.to_move(m) for m in r["moves"]]
            stable = ac + [Destabilize(1), Destabilize(0)]
            begin = Presentation(2, start)
            if not verify(begin, ac, stable=False):
                raise AssertionError(f"{cid}: ac path does not replay")
            if not verify(begin, stable, stable=True):
                raise AssertionError(f"{cid}: stable path does not replay")
            for problem, moves in (("ac", ac), ("stable_ac", stable)):
                log.write(json.dumps(
                    {"id": pool["id"], "problem": problem,
                     "length": len(moves),
                     "moves": [move_to_json(m) for m in moves],
                     "relators": pool["relators"], "found_at": stamp,
                     "cfg": {"method": "beam-length", "beam": r.get("beam")}})
                    + "\n")
            n += 1
            print(f"  {cid}: {r['length']} against record {pool['ac_best']} "
                  f"(k {pool['ac_k']}) verified on both boards", flush=True)
    print(f"\n{n} challenges written to {out / 'solutions.jsonl'}", flush=True)


if __name__ == "__main__":
    main()
