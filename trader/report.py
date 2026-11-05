"""ReportBot: paper account vs. buy-and-hold SPY since the first trade (2026-11-05)."""
import bots as B, pandas as pd
START = "2026-11-05"
a = B.api(f"{B.PAPER}/v2/account"); eq = float(a["equity"])
s = B.data_bot([B.BENCH], START)[B.BENCH]
r = f"Konto {eq:,.0f} $ ({eq / 100000 - 1:+.2%}) | SPY {s.iloc[-1] / s.iloc[0] - 1:+.2%} seit {START}"
print(r)
for p in B.api(f"{B.PAPER}/v2/positions"):
    print(f" {p['symbol']:6} {float(p['market_value']):>10,.0f} $  {float(p['unrealized_plpc']):+.1%}")
