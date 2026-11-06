# NOTICE / Attribution — MI3

## MI3
- Project: MI3 — Global Freight & Trade Intelligence
- Integration layer for MI2 + WorldMonitor.
- Composite index, transmission-chain weights, alert rules, and dashboard UI are original to MI3 and are not official MI2 or WorldMonitor indices.

## MI2
- Source: https://github.com/JamesJang-GU/MI2
- Copyright © JamesJang-GU
- Used: `summary.json` and per-module SQLite snapshots (SCFI/BDI, Linerlytica, Alphaliner, forwarders, TAC, oil, macro).

## WorldMonitor — Chokepoint Status open data
- Source: https://www.worldmonitor.app/data/v1/chokepoints/
- License: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)
- Attribution (must reproduce):
  > WorldMonitor (https://www.worldmonitor.app). Scores and statuses are computed by WorldMonitor from IMF PortWatch, NGA Maritime Safety Information, and AIS data via aisstream.io.
- Upstream: IMF PortWatch, NGA Maritime Safety Information, AISstream, Lloyd's Joint War Committee listed areas + open-source reporting.

## WorldMonitor — Five-Factor Scorecard
- Source: https://api.worldmonitor.app/api/scorecard/v1/list-five-factor-scorecards
- Public endpoint, no key. Pillars: food, energy, demographics, technology, defense.

## WorldMonitor API (optional live mode)
- Source: https://api.worldmonitor.app
- Requires `WORLDMONITOR_API_KEY`. Key-gated endpoints: shipping rates, commodity quotes, energy prices, chokepoint history/bypass, country chokepoint exposure, macro signals, world CPI, FRED series.
- See https://www.worldmonitor.app/pricing and https://www.worldmonitor.app/docs/api-reference.
