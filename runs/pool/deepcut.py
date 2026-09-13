"""Does deeper detour shortening close the 10 percent gap?

Depth 3 cut only about 2 percent, not enough to beat a record. The detour ball
is bounded by the relator cap as well as by depth, so going deeper may stay
affordable. If depth 5 reaches 10 to 15 percent then the ball search, which
finds far more paths than the exact search, becomes worth using after all.
"""
import json
import os
import pathlib
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from src.ac.presentation import Presentation  # noqa: E402
from src.ac.verify import move_to_json, verify  # noqa: E402
from src.search import engine as E  # noqa: E402

ID_OF = {json.dumps(move_to_json(E.to_move(k)), sort_keys=True): k
         for k in range(14)}

byid = {r["id"]: r for r in
        (json.loads(l) for l in open(REPO / "runs/pool/pool.jsonl", encoding="utf-8"))}

seen, cases = set(), []
for name in ("ball88cut", "ball31", "ball61s2"):
    f = REPO / "runs/pool" / name / "solutions.jsonl"
    if not f.exists():
        continue
    for line in open(f, encoding="utf-8"):
        rec = json.loads(line)
        if rec["problem"] != "ac" or rec["id"] in seen:
            continue
        seen.add(rec["id"])
        cases.append(rec)

print(f"{len(cases)} found paths available, testing up to 5\n", flush=True)
for rec in cases[:5]:
    r = byid[rec["id"]]
    start = tuple(tuple(w) for w in rec["relators"])
    try:
        ids = [ID_OF[json.dumps(m, sort_keys=True)] for m in rec["moves"]]
    except KeyError as exc:
        print(f"{r['ac_id']}: unrecognised move {exc}, skipping", flush=True)
        continue
    print(f"{r['ac_id']}: record {r['ac_best']}, ours {len(ids)}", flush=True)
    for depth in (3, 4, 5):
        t0 = time.time()
        try:
            cut = E.shorten(start, ids, depth=depth)
        except Exception as exc:
            print(f"   depth {depth}: failed, {exc}", flush=True)
            continue
        ok = verify(Presentation(2, start), [E.to_move(m) for m in cut],
                    stable=False)
        pct = 100.0 * (len(ids) - len(cut)) / len(ids)
        print(f"   depth {depth}: {len(ids)} -> {len(cut)} ({pct:.1f}% cut, "
              f"{time.time()-t0:.0f}s, verified {ok})"
              f"{'   BEATS THE RECORD' if len(cut) <= r['ac_best'] else ''}",
              flush=True)
os._exit(0)
