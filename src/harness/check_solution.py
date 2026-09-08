# ==============================================================================
# File: check_solution.py
# Description: Check a Discovery Track solution before it is submitted. A
#   solution is a challenge id and a list of moves, so this replays the moves
#   against the stated presentation and exits non-zero if they do not reach the
#   target. Checking locally costs nothing; submitting a sequence that does not
#   replay costs a leaderboard entry.
# Usage: python -m src.harness.check_solution solution.json
# Tech Stack: Python 3.10+, standard library only
# ==============================================================================

from __future__ import annotations

import json
import sys

from ..ac.presentation import presentation
from ..ac.verify import moves_from_json, verify

OK, BAD, ERROR = 0, 1, 2


def load(obj):
    """Read one solution object.

    Expected shape, which follows the challenge's own description of a
    solution as an id and a list of moves:

        {"id": "...", "problem": "ac" | "stable-ac",
         "rank": 2, "relators": [[1, 1, -2, -2, -2], [...]],
         "moves": [{"move": "invert", "i": 0}, ...]}
    """
    if not isinstance(obj, dict):
        raise ValueError("a solution must be an object")
    for key in ("problem", "rank", "relators", "moves"):
        if key not in obj:
            raise ValueError(f"missing {key!r}")
    problem = obj["problem"]
    if problem not in ("ac", "stable-ac"):
        raise ValueError(f"problem must be ac or stable-ac, not {problem!r}")
    start = presentation(int(obj["rank"]),
                         *[tuple(int(x) for x in r) for r in obj["relators"]])
    return obj.get("id", "?"), problem, start, moves_from_json(obj["moves"])


def check(obj):
    """Return (ok, message) for one solution object."""
    try:
        cid, problem, start, moves = load(obj)
    except ValueError as exc:
        return False, f"malformed solution: {exc}"
    result = verify(start, moves, stable=(problem == "stable-ac"))
    if result:
        return True, (f"{cid}: {problem} verified in {result.steps} moves "
                      f"from {start}")
    return False, f"{cid}: {result.reason}"


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__ or "usage: python -m src.harness.check_solution FILE",
              file=sys.stderr)
        return ERROR
    try:
        with open(argv[0], "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return ERROR
    except json.JSONDecodeError as exc:
        print(f"error: not JSON: {exc}", file=sys.stderr)
        return ERROR

    items = payload if isinstance(payload, list) else [payload]
    failures = 0
    for obj in items:
        ok, message = check(obj)
        print(("  ok  " if ok else "  BAD ") + message)
        failures += 0 if ok else 1
    print(f"{len(items) - failures} of {len(items)} verified", file=sys.stderr)
    return OK if failures == 0 else BAD


if __name__ == "__main__":
    raise SystemExit(main())
