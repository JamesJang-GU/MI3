#!/usr/bin/env python3
"""Inline data.js into index.html to produce a single-file dashboard."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent
html = (ROOT / 'index.html').read_text(encoding='utf-8')
data = (ROOT / 'data.js').read_text(encoding='utf-8')
if '</script>' in data:
    raise SystemExit('data.js contains a closing script tag; escape it before inlining')
out = html.replace('<script src="data.js"></script>', '<script>' + data + '</script>')
(ROOT / 'standalone.html').write_text(out, encoding='utf-8')
print(f'standalone.html {len(out):,} bytes')
