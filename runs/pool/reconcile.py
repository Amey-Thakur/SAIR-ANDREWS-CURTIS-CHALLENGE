"""What is solved on this machine but not scoring on the leaderboard.

The campaign wrote solutions into one directory per run, and each directory
carries its own `submitted.jsonl`. A solution found in run A and submitted
from run A is invisible to run B's ledger, so no single directory can answer
"is there anything left to send". The leaderboard can: the team-challenges
endpoint lists exactly which challenges are scoring for us right now, and
the snapshot gives the record and the number of teams tied at it.

So this reads the ground truth from the API, scans every solution file on
disk, and reports the gap. It sends nothing. Where it finds something worth
sending, the run directory holding it is named, and `src.harness.submit` is
the thing that sends it.

Reads the key from the environment and never prints it.
"""

import collections
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from src.harness.submit import call  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PREFIX = {"ac": "ac-", "stable_ac": "sac-"}
POOL = REPO / "runs" / "pool"


def snapshot(problem):
    """challengeId -> (currentBestLength or None, kTeams) for the whole pool."""
    code, body, _ = call(
        "GET", f"/competitions/acc/discoveries/snapshot?problem={problem}")
    if code != 200:
        raise SystemExit(f"snapshot {problem}: HTTP {code}")
    data = body["data"]
    out = {}
    for it in data["items"]:
        out[it["challengeId"]] = (it.get("currentBestLength"),
                                  it.get("kTeams") or 0)
    return out, data.get("generatedAt")


def held(problem):
    """challengeId -> currentBestLength for the challenges scoring for us."""
    code, body, _ = call("GET",
                         f"/competitions/acc/leaderboard/me?problem={problem}")
    if code != 200:
        raise SystemExit(f"leaderboard/me {problem}: HTTP {code}")
    entry = body["data"]["entry"]
    if not entry:
        return {}, None
    team_id = entry["team"]["teamId"]
    snap = body["data"].get("snapshotId")
    out, cursor = {}, None
    while True:
        q = (f"/competitions/acc/leaderboard/teams/{team_id}/challenges"
             f"?problem={problem}&limit=100")
        if snap:
            q += f"&snapshotId={snap}"
        if cursor:
            q += f"&cursor={cursor}"
        code, body, _ = call("GET", q)
        if code != 200:
            raise SystemExit(f"team challenges {problem}: HTTP {code}")
        d = body["data"]
        for it in d["items"]:
            out[it["challengeId"]] = it["currentBestLength"]
        cursor = d.get("nextCursor")
        if not cursor:
            return out, d.get("totalCount")


def local_best():
    """(challengeId) -> (length, run directory) for the shortest path on disk.

    Every run directory wrote JSON lines carrying `id`, `problem`, `length`
    and `moves`. Files without those keys belong to ledgers and logs and are
    skipped by the key check rather than by name, so a renamed output file is
    still read.
    """
    best = {}
    files = 0
    for path in sorted(POOL.rglob("*.jsonl")):
        took = False
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
            cid = PREFIX[problem] + str(r["id"])
            length = r.get("length")
            if length is None:
                length = len(moves)
            took = True
            if cid not in best or length < best[cid][0]:
                best[cid] = (length, path.parent.name)
        files += took
    return best, files


def main():
    local, nfiles = local_best()
    print(f"  {len(local)} distinct challenges solved on disk, "
          f"across {nfiles} result files\n")

    grand = collections.Counter()
    for problem in ("ac", "stable_ac"):
        snap, at = snapshot(problem)
        mine, total = held(problem)
        pre = PREFIX[problem]
        rows = {c: v for c, v in local.items() if c.startswith(pre)}

        buckets = collections.defaultdict(list)
        for cid, (ours, where) in rows.items():
            if cid not in snap:
                buckets["not a scored challenge"].append((cid, ours, where))
                continue
            rec, k = snap[cid]
            if rec is None:
                buckets["UNSOLVED by anyone"].append((cid, ours, where))
            elif ours < rec:
                buckets["BEATS the record"].append((cid, ours, where, rec, k))
            elif ours == rec and cid not in mine:
                buckets["ties the record, not held"].append((cid, ours, where, rec, k))
            elif ours == rec:
                buckets["ties, already held"].append((cid, ours, where))
            else:
                buckets["longer than the record"].append((cid, ours, where))

        print(f"  {problem}: snapshot {at}, we hold {total}, "
              f"{len(rows)} solved here")
        for name in ("UNSOLVED by anyone", "BEATS the record",
                     "ties the record, not held", "ties, already held",
                     "longer than the record", "not a scored challenge"):
            got = buckets.get(name, [])
            if got:
                print(f"      {len(got):5}  {name}")
                grand[name] += len(got)
            if got and name in ("UNSOLVED by anyone", "BEATS the record",
                                "ties the record, not held"):
                by_dir = collections.Counter(g[2] for g in got)
                for cid_row in sorted(got)[:8]:
                    print(f"             {cid_row}")
                print(f"             run directories: {dict(by_dir)}")
        print()

    actionable = (grand["UNSOLVED by anyone"] + grand["BEATS the record"]
                  + grand["ties the record, not held"])
    print(f"  actionable: {actionable}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
