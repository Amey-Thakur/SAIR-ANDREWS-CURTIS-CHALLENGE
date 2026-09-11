# ==============================================================================
# File: test_verify.py
# Description: Tests for the verifier, which is the only thing that decides
#   whether a move sequence is a solution. Every case here is a way a sequence
#   can fail to be one, because that is what the verifier exists to catch.
# Usage: python -m pytest tests -q
# Tech Stack: Python 3.10+, pytest
# ==============================================================================

import json

import pytest

from src.ac.moves import (Conjugate, Destabilize, Invert, Multiply, Stabilize)
from src.ac.presentation import AK, EMPTY, presentation, trivial
from src.ac.verify import (move_from_json, move_to_json, moves_from_json,
                           verify)
from src.harness.check_solution import BAD, OK, check, main

X, Y = 1, 2


# -- what counts as a solution ---------------------------------------------

def test_the_target_needs_no_moves():
    assert verify(trivial(2), [])


def test_a_sequence_that_returns_to_the_target_verifies():
    """Invert twice and you are back where you started, which is a legal if
    pointless solution."""
    r = verify(trivial(2), [Invert(0), Invert(0)])
    assert r and r.steps == 2


def test_the_ordered_pair_matters():
    """Reaching (y, x) is not reaching (x, y). The challenge asks for the
    ordered relator pair."""
    swapped = presentation(2, (Y,), (X,))
    assert not verify(swapped, [])
    assert "not" in verify(swapped, []).reason


def test_stable_ac_finishes_at_the_empty_presentation():
    r = verify(trivial(2), [Destabilize(1), Destabilize(0)], stable=True)
    assert r and r.reached == EMPTY


def test_the_same_sequence_is_not_a_solution_to_ordinary_ac():
    r = verify(trivial(2), [Destabilize(1), Destabilize(0)], stable=False)
    assert not r
    assert "only legal in the stable problem" in r.reason


# -- how a sequence fails ---------------------------------------------------

def test_a_sequence_that_stops_short_is_rejected():
    r = verify(AK(2), [Invert(0)])
    assert not r
    assert "ends at" in r.reason


def test_an_illegal_move_names_the_step():
    r = verify(trivial(2), [Invert(0), Multiply(0, 0)])
    assert not r
    assert r.reason.startswith("step 2")


def test_an_unbalanced_start_is_rejected_before_any_move():
    lopsided = presentation(2, (X,))
    r = verify(lopsided, [])
    assert not r and "not balanced" in r.reason


def test_exceeding_the_generator_cap_is_rejected():
    # rank 2 plus six stabilisations is exactly the cap of eight; the seventh
    # is the one that has to be refused
    r = verify(trivial(2), [Stabilize()] * 6, stable=True)
    assert not r and "ends at" in r.reason        # legal, just not a solution
    r = verify(trivial(2), [Stabilize()] * 7, stable=True)
    assert not r
    assert r.reason.startswith("step 7") and "exceed" in r.reason


# -- the wire format --------------------------------------------------------

@pytest.mark.parametrize("move", [
    Invert(0), Multiply(0, 1), Multiply(1, 0, -1), Conjugate(0, -2),
    Stabilize(), Destabilize(2),
])
def test_moves_round_trip_through_json(move):
    assert move_from_json(json.loads(json.dumps(move_to_json(move)))) == move


def test_an_unknown_move_is_refused():
    with pytest.raises(ValueError, match="unknown move"):
        move_from_json({"move": "teleport"})


def test_a_move_with_the_wrong_arguments_is_refused():
    with pytest.raises(ValueError):
        move_from_json({"move": "invert", "j": 3})


def test_moves_from_json_reads_a_list():
    got = moves_from_json([{"move": "invert", "i": 0},
                           {"move": "conjugate", "i": 1, "c": 2}])
    assert got == [Invert(0), Conjugate(1, 2)]


# -- the solution checker ---------------------------------------------------

GOOD = {"id": "demo", "problem": "ac", "rank": 2,
        "relators": [[1], [2]], "moves": [{"move": "invert", "i": 0},
                                          {"move": "invert", "i": 0}]}


def test_the_checker_accepts_a_real_solution():
    ok, message = check(GOOD)
    assert ok and "verified in 2 moves" in message


def test_the_checker_rejects_one_that_does_not_replay():
    bad = dict(GOOD, moves=[{"move": "invert", "i": 0}])
    ok, message = check(bad)
    assert not ok and "ends at" in message


def test_the_checker_reports_a_malformed_solution():
    ok, message = check({"problem": "ac"})
    assert not ok and "missing" in message


def test_the_checker_rejects_an_unknown_problem():
    ok, message = check(dict(GOOD, problem="unstable-ac"))
    assert not ok and "ac or stable_ac" in message


def test_the_cli_exits_zero_only_when_everything_verifies(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps([GOOD]), encoding="utf-8")
    assert main([str(good)]) == OK

    # AK(2) with no moves is a real failure: legal input, wrong destination.
    # `GOOD` with no moves would still verify, because its start is the target.
    unfinished = {"id": "ak2", "problem": "ac", "rank": 2,
                  "relators": [[1, 1, -2, -2, -2], [1, 2, 1, -2, -1, -2]],
                  "moves": []}
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([GOOD, unfinished]), encoding="utf-8")
    assert main([str(bad)]) == BAD
