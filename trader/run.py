"""One trading round on the Alpaca PAPER account. Without --send it only prints the plan.
Stateless: positions, entry prices and the equity curve all live in the paper account."""
import json, sys, urllib.error
import pandas as pd
import bots as B

SEND = "--send" in sys.argv
clock = B.api(f"{B.PAPER}/v2/clock")
acct = B.api(f"{B.PAPER}/v2/account")
eq = float(acct["equity"])
pos = {p["symbol"]: p for p in B.api(f"{B.PAPER}/v2/positions")}
hist = B.api(f"{B.PAPER}/v2/account/portfolio/history?period=1A&timeframe=1D")
curve = [e for e in hist.get("equity", []) if e] + [eq]
peak = max(curve); dd = 1 - eq / peak

c = B.data_bot(B.UNIVERSE + [B.BENCH])
spy = c[B.BENCH]; px = c.drop(columns=[B.BENCH])
news = B.news_bot([s for s in B.UNIVERSE if len(s) <= 4])
regime = B.regime_bot(spy)
w, scores = B.portfolio_bot(px, news, held=list(pos))
entries = {s: float(p["avg_entry_price"]) for s, p in pos.items()}
prices = {s: float(p["current_price"]) for s, p in pos.items()}
w, notes = B.risk_bot(w, regime, prices, entries, dd)

cur = {s: float(p["market_value"]) / eq for s, p in pos.items()}
plan = []
for s in sorted(set(cur) | set(w.index)):
    d = w.get(s, 0.) - cur.get(s, 0.)
    if s not in w.index: plan.append(("close", s, cur[s]))
    elif abs(d) > B.DRIFT: plan.append(("sell" if d < 0 else "buy", s, abs(d)))
plan.sort(key=lambda x: x[0] == "buy")      # sells first, they free the cash

sent, errors = [], []
if SEND and clock["is_open"]:
    for o in B.api(f"{B.PAPER}/v2/orders?status=open"): B.api(f"{B.PAPER}/v2/orders/{o['id']}", "DELETE")
    for side, s, amt in plan[:20]:
        if amt > .20: amt = .20                # ExecutionBot: hard cap per order
        try:
            if side == "close": B.api(f"{B.PAPER}/v2/positions/{s}", "DELETE")
            else: B.api(f"{B.PAPER}/v2/orders", "POST", dict(symbol=s, notional=round(amt * eq, 2), side=side, type="market", time_in_force="day"))
            sent.append(f"{side} {s}")
        except urllib.error.HTTPError as e:
            errors.append(f"{side} {s}: {e.code} {e.read()[:150]!r}")

print(json.dumps(dict(market_open=clock["is_open"], equity=eq, drawdown=round(dd, 4), regime=regime, notes=notes,
                      target={k: round(v, 3) for k, v in w.items()}, plan=[(a, b, round(x, 3)) for a, b, x in plan],
                      sent=sent, errors=errors,
                      top_scores=scores.nlargest(5).round(2).to_dict()), indent=1))
