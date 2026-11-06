#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build unified global freight / trade intelligence dashboard data.

Sources
-------
- MI2 (local): summary.json + per-module SQLite DBs
- WorldMonitor chokepoint open data (public, CC-BY-4.0)
- WorldMonitor Five-Factor Scorecard (public, no key)
- Optional: data/worldmonitor-live.json (fetched with an API key)

Output
------
- data/unified.json
- data.js  (window.UNIFIED + window.WORLD_MAP, works from file://)
"""
from __future__ import annotations

import json
import math
import os
import sqlite3
import statistics as st
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG = {}
_cfg_path = ROOT / 'mi3.config.json'
if _cfg_path.exists():
    CFG = json.loads(_cfg_path.read_text(encoding='utf-8'))
MI2 = Path(os.environ.get('MI2_ROOT', CFG.get('data_sources', {}).get('mi2', '../MI2')))
if not MI2.is_absolute():
    MI2 = (ROOT / MI2).resolve()
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)

def jload(p: Path):
    return json.loads(p.read_text(encoding='utf-8'))

def r2(v):
    if v is None:
        return None
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None

def clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))

def mean(xs):
    xs = [x for x in xs if x is not None]
    return st.mean(xs) if xs else None

def zscore(arr):
    arr = [float(x) for x in arr if x is not None]
    if len(arr) < 3:
        return 0.0
    m = st.mean(arr); s = st.pstdev(arr)
    return (arr[-1] - m) / s if s else 0.0

def pct(cur, prev):
    if cur is None or prev is None or float(prev) == 0:
        return None
    return round((float(cur) - float(prev)) / abs(float(prev)) * 100, 1)

def connect(module: str):
    p = MI2 / module / f'{module}.db'
    if not p.exists():
        return None
    c = sqlite3.connect(f'file:{p}?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    return c

def q(c, sql, args=()):
    return c.execute(sql, args).fetchall()

# ---------------------------------------------------------------------------
# Load MI2 summary
# ---------------------------------------------------------------------------
summary = jload(MI2 / 'summary.json')
mods = {m['id']: m for m in summary['modules']}

def flatten_metrics(mod):
    out = []
    for m in mod.get('metrics', []):
        out.append(m)
    for g in mod.get('groups', []):
        out.extend(g.get('metrics', []))
    return out

def find_metric(module_id, label):
    for m in flatten_metrics(mods.get(module_id, {})):
        if m.get('label') == label:
            return m
    return None

def series_of(module_id, label):
    for s in mods.get(module_id, {}).get('series', []):
        if s.get('label') == label:
            return s.get('points', [])
    for g in mods.get(module_id, {}).get('groups', []):
        for s in g.get('series', []):
            if s.get('label') == label:
                return s.get('points', [])
    return []

def metric_id(module_id, label, mid, category, unit=None, source='MI2'):
    m = find_metric(module_id, label)
    if not m:
        return None
    return {
        'id': mid,
        'label': m['label'],
        'value': m['value'],
        'unit': m.get('unit') or unit or '',
        'prev': m.get('prev'),
        'change': m.get('change'),
        'pct': m.get('pct'),
        'asof': m.get('asof'),
        'prev_asof': m.get('prev_asof'),
        'series': series_of(module_id, label),
        'category': category,
        'source': source,
    }

freight_metrics = []
for mid, label in [('scfi', 'SCFI 종합'), ('bdi', 'BDI')]:
    x = metric_id('sea', label, mid, 'freight', source='MI2 · KSG')
    if x: freight_metrics.append(x)
for mid, label in [('fleet_ships', '운항 선박 수'), ('fleet_teu', '운항 선대')]:
    x = metric_id('linerlytica', label, mid, 'freight', source='MI2 · Linerlytica')
    if x: freight_metrics.append(x)
for mid, label in [('active_ships', 'Active Ships'), ('top100_teu', 'Top100 선대')]:
    x = metric_id('alphaliner', label, mid, 'freight', source='MI2 · Alphaliner')
    if x: freight_metrics.append(x)
x = metric_id('air', 'TAC 종합', 'tac', 'freight', source='MI2 · TAC Index')
if x: freight_metrics.append(x)

energy_metrics = []
for mid, label in [('brent', 'Brent'), ('wti', 'WTI'), ('dubai', 'Dubai')]:
    x = metric_id('oil', label, mid, 'energy', source='MI2 · Opinet')
    if x: energy_metrics.append(x)
for port, mid in [('Rotterdam', 'vlsfo_rotterdam'), ('Singapore', 'vlsfo_singapore'), ('Fujairah', 'vlsfo_fujairah')]:
    x = metric_id('oil', port, mid, 'energy', source='MI2 · Ship & Bunker')
    if x: energy_metrics.append(x)

macro_metrics = []
for mid, label in [('gscpi', 'GSCPI'), ('gdp', 'GDP 성장률 (월드)'), ('cpi', '물가상승률 (월드)')]:
    x = metric_id('macro', label, mid, 'macro', source='MI2 · NY Fed / World Bank')
    if x: macro_metrics.append(x)

# ---------------------------------------------------------------------------
# MI2 detail tables
# ---------------------------------------------------------------------------
sea = connect('sea')
scfi_regions = []
if sea:
    rows = q(sea, "SELECT region, dt, value FROM index_raw WHERE index_name='SCFI' ORDER BY dt")
    latest_dt = max(r['dt'] for r in rows)
    prev_dt = max((r['dt'] for r in rows if r['dt'] < latest_dt), default=None)
    latest = {r['region']: r['value'] for r in rows if r['dt'] == latest_dt}
    prev = {r['region']: r['value'] for r in rows if r['dt'] == prev_dt} if prev_dt else {}
    for region, value in sorted(latest.items(), key=lambda kv: -kv[1]):
        scfi_regions.append({'region': region, 'value': r2(value),
                             'prev': r2(prev.get(region)), 'pct': pct(value, prev.get(region))})
    bdi_latest_dt = max(r['dt'] for r in q(sea, "SELECT dt FROM index_raw WHERE index_name='BDI'"))
    bdi_rows = q(sea, "SELECT region, value FROM index_raw WHERE index_name='BDI' AND dt=?", (bdi_latest_dt,))
    bdi_prev_dt = max((r['dt'] for r in q(sea, "SELECT DISTINCT dt FROM index_raw WHERE index_name='BDI'")) if False else [r['dt'] for r in q(sea, "SELECT DISTINCT dt FROM index_raw WHERE index_name='BDI'") if r['dt'] < bdi_latest_dt], default=None)
    bdi_prev = {r['region']: r['value'] for r in q(sea, "SELECT region, value FROM index_raw WHERE index_name='BDI' AND dt=?", (bdi_prev_dt,))} if bdi_prev_dt else {}
    bdi_subindices = []
    for r in bdi_rows:
        bdi_subindices.append({'region': r['region'], 'value': r2(r['value']),
                               'prev': r2(bdi_prev.get(r['region'])), 'pct': pct(r['value'], bdi_prev.get(r['region']))})
    sea.close()

air = connect('air')
tac_routes = []
if air:
    latest = q(air, "SELECT snapshot_id, data_date FROM tac_master ORDER BY data_date DESC LIMIT 1")[0]
    prev = q(air, "SELECT snapshot_id FROM tac_master WHERE data_date < ? ORDER BY data_date DESC LIMIT 1", (latest['data_date'],))
    cur = {r['route_code']: r['index_value'] for r in q(air, "SELECT route_code, index_value FROM tac_detail WHERE snapshot_id=?", (latest['snapshot_id'],))}
    prv = {r['route_code']: r['index_value'] for r in q(air, "SELECT route_code, index_value FROM tac_detail WHERE snapshot_id=?", (prev[0]['snapshot_id'],))} if prev else {}
    for route, value in cur.items():
        tac_routes.append({'route': route, 'value': r2(value), 'prev': r2(prv.get(route)), 'pct': pct(value, prv.get(route))})
    air.close()

lin = connect('linerlytica')
fleet_status = []
if lin:
    d = q(lin, "SELECT MAX(snapshot_date) AS d FROM fleet_snapshot")[0]['d']
    for r in q(lin, "SELECT ship_status, ships, teu FROM fleet_snapshot WHERE snapshot_date=? ORDER BY ships DESC", (d,)):
        fleet_status.append({'status': r['ship_status'], 'ships': r['ships'], 'teu': r['teu']})
    lin.close()

alpha = connect('alphaliner')
top_operators = []
if alpha:
    d = q(alpha, "SELECT MAX(snapshot_date) AS d FROM operator_snapshots")[0]['d']
    for r in q(alpha, "SELECT rank, operator_name, total_teu, total_ships, market_share, country FROM operator_snapshots WHERE snapshot_date=? ORDER BY rank LIMIT 12", (d,)):
        top_operators.append({'rank': r['rank'], 'name': r['operator_name'], 'teu': r['total_teu'],
                              'ships': r['total_ships'], 'share': r['market_share'], 'country': r['country']})
    alpha.close()

fwd = connect('forwarders')
forwarders = []
if fwd:
    d = q(fwd, "SELECT MAX(date) AS d FROM forwarders")[0]['d']
    for r in q(fwd, "SELECT rank, provider, hq, revenue, teu, air_tons FROM forwarders WHERE date=? ORDER BY rank, revenue DESC LIMIT 12", (d,)):
        forwarders.append({'rank': r['rank'], 'name': r['provider'], 'hq': r['hq'], 'revenue': r['revenue'],
                           'teu': r['teu'], 'air_tons': r['air_tons']})
    fwd.close()

# ---------------------------------------------------------------------------
# WorldMonitor chokepoint open data
# ---------------------------------------------------------------------------
latest_cp = jload(DATA / 'chokepoints-latest.json')
cp_index = jload(DATA / 'chokepoints-index.json')
cp_history = {}
for d in cp_index['dates']:
    p = DATA / f'chokepoints-{d}.json'
    if p.exists():
        cp_history[d] = jload(p)

CHOKE_WEIGHTS = {
    'hormuz_strait': 0.20, 'malacca_strait': 0.18, 'suez': 0.15, 'bab_el_mandeb': 0.13,
    'panama': 0.08, 'taiwan_strait': 0.06, 'korea_strait': 0.05, 'dover_strait': 0.04,
    'gibraltar': 0.03, 'bosphorus': 0.03, 'cape_of_good_hope': 0.02, 'lombok_strait': 0.02,
    'kerch_strait': 0.01,
}
CHOKE_ROUTES = {
    'suez': ['China–Europe via Suez', 'China–US East via Suez', 'Gulf–Europe oil', 'Singapore–Med'],
    'malacca_strait': ['China–Europe via Suez', 'Gulf–Asia oil', 'Qatar–Asia LNG', 'India–SE Asia'],
    'hormuz_strait': ['Gulf–Europe oil', 'Gulf–Asia oil', 'Qatar–Europe LNG', 'Gulf–Americas via Cape'],
    'bab_el_mandeb': ['China–Europe via Suez', 'Gulf–Europe oil', 'India–Europe'],
    'panama': ['China–US East via Panama', 'US Gulf–Asia via Panama'],
    'taiwan_strait': ['China–US West', 'Intra-Asia container'],
    'cape_of_good_hope': ['Asia–Europe diversion', 'Gulf–Americas'],
    'bosphorus': ['Black Sea grain', 'Black Sea energy'],
    'kerch_strait': ['Black Sea grain', 'Black Sea energy'],
    'dover_strait': ['North Europe short-sea', 'UK–Europe'],
    'gibraltar': ['Med–Europe', 'Asia–Europe via Med'],
    'korea_strait': ['Korea–Japan', 'Korea–China'],
    'lombok_strait': ['Malacca bypass', 'Australia–Asia'],
}
BYPASS = {
    'suez': 'Cape of Good Hope (+12일, +35% 비용)',
    'bab_el_mandeb': 'Cape of Good Hope (+12일, +35% 비용)',
    'hormuz_strait': '파이프라인/육상 대체 (제한적)',
    'malacca_strait': 'Lombok Strait (우회, 소요 증가)',
    'panama': 'Suez/태평양 우회 (거리 증가)',
    'taiwan_strait': '항공/철도 대체 (컨테이너 한계)',
}

chokepoints = []
for c in latest_cp['chokepoints']:
    hist = []
    for d in cp_index['dates']:
        snap = cp_history.get(d)
        if not snap:
            continue
        row = next((x for x in snap['chokepoints'] if x['id'] == c['id']), None)
        if row:
            hist.append({'date': d, 'score': row['disruption_score'], 'status': row['status'],
                         'flow_ratio': row['flow_ratio'], 'wow': row['transit_wow_change_pct'],
                         'congestion': row['congestion_level'], 'war': row['war_risk_tier']})
    chokepoints.append({
        'id': c['id'], 'name': c['name'], 'lat': c['lat'], 'lon': c['lon'],
        'status': c['status'], 'score': c['disruption_score'], 'war_risk_tier': c['war_risk_tier'],
        'congestion_level': c['congestion_level'], 'active_warnings': c['active_warnings'],
        'ais_disruptions': c['ais_disruptions'], 'transit_today_total': c['transit_today_total'],
        'transit_today_tanker': c['transit_today_tanker'], 'transit_today_cargo': c['transit_today_cargo'],
        'transit_today_other': c['transit_today_other'], 'transit_wow_change_pct': c['transit_wow_change_pct'],
        'flow_ratio': c['flow_ratio'], 'flow_disrupted': c['flow_disrupted'], 'flow_source': c['flow_source'],
        'weight': CHOKE_WEIGHTS.get(c['id'], 0.02), 'routes': CHOKE_ROUTES.get(c['id'], []),
        'bypass': BYPASS.get(c['id']), 'history': hist,
    })

# ---------------------------------------------------------------------------
# WorldMonitor scorecard
# ---------------------------------------------------------------------------
sc = jload(DATA / 'scorecard.json')
countries = []
for c in sc.get('scorecards', []):
    ps = {p['pillar']: p for p in c['pillars']}
    scored = [p['subScore'] for p in c['pillars'] if p.get('hasScore')]
    avg = round(mean(scored), 1) if scored else None
    countries.append({
        'code': c['countryCode'], 'avg': avg,
        'pillars': {k: (v['subScore'] if v.get('hasScore') else None) for k, v in ps.items()},
        'bands': {k: v.get('band', '') for k, v in ps.items()},
        'coverage': {k: v.get('inputCoverage') for k, v in ps.items()},
    })
countries.sort(key=lambda x: (x['avg'] is None, -(x['avg'] or 0)))

# ---------------------------------------------------------------------------
# Composite scores
# ---------------------------------------------------------------------------
cp_weighted = sum(c['score'] * c['weight'] for c in chokepoints)
cp_max = max(c['score'] for c in chokepoints)
cp_top3 = sorted([c['score'] for c in chokepoints], reverse=True)[:3]
cp_top3_avg = mean(cp_top3) or 0
flows = [c['flow_ratio'] for c in chokepoints if c['flow_ratio'] is not None]
flow_stress = mean([max(0.0, min(1.0, 1.0 - f)) for f in flows]) if flows else 0
choke_score = clamp(0.5 * cp_weighted + 0.3 * cp_max + 0.2 * cp_top3_avg + flow_stress * 10)

scfi = next((m for m in freight_metrics if m['id'] == 'scfi'), None)
bdi = next((m for m in freight_metrics if m['id'] == 'bdi'), None)
tac = next((m for m in freight_metrics if m['id'] == 'tac'), None)
scfi_z = zscore([p[1] for p in (scfi or {}).get('series', [])])
bdi_z = zscore([p[1] for p in (bdi or {}).get('series', [])])
tac_z = zscore([p[1] for p in (tac or {}).get('series', [])])
freight_score = clamp(50 + 8 * scfi_z + 8 * bdi_z + 5 * tac_z)

brent = next((m for m in energy_metrics if m['id'] == 'brent'), None)
vlsfo_sg = next((m for m in energy_metrics if m['id'] == 'vlsfo_singapore'), None)
brent_z = zscore([p[1] for p in (brent or {}).get('series', [])])
vlsfo_z = zscore([p[1] for p in (vlsfo_sg or {}).get('series', [])])
energy_score = clamp(50 + 6 * brent_z + 6 * vlsfo_z)

gscpi = next((m for m in macro_metrics if m['id'] == 'gscpi'), None)
gdp = next((m for m in macro_metrics if m['id'] == 'gdp'), None)
cpi = next((m for m in macro_metrics if m['id'] == 'cpi'), None)
gscpi_v = gscpi['value'] if gscpi else 1.0
gdp_v = gdp['value'] if gdp else 3.0
cpi_v = cpi['value'] if cpi else 2.5
macro_score = clamp(50 + 20 * (gscpi_v - 1) + 3 * (cpi_v - 2.5) - 2 * (gdp_v - 3))

components = [
    {'id': 'chokepoint', 'label': 'Chokepoint risk', 'score': round(choke_score, 1), 'weight': 0.40,
     'summary': f'가중 평균 {cp_weighted:.1f} · 최대 {cp_max:.0f} · 상위 3개 평균 {cp_top3_avg:.1f}',
     'detail': '13개 해상 병목의 WorldMonitor 복합 교란 점수. 원유 수송 비중 가중 + 최대/상위 3개 꼬리 위험 + 유량 스트레스.'},
    {'id': 'freight', 'label': 'Freight pressure', 'score': round(freight_score, 1), 'weight': 0.25,
     'summary': f'SCFI z={scfi_z:.2f} · BDI z={bdi_z:.2f} · TAC z={tac_z:.2f}',
     'detail': 'SCFI/BDI/TAC의 1년 z-score 기반 운임 압력. 50 = 1년 평균, 100 = 극단적 고점.'},
    {'id': 'energy', 'label': 'Energy & bunker', 'score': round(energy_score, 1), 'weight': 0.20,
     'summary': f'Brent z={brent_z:.2f} · VLSFO(SG) z={vlsfo_z:.2f}',
     'detail': 'Brent/VLSFO 1년 z-score 기반 에너지 비용 압력.'},
    {'id': 'macro', 'label': 'Macro stress', 'score': round(macro_score, 1), 'weight': 0.15,
     'summary': f'GSCPI {gscpi_v} · CPI {cpi_v}% · GDP {gdp_v}%',
     'detail': 'GSCPI 수준 + 물가 - 성장 기반 거시 스트레스. 50 = 중립.'},
]
composite_score = round(sum(c['score'] * c['weight'] for c in components), 1)
band = 'critical' if composite_score >= 75 else 'high' if composite_score >= 60 else 'elevated' if composite_score >= 40 else 'normal'

# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------
alerts = []
def add_alert(severity, category, title, detail, entity=None):
    alerts.append({'severity': severity, 'category': category, 'title': title, 'detail': detail, 'entity': entity})

for c in chokepoints:
    if c['score'] >= 70:
        add_alert('critical', 'chokepoint', f"{c['name']} 교란 점수 {c['score']}", f"전쟁 위험 {c['war_risk_tier']} · 혼잡 {c['congestion_level']} · AIS 차질 {c['ais_disruptions']}건", {'type': 'chokepoint', 'id': c['id']})
    elif c['score'] >= 40:
        add_alert('high', 'chokepoint', f"{c['name']} 교란 점수 {c['score']}", f"전쟁 위험 {c['war_risk_tier']} · 혼잡 {c['congestion_level']}", {'type': 'chokepoint', 'id': c['id']})
    elif c['score'] >= 20:
        add_alert('watch', 'chokepoint', f"{c['name']} 교란 점수 {c['score']}", f"전쟁 위험 {c['war_risk_tier']} · 모니터링", {'type': 'chokepoint', 'id': c['id']})
    if c['flow_ratio'] is not None and c['flow_ratio'] < 0.85:
        add_alert('high', 'flow', f"{c['name']} 유량 {c['flow_ratio']*100:.0f}%", f"기준선 대비 유량 급감 · WoW {c['transit_wow_change_pct']}%", {'type': 'chokepoint', 'id': c['id']})
    if c['transit_wow_change_pct'] is not None and c['transit_wow_change_pct'] <= -15:
        add_alert('watch', 'transit', f"{c['name']} 통항 WoW {c['transit_wow_change_pct']}%", "주간 통항량 감소", {'type': 'chokepoint', 'id': c['id']})

if brent and brent['pct'] is not None and abs(brent['pct']) >= 5:
    add_alert('high' if abs(brent['pct']) >= 8 else 'watch', 'energy', f"Brent {brent['pct']:+.1f}%", f"${brent['value']} · 1일 급변동", {'type': 'metric', 'id': 'brent'})
if vlsfo_sg and vlsfo_sg['pct'] is not None and abs(vlsfo_sg['pct']) >= 4:
    add_alert('watch', 'energy', f"VLSFO Singapore {vlsfo_sg['pct']:+.1f}%", f"${vlsfo_sg['value']}/ton", {'type': 'metric', 'id': 'vlsfo_singapore'})
if bdi and bdi['pct'] is not None and bdi['pct'] >= 3:
    add_alert('watch', 'freight', f"BDI {bdi['pct']:+.1f}%", f"{bdi['value']} · dry bulk 반등", {'type': 'metric', 'id': 'bdi'})
if tac and tac['pct'] is not None and tac['pct'] >= 5:
    add_alert('watch', 'freight', f"TAC Index {tac['pct']:+.1f}%", f"{tac['value']} · 항공 운임 상승", {'type': 'metric', 'id': 'tac'})
if gscpi and gscpi['value'] is not None and gscpi['value'] >= 1.5:
    add_alert('high', 'macro', f"GSCPI {gscpi['value']}", "공급망 압력 고조", {'type': 'metric', 'id': 'gscpi'})
if cpi and cpi['value'] is not None and cpi['value'] >= 3.5:
    add_alert('watch', 'macro', f"World CPI {cpi['value']}%", "물가 압력", {'type': 'metric', 'id': 'cpi'})

sev_rank = {'critical': 0, 'high': 1, 'watch': 2, 'info': 3}
alerts.sort(key=lambda a: sev_rank.get(a['severity'], 9))

# ---------------------------------------------------------------------------
# Transmission chain
# ---------------------------------------------------------------------------
consumer_score = clamp(50 + 10 * (cpi_v - 2.5))
chain_nodes = [
    {'id': 'chokepoint', 'label': 'Chokepoint', 'score': round(choke_score, 1), 'color': 'amber'},
    {'id': 'freight', 'label': 'Freight', 'score': round(freight_score, 1), 'color': 'blue'},
    {'id': 'energy', 'label': 'Energy', 'score': round(energy_score, 1), 'color': 'orange'},
    {'id': 'macro', 'label': 'Macro', 'score': round(macro_score, 1), 'color': 'violet'},
    {'id': 'consumer', 'label': 'Consumer prices', 'score': round(consumer_score, 1), 'color': 'red'},
]
chain_links = [
    {'from': 'chokepoint', 'to': 'freight', 'weight': 0.8, 'label': '운항 차질 → 운임'},
    {'from': 'chokepoint', 'to': 'energy', 'weight': 0.9, 'label': '호르무즈/수에즈 → 원유'},
    {'from': 'freight', 'to': 'energy', 'weight': 0.6, 'label': '운임·벙커 수요'},
    {'from': 'energy', 'to': 'macro', 'weight': 0.7, 'label': '유가 → 물가'},
    {'from': 'freight', 'to': 'consumer', 'weight': 0.6, 'label': '운임 → 소비자 물가'},
    {'from': 'energy', 'to': 'consumer', 'weight': 0.8, 'label': '에너지 → 소비자 물가'},
    {'from': 'macro', 'to': 'freight', 'weight': 0.5, 'label': '경기 → 물동량'},
    {'from': 'macro', 'to': 'consumer', 'weight': 0.7, 'label': '경기·물가 → 소비자'},
]

# ---------------------------------------------------------------------------
# Optional WorldMonitor live data (API key)
# ---------------------------------------------------------------------------
live = None
live_path = DATA / 'worldmonitor-live.json'
if live_path.exists():
    try:
        live = jload(live_path)
    except Exception:
        live = None

# ---------------------------------------------------------------------------
# Assemble
# ---------------------------------------------------------------------------
unified = {
    'meta': {
        'project': 'MI3',
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
        'snapshot_date': latest_cp['snapshot_date'],
        'sources': [
            {'id': 'mi2', 'name': 'MI2 — Global Freight & Trade Intelligence', 'url': 'https://github.com/JamesJang-GU/MI2', 'license': '© JamesJang-GU'},
            {'id': 'wm-chokepoints', 'name': 'WorldMonitor Chokepoint Status (open data)', 'url': 'https://www.worldmonitor.app/data/v1/chokepoints/', 'license': 'CC-BY-4.0', 'attribution': latest_cp['attribution']},
            {'id': 'wm-scorecard', 'name': 'WorldMonitor Five-Factor Scorecard', 'url': 'https://www.worldmonitor.app/api/scorecard/v1/list-five-factor-scorecards', 'license': 'WorldMonitor'},
        ],
        'methodology': {
            'composite': '0.40*chokepoint + 0.25*freight + 0.20*energy + 0.15*macro',
            'chokepoint': '0.5*weighted_avg + 0.3*max + 0.2*top3_avg + 10*flow_stress',
            'freight': '50 + 8*z(SCFI) + 8*z(BDI) + 5*z(TAC)',
            'energy': '50 + 6*z(Brent) + 6*z(VLSFO SG)',
            'macro': '50 + 20*(GSCPI-1) + 3*(CPI-2.5) - 2*(GDP-3)',
            'z': '1-year z-score, 50 = 1-year mean',
        },
    },
    'composite': {
        'score': composite_score, 'band': band, 'components': components, 'alerts': alerts[:12],
    },
    'freight': {
        'updated': mods.get('sea', {}).get('updated'),
        'metrics': freight_metrics,
        'details': {
            'scfi_regions': scfi_regions,
            'bdi_subindices': bdi_subindices,
            'tac_routes': tac_routes,
            'fleet_status': fleet_status,
            'top_operators': top_operators,
            'forwarders': forwarders,
        },
    },
    'chokepoints': {
        'snapshot_date': latest_cp['snapshot_date'],
        'generated_at': latest_cp['generated_at'],
        'upstream_unavailable': latest_cp['upstream_unavailable'],
        'license': latest_cp['license'],
        'attribution': latest_cp['attribution'],
        'items': chokepoints,
    },
    'energy': {'metrics': energy_metrics},
    'macro': {'metrics': macro_metrics},
    'countries': {
        'source': 'WorldMonitor Five-Factor Scorecard',
        'computed_at': sc.get('computedAt'),
        'methodology_version': sc.get('methodologyVersion'),
        'items': countries,
        'selected': ['KR', 'US', 'CN', 'JP', 'DE', 'NL', 'SG', 'AE', 'IN', 'BR'],
    },
    'chain': {'nodes': chain_nodes, 'links': chain_links},
    'live': live,
}
(DATA / 'unified.json').write_text(json.dumps(unified, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')

world_map = jload(DATA / 'world-map.json')
js = '// Generated by build.py — do not edit by hand.\n'
js += 'window.UNIFIED = ' + json.dumps(unified, ensure_ascii=False, separators=(',', ':')) + ';\n'
js += 'window.WORLD_MAP = ' + json.dumps(world_map, ensure_ascii=False, separators=(',', ':')) + ';\n'
(ROOT / 'data.js').write_text(js, encoding='utf-8')

print('unified.json', (DATA / 'unified.json').stat().st_size, 'bytes')
print('data.js', (ROOT / 'data.js').stat().st_size, 'bytes')
print('composite', composite_score, band)
print('components', [(c['id'], c['score']) for c in components])
print('alerts', len(alerts), 'top:', alerts[0]['title'] if alerts else None)
print('chokepoints', len(chokepoints), 'countries', len(countries))
