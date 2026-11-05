# Paper-Trading-Test (11 Bots)
Nur Alpaca Paper Trading, kein echtes Geld: `run.py` kennt nur den Paper-Endpunkt und bricht ab, wenn der Schlüssel nicht mit PK beginnt.
Schlüssel kommen ausschließlich über die Umgebung (APCA_API_KEY_ID, APCA_API_SECRET_KEY), nie ins Repo.

- `python3 run.py` zeigt den Plan, `python3 run.py --send` handelt im Paper-Konto
- `python3 report.py` vergleicht das Konto mit SPY
- `python3 backtest.py` testet dieselben Regeln rückwirkend

Backtest 08/2021–11/2026 nach Kosten: Bots +39,9 % (max. −14,1 %), SPY +78,5 % (max. −24,5 %).
Geschönt durch die Auswahl heutiger Großkonzerne (Survivorship Bias); NewsBot nicht enthalten.
