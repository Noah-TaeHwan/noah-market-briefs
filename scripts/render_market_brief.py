#!/usr/bin/env python3
"""JSON 페이로드로부터 정적 마켓 브리프 HTML을 렌더링한다.

향후 cron 자동화 연동을 위한 의존성 없는 헬퍼. 출력 마크업은
`assets/brief.css`("Lamplight Ledger" 다크 노턴 디자인 시스템)와 1:1로 대응한다.
숫자가 주인공인 와이어 보드 + 시그니처 라이브 와이어 + 보유논지 민감도 미터.

Example:
  python3 scripts/render_market_brief.py input.json 2026/06/23/us-close.html
"""
from __future__ import annotations
import argparse, html, json, re
from pathlib import Path

CSS_REL_DEFAULT = "../../../assets/brief.css"
INDEX_REL_DEFAULT = "../../../index.html"

# 톤 화이트리스트 — 알 수 없는 값은 무신호(slate)로 떨어진다.
_TONES = {"up", "down", "warn", "flat", "unknown"}
# "무신호" 판정 토큰(미확인/no signal). 값이 비었거나 이 토큰이면 nosignal 처리.
_NOSIGNAL_TOKENS = {"미확인", "no signal", "n/a", "na", "—", "-"}
# H1 제목의 끝-날짜를 분리하는 em-dash(—). 예: "한국 시장 마감 — 2026-06-23".
_EM_DASH = "—"

# 어제 대비 방향 칩: up=▲ / down=▼ / flat== (색은 brief.css --good/--bad/--muted)
_DIRS = {"up": "▲", "down": "▼", "flat": "="}


def _dir_chip(d) -> str:
    """어제 대비 방향 칩 HTML. up/down/flat 외 값은 flat 으로 떨어진다.

    @param d 방향 문자열(up/down/flat)
    @returns ``<span class="dir ...">`` 칩 HTML
    """
    d = str(d or "flat").strip().lower()
    if d not in _DIRS:
        d = "flat"
    return f'<span class="dir {d}" aria-hidden="true">{_DIRS[d]}</span>'


def esc(x):
    """HTML 특수문자를 이스케이프한다(속성/본문 공용)."""
    return html.escape(str(x), quote=True)


def _value_tone(text: str, fallback: str) -> str:
    """복합 지표 조각의 숫자 방향을 텍스트에서 추론한다.

    @param text 지표 조각(예: ``"S&P 500 -0.01%"`` 또는 ``"18.89 (+1.40%)"``)
    @param fallback 명시적 부호가 없을 때 사용할 카드 톤
    @returns ``up``/``down``/``warn``/``flat`` 중 하나
    """
    s = str(text or "")
    if re.search(r"(^|[\s(])\+\s*\d", s):
        return "up"
    if re.search(r"(^|[\s(])-\s*\d", s):
        return "down"
    return fallback if fallback in {"up", "down", "warn", "flat"} else "flat"


def _segment_parts(segment: str) -> tuple[str, str]:
    """복합 지표 한 조각을 라벨과 숫자로 나눈다.

    부호가 있는 마지막 숫자 덩어리를 값으로 본다. 예를 들어
    ``"Dow +0.14%"`` → (``"Dow"``, ``"+0.14%"``). 부호가 없으면 원문 전체를
    라벨로 둬서 손실 없이 표시한다.

    @param segment 슬래시로 분리된 지표 조각
    @returns (label, number) 튜플. 숫자 추출 실패 시 number는 빈 문자열.
    """
    seg = str(segment or "").strip()
    m = re.match(
        r"^(?P<label>.*?)(?P<num>[+-]\s*\d[\d,]*(?:\.\d+)?(?:%|%p|bp|원|조원|억원|달러|pts?|p)?(?:\s*\([^)]*\))?)$",
        seg,
    )
    if not m:
        return seg, ""
    label = m.group("label").strip()
    num = m.group("num").replace("+ ", "+").replace("- ", "-").strip()
    return label, num


def _metric_value_html(value: str, fallback_tone: str) -> tuple[bool, str]:
    """복합 값(``A +x / B -y``)을 행 단위 HTML로 바꾼다.

    슬래시로 여러 지표가 묶인 경우 카드 안에서 각 지표를 ``라벨 | 숫자`` 행으로
    분리해 읽기 쉽게 만든다. 단일 값은 기존 렌더링을 유지한다.

    @param value metric value 원문
    @param fallback_tone 카드의 기본 tone
    @returns (복합 렌더 여부, HTML 문자열)
    """
    raw = str(value or "")
    parts = [p.strip() for p in raw.split(" / ") if p.strip()]
    if len(parts) < 2:
        return False, esc(raw)
    rows = []
    for part in parts:
        label, num = _segment_parts(part)
        if num:
            tone = _value_tone(num, fallback_tone)
            rows.append(
                f'<span class="metric-seg"><span class="seg-label">{esc(label)}</span>'
                f'<span class="seg-num {tone} tnum">{esc(num)}</span></span>'
            )
        else:
            rows.append(
                f'<span class="metric-seg single"><span class="seg-label">{esc(label)}</span></span>'
            )
    return True, f'<span class="metric-segs" aria-label="{esc(raw)}">{"".join(rows)}</span>'


def _macro_cols(count: int) -> int:
    """매크로 카드 그리드의 빈 칸이 최소가 되는 컬럼 수를 고른다.

    @param count macro_tier 카드 수
    @returns CSS 클래스 ``mcols-N``의 N 값
    """
    if count <= 0:
        return 0
    if count <= 4:
        return count
    if count % 3 == 0 or count % 4 == 1:
        return 3
    return 4


def _h1_html(title: str) -> str:
    """H1 표시용 HTML 을 만든다(데이터 불변 · 표시 마크업만 추가).

    제목이 em-dash(—)로 본문과 끝-날짜를 가르면, 트레일링 날짜 토큰을
    줄바꿈 불가 span(``.h1-date``)으로 감싸 "— 2026-06-23"이 하이픈에서
    어색하게 쪼개지지 않게 한다. em-dash 가 없으면 제목을 그대로 이스케이프.

    @param title 페이로드 title(예: "한국 시장 마감 — 2026-06-23")
    @returns H1 내부 HTML 문자열(이스케이프 완료)
    """
    title = str(title)
    if _EM_DASH in title:
        head, _sep, tail = title.rpartition(_EM_DASH)  # 마지막 em-dash 기준 → 끝-날짜 분리
        head, tail = head.strip(), tail.strip()
        if head and tail:
            return (f'{esc(head)} <span class="dash">{_EM_DASH}</span> '
                    f'<span class="h1-date">{esc(tail)}</span>')
    return esc(title)


def _tone(m: dict) -> str:
    """metric 의 tone 을 화이트리스트로 정규화한다(없으면 flat)."""
    t = str(m.get("tone", "flat")).strip().lower()
    return t if t in _TONES else "flat"


def _is_nosignal(m: dict) -> bool:
    """값이 비었거나 '미확인' 류면 무신호(no signal) 카드로 본다."""
    val = str(m.get("value", "")).strip()
    return (not val) or val.lower() in _NOSIGNAL_TOKENS or _tone(m) == "unknown"


def _split_note(note: str):
    """note 를 (delta, source) 로 분리한다.

    첫 ' · '(가운뎃점)·em dash·pipe 기준으로 ``delta``와 ``source``를 나눈다.
    구분자가 없어도 CNBC/Naver/연합뉴스/date 같은 출처형 문자열이면 숫자 아래의
    컬러 delta 줄이 아니라 작은 출처 줄(``.isrc``)로 보낸다.

    예: "-910.71 / -9.99% · Naver Finance 2026.06.23"
        → ("-910.71 / -9.99%", "Naver Finance 2026.06.23")
    예: "CNBC quote-cache, 2026-06-25 ..." → ("", "CNBC quote-cache, ...")
    """
    note = str(note or "")
    for sep in (" · ", " — ", " | "):
        if sep in note:
            head, tail = note.split(sep, 1)
            return head.strip(), tail.strip()
    source_like = re.search(
        r"\b(CNBC|Naver|Hana|Yonhap|Yahoo|Tradeweb|CBOE|CBOT|quote-cache)\b|연합뉴스|20\d{2}[-./년]",
        note,
        re.IGNORECASE,
    )
    if source_like:
        return "", note.strip()
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
            has_segs = False
        else:
            has_segs, val_html = _metric_value_html(m.get("value", ""), tone)
        wire = f'<div class="wire {tone if tone in ("up","down","warn") else ""}" aria-hidden="true"></div>' if feature else ""
        delta_html = f'<div class="idelta {ival_tone} tnum">{esc(delta)}</div>' if delta else ""
        src_html = f'<div class="isrc">{esc(src)}</div>' if src else ""
        val_cls = f'ival {ival_tone} tnum' + (' has-segs' if has_segs else '')
        return (
            f'<article class="{cls}">'
            f'<div class="iname">{esc(m.get("name",""))}</div>'
            f'<div class="{val_cls}">{val_html}</div>'
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
        has_segs, val_html = _metric_value_html(m.get("value", ""), tone)
        val_cls = f'mval {tone} tnum' + (' has-segs' if has_segs else '')
        return (
            f'<div class="mcard">'
            f'<div class="mname">{esc(m.get("name",""))}</div>'
            f'<div class="{val_cls}">{val_html}</div>'
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
            m_cols = _macro_cols(len(macro_tier))
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
        """투자 관점 읽기(렌즈) 섹션. signal 태그 + 선택적 level 미터(●●●) +
        선택적 delta(어제 대비 한 줄) + 선택적 lead.

        @note level(1~3) 이 있으면 ``signal lvlN`` + 3-도트 미터 + 카드 테두리 톤
              (s-high/s-mid). delta(``{dir,text}``) 가 있으면 본문 앞 어제 대비 한 줄,
              lead 가 있으면 굵은 리드 줄. 모두 없으면 깔끔하게 degrade(하위호환).
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
            delta = t.get("delta")
            delta_html = ""
            if isinstance(delta, dict) and str(delta.get("text", "")).strip():
                delta_html = (f'<div class="thesis-delta">{_dir_chip(delta.get("dir"))}'
                              f'<span>{esc(delta.get("text",""))}</span></div>')
            lead = t.get("lead", "")
            lead_html = f'<span class="thesis-lead">{esc(lead)}</span>' if lead else ""
            sig_inner = f'{esc(t.get("signal",""))} {meter}' if meter else esc(t.get("signal", ""))
            out.append(
                f'<article class="{card_cls}"><div class="thesis-head">'
                f'<span class="thesis-name">{esc(t.get("name",""))}</span>'
                f'<span class="{sig_cls}">{sig_inner}</span></div>'
                f'<div class="thesis-body">{delta_html}{lead_html}{esc(t.get("body",""))}</div></article>'
            )
        return f'<section class="section"><h2>투자 관점 읽기</h2><div class="thesis-stack">{"".join(out)}</div></section>'

    def watch_section() -> str:
        """볼 센서 섹션. 장전(preopen)이면 '오늘', 마감·기본이면 '내일'. 없으면 빈 문자열."""
        items = payload.get("watch", [])
        if not items:
            return ""
        heading = "오늘 볼 센서" if payload.get("window_code") == "preopen" else "내일 볼 센서"
        lis = "".join(f'<li>{esc(w)}</li>' for w in items)
        return f'<section class="section"><h2>{esc(heading)}</h2><ul class="watch-list">{lis}</ul></section>'

    def hypothesis_review_section() -> str:
        """직전 브리프의 체크 가설을 이번 데이터로 검증한 결과.

        item 은 ``{previous_hypothesis|hypothesis, verdict, evidence, reason, lesson}`` 권장.
        문자열만 들어와도 크래시 없이 단순 카드로 렌더한다.
        """
        items = payload.get("hypothesis_review", [])
        if not items:
            return ""
        rows = []
        for item in items:
            if isinstance(item, dict):
                hyp = str(item.get("previous_hypothesis") or item.get("hypothesis") or "").strip()
                verdict = str(item.get("verdict") or "검증").strip()
                evidence = str(item.get("evidence") or "").strip()
                reason = str(item.get("reason") or "").strip()
                lesson = str(item.get("lesson") or "").strip()
                if not any([hyp, evidence, reason, lesson]):
                    continue
                body_parts = []
                if evidence:
                    body_parts.append(f'<p><b>근거</b> — {esc(evidence)}</p>')
                if reason:
                    body_parts.append(f'<p><b>판단</b> — {esc(reason)}</p>')
                if lesson:
                    body_parts.append(f'<p><b>학습</b> — {esc(lesson)}</p>')
                rows.append(
                    f'<article class="hcard"><div class="hhead"><span class="hname">{esc(hyp)}</span>'
                    f'<span class="verdict">{esc(verdict)}</span></div>'
                    f'<div class="hbody">{"".join(body_parts)}</div></article>'
                )
            else:
                text = str(item or "").strip()
                if text:
                    rows.append(f'<article class="hcard"><div class="hbody">{esc(text)}</div></article>')
        if not rows:
            return ""
        return f'<section class="section"><h2>이전 가설 검증</h2><div class="hypothesis-stack">{"".join(rows)}</div></section>'

    def next_hypotheses_section() -> str:
        """다음 회차에서 검증할 관찰 가능한 가설.

        item 은 ``{hypothesis, observable, invalidation, horizon}`` 권장. 예측 확정이 아니라
        다음 cron이 판정할 체크포인트로 렌더한다.
        """
        items = payload.get("next_hypotheses", [])
        if not items:
            return ""
        rows = []
        for item in items:
            if isinstance(item, dict):
                hyp = str(item.get("hypothesis") or "").strip()
                obs = str(item.get("observable") or "").strip()
                inv = str(item.get("invalidation") or "").strip()
                horizon = str(item.get("horizon") or "").strip()
                if not any([hyp, obs, inv, horizon]):
                    continue
                meta = []
                if obs:
                    meta.append(f'<p><b>관찰값</b> — {esc(obs)}</p>')
                if inv:
                    meta.append(f'<p><b>반증 조건</b> — {esc(inv)}</p>')
                if horizon:
                    meta.append(f'<p><b>검증 시점</b> — {esc(horizon)}</p>')
                rows.append(
                    f'<article class="hcard next"><div class="hhead"><span class="hname">{esc(hyp)}</span></div>'
                    f'<div class="hbody">{"".join(meta)}</div></article>'
                )
            else:
                text = str(item or "").strip()
                if text:
                    rows.append(f'<article class="hcard next"><div class="hbody">{esc(text)}</div></article>')
        if not rows:
            return ""
        return f'<section class="section"><h2>다음 체크 가설</h2><div class="hypothesis-stack">{"".join(rows)}</div></section>'

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

    def changes_section():
        """'어제 대비 변화' 섹션 — 직전 같은 윈도 브리프 대비 시장 변화. 없으면 빈 문자열.

        item 은 ``{dir,text}`` 권장이나, 문자열(줄 리스트)도 칩 없이 관대하게 렌더한다.
        텍스트 없는 항목·잘못된 모양은 건너뛴다(한 회차 결함이 빌드를 죽이지 않게).
        """
        items = payload.get("changes", [])
        if not items:
            return ""
        rows = []
        for c in items:
            if isinstance(c, dict):
                text = str(c.get("text", "")).strip()
                if not text:
                    continue
                rows.append(f'<li>{_dir_chip(c.get("dir"))}'
                            f'<span class="chg-text">{esc(text)}</span></li>')
            else:                                   # 문자열 등: 칩 없이 텍스트만
                text = str(c or "").strip()
                if text:
                    rows.append(f'<li><span class="chg-text">{esc(text)}</span></li>')
        if not rows:
            return ""
        return (f'<section class="section changes"><h2>어제 대비 변화</h2>'
                f'<ul class="change-list">{"".join(rows)}</ul></section>')

    takeaway = payload.get("takeaway", "")
    favicon_rel = css_rel.rsplit("/", 1)[0] + "/favicon.svg" if "/" in css_rel else "favicon.svg"

    body_blocks = "\n".join(b for b in [
        changes_section(),
        hypothesis_review_section(),
        market_board(),
        grid_row("split", [drivers_section(), theses_section()]),
        grid_row("even", [next_hypotheses_section(), watch_section()]),
        risks_section(),
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
<h1>{_h1_html(payload.get("title","Market Brief"))}</h1>
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
