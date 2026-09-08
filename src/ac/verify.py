# ==============================================================================
# File: verify.py
# Description: The verifier. A Discovery Track solution is a challenge id and a
#   list of moves, so the only thing that makes it a solution is that replaying
#   the moves legally reaches the target. This replays them and says where it
#   stopped. It never repairs a move and never accepts a sequence it could not
#   finish, because the whole value of a short path is that it is real.
# Usage: from src.ac.verify import verify
# Tech Stack: Python 3.10+, standard library only
# ==============================================================================

from __future__ import annotations

from dataclasses import dataclass

from .moves import (Conjugate, Destabilize, IllegalMove, Invert, Multiply,
                    MAX_RANK, Stabilize, apply)
from .presentation import EMPTY, Presentation, trivial


@dataclass
class Result:
    ok: bool
    steps: int
    reached: Presentation
    reason: str = ""

    def __bool__(self):
        return self.ok


def target_for(start: Presentation, stable: bool) -> Presentation:
    """Stable AC finishes at the empty presentation. Ordinary AC finishes at
    the standard presentation of the rank it started in, with the generators
    fixed."""
    return EMPTY if stable else trivial(start.rank)


def verify(start: Presentation, moves, stable: bool = False) -> Result:
    """Replay a move sequence and report whether it reaches the target."""
    if not start.is_balanced:
        return Result(False, 0, start,
                      "the starting presentation is not balanced")

    p = start
    for step, move in enumerate(moves, 1):
        if not stable and isinstance(move, (Stabilize, Destabilize)):
            return Result(False, step, p,
                          f"step {step}: {move} is only legal in the stable "
                          f"problem")
        try:
            p = apply(p, move)
        except IllegalMove as exc:
            return Result(False, step, p, f"step {step}: {exc}")
        if p.rank > MAX_RANK:
            return Result(False, step, p,
                          f"step {step}: rank {p.rank} exceeds the limit of "
                          f"{MAX_RANK}")

    goal = target_for(start, stable)
    if p == goal:
        return Result(True, len(moves), p)
    return Result(False, len(moves), p,
                  f"the sequence ends at {p}, not {goal}")


# -- the wire format --------------------------------------------------------
# The official submission format arrives with the launch on 11 September 2026.
# Until then a solution is written the way the challenge describes it, as an id
# and a list of moves, and this is the reading of that.

_KINDS = {"invert": Invert, "multiply": Multiply, "conjugate": Conjugate,
          "stabilize": Stabilize, "destabilize": Destabilize}


def move_from_json(obj):
    """One move from a plain object, refusing anything it does not recognise."""
    if not isinstance(obj, dict) or "move" not in obj:
        raise ValueError(f"not a move: {obj!r}")
    kind = obj["move"]
    cls = _KINDS.get(kind)
    if cls is None:
        raise ValueError(f"unknown move: {kind!r}")
    args = {k: v for k, v in obj.items() if k != "move"}
    try:
        return cls(**args)
    except TypeError as exc:
        raise ValueError(f"{kind} does not take {sorted(args)}: {exc}") from exc


def moves_from_json(items):
    return [move_from_json(o) for o in items]


def move_to_json(move):
    kind = {v: k for k, v in _KINDS.items()}[type(move)]
    out = {"move": kind}
    out.update(vars(move))
    return out
