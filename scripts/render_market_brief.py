#!/usr/bin/env python3
"""Render a static market brief HTML file from a JSON payload.

Dependency-free helper for future cron 러너 cron integration.
Example:
  python3 market-briefs/scripts/render_market_brief.py input.json market-briefs/2026/06/23/us-close.html
"""
from __future__ import annotations
import argparse, html, json
from pathlib import Path

CSS_REL_DEFAULT = "../../../assets/brief.css"
INDEX_REL_DEFAULT = "../../../index.html"

def esc(x):
    return html.escape(str(x), quote=True)

def render(payload: dict, css_rel: str = CSS_REL_DEFAULT, index_rel: str = INDEX_REL_DEFAULT) -> str:
    def metrics():
        return "".join(
            f'<article class="metric-card"><div class="metric-name">{esc(m.get("name",""))}</div><div class="metric-value {esc(m.get("tone","flat"))}">{esc(m.get("value",""))}</div><div class="metric-note">{esc(m.get("note",""))}</div></article>'
            for m in payload.get("metrics", [])
        )
    def drivers():
        return "".join(f'<li><b>{esc(d.get("label",""))}</b> — {esc(d.get("text",""))}</li>' for d in payload.get("drivers", []))
    def theses():
        return "".join(
            f'<article class="thesis-card"><div class="thesis-head"><span class="thesis-name">{esc(t.get("name",""))}</span><span class="signal">{esc(t.get("signal",""))}</span></div><div class="thesis-body">{esc(t.get("body",""))}</div></article>'
            for t in payload.get("theses", [])
        )
    watch = "".join(f'<li>{esc(w)}</li>' for w in payload.get("watch", []))
    risks = "".join(f'<li>{esc(r)}</li>' for r in payload.get("risks", []))
    return f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><title>{esc(payload.get("title","Market Brief"))}</title><link rel="stylesheet" href="{esc(css_rel)}"/></head>
<body><main class="shell"><section class="hero"><div class="kicker"><span class="badge">{esc(payload.get("market","Market"))}</span><span>{esc(payload.get("window","Brief"))}</span></div><h1>{esc(payload.get("title","Market Brief"))}</h1><p class="takeaway">{esc(payload.get("takeaway",""))}</p><div class="meta-grid"><div class="meta-card"><div class="label">Generated</div><div class="value">{esc(payload.get("generated",""))}</div></div><div class="meta-card"><div class="label">Source</div><div class="value">{esc(payload.get("source",""))}</div></div><div class="meta-card"><div class="label">Data quality</div><div class="value">{esc(payload.get("data_quality",""))}</div></div><div class="meta-card"><div class="label">Use</div><div class="value">Market sensitivity journal</div></div></div></section><section class="grid"><div class="section"><h2>숫자로 보는 시장</h2><div class="metrics">{metrics()}</div></div><div class="section"><h2>오늘의 핵심 driver</h2><ul class="driver-list">{drivers()}</ul></div></section><section class="grid"><div class="section"><h2>Noah 보유논지 민감도</h2><div class="thesis-stack">{theses()}</div></div><div class="section"><h2>내일 볼 센서</h2><ul class="watch-list">{watch}</ul><h2 style="margin-top:18px">리스크 / 무효화 기준</h2><ul class="risk-list">{risks}</ul></div></section><footer class="footer"><span><a href="{esc(index_rel)}">← Archive index</a></span><span>Not investment advice · source-backed only</span></footer></main></body></html>'''

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_json")
    ap.add_argument("output_html")
    ap.add_argument("--css-rel", default=CSS_REL_DEFAULT)
    ap.add_argument("--index-rel", default=INDEX_REL_DEFAULT)
    args = ap.parse_args()
    payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    out = Path(args.output_html)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(payload, args.css_rel, args.index_rel), encoding="utf-8")

if __name__ == "__main__":
    main()
