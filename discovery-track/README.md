<div align="center">

# Discovery Track

**Find the shortest sequence of moves that trivialises a presentation.**

<br>

Opened 11 September 2026 · deadline **30 November 2026 AoE**

[How it is run](#running-a-pass) &nbsp;·&nbsp;
[What happened](#what-happened) &nbsp;·&nbsp;
[Proof Track](../proof-track/README.md) &nbsp;·&nbsp;
[Repository home](../README.md)

<br>

[![License](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey)](../LICENSE)
[![Track](https://img.shields.io/badge/Track-Discovery-2EA043)](https://competition.sair.foundation/competitions/acc/overview)
[![Submitted](https://img.shields.io/badge/Verified_lines-146-340825)](#what-happened)
[![Author](https://img.shields.io/badge/Author-Amey_Thakur-0969DA)](https://github.com/Amey-Thakur)

</div>

---

<br>

## The task

Each challenge is a balanced presentation. A submission is a sequence of move
ids that reduces it to the target, and it scores only if the platform can replay
it. Per challenge, the `k` teams tied at the shortest verified length each score
`2^(1-k)`, so a strictly shorter path takes the whole point and drops the
previous holder to zero.

| Problem | Challenge ids | Move ids | Target |
|---|---|---|---|
| `ac` | `ac-00001`–`ac-10115` | 0–13 | `[[1],[2]]` |
| `stable_ac` | `sac-00001`–`sac-10115` | 0–256 | `[]` |

`sac-N` and `ac-N` are the same presentation; stable AC additionally allows
adding and removing an isolated generator–relator pair.

<br>

## What happened

**146 verified lines across 10 submissions**, holding 144 challenges on `ac` and
128 on `stable_ac` at the last check (25 September 2026). Of the 76 challenges
whose record was 17 moves or shorter, 75 were held.

The score, however, collapsed without a single challenge being lost:

| | 12 Sep | 16 Sep | 25 Sep |
|---|---:|---:|---:|
| `ac` rank | 7 | 12 | **22** |
| `ac` score | 24.5 | 3.16 | **0.037** |

This is the tie rule doing exactly what it is designed to do. Every challenge
held is a *shared* tie, and `2^(1-k)` with roughly thirteen teams on each one
pays about 0.0002. The bands a search of this family can reach are the bands
everybody can reach.

That is not a complaint about the rule; it is the finding. It is written up as
§6 of the [Proof Track submission](../proof-track/DESCRIPTION.md), which shows
the anti-correlation is structural rather than incidental: a record is short and
widely shared *because* its optimum is easy to reach, and long and singly held
*because* it is not.

**Nothing further is pending.** A dry run over all 2,464 computed solutions
reports zero opportunities: every line that could score has been sent, and the
rest have been overtaken. Sending anything new requires a solver that reaches
further, not another pass of these.

<br>

## Running a pass

The harness lives at the repository root, not in this folder, because `src/` is
an importable Python package and `runs/` holds paths the solvers resolve
relative to themselves. Moving either would break both.

```bash
# 1. Refresh the pool. Records only improve, so a stale pool sends paths
#    that can no longer score and the harness rightly refuses them.
python runs/pool/refresh_pool.py

# 2. Search. bestfirst.py orders by length plus a depth charge and is the
#    scorer; astar.py is cheaper per node, less accurate, and only a lead
#    generator.
python runs/pool/bestfirst.py --depth-weight 12 --out runs/pool/NAME

# 3. Submit. Dry run is the default and prints what would be sent.
python -m src.harness.submit runs/pool/NAME          # dry run
python -m src.harness.submit runs/pool/NAME --live    # sends
```

<br>

> [!IMPORTANT]
> **Merge ledgers, never copy one over another.** `submitted.jsonl` is the record
> of what the platform verified. Overwriting one run's ledger with another's
> loses history and resends challenges already held:
> `cat runs/pool/*/submitted.jsonl | sort -u`.

> [!WARNING]
> **A POST is never retried automatically.** The submission endpoint has no
> idempotency contract, so an accepted retry creates a second batch and consumes
> another of the 40 daily batches.

<br>

## Limits

From the live submission spec: 500 lines per batch, **40 batches per UTC day**,
path at most 100,000 moves, total relator length at most 10,000, work at most
5,000,000.

<br>

## Reading the results

| Where | What |
|---|---|
| [`runs/campaign_log.md`](../runs/campaign_log.md) | the measurement log every figure above is drawn from, dated entry by entry |
| [`runs/CAMPAIGN_RUNBOOK.md`](../runs/CAMPAIGN_RUNBOOK.md) | how the campaign is operated |
| [`runs/pool/`](../runs/pool/) | the solvers, one file per architecture tried |
| [`src/`](../src/) | the move engine, the verifier, and the submission harness |
| [`solutions/`](../solutions/) | verified paths |

<br>

---

<div align="center">

**[Repository home](../README.md)** &nbsp;·&nbsp;
**[Proof Track](../proof-track/README.md)** &nbsp;·&nbsp;
**[The campaign log](../runs/campaign_log.md)**

</div>
