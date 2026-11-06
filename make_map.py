#!/usr/bin/env python3
"""Convert worldmonitor TopoJSON land to an equirectangular SVG path."""
import json, math, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG = {}
_cfg_path = ROOT / 'mi3.config.json'
if _cfg_path.exists():
    CFG = json.loads(_cfg_path.read_text(encoding='utf-8'))
WM = Path(os.environ.get('WORLDMONITOR_ROOT', CFG.get('data_sources', {}).get('worldmonitor', '../worldmonitor')))
if not WM.is_absolute():
    WM = (ROOT / WM).resolve()
SRC = WM / 'public/data/countries-110m.json'
OUT = Path('data/world-map.json')
W, H = 1000.0, 500.0

topo = json.loads(SRC.read_text())
tr = topo['transform']
sx, sy = tr['scale']; tx, ty = tr['translate']

def decode_arc(arc):
    x = y = 0
    pts = []
    for dx, dy in arc:
        x += dx; y += dy
        pts.append((tx + x * sx, ty + y * sy))
    return pts

arcs = [decode_arc(a) for a in topo['arcs']]

def project(lon, lat):
    return ((lon + 180.0) / 360.0 * W, (90.0 - lat) / 180.0 * H)

def ring_coords(ring):
    coords = []
    for idx in ring:
        if idx >= 0:
            arc = arcs[idx]
        else:
            arc = list(reversed(arcs[~idx]))
        if coords:
            coords.extend(arc[1:])
        else:
            coords.extend(arc)
    return [project(lon, lat) for lon, lat in coords]

def geom_paths(geom):
    t = geom['type']
    polys = []
    if t == 'Polygon':
        polys = [geom['arcs']]
    elif t == 'MultiPolygon':
        polys = geom['arcs']
    out = []
    for poly in polys:
        for ring in poly:
            pts = ring_coords(ring)
            if len(pts) < 3:
                continue
            # drop consecutive duplicates
            clean = [pts[0]]
            for p in pts[1:]:
                if abs(p[0]-clean[-1][0]) > 0.01 or abs(p[1]-clean[-1][1]) > 0.01:
                    clean.append(p)
            if len(clean) < 3:
                continue
            d = 'M' + ' '.join(f'{x:.1f},{y:.1f}' for x, y in clean) + 'Z'
            out.append(d)
    return out

land = topo['objects']['land']
paths = []
for g in land['geometries']:
    paths.extend(geom_paths(g))
# simplify: keep rings with a reasonable bbox area
filtered = []
for d in paths:
    nums = [float(v) for v in d.replace('M','').replace('Z','').split(',') for v in v.split(' ')]
    # not used; keep all
    filtered.append(d)
land_path = ''.join(filtered)
OUT.write_text(json.dumps({'width': W, 'height': H, 'land_path': land_path}, ensure_ascii=False, separators=(',',':')))
print('paths', len(filtered), 'bytes', OUT.stat().st_size)
