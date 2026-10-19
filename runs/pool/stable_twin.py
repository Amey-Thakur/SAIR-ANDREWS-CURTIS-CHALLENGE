"""Derive the stable_ac twin of every ac path in a run directory.

Our stable path is the ordinary descent plus two destabilisations, and that
construction is exact: over the 396 challenges solved on this machine, our
stable length minus our ac length is 2 on 393 of them. So any ac path of length
L gives a verified stable path of length L + 2 for no search at all, and
whenever `L + 2 <= sac_best` that is a scoring submission the run that produced
the ac path never emitted.

This matters because a shortener run writes only the board it was pointed at. A
one-move ac improvement that merely ties a record shared eleven ways can carry a
stable tie on a record shared eight ways, which pays more; and where
`sac_best - ac_best >= 3` it is an outright stable BEAT.

Every derived path is replayed through `src.ac.verify` on the stable board
before it is written, and `src.harness.submit` replays it again through the
official verifier before sending.

Usage (from the repo root):
  python runs/pool/stable_twin.py runs/pool/wid_g3_ac --out runs/pool/twins
"""
import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from src.ac.moves import (Conjugate, Destabilize, Invert,      # noqa: E402
                          Multiply, Stabilize)
from src.ac.presentation import Presentation                   # noqa: E402
from src.ac.verify import verify                               # noqa: E402
from src.search.campaign import move_to_json                   # noqa: E402


def rebuild(m):
    k = m["move"]
    if k == "invert":
        return Invert(m["i"])
    if k == "multiply":
        return Multiply(m["i"], m["j"], m["sign"])
    if k == "conjugate":
        return Conjugate(m["i"], m["c"])
    if k == "destabilize":
        return Destabilize(m["i"])
    if k == "stabilize":
        return Stabilize()
    raise ValueError(f"unknown move {m}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--out", default="runs/pool/twins")
    args = ap.parse_args()

    pool = {}
    for line in open(REPO / "runs/pool/pool.jsonl", encoding="utf-8"):
        r = json.loads(line)
        pool[r["id"]] = r

    # the shortest ac path in the given directories
    best = {}
    for d in args.dirs:
        p = pathlib.Path(d) / "solutions.jsonl"
        if not p.exists():
            print(f"  {p} does not exist")
            continue
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if not line or line[0] != "{":
                continue
            r = json.loads(line)
            if r.get("problem") != "ac" or not r.get("moves"):
                continue
            cid = str(r["id"])
            ln = r.get("length") or len(r["moves"])
            if cid not in best or ln < best[cid][0]:
                best[cid] = (ln, r["moves"])

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    written = beats = ties = 0
    with (out / "solutions.jsonl").open("a", encoding="utf-8") as fh:
        for cid, (L, moves) in sorted(best.items()):
            row = pool.get(cid)
            if not row:
                continue
            sb = row["sac_best"]
            # sb is None when nobody has solved the stable problem either, and
            # then ANY verified path is a full point, whatever its length
            if sb is not None and L + 2 > sb:
                print(f"  ac-{cid}: ac {L} -> stable {L + 2}, stable record "
                      f"{sb}; {L + 2 - sb} over, nothing to send")
                continue
            start = tuple(tuple(w) for w in row["relators"])
            stable = [rebuild(m) for m in moves] + [Destabilize(1),
                                                    Destabilize(0)]
            chk = verify(Presentation(2, start), stable, stable=True)
            if not chk:
                print(f"  ac-{cid}: VERIFIER REJECTED the twin: {chk.reason}")
                continue
            kind = ("takes an UNSOLVED challenge" if sb is None else
                    "BEATS" if L + 2 < sb else "ties")
            beats += sb is None or L + 2 < sb
            ties += sb is not None and L + 2 == sb
            where = ("no stable record exists" if sb is None else
                     f"the stable record {sb} (k {row['sac_k']})")
            print(f"  ac-{cid}: ac {L} -> stable {len(stable)}, {kind}, "
                  f"{where}")
            fh.write(json.dumps(
                {"id": cid, "problem": "stable_ac", "length": len(stable),
                 "moves": [move_to_json(m) for m in stable],
                 "record_at_find": sb}) + "\n")
            written += 1
    print(f"\n  {written} stable twins written: {beats} beat a record, "
          f"{ties} tie one")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
