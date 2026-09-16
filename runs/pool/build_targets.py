"""Rebuild both retry lists from the CURRENT pool and our ledger.

Two kinds of pre-qualified target, both of which need a path we already hold so
the cap walk knows a solution exists nearby:

  near miss  - we have a path but it is longer than the record
  live tie   - we hold the record jointly, and few enough teams share it that
               the incumbent may still be beatable

A tie split many ways is NOT a target. Challenges are shared precisely because
their minimum is short and everybody found it; k=8 ties have a median record of
15 and a pass over them scored 0 from 61 steps. Long records with few holders
are where the incumbent is still soft.
"""
import collections
import json
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[2]
POOL = REPO / "runs/pool"

rows = {r["ac_id"]: r for r in
        (json.loads(l) for l in open(POOL / "pool.jsonl", encoding="utf-8"))}

mine = {}
for line in open(POOL / "LEDGER.jsonl", encoding="utf-8"):
    r = json.loads(line)
    if r.get("ok") and r["challenge_id"].startswith("ac-"):
        cid = r["challenge_id"]
        if cid not in mine or r["length"] < mine[cid]:
            mine[cid] = r["length"]

# the best path any run has ever produced, submitted or not
pat = re.compile(r"\s+(ac-\d+) record\s+[\d-]+ \(k \d+\): ours\s+(\d+)")
for f in POOL.glob("*.out"):
    for line in open(f, encoding="utf-8", errors="replace"):
        m = pat.match(line)
        if m:
            cid, ln = m.group(1), int(m.group(2))
            if cid not in mine or ln < mine[cid]:
                mine[cid] = ln

near, ties = [], []
for cid, ln in mine.items():
    r = rows.get(cid)
    if not r or r["ac_best"] is None:
        continue
    rec, k = r["ac_best"], r["ac_k"]
    if ln > rec:
        near.append((cid, rec, ln, k, ln - rec))
    elif ln == rec and 2 <= k <= 3 and rec >= 24:
        # ties are now close to worthless: the field has converged and our holds
        # are shared up to 16 ways, where 2^(1-k) is a rounding error. Only a
        # tie we can plausibly turn into an outright beat is worth the compute,
        # which means few holders and a long record.
        ties.append((cid, rec, ln, k, 0))

# A cap walk that already failed on a challenge will fail again unless its
# record has moved since. Re-walking the same targets every cycle burned 127
# steps for nothing; record what was walked, and at what record, and only
# retry when the record has changed.
walked = {}
wf = POOL / "walked.txt"
if wf.exists():
    for line in open(wf, encoding="utf-8"):
        if line.strip():
            cid, rec = line.split()
            walked[cid] = int(rec)
for f in POOL.glob("*.out"):
    for line in open(f, encoding="utf-8", errors="replace"):
        m = re.match(r"\s+(ac-\d+) record\s+(\d+) \(was \d+\): slack", line)
        if m:
            walked[m.group(1)] = int(m.group(2))
wf.write_text("\n".join(f"{c} {r}" for c, r in sorted(walked.items()))
              + "\n", encoding="utf-8")
fresh = [t for t in near if walked.get(t[0]) != rows[t[0]]["ac_best"]]
stale = len(near) - len(fresh)
near = fresh

near.sort(key=lambda t: t[4])
ties.sort(key=lambda t: -t[1])          # longest record first, it flips most


def write(name, rowset):
    (POOL / name).write_text(
        "\n".join(f"{c} {rec} {ln} {k}" for c, rec, ln, k, _ in rowset) + "\n",
        encoding="utf-8")
    return len(rowset)


n1 = write("t_near.txt", near)
n2 = write("t_ties.txt", ties)
print(f"{len(mine)} challenges we have a path for "
      f"({stale} near misses already walked at the current record, skipped)")
print(f"  near misses (path too long):   {n1}")
print(f"  live ties (k<=4, record>=20):  {n2}")
d = collections.Counter(min(t[4], 9) for t in near)
print("  near-miss distance:", {k: d[k] for k in sorted(d)})
