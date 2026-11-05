"""Honest-as-possible check: same bots, decided on close t, earning from t+1, with costs, against buy-and-hold SPY.
Known flatter: the universe is today's large caps (survivorship bias) and NewsBot is absent."""
import pandas as pd, numpy as np
import bots as B

c = B.data_bot(B.UNIVERSE + [B.BENCH]); spy = c[B.BENCH]; px = c.drop(columns=[B.BENCH]); ret = px.pct_change().fillna(0)
start = 260; eq, peak, cur, entries, cost, rows = 1., 1., pd.Series(dtype=float), {}, 0., []
for i in range(start, len(c) - 1):
    h = px.iloc[:i + 1]
    w, _ = B.portfolio_bot(h, held=list(cur.index))
    w, _ = B.risk_bot(w, B.regime_bot(spy.iloc[:i + 1]), h.iloc[-1].to_dict(), entries, 1 - eq / peak)
    idx = cur.index.union(w.index); d = w.reindex(idx).fillna(0) - cur.reindex(idx).fillna(0)
    big = d.abs() > B.DRIFT
    if big.any():
        new = cur.reindex(idx).fillna(0) + d.where(big, 0)
        for s in idx:
            if new[s] > 0 and cur.get(s, 0) == 0: entries[s] = px[s].iloc[i]
            if new[s] <= 0: entries.pop(s, None)
        fee = d.where(big, 0).abs().sum() * B.COST; cost += fee; eq *= 1 - fee
        cur = new[new > 0]
    eq *= 1 + (cur * ret.iloc[i + 1].reindex(cur.index)).sum(); peak = max(peak, eq)
    cur = cur * (1 + ret.iloc[i + 1].reindex(cur.index)) / (1 + (cur * ret.iloc[i + 1].reindex(cur.index)).sum())
    rows.append((c.index[i + 1], eq))
e = pd.Series(dict(rows)); b = spy.reindex(e.index) / spy.reindex(e.index).iloc[0]
def stats(s):
    y = len(s) / 252; r = s.pct_change().dropna()
    return f"{s.iloc[-1] / s.iloc[0] - 1:7.1%} total  {(s.iloc[-1] / s.iloc[0]) ** (1 / y) - 1:6.1%}/y  maxDD {(s / s.cummax() - 1).min():6.1%}  sharpe {r.mean() / r.std() * 252 ** .5:.2f}"
print(e.index[0].date(), "->", e.index[-1].date(), f"({len(e)} days), costs paid {cost:.2%}")
print("BOTS", stats(e)); print("SPY ", stats(b))
for y, g in e.groupby(e.index.year):
    bb = b[b.index.year == y]; print(y, f"bots {g.iloc[-1] / g.iloc[0] - 1:7.1%}   SPY {bb.iloc[-1] / bb.iloc[0] - 1:7.1%}")
