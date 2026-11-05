"""Eleven single-purpose bots for a PAPER-trading test. No bot can reach a live account.
 1 DataBot  2 TrendBot  3 MomentumBot  4 MeanReversionBot  5 VolatilityBot  6 NewsBot
 7 RegimeBot  8 PortfolioBot  9 RiskBot  10 ExecutionBot  11 ReportBot
Bots 2-9 are pure functions shared by run.py and backtest.py, so the test and the live run use the same logic.
"""
import json, os, re, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
import numpy as np, pandas as pd

PAPER = "https://paper-api.alpaca.markets"          # hard-coded: the live endpoint does not exist in this code
DATA = "https://data.alpaca.markets"
UNIVERSE = ("AAPL MSFT NVDA GOOGL AMZN META AVGO TSLA BRK.B JPM V MA LLY UNH XOM COST WMT HD PG JNJ "
            "ABBV KO BAC NFLX CRM ORCL AMD CSCO MCD CAT "
            "XLB XLC XLE XLF XLI XLK XLP XLRE XLU XLV XLY GLD TLT").split()
BENCH = "SPY"
W = dict(trend=.35, momentum=.35, meanrev=.10, vol=.20)
NEWS_W = .10
TOP_N, MAX_POS, DRIFT, HOLD_BONUS = 8, .15, .05, .25
STOP, KILL_DD, DEFENSIVE = .08, .12, .30
COST = .0005            # 5 bp per unit traded, used by the backtest and by the fee estimate in reports


def _headers():
    k, s = os.environ["APCA_API_KEY_ID"], os.environ["APCA_API_SECRET_KEY"]
    if not k.startswith("PK"): raise SystemExit("Refusing to run: key is not a paper key (must start with PK)")
    return {"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": s, "Content-Type": "application/json"}


def api(url, method="GET", body=None):
    r = urllib.request.Request(url, method=method, headers=_headers(), data=json.dumps(body).encode() if body else None)
    with urllib.request.urlopen(r, timeout=30) as f:
        t = f.read()
    return json.loads(t) if t else None


def data_bot(symbols, start="2020-01-01"):
    """1 DataBot: split/dividend-adjusted daily closes, one column per symbol."""
    rows, tok = {}, None
    while True:
        q = dict(symbols=",".join(symbols), timeframe="1Day", start=start, limit=10000, adjustment="all", feed="iex")
        if tok: q["page_token"] = tok
        d = api(f"{DATA}/v2/stocks/bars?" + urllib.parse.urlencode(q))
        for s, bars in d["bars"].items():
            rows.setdefault(s, {}).update({b["t"][:10]: b["c"] for b in bars})
        tok = d.get("next_page_token")
        if not tok: break
    df = pd.DataFrame(rows).sort_index()
    df.index = pd.to_datetime(df.index)
    return df.ffill()


def rank(s): return 2 * (s.rank(pct=True) - .5)


def trend_bot(c):
    p, a, b = c.iloc[-1], c.iloc[-50:].mean(), c.iloc[-200:].mean()
    return ((p > a) & (a > b)).astype(float) - (p < b).astype(float)


def momentum_bot(c): return rank(c.iloc[-22] / c.iloc[-253] - 1)


def _rsi(c, n=14):
    d = c.diff().iloc[-n:]
    up, dn = d.clip(lower=0).mean(), (-d.clip(upper=0)).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def meanrev_bot(c):
    r, up = _rsi(c), c.iloc[-1] > c.iloc[-200:].mean()
    return ((r < 35) & up).astype(float) - .5 * (r > 75).astype(float)


def _vol(c): return c.pct_change().iloc[-60:].std() * 252 ** .5


def volatility_bot(c): return rank(-_vol(c))


POS = re.compile(r"\b(beat|beats|surge|surges|soar|soars|upgrade|upgraded|record|raises|raised|strong|rally|rallies)\b", re.I)
NEG = re.compile(r"\b(miss|misses|plunge|plunges|slump|slumps|downgrade|downgraded|lawsuit|probe|recall|cuts|weak|falls|fraud)\b", re.I)


def news_bot(symbols, days=3):
    """6 NewsBot: simple headline tone per symbol in [-1,1]. Not backtestable, so it only gets a small weight."""
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    pts = {s: [] for s in symbols}
    q = dict(symbols=",".join(symbols), start=start, limit=50, sort="desc")
    for n in api(f"{DATA}/v1beta1/news?" + urllib.parse.urlencode(q)).get("news", []):
        v = len(POS.findall(n["headline"])) - len(NEG.findall(n["headline"]))
        for s in n.get("symbols", []):
            if s in pts: pts[s].append(np.sign(v))
    return pd.Series({s: (np.mean(v) if v else 0.) for s, v in pts.items()})


def regime_bot(spy):
    """7 RegimeBot: full exposure above the 200-day average, defensive below."""
    return 1. if spy.iloc[-1] > spy.iloc[-200:].mean() else DEFENSIVE


def portfolio_bot(c, news=None, held=()):
    """8 PortfolioBot: blend scores, take the best names, weight by inverse volatility, cap each."""
    c = c.dropna(axis=1, thresh=253)
    s = sum(W[k] * f(c) for k, f in [("trend", trend_bot), ("momentum", momentum_bot), ("meanrev", meanrev_bot), ("vol", volatility_bot)])
    if news is not None: s = s + NEWS_W * news.reindex(s.index).fillna(0)
    keep = s.copy()
    for h in held:
        if h in keep.index: keep[h] += HOLD_BONUS        # reduces churn: a holding must be clearly beaten
    best = s[keep.nlargest(TOP_N).index]; best = best[best > 0]
    if best.empty: return pd.Series(dtype=float), s
    w = 1 / _vol(c)[best.index]
    w /= w.sum()
    for _ in range(10): w = w.clip(upper=MAX_POS) / max(1, w.clip(upper=MAX_POS).sum())
    return w, s


def risk_bot(w, exposure, prices, entries, dd):
    """9 RiskBot: scale for the regime, drop stopped-out names, cut to defensive after a big drawdown."""
    notes, w = [], w * exposure
    for s in list(w.index):
        e = entries.get(s)
        if e and prices.get(s, e) < e * (1 - STOP):
            notes.append(f"Stop-Loss {s}"); w = w.drop(s)
    if dd >= KILL_DD:
        notes.append(f"Drawdown {dd:.1%}: defensiv"); w = w * DEFENSIVE
    return w, notes
