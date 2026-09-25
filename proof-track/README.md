<div align="center">

# Proof Track

**Ideas, partial results, and proofs or disproofs about AC and Stable AC.**

<br>

Submissions opened 11 September 2026 · deadline **30 November 2026 AoE**

[The submission](DESCRIPTION.md) &nbsp;·&nbsp;
[Submit](https://competition.sair.foundation/competitions/acc/proof-track) &nbsp;·&nbsp;
[Discovery Track](../discovery-track/README.md) &nbsp;·&nbsp;
[Repository home](../README.md)

<br>

[![License](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey)](../LICENSE)
[![Track](https://img.shields.io/badge/Track-Proof-3949AB)](https://competition.sair.foundation/competitions/acc/proof-track)
[![Result](https://img.shields.io/badge/Result-Partial-DBAB0A)](DESCRIPTION.md)
[![Conjecture](https://img.shields.io/badge/Conjecture-AC-340825)](DESCRIPTION.md)
[![Author](https://img.shields.io/badge/Author-Amey_Thakur-0969DA)](https://github.com/Amey-Thakur)

</div>

---

<br>

## What is being submitted

**[`DESCRIPTION.md`](DESCRIPTION.md)** is the submission. It is a **partial
result** and makes no claim about the conjecture in either direction. It reports
measurements over the 10,115 balanced presentations of the Discovery pool that
fix how a search for an AC reduction should be structured, a structural
obstruction that limits what any search of this family can score, and one
verified non-existence statement at a bounded length.

Five findings, each measured rather than argued:

| § | Finding |
|---|---|
| 1 | A hard bound on total relator length is the dominant design error. Replacing the cap with a priority `ℓ(P) + w·d(P)` solves 10 of 10 known optima **exactly**, where the capped search often found no path at all. |
| 2 | The two terms of that priority trade off sharply, so any one setting is competent on a *band* rather than on the pool. |
| 4 | The backward half of a bidirectional search never reads the presentation. That permits amortisation and also bounds what precomputation can buy. |
| 6 | Solver competence and point value are **anti-correlated by construction** under the `2^(1-k)` tie rule: what is reachable is worth almost nothing. |
| 6b | For `ac-07351`, **no AC path of length ≤ 24 exists** within word cap 42. The search terminated by exhausting the space, not by running out of budget. |

<br>

## There is no Proof Track API

The competition exposes one submission kind for `acc`, `acc-solutions`, which is
the Discovery Track. Verified against the live API: `GET /competitions` lists six
competitions and `acc` carries that single kind, and the documented endpoint map
for `acc` covers Discovery only. **This track is submitted through the web form.**

Discovery, by contrast, *is* submitted through the API — see
[`../discovery-track/README.md`](../discovery-track/README.md). Nothing in this
folder belongs there.

<br>

## Filling the form

<https://competition.sair.foundation/competitions/acc> → **Proof Track** → Submit

| Field | What to enter |
|---|---|
| **Conjecture** | `AC` |
| **Direction** | `proof` |
| **Description** | the whole of [`DESCRIPTION.md`](DESCRIPTION.md), starting at its title line |
| **Public GitHub repository link** | `https://github.com/Amey-Thakur/SAIR-ANDREWS-CURTIS-CHALLENGE` |
| **Git commit hash** | the full hash of the pushed commit being submitted — `git rev-parse HEAD` |
| **arXiv or paper link** | leave empty until the paper is announced |
| **Sharing agreement** | required; tick it |

> [!NOTE]
> **Direction states the aim, not the achievement.** The form says so explicitly,
> and the description's first sentence says it is a partial result, so `proof` is
> the honest choice for work that searches for reductions rather than for a
> counterexample.

> [!IMPORTANT]
> A commit hash cannot be embedded in the commit it names, so this file does not
> quote one. Take it from the repository at the moment you submit, and update it
> if you revise and resubmit.

<br>

## Before submitting

- [ ] The commit is **pushed**. A hash the graders cannot fetch is worse than no link.
- [ ] `DESCRIPTION.md` is pasted in full, from its title line to the last line.
- [ ] Conjecture `AC`, direction `proof`.
- [ ] The commit hash matches the pushed `HEAD`.
- [ ] Sharing agreement ticked. Submitting publishes the work to the Contributor
      Network with a timestamp and version history, which is the point: it
      establishes priority on the findings above.

<br>

## Scope and honesty

Two things this submission deliberately does not do.

It does not claim the conjecture. The one non-existence statement is bounded —
no path of length at most 24 within word cap 42 for a single presentation — and
the conjecture places no bound on path length, so the statement constrains a
search space rather than the mathematics.

It does not present its negative results as successes. Five search architectures
were measured and all score zero on the band that carries the point value; that
is reported because it bounds what the approach can do. Being recorded in the
Contributor Network does not certify correctness, and the findings are open to
community review.

<br>

---

<div align="center">

**[Repository home](../README.md)** &nbsp;·&nbsp;
**[Discovery Track](../discovery-track/README.md)** &nbsp;·&nbsp;
**[The submission](DESCRIPTION.md)**

</div>
