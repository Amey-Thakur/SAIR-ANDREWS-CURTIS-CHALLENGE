# ==============================================================================
# File: test_engine.py
# Description: The engine is only worth anything if its fast moves are the same
#   moves the verifier replays, so the first test checks every move id against
#   the verifier's own move objects on random presentations. The rest check
#   that finishes, shortening and the whole solve produce paths that verify.
# Usage: python -m pytest tests -q
# Tech Stack: Python 3.10+, pytest
# ==============================================================================

import json
import random

import pytest

from src.ac.moves import apply
from src.ac.presentation import AK, Presentation
from src.ac.verify import verify
from src.ac.word import free_reduce
from src.search import engine as E


def _random_state(rng, longest=7):
    while True:
        words = tuple(
            free_reduce(tuple(rng.choice((1, -1, 2, -2))
                              for _ in range(rng.randint(1, longest))))
            for _ in range(2))
        if all(words):
            return words


def test_every_move_id_is_the_verifiers_move():
    rng = random.Random(7)
    for _ in range(400):
        s = _random_state(rng)
        p = Presentation(2, s)
        fast = dict(E.expand(s))
        for mid in range(14):
            expected = apply(p, E.to_move(mid)).relators
            assert E.step(s, mid) == expected, (s, mid)
            assert fast[mid] == expected, (s, mid)


def test_every_trivial_state_has_verified_finishes():
    for t in E.TRIVIAL:
        start = Presentation(2, t)
        assert verify(start, [E.to_move(m) for m in E.FINISH_AC[t]],
                      stable=False)
        assert verify(start, E.FINISH_STABLE[t], stable=True)


def test_shorten_removes_waste_and_keeps_the_endpoint():
    start = AK(2).relators
    core, _ = E.greedy(start, max_nodes=100_000)
    assert core is not None
    padded = [0, 0, 6, 7] + core          # invert twice, conjugate and undo
    short = E.shorten(start, padded)
    assert len(short) <= len(core)
    assert E.replay(start, short)[-1] == E.replay(start, core)[-1]


def test_solve_returns_verified_paths_for_AK2():
    out = E.solve(AK(2).relators, max_nodes=200_000)
    assert out["ac"] is not None and out["stable_ac"] is not None
    assert verify(AK(2), out["ac"], stable=False)
    assert verify(AK(2), out["stable_ac"], stable=True)
    assert len(out["ac"]) <= 18


def test_every_engine_move_keeps_its_official_id():
    from src.ac.moves import Destabilize
    from src.ac.verify import move_to_json
    from src.harness.submit import official_id
    for mid in range(14):
        assert official_id(move_to_json(E.to_move(mid))) == mid
    assert official_id(move_to_json(Destabilize(0))) == 15
    assert official_id(move_to_json(Destabilize(1))) == 16


def test_load_best_keeps_the_shortest(tmp_path):
    from src.search.campaign import load_best
    rows = [{"id": "a", "problem": "ac", "length": 9},
            {"id": "a", "problem": "ac", "length": 7},
            {"id": "a", "problem": "stable_ac", "length": 8}]
    (tmp_path / "solutions.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    best = load_best(tmp_path)
    assert best[("a", "ac")]["length"] == 7
    assert best[("a", "stable_ac")]["length"] == 8
