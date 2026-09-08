<div align="center">

# Documentation

**The conjecture, the challenge, and what this repository can and cannot say.**

[Back to the repository](../README.md) &nbsp;·&nbsp;
[The moves](../src/README.md) &nbsp;·&nbsp;
[Competition](https://competition.sair.foundation/competitions/acc/overview)

</div>

---

## 1. The problem

| Document | Question it answers |
| :--- | :--- |
| [research/conjecture.md](research/conjecture.md) | What the Andrews–Curtis conjecture says, what balanced means, and why the stable version is a different question |

## 2. The competition

| Document | Question it answers |
| :--- | :--- |
| [competition/analysis.md](competition/analysis.md) | The two tracks, the two problems, what the verifier checks, and what a leaderboard entry is worth |

## 3. What has been measured

| Document | Question it answers |
| :--- | :--- |
| [research/baseline.md](research/baseline.md) | What a length-guided search reaches, what it does not, and why that is the interesting part |
| [research/open_questions.md](research/open_questions.md) | What is unfinished here, stated plainly |

## 4. Prior work

| Document | Question it answers |
| :--- | :--- |
| [literature/review.md](literature/review.md) | The candidate counterexamples, and what previous searches settled |

## The one idea to take away

Every move is reversible, so the reachable set from a presentation is an
equivalence class and the question is only ever whether two things lie in the
same one. That makes the problem a search rather than a construction, and it
makes a negative result almost worthless: failing to find a path proves
nothing, because the path may be longer than the budget.

Which is why the honest unit of work here is a *verified* path and a *stated*
budget. A shorter path is a result. A search that stopped is a measurement.
Neither is a claim about the conjecture.

**[Back to the repository](../README.md)** &nbsp;·&nbsp;
**[On to the moves](../src/README.md)**
