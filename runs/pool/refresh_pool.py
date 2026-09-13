"""Rebuild runs/pool/pool.jsonl from the live snapshot.

Records only ever improve, and they move fast. A stale pool sends the search
after targets that have already been beaten, so every win it reports is
rejected at submission time as no longer scoring. Refresh before any campaign
of work, not once a night.
"""
import json
import os
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from src.harness.submit import call  # noqa: E402


def snapshot(problem):
    """challengeId -> (best, kTeams). The endpoint returns the whole pool in one
    response and rejects include=initialRelators, so relators are carried over
    from the existing pool file; they never change."""
    code, body, _ = call("GET",
                         f"/competitions/acc/discoveries/snapshot?problem={problem}")
    if code != 200:
        raise SystemExit(f"{problem} snapshot: HTTP {code} {str(body)[:200]}")
    data = body["data"]
    out = {it["challengeId"]: (it["currentBestLength"], it["kTeams"])
           for it in data["items"]}
    print(f"  {problem}: {len(out)} challenges, generated {data['generatedAt']}",
          flush=True)
    return out


ac = snapshot("ac")
sac = snapshot("stable_ac")

old = {}
p = REPO / "runs/pool/pool.jsonl"
if p.exists():
    for line in open(p, encoding="utf-8"):
        r = json.loads(line)
        old[r["ac_id"]] = r

rows, moved = [], 0
for cid, (best, k) in sorted(ac.items()):
    num = cid.split("-", 1)[1]
    prev = old.get(cid)
    if prev is None:
        continue
    relators = prev["relators"]
    sb, sk = sac.get(f"sac-{num}", (None, 0))
    if prev and prev["ac_best"] != best:
        moved += 1
    rows.append({"id": num, "ac_id": cid, "sac_id": f"sac-{num}",
                 "relators": relators, "ac_best": best, "ac_k": k,
                 "sac_best": sb, "sac_k": sk})

tmp = p.with_suffix(".jsonl.new")
with tmp.open("w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
tmp.replace(p)
print(f"\n{len(rows)} challenges written; {moved} records changed since the old pool")
os._exit(0)
