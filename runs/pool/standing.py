"""Current position on both boards, and what the ranks above us cost.

Reads the key from the environment and never prints it.
"""
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from src.harness.submit import call  # noqa: E402

# team names can carry characters the console codepage cannot encode
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

US = "ACC01-T00013"


def row(e):
    t = e.get("team", {})
    # the API sends score as a string
    return (e.get("rank"), t.get("teamName") or t.get("teamNumber"),
            float(e.get("score") or 0), e.get("currentBestCount"))


for problem in ("ac", "stable_ac"):
    _, me, _ = call("GET", f"/competitions/acc/leaderboard/me?problem={problem}")
    _, board, _ = call("GET",
                       f"/competitions/acc/leaderboard?problem={problem}&limit=10")
    entry = me["data"]["entry"]
    rank, name, score, held = row(entry)
    print(f"{problem}: rank {rank}, score {score:.4f}, {held} challenges held "
          f"(snapshot {me['data']['generatedAt']})")
    for e in board["data"]["items"]:
        r, n, s, h = row(e)
        gap = "" if r >= rank else f"   +{s - score:.1f} to pass"
        mark = "  <- us" if e.get("team", {}).get("teamNumber") == US else gap
        print(f"    {r:>3}  {str(n):<16} {s:>10.2f}  held {h!s:>5}{mark}")
    print()
