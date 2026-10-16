"""The trained-policy solver of arXiv 2408.15332, in the smallest honest form.

The paper trains an actor-critic by PPO: two networks, two hidden layers of 512
units each, over a presentation encoded as a padded token sequence, and it
reports 100 million environment interactions for one run.  That loop is not the
part worth reproducing first.  The part worth reproducing first is the question
underneath it: does a network over this state space learn anything that guides a
search better than total relator length does?

So this trains the same shape of network on supervision that costs nothing:
backward scrambles from (x, y), where the correct action is known by
construction (policy_data.py).  If the network cannot learn to undo a scramble,
PPO on the same architecture has nothing to find either, and the 100M-step loop
is not worth the hardware.  If it can, the next question is whether it
transfers to the pool, which policy_solve.py measures.

Usage (from the repo root):
  python runs/pool/policy_net.py --data runs/pool/policy/scramble.npz \
      --epochs 8 --out runs/pool/policy/net.pt
"""
import argparse
import json
import pathlib
import time

import numpy as np
import torch
import torch.nn as nn

REPO = pathlib.Path(__file__).resolve().parents[2]
ENC = 48
NTOK = 5
NMOVE = 14


class Net(nn.Module):
    """Actor and critic sharing the paper's two-by-512 body.

    The paper runs two separate towers; one shared body with two heads is the
    same parameter budget within a factor of two and is what a supervised fit
    wants, because both heads read the same features."""

    def __init__(self, hidden=512):
        super().__init__()
        self.body = nn.Sequential(
            nn.Linear(2 * ENC * NTOK, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
        )
        self.pi = nn.Linear(hidden, NMOVE)
        self.v = nn.Linear(hidden, 1)

    def forward(self, x):
        h = self.body(x)
        return self.pi(h), self.v(h).squeeze(-1)


def onehot(x, device):
    """int8 token matrix (n, 2*ENC) to float one-hot (n, 2*ENC*NTOK)."""
    t = torch.as_tensor(x, dtype=torch.long, device=device)
    return torch.nn.functional.one_hot(t, NTOK).float().flatten(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="runs/pool/policy/scramble.npz")
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--batch", type=int, default=4096)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--hidden", type=int, default=512)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--out", default="runs/pool/policy/net.pt")
    args = ap.parse_args()

    torch.set_num_threads(args.threads)
    dev = "cpu"
    d = np.load(REPO / args.data)
    x, mv, dp = d["x"], d["move"].astype(np.int64), d["depth"].astype(np.float32)
    n = x.shape[0]
    rng = np.random.default_rng(7)
    perm = rng.permutation(n)
    x, mv, dp = x[perm], mv[perm], dp[perm]
    nval = min(50_000, n // 10)
    xv, mvv, dpv = x[:nval], mv[:nval], dp[:nval]
    xt, mvt, dpt = x[nval:], mv[nval:], dp[nval:]
    print(f"train {len(xt):,}  val {len(xv):,}", flush=True)

    net = Net(args.hidden).to(dev)
    npar = sum(p.numel() for p in net.parameters())
    print(f"parameters: {npar:,}", flush=True)
    opt = torch.optim.Adam(net.parameters(), lr=args.lr)
    ce = nn.CrossEntropyLoss()

    hist = []
    t_start = time.time()
    for ep in range(args.epochs):
        net.train()
        idx = rng.permutation(len(xt))
        tot = seen = 0.0
        t0 = time.time()
        for i in range(0, len(idx) - args.batch + 1, args.batch):
            b = idx[i:i + args.batch]
            xb = onehot(xt[b], dev)
            pb = torch.as_tensor(mvt[b], device=dev)
            vb = torch.as_tensor(dpt[b], device=dev)
            logits, val = net(xb)
            loss = ce(logits, pb) + 0.05 * nn.functional.mse_loss(val, vb)
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += float(loss) * len(b)
            seen += len(b)
        el = time.time() - t0
        net.eval()
        with torch.no_grad():
            acc = top3 = 0
            vmae = 0.0
            for i in range(0, len(xv), 8192):
                xb = onehot(xv[i:i + 8192], dev)
                logits, val = net(xb)
                pb = torch.as_tensor(mvv[i:i + 8192], device=dev)
                acc += int((logits.argmax(1) == pb).sum())
                t3 = logits.topk(3, dim=1).indices
                top3 += int((t3 == pb[:, None]).any(1).sum())
                vmae += float((val - torch.as_tensor(
                    dpv[i:i + 8192], device=dev)).abs().sum())
        row = {"epoch": ep, "loss": tot / seen, "val_top1": acc / len(xv),
               "val_top3": top3 / len(xv), "val_depth_mae": vmae / len(xv),
               "sec": el, "samples_per_s": seen / el}
        hist.append(row)
        print(f"  epoch {ep}: loss {row['loss']:.4f}  top1 {row['val_top1']:.3f}"
              f"  top3 {row['val_top3']:.3f}  depthMAE {row['val_depth_mae']:.2f}"
              f"  {row['samples_per_s']:,.0f} samples/s", flush=True)

    out = REPO / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state": net.state_dict(), "hidden": args.hidden}, out)
    (out.parent / (out.stem + "_hist.json")).write_text(
        json.dumps({"params": npar, "train_s": time.time() - t_start,
                    "hist": hist}, indent=2), encoding="utf-8")
    print(f"wrote {out}  ({time.time() - t_start:.0f}s total)", flush=True)


if __name__ == "__main__":
    main()
