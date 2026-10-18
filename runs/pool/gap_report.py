"""The near-miss gap distribution, with the actual move sequences attached.

`reconcile.py` answers "is anything left to send" by counting buckets against
the live board. It throws the moves away, so it cannot answer the question a
shortener needs: how many moves short of the record is each path we hold, and
where is that path stored.

This writes one work file, `runs/pool/work/near_<problem>.jsonl`, one line per
challenge where we hold a path LONGER than the current record:

    {"id", "problem", "record", "k", "ours", "gap", "relators", "moves", "src"}

Records come from the refreshed pool file, not from the API, so run
`refresh_pool.py` first. Nothing is sent and nothing is submitted.
"""
import collections
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
POOL = REPO / "runs" / "pool"
OUT = POOL / "work"

PREFIX = {"ac": "ac-", "stable_ac": "sac-"}


def load_pool():
    rows = {}
    with open(POOL / "pool.jsonl", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            rows[r["id"]] = r
    return rows


def best_on_disk():
    """(problem, id) -> (length, moves, source file)."""
    best = {}
    for path in sorted(POOL.rglob("*.jsonl")):
        if path.parent.name == "work":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line[0] != "{":
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            moves = r.get("moves")
            if not moves or "id" not in r:
                continue
            problem = r.get("problem")
            if problem not in PREFIX:
                continue
            key = (problem, str(r["id"]))
            length = r.get("length") or len(moves)
            if key not in best or length < best[key][0]:
                best[key] = (length, moves, str(path.relative_to(REPO)))
    return best


def main():
    pool = load_pool()
    best = best_on_disk()
    OUT.mkdir(exist_ok=True)
    print(f"  {len(best)} (problem, id) paths on disk")

    for problem in ("ac", "stable_ac"):
        key_best = "ac_best" if problem == "ac" else "sac_best"
        key_k = "ac_k" if problem == "ac" else "sac_k"
        gaps = collections.Counter()
        rows = []
        for (prob, cid), (length, moves, src) in best.items():
            if prob != problem:
                continue
            pr = pool.get(cid)
            if not pr or pr[key_best] is None:
                continue
            rec, k = pr[key_best], pr[key_k]
            if length <= rec:
                continue
            rows.append({"id": cid, "problem": problem, "record": rec, "k": k,
                         "ours": length, "gap": length - rec,
                         "relators": pr["relators"], "moves": moves,
                         "src": src})
            gaps[length - rec] += 1
        rows.sort(key=lambda r: (r["gap"], r["record"]))
        out = OUT / f"near_{problem}.jsonl"
        with open(out, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        print(f"\n  {problem}: {len(rows)} near misses -> {out.name}")
        cum = 0
        for g in sorted(gaps):
            cum += gaps[g]
            if g <= 12 or g % 10 == 0:
                print(f"      gap {g:4}  {gaps[g]:4}   cumulative {cum:4}")
        if rows:
            med = rows[len(rows) // 2]
            print(f"      median gap {med['gap']}, "
                  f"ratio min {min(r['ours'] / r['record'] for r in rows):.3f}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
