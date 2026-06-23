#!/usr/bin/env python3
"""JSON 페이로드로부터 정적 마켓 브리프 HTML을 렌더링한다.

향후 cron 자동화 연동을 위한 의존성 없는 헬퍼. 출력 마크업은
`assets/brief.css`("Lamplight Ledger" 다크 노턴 디자인 시스템)와 1:1로 대응한다.
숫자가 주인공인 와이어 보드 + 시그니처 라이브 와이어 + 보유논지 민감도 미터.

Example:
  python3 scripts/render_market_brief.py input.json 2026/06/23/us-close.html
"""
from __future__ import annotations
import argparse, html, json
from pathlib import Path

CSS_REL_DEFAULT = "../../../assets/brief.css"
INDEX_REL_DEFAULT = "../../../index.html"

# 톤 화이트리스트 — 알 수 없는 값은 무신호(slate)로 떨어진다.
_TONES = {"up", "down", "warn", "flat", "unknown"}
# "무신호" 판정 토큰(미확인/no signal). 값이 비었거나 이 토큰이면 nosignal 처리.
_NOSIGNAL_TOKENS = {"미확인", "no signal", "n/a", "na", "—", "-"}


def esc(x):
    """HTML 특수문자를 이스케이프한다(속성/본문 공용)."""
    return html.escape(str(x), quote=True)


def _tone(m: dict) -> str:
    """metric 의 tone 을 화이트리스트로 정규화한다(없으면 flat)."""
    t = str(m.get("tone", "flat")).strip().lower()
    return t if t in _TONES else "flat"


def _is_nosignal(m: dict) -> bool:
    """값이 비었거나 '미확인' 류면 무신호(no signal) 카드로 본다."""
    val = str(m.get("value", "")).strip()
    return (not val) or val.lower() in _NOSIGNAL_TOKENS or _tone(m) == "unknown"


def _split_note(note: str):
    """note 를 (delta, source) 로 분리한다. 첫 ' · '(가운뎃점) 기준.

    예: "-910.71 / -9.99% · Naver Finance 2026.06.23"
        → ("-910.71 / -9.99%", "Naver Finance 2026.06.23")
    구분자가 없으면 (note, "") — delta 줄에 전체를 둔다.
    """
    note = str(note or "")
    for sep in (" · ", " — ", " | "):
        if sep in note:
            head, tail = note.split(sep, 1)
            return head.strip(), tail.strip()
    return note.strip(), ""


def render(payload: dict, css_rel: str = CSS_REL_DEFAULT, index_rel: str = INDEX_REL_DEFAULT) -> str:
    """페이로드를 완성된 브리프 HTML 문서 문자열로 렌더링한다(Lamplight Ledger).

    데이터 주도 규칙:
      - metrics[0]      → 히어로 feature 카드(가장 큰 숫자 + 라이브 와이어 시그니처)
      - metrics[1:4]    → 헤드라인 인덱스 카드(최대 3개) — feature 와 같은 보드(.indices)
      - metrics[4:]     → 컴팩트 매크로 카드(.macros). 값이 '미확인'이면 무신호 처리.
    누락 필드는 payload.get(k, default) 로 우아하게 degrade 한다(thesis level/lead 등 선택).

    @param payload 브리프 데이터(title/market/window/note/generated/source/data_quality/
                   use/takeaway/metrics/drivers/theses/watch/risks/quality)
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

    def idx_card(m: dict, feature: bool = False) -> str:
        """헤드라인 보드의 인덱스 카드 하나. feature=True 면 라이브 와이어를 단다."""
        tone = _tone(m)
        nosig = _is_nosignal(m)
        delta, src = _split_note(m.get("note", ""))
        cls = "idx feature" if feature else "idx"
        ival_tone = "" if nosig else tone
        if nosig:
            val_html = f'{esc(m.get("value","미확인") or "미확인")} <span class="nosig-chip">no signal</span>'
        else:
            val_html = esc(m.get("value", ""))
        wire = f'<div class="wire {tone if tone in ("up","down","warn") else ""}" aria-hidden="true"></div>' if feature else ""
        delta_html = f'<div class="idelta {ival_tone} tnum">{esc(delta)}</div>' if delta else ""
        src_html = f'<div class="isrc">{esc(src)}</div>' if src else ""
        return (
            f'<article class="{cls}">'
            f'<div class="iname">{esc(m.get("name",""))}</div>'
            f'<div class="ival {ival_tone} tnum">{val_html}</div>'
            f'{delta_html}{wire}{src_html}</article>'
        )

    def mcard(m: dict) -> str:
        """컴팩트 매크로 카드 하나. 값이 '미확인'이면 무신호(slate) 처리."""
        tone = _tone(m)
        if _is_nosignal(m):
            return (
                f'<div class="mcard nosignal">'
                f'<div class="mname">{esc(m.get("name",""))}</div>'
                f'<div class="mval">{esc(m.get("value","미확인") or "미확인")} '
                f'<span class="nosig-chip">no signal</span></div>'
                f'<div class="mnote">{esc(m.get("note",""))}</div></div>'
            )
        return (
            f'<div class="mcard">'
            f'<div class="mname">{esc(m.get("name",""))}</div>'
            f'<div class="mval {tone} tnum">{esc(m.get("value",""))}</div>'
            f'<div class="mnote">{esc(m.get("note",""))}</div></div>'
        )

    def market_board() -> str:
        """'숫자로 보는 시장' 섹션. metrics 가 없으면 빈 문자열."""
        metrics = payload.get("metrics", [])
        if not metrics:
            return ""
        hero = metrics[0]
        index_tier = metrics[1:4]          # 최대 3개
        macro_tier = metrics[4:]
        n_cols = 1 + len(index_tier)       # 1(feature) + index 카드 수 (1~4)
        attached = " attached" if macro_tier else ""
        idx_html = idx_card(hero, feature=True) + "".join(idx_card(m) for m in index_tier)
        board = f'<div class="indices cols-{n_cols}{attached}">{idx_html}</div>'
        if macro_tier:
            m_cols = min(4, len(macro_tier))
            board += f'<div class="macros mcols-{m_cols}">{"".join(mcard(m) for m in macro_tier)}</div>'
        return f'<section class="section"><h2>숫자로 보는 시장</h2>{board}</section>'

    def drivers_section() -> str:
        """핵심 driver 섹션. 없으면 빈 문자열."""
        items = payload.get("drivers", [])
        if not items:
            return ""
        lis = "".join(
            f'<li><b>{esc(d.get("label",""))}</b> — {esc(d.get("text",""))}</li>'
            for d in items
        )
        return f'<section class="section"><h2>오늘의 핵심 driver</h2><ul class="driver-list">{lis}</ul></section>'

    def theses_section() -> str:
        """보유논지 민감도 섹션. signal 태그 + 선택적 level 미터(●●●) + 선택적 lead.

        @note level(1~3) 이 있으면 ``signal lvlN`` + 3-도트 미터를 달고, 카드 테두리
              톤(s-high/s-mid)을 입힌다. lead 가 있으면 본문 앞 굵은 리드 줄. 둘 다
              없으면 핀/미터/리드 없이 깔끔하게 degrade(예: us-close).
        """
        items = payload.get("theses", [])
        if not items:
            return ""
        out = []
        for t in items:
            lvl = t.get("level")
            has_lvl = lvl in (1, 2, 3)
            sig_cls = "signal lvl%d" % lvl if has_lvl else "signal"
            meter = '<span class="meter" aria-hidden="true"><i></i><i></i><i></i></span>' if has_lvl else ""
            card_cls = {3: "thesis-card s-high", 2: "thesis-card s-mid"}.get(lvl, "thesis-card")
            lead = t.get("lead", "")
            lead_html = f'<span class="thesis-lead">{esc(lead)}</span>' if lead else ""
            sig_inner = f'{esc(t.get("signal",""))} {meter}' if meter else esc(t.get("signal", ""))
            out.append(
                f'<article class="{card_cls}"><div class="thesis-head">'
                f'<span class="thesis-name">{esc(t.get("name",""))}</span>'
                f'<span class="{sig_cls}">{sig_inner}</span></div>'
                f'<div class="thesis-body">{lead_html}{esc(t.get("body",""))}</div></article>'
            )
        return f'<section class="section"><h2>Noah 보유논지 민감도</h2><div class="thesis-stack">{"".join(out)}</div></section>'

    def watch_section() -> str:
        """내일 볼 센서 섹션. 없으면 빈 문자열."""
        items = payload.get("watch", [])
        if not items:
            return ""
        lis = "".join(f'<li>{esc(w)}</li>' for w in items)
        return f'<section class="section"><h2>내일 볼 센서</h2><ul class="watch-list">{lis}</ul></section>'

    def risks_section() -> str:
        """리스크 / 무효화 기준 섹션(번호 없는 h2). 없으면 빈 문자열."""
        items = payload.get("risks", [])
        if not items:
            return ""
        lis = "".join(f'<li>{esc(r)}</li>' for r in items)
        return f'<section class="section"><h2 class="no-index">리스크 / 무효화 기준</h2><ul class="risk-list">{lis}</ul></section>'

    def quality_section() -> str:
        """data quality 패널(번호 없는 h2). 없으면 빈 문자열."""
        items = payload.get("quality", [])
        if not items:
            return ""
        cells = "".join(
            f'<div><div class="label">{esc(q.get("label",""))}</div>'
            f'<div class="value">{esc(q.get("value",""))}</div></div>'
            for q in items
        )
        return f'<section class="section"><h2 class="no-index">Data quality</h2><div class="quality">{cells}</div></section>'

    def grid_row(grid_cls: str, sections: list) -> str:
        """두 섹션을 한 그리드 줄로 묶는다. 하나만 있으면 풀-width, 없으면 생략."""
        present = [s for s in sections if s]
        if not present:
            return ""
        if len(present) == 1:
            return present[0]
        return f'<div class="grid {grid_cls}">{"".join(present)}</div>'

    takeaway = payload.get("takeaway", "")
    favicon_rel = css_rel.rsplit("/", 1)[0] + "/favicon.svg" if "/" in css_rel else "favicon.svg"

    body_blocks = "\n".join(b for b in [
        market_board(),
        grid_row("split", [drivers_section(), theses_section()]),
        grid_row("even", [watch_section(), risks_section()]),
        quality_section(),
    ] if b)

    return f'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{esc(payload.get("title","Market Brief"))}</title>
<link rel="icon" type="image/svg+xml" href="{esc(favicon_rel)}"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin/>
<link rel="stylesheet" href="{esc(css_rel)}"/>
</head>
<body>
<main class="shell">
<header class="masthead"><a class="wordmark" href="{esc(index_rel)}">Noah <span class="tag">Market Briefs</span></a><div class="masthead-meta"><span class="live-dot" aria-hidden="true"></span><span><span class="stamp">{esc(payload.get("market","Market"))} · {esc(payload.get("window","Brief"))}</span><span class="stamp"><b>{esc(payload.get("generated",""))}</b></span></span></div></header>
<section class="hero">
<div class="kicker">{kicker()}</div>
<h1>{esc(payload.get("title","Market Brief"))}</h1>
<p class="takeaway" data-label="한 줄 결론">{esc(takeaway)}</p>
<div class="meta-grid"><div class="meta-card"><div class="label">Generated</div><div class="value">{esc(payload.get("generated",""))}</div></div><div class="meta-card"><div class="label">Source</div><div class="value">{esc(payload.get("source",""))}</div></div><div class="meta-card"><div class="label">Data quality</div><div class="value">{esc(payload.get("data_quality",""))}</div></div><div class="meta-card"><div class="label">Use</div><div class="value">{esc(payload.get("use","Market sensitivity journal"))}</div></div></div>
</section>
{body_blocks}
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
