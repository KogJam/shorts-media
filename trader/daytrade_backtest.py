"""Intraday test: opening-range breakout on liquid ETFs/stocks, flat before the close, one trade per symbol per day.
Rules were fixed before the first run: entry on a 5-min close beyond the range, stop at the other side of the range,
exit 15:55 ET, equal capital per symbol, no leverage. Prices are IEX-only bars, fills at the next bar's open."""
import os, sys, pickle, urllib.parse
import numpy as np, pandas as pd
import bots as B
SYMS = "SPY QQQ IWM AAPL NVDA TSLA AMD".split()
CACHE = sys.argv[1] if len(sys.argv) > 1 else "bars5.pkl"
if os.path.exists(CACHE): d = pickle.load(open(CACHE, "rb"))
else:
    rows, tok = [], None
    while True:
        q = dict(symbols=",".join(SYMS), timeframe="5Min", start="2021-01-01", limit=10000, adjustment="all", feed="iex")
        if tok: q["page_token"] = tok
        r = B.api(f"{B.DATA}/v2/stocks/bars?" + urllib.parse.urlencode(q))
        for s, bs in r["bars"].items(): rows += [(s, b["t"], b["o"], b["h"], b["l"], b["c"]) for b in bs]
        tok = r.get("next_page_token")
        if not tok: break
    d = pd.DataFrame(rows, columns="s t o h l c".split())
    d["t"] = pd.to_datetime(d.t, utc=True).dt.tz_convert("America/New_York")
    d = d[(d.t.dt.time >= pd.Timestamp("09:30").time()) & (d.t.dt.time < pd.Timestamp("16:00").time())]
    d["day"] = d.t.dt.date; pickle.dump(d, open(CACHE, "wb"))

def trades(g, minutes):
    end = g.t.iloc[0].normalize() + pd.Timedelta(hours=9, minutes=30 + minutes)
    r, a = g[g.t < end], g[g.t >= end]
    if len(r) < minutes / 5 * .8 or len(a) < 20: return None
    hi, lo = r.h.max(), r.l.min(); a = a.reset_index(drop=True)
    sig = np.where(a.c > hi, 1, np.where(a.c < lo, -1, 0)); idx = np.nonzero(sig)[0]
    idx = idx[idx < len(a) - 1]
    if not len(idx): return 0.
    i = idx[0]; side = sig[i]; entry = a.o[i + 1]; stop = lo if side > 0 else hi
    for j in range(i + 1, len(a)):
        if a.t[j].time() >= pd.Timestamp("15:55").time(): return side * (a.o[j] / entry - 1)
        if (side > 0 and a.l[j] <= stop) or (side < 0 and a.h[j] >= stop): return side * (stop / entry - 1)
    return side * (a.c.iloc[-1] / entry - 1)

res = {}
for m in (30, 60):
    res[m] = pd.DataFrame({s: {day: trades(g, m) for day, g in x.groupby("day")} for s, x in d.groupby("s")}).astype(float)
spy = d[d.s == "SPY"].groupby("day").c.last(); spy.index = pd.to_datetime(spy.index)
def show(name, r, bp):
    traded = r.fillna(0) != 0
    net = (r.fillna(0) - traded * 2 * bp / 1e4).mean(axis=1); net.index = pd.to_datetime(net.index)
    e = (1 + net).cumprod(); y = len(e) / 252
    print(f"{name:26} total {e.iloc[-1] - 1:8.1%}  {e.iloc[-1] ** (1 / y) - 1:6.1%}/y  maxDD {(e / e.cummax() - 1).min():6.1%}  trades {int(traded.sum().sum())}  hit {(r[traded] > 0).sum().sum() / traded.sum().sum():.0%}")
    return e
print(res[60].index[0], "->", res[60].index[-1], len(res[60]), "days")
for m in (60, 30):
    for bp in (0, 1, 3): e = show(f"ORB {m}min, {bp}bp je Seite", res[m], bp)
e60 = show("ORB 60min, 3bp", res[60], 3)
s = spy.reindex(e60.index).ffill(); print(f"SPY halten total {s.iloc[-1] / s.iloc[0] - 1:.1%}, maxDD {(s / s.cummax() - 1).min():.1%}")
for y, g in e60.groupby(e60.index.year):
    b = s[s.index.year == y]; print(y, f"ORB60 {g.iloc[-1] / g.iloc[0] - 1:7.1%}  SPY {b.iloc[-1] / b.iloc[0] - 1:7.1%}")
print("nach Symbol, 60min, 3bp:", {c: f"{(res[60][c].dropna().sub((res[60][c].dropna() != 0) * 6e-4) + 1).prod() - 1:.0%}" for c in res[60]})
