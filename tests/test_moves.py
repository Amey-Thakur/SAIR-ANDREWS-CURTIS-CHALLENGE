# ==============================================================================
# File: test_moves.py
# Description: Tests for the moves. Half check that legal moves do what the
#   challenge says; the other half check that illegal ones are refused, which
#   is the half that matters, because a verifier that quietly repairs a bad
#   move accepts a path nobody walked.
# Usage: python -m pytest tests -q
# Tech Stack: Python 3.10+, pytest
# ==============================================================================

import pytest

from src.ac.moves import (Conjugate, Destabilize, IllegalMove, Invert,
                          MAX_RANK, Multiply, Stabilize, apply, neighbours)
from src.ac.presentation import AK, EMPTY, presentation, trivial
from src.ac.word import exponent_sum, free_reduce, inverse, multiply

X, Y, Z = 1, 2, 3


# -- words ------------------------------------------------------------------

def test_free_reduction_cancels_adjacent_inverses():
    assert free_reduce((X, -X, Y)) == (Y,)
    assert free_reduce((X, Y, -Y, -X)) == ()
    assert free_reduce((X, Y, -Y, -X, Y)) == (Y,)


def test_inverse_reverses_and_flips():
    assert inverse((X, Y, -X)) == (X, -Y, -X)
    assert multiply((X, Y), inverse((X, Y))) == ()


def test_a_word_times_its_inverse_is_empty():
    w = (X, Y, Y, -X, Y)
    assert multiply(w, inverse(w)) == ()


# -- the three ordinary moves ----------------------------------------------

def test_invert_replaces_one_relator_only():
    p = presentation(2, (X, Y), (Y,))
    q = apply(p, Invert(0))
    assert q.relators == ((-Y, -X), (Y,))


def test_multiply_appends_the_other_relator():
    p = presentation(2, (X,), (Y,))
    assert apply(p, Multiply(0, 1)).relators == ((X, Y), (Y,))
    assert apply(p, Multiply(0, 1, -1)).relators == ((X, -Y), (Y,))


def test_multiply_reduces_after_the_move():
    p = presentation(2, (X, Y), (-Y, X))
    assert apply(p, Multiply(0, 1)).relators[0] == (X, X)


def test_conjugate_wraps_and_reduces():
    p = presentation(2, (X,), (Y,))
    assert apply(p, Conjugate(0, Y)).relators[0] == (Y, X, -Y)
    # conjugating x by x is x again, once the pair cancels
    assert apply(p, Conjugate(0, X)).relators[0] == (X,)


def test_a_relator_may_not_be_multiplied_by_itself():
    p = presentation(2, (X,), (Y,))
    with pytest.raises(IllegalMove, match="two different relators"):
        apply(p, Multiply(0, 0))


def test_conjugating_by_a_generator_outside_the_rank_is_refused():
    p = presentation(2, (X,), (Y,))
    with pytest.raises(IllegalMove):
        apply(p, Conjugate(0, Z))


def test_a_missing_relator_is_refused():
    p = presentation(2, (X,), (Y,))
    with pytest.raises(IllegalMove, match="no relator"):
        apply(p, Invert(5))


# -- what the moves preserve ------------------------------------------------

def test_conjugation_preserves_exponent_sums():
    """Exponent sum is invariant under conjugation, which is why it is the
    cheapest obstruction a search can test."""
    p = presentation(2, (X, X, -Y, -Y, -Y), (X, Y, X, -Y, -X, -Y))
    for c in (X, -X, Y, -Y):
        q = apply(p, Conjugate(0, c))
        for g in (X, Y):
            assert exponent_sum(q.relators[0], g) == exponent_sum(p.relators[0], g)


def test_inversion_negates_exponent_sums():
    r = (X, X, -Y, -Y, -Y)
    p = presentation(2, r, (Y,))
    q = apply(p, Invert(0))
    for g in (X, Y):
        assert exponent_sum(q.relators[0], g) == -exponent_sum(r, g)


def test_every_move_keeps_the_presentation_balanced():
    p = AK(3)
    assert p.is_balanced
    for move, q in neighbours(p, stable=True):
        assert q.is_balanced, f"{move} unbalanced the presentation"


# -- the stable moves -------------------------------------------------------

def test_stabilize_adds_a_generator_and_its_relator():
    p = trivial(2)
    q = apply(p, Stabilize())
    assert q.rank == 3
    assert q.relators == ((X,), (Y,), (Z,))


def test_destabilize_undoes_it():
    p = trivial(2)
    q = apply(apply(p, Stabilize()), Destabilize(2))
    assert q == p


def test_destabilize_refuses_a_relator_that_is_not_the_bare_generator():
    p = presentation(3, (X,), (Y,), (Z, X))
    with pytest.raises(IllegalMove, match="not the bare generator"):
        apply(p, Destabilize(2))


def test_destabilize_refuses_while_the_generator_is_still_used():
    p = presentation(3, (X,), (Y, Z), (Z,))
    with pytest.raises(IllegalMove, match="still occurs"):
        apply(p, Destabilize(2))


def test_stabilizing_past_the_cap_is_refused():
    p = trivial(2)
    for _ in range(MAX_RANK - 2):
        p = apply(p, Stabilize())
    assert p.rank == MAX_RANK
    with pytest.raises(IllegalMove, match=str(MAX_RANK)):
        apply(p, Stabilize())


def test_the_empty_presentation_is_reachable_by_destabilizing():
    p = trivial(1)
    assert apply(p, Destabilize(0)) == EMPTY
