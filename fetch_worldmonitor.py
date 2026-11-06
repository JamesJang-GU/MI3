#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch WorldMonitor data for the unified dashboard.

Public (no key):
  - Chokepoint status open data (daily snapshots, CC-BY-4.0)
  - Five-Factor Country Scorecard

Live (optional, requires WORLDMONITOR_API_KEY):
  - Chokepoint status, shipping rates, commodity quotes, energy prices
  - Chokepoint history / bypass options / country chokepoint exposure
  - Macro signals, world CPI, FRED series

Usage:
    python3 fetch_worldmonitor.py                 # public + live if key present
    python3 fetch_worldmonitor.py --public-only   # public only
    python3 fetch_worldmonitor.py --no-live       # same as --public-only
    WORLDMONITOR_API_KEY=wm_xxx python3 fetch_worldmonitor.py

Output:
    data/chokepoints-*.json, data/scorecard.json
    data/worldmonitor-live.json (only when live data is fetched)
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)

UA = 'MI3-GlobalIntel/0.1.0 (contact: ops@example.test)'
PUBLIC = 'https://www.worldmonitor.app'
API = 'https://api.worldmonitor.app'
TIMEOUT = 30


def fetch(url: str, headers=None, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json', **(headers or {})})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return json.loads(r.read().decode('utf-8'))


def get(url: str, headers=None):
    try:
        return {'ok': True, 'data': fetch(url, headers)}
    except urllib.error.HTTPError as e:
        body = ''
        try:
            body = e.read().decode('utf-8', 'replace')[:300]
        except Exception:
            pass
        return {'ok': False, 'error': f'HTTP {e.code}', 'body': body}
    except Exception as e:
        return {'ok': False, 'error': f'{type(e).__name__}: {e}'}


def public_data():
    print('[public] chokepoint index…')
    idx = fetch(f'{PUBLIC}/data/v1/chokepoints/index.json')
    (DATA / 'chokepoints-index.json').write_text(json.dumps(idx, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    dates = idx.get('dates', [])
    latest = fetch(f'{PUBLIC}/data/v1/chokepoints/latest.json')
    (DATA / 'chokepoints-latest.json').write_text(json.dumps(latest, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    for d in dates:
        p = DATA / f'chokepoints-{d}.json'
        if p.exists():
            continue
        print(f'[public] chokepoint snapshot {d}…')
        try:
            snap = fetch(f'{PUBLIC}/data/v1/chokepoints/{d}.json')
            p.write_text(json.dumps(snap, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        except Exception as e:
            print(f'  skip {d}: {e}')
    print('[public] scorecard…')
    sc = fetch(f'{API}/api/scorecard/v1/list-five-factor-scorecards')
    (DATA / 'scorecard.json').write_text(json.dumps(sc, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'[public] {len(latest.get("chokepoints", []))} chokepoints, {len(sc.get("scorecards", []))} countries')


def live_data(api_key: str):
    print('[live] fetching WorldMonitor API…')
    headers = {'X-WorldMonitor-Key': api_key}
    out = {'fetched_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'api_key_used': True, 'endpoints': {}, 'errors': {}}
    calls = {
        'chokepoint_status': f'{API}/api/supply-chain/v1/get-chokepoint-status',
        'shipping_rates': f'{API}/api/supply-chain/v1/get-shipping-rates',
        'commodity_quotes': f'{API}/api/market/v1/list-commodity-quotes',
        'energy_prices': f'{API}/api/economic/v1/get-energy-prices',
        'macro_signals': f'{API}/api/economic/v1/get-macro-signals',
        'world_cpi': f'{API}/api/economic/v1/get-world-cpi-monthly?history=false&limit=200',
    }
    for name, url in calls.items():
        r = get(url, headers)
        if r['ok']:
            out['endpoints'][name] = r['data']
            print(f'[live] {name} ok')
        else:
            out['errors'][name] = r
            print(f'[live] {name} failed: {r.get("error")}')
    # per-chokepoint history + bypass + country exposure
    cp_status = out['endpoints'].get('chokepoint_status', {})
    cp_ids = [c.get('id') for c in cp_status.get('chokepoints', []) if c.get('id')]
    if not cp_ids:
        try:
            latest = json.loads((DATA / 'chokepoints-latest.json').read_text(encoding='utf-8'))
            cp_ids = [c['id'] for c in latest['chokepoints']]
        except Exception:
            cp_ids = []
    out['endpoints']['chokepoint_history'] = {}
    out['endpoints']['bypass_options'] = {}
    for cid in cp_ids:
        r = get(f'{API}/api/supply-chain/v1/get-chokepoint-history?chokepointId={cid}', headers)
        if r['ok']:
            out['endpoints']['chokepoint_history'][cid] = r['data']
        r = get(f'{API}/api/supply-chain/v1/get-bypass-options?chokepointId={cid}&cargoType=container&closurePct=100', headers)
        if r['ok']:
            out['endpoints']['bypass_options'][cid] = r['data']
    out['endpoints']['country_chokepoint_index'] = {}
    for iso2 in ['KR', 'US', 'CN', 'JP', 'DE', 'NL', 'SG', 'AE', 'IN', 'BR']:
        r = get(f'{API}/api/supply-chain/v1/get-country-chokepoint-index?iso2={iso2}&hs2=27', headers)
        if r['ok']:
            out['endpoints']['country_chokepoint_index'][iso2] = r['data']
    # FRED series
    out['endpoints']['fred'] = {}
    for sid in ['GSCPI', 'GDP', 'CPIAUCSL', 'FEDFUNDS', 'DGS10', 'T10Y2Y', 'UNRATE', 'VIXCLS']:
        r = get(f'{API}/api/economic/v1/get-fred-series?series_id={sid}&limit=120', headers)
        if r['ok']:
            out['endpoints']['fred'][sid] = r['data']
    (DATA / 'worldmonitor-live.json').write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'[live] saved {len(out["endpoints"])} endpoint groups, {len(out["errors"])} errors')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--public-only', action='store_true')
    ap.add_argument('--no-live', action='store_true')
    ap.add_argument('--api-key', default=None)
    args = ap.parse_args()
    public_data()
    if args.public_only or args.no_live:
        print('[live] skipped')
        return 0
    key = args.api_key or os.environ.get('WORLDMONITOR_API_KEY')
    if not key:
        print('[live] no WORLDMONITOR_API_KEY — public data only. Set the env var to fetch live endpoints.')
        return 0
    live_data(key)
    return 0


if __name__ == '__main__':
    sys.exit(main())
