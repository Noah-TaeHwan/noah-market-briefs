#!/usr/bin/env python3
"""JSON 페이로드로부터 정적 마켓 브리프 HTML을 렌더링한다.

향후 cron 자동화 연동을 위한 의존성 없는 헬퍼. 출력 마크업은
`assets/brief.css`(Premium Editorial 디자인 시스템)와 `2026/06/23/us-close.html`
샘플과 구조가 일치한다.
Example:
  python3 market-briefs/scripts/render_market_brief.py input.json market-briefs/2026/06/23/us-close.html
"""
from __future__ import annotations
import argparse, html, json
from pathlib import Path

CSS_REL_DEFAULT = "../../../assets/brief.css"
INDEX_REL_DEFAULT = "../../../index.html"


def esc(x):
    """HTML 특수문자를 이스케이프한다(속성/본문 공용)."""
    return html.escape(str(x), quote=True)


def render(payload: dict, css_rel: str = CSS_REL_DEFAULT, index_rel: str = INDEX_REL_DEFAULT) -> str:
    """페이로드를 완성된 브리프 HTML 문서 문자열로 렌더링한다.

    @param payload 브리프 데이터(title/market/window/takeaway/metrics/drivers/theses/watch/risks/quality 등)
    @param css_rel 문서 기준 brief.css 상대 경로
    @param index_rel 문서 기준 아카이브 인덱스 상대 경로
    @returns 단일 HTML 문서 문자열
    """

    def kicker():
        """히어로 상단 배지(시장·윈도우·선택적 note)를 만든다."""
        parts = [
            f'<span class="badge">{esc(payload.get("market","Market"))}</span>',
            f'<span class="badge">{esc(payload.get("window","Brief"))}</span>',
        ]
        note = payload.get("note", "")
        if note:
            parts.append(f'<span class="badge">{esc(note)}</span>')
        return "".join(parts)

    def metrics():
        """지표 카드 그리드를 만든다(tone: up/down/flat/warn → 색·방향 표시)."""
        return "".join(
            f'<div class="metric-card"><div class="metric-name">{esc(m.get("name",""))}</div>'
            f'<div class="metric-value {esc(m.get("tone","flat"))}">{esc(m.get("value",""))}</div>'
            f'<div class="metric-note">{esc(m.get("note",""))}</div></div>'
            for m in payload.get("metrics", [])
        )

    def drivers():
        """핵심 driver 리스트 항목을 만든다."""
        return "".join(
            f'<li><b>{esc(d.get("label",""))}</b> — {esc(d.get("text",""))}</li>'
            for d in payload.get("drivers", [])
        )

    def theses():
        """보유논지 민감도 카드를 만든다(signal: 시그널 태그 또는 민감도 핀)."""
        return "".join(
            f'<article class="thesis-card"><div class="thesis-head">'
            f'<span class="thesis-name">{esc(t.get("name",""))}</span>'
            f'<span class="signal">{esc(t.get("signal",""))}</span></div>'
            f'<div class="thesis-body">{esc(t.get("body",""))}</div></article>'
            for t in payload.get("theses", [])
        )

    def quality():
        """data quality 패널(라벨/값 셀)을 만든다. 없으면 빈 문자열."""
        items = payload.get("quality", [])
        if not items:
            return ""
        cells = "".join(
            f'<div><div class="label">{esc(q.get("label",""))}</div>'
            f'<div class="value">{esc(q.get("value",""))}</div></div>'
            for q in items
        )
        return f'<section class="section"><h2>Data quality</h2><div class="quality">{cells}</div></section>'

    watch = "".join(f'<li>{esc(w)}</li>' for w in payload.get("watch", []))
    risks = "".join(f'<li>{esc(r)}</li>' for r in payload.get("risks", []))
    favicon_rel = css_rel.rsplit("/", 1)[0] + "/favicon.svg" if "/" in css_rel else "favicon.svg"

    return f'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{esc(payload.get("title","Market Brief"))}</title>
<link rel="icon" type="image/svg+xml" href="{esc(favicon_rel)}"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link rel="stylesheet" href="{esc(css_rel)}"/>
</head>
<body>
<main class="shell">
<header class="masthead"><a class="wordmark" href="{esc(index_rel)}">Noah <span class="tag">Market Briefs</span></a><span class="masthead-meta">{esc(payload.get("market","Market"))} · {esc(payload.get("window","Brief"))}<br/>{esc(payload.get("generated",""))}</span></header>
<section class="hero">
<div class="kicker">{kicker()}</div>
<h1>{esc(payload.get("title","Market Brief"))}</h1>
<div class="takeaway" data-label="한 줄 결론">{esc(payload.get("takeaway",""))}</div>
<div class="meta-grid"><div class="meta-card"><div class="label">Generated</div><div class="value">{esc(payload.get("generated",""))}</div></div><div class="meta-card"><div class="label">Source</div><div class="value">{esc(payload.get("source",""))}</div></div><div class="meta-card"><div class="label">Data quality</div><div class="value">{esc(payload.get("data_quality",""))}</div></div><div class="meta-card"><div class="label">Use</div><div class="value">{esc(payload.get("use","Market sensitivity journal"))}</div></div></div>
</section>
<div class="grid">
<section class="section"><h2>숫자로 보는 시장</h2><div class="metrics">{metrics()}</div></section>
<section class="section"><h2>오늘의 핵심 driver</h2><ul class="driver-list">{drivers()}</ul></section>
</div>
<div class="grid">
<section class="section"><h2>Noah 보유논지 민감도</h2><div class="thesis-stack">{theses()}</div></section>
<section class="section"><h2>내일 볼 센서</h2><ul class="watch-list">{watch}</ul><h2 class="no-index" style="margin-top:20px">리스크 / 무효화 기준</h2><ul class="risk-list">{risks}</ul></section>
</div>
{quality()}
<footer class="footer"><span><a href="{esc(index_rel)}">← Archive index</a></span><span>Not investment advice · source-backed only</span></footer>
</main>
</body>
</html>'''


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
