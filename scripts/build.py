#!/usr/bin/env python3
"""data/ 의 브리프 JSON들로부터 사이트(브리프 HTML + 아카이브 index)를 빌드한다.

데이터/화면 분리의 '화면' 쪽:
  - cron 에이전트는 data/YYYY/MM/DD/<window>.json 에 **데이터만** 쌓는다.
  - 이 스크립트가 그 JSON들을 읽어 **항상 같은 디자인**의 사이트를 생성한다.

핵심 사고: "나는 HTML을 손으로 안 짠다. data/ 에 JSON을 넣고 build.py를 돌린다."
의존성 없음(표준 라이브러리만). 사용:
  python3 scripts/build.py            # 레포 루트 기준으로 전체 빌드

@returns build()는 {'live': n, 'sample': m, 'pages': k} 요약 dict를 돌려준다.
"""
from __future__ import annotations
import json
import posixpath
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# render_market_brief 는 같은 scripts/ 디렉토리의 형제 모듈이다. 어디서 실행하든
# (다른 cwd, 모듈 import 등) 형제를 찾도록 scripts/ 를 모듈 검색 경로 맨 앞에 넣는다.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_market_brief import render, esc  # noqa: E402
from verify_brief import Severity, verify_record  # noqa: E402

# 레포 루트 = 이 파일(scripts/build.py)의 두 단계 위.
REPO = Path(__file__).resolve().parent.parent
SITE_URL = "https://noah-market-briefs.vercel.app/market-briefs"
OG_IMAGE_URL = f"{SITE_URL}/docs/images/index.png"
VERIFY_URL = "https://github.com/Noah-TaeHwan/noah-market-briefs-public/blob/main/scripts/verify_brief.py"
PUBLIC_PATH_PREFIX = "/market-briefs"

# 머신 코드 → 사람이 읽는 라벨 (index 카드/필터용)
MARKET_LABEL = {"US": "미국", "KR": "한국"}
WINDOW_LABEL = {"preopen": "장 시작 전", "close": "장 마감"}
# 시장 모르는 레코드(합성/레거시) 폴백: preopen < close
WINDOW_RANK = {"preopen": 0, "close": 1}

# 같은 세션 날짜 안의 브리프 순서(숫자가 클수록 뒤 세션).
# 정렬은 (date, 이 랭크) 내림차순으로 시장·세션의 일관된 표시 순서를 유지한다.
GEN_ORDER_RANK = {
    ("KR", "preopen"): 0,
    ("KR", "close"): 1,
    ("US", "preopen"): 2,
    ("US", "close"): 3,
}
LATEST_SLOT_ORDER = (("KR", "preopen"), ("KR", "close"), ("US", "preopen"), ("US", "close"))

STATUS_LABELS = {
    "live": "공개", "published": "공개", "sample": "샘플", "partial": "부분 공개",
    "skipped_market_closed": "휴장으로 건너뜀", "failed": "생성 실패", "corrected": "정정됨",
}
EVIDENCE_LABELS = {
    "confirmed": "근거 확인", "partial": "근거 일부", "not_proven": "미검증",
    "legacy_unverified": "레거시 미검증",
}
LINKED_EVIDENCE_FIELDS = ("claims", "metrics", "changes", "drivers", "counterevidence", "hypotheses", "reviews")


def _public_href(path: str) -> str:
    """랜딩 페이지 내부 경로에 공개 URL prefix를 붙인다.

    @param path 레포 루트 기준 정적 파일 또는 브리프 경로
    @returns `/market-briefs/`를 유지하는 root-relative URL
    """
    raw = str(path).replace("\\", "/").lstrip("/")
    if any(part == ".." for part in raw.split("/")):
        raise ValueError(f"공개 경로가 prefix를 벗어남: {path!r}")
    normalized = posixpath.normpath(raw)
    return f"{PUBLIC_PATH_PREFIX}/{'' if normalized == '.' else normalized}"


def recency_rank(rec: dict) -> int:
    """같은 날짜 내 생성-시각 순위(클수록 최신).

    (시장, 윈도) 복합 랭크. 미지의 시장은 윈도(preopen<close)만으로 폴백한다.
    @param rec 브리프 레코드(market_code·window_code 사용)
    @returns int 생성 시각 순위(클수록 최신)
    """
    key = (rec.get("market_code", ""), rec.get("window_code", ""))
    if key in GEN_ORDER_RANK:
        return GEN_ORDER_RANK[key]
    return WINDOW_RANK.get(rec.get("window_code", ""), 0)


def _record_date(rec: dict) -> str:
    """v3 세션 날짜를 우선하고, 기존 레코드는 date 호환 필드를 쓴다."""
    return str(rec.get("market_session_date", rec.get("date", "")))


def is_published(rec: dict) -> bool:
    """공개 카운트에 포함할 기존 live 및 v3 published 상태인지 확인한다."""
    return rec.get("status") in {"live", "published"}


def _is_legacy(rec: dict) -> bool:
    """v1/v2 또는 버전 없는 기존 레코드인지 확인한다."""
    return rec.get("schema_version", 1) < 3


def _evidence_status(rec: dict) -> str:
    """화면/피드에 쓸 공개 근거 상태를 정규화한다."""
    return "legacy_unverified" if _is_legacy(rec) else str(rec.get("evidence_status", "not_proven"))


def status_badge(rec: dict) -> str:
    """상태와 근거를 텍스트로 함께 표시한다."""
    status = str(rec.get("status", "failed"))
    status_label = STATUS_LABELS.get(status, status)
    evidence = _evidence_status(rec)
    return (
        f'<span class="ar-badge {esc(status)} status-badge">{esc(status_label)}</span>'
        f'<span class="evidence-badge {esc(evidence)}">{esc(EVIDENCE_LABELS.get(evidence, evidence))}</span>'
    )


def latest_slots(records: list[dict]) -> list[tuple[str, str, dict | None]]:
    """KR 장전→KR 마감→US 장전→US 마감 고정 슬롯별 최신 레코드를 고른다."""
    slots = []
    for market, window in LATEST_SLOT_ORDER:
        matches = [r for r in records if r.get("market_code") == market and r.get("window_code") == window]
        latest = max(
            matches,
            key=lambda r: (_record_date(r), recency_rank(r), str(r.get("out_path", ""))),
            default=None,
        )
        slots.append((market, window, latest))
    return slots


def _latest_summary(records: list[dict]) -> tuple[dict | None, str | None, int, int, int]:
    """최신 슬롯 집합의 현재 읽기용 대표 레코드와 상태 카운트를 계산한다.

    @param records 검증을 통과한 브리프 레코드 목록
    @returns (최신 레코드, 최신 기준일, 채워진 슬롯 수, 레거시 슬롯 수, 부분 공개 슬롯 수)
    """
    slots = latest_slots(records)
    filled = [rec for _, _, rec in slots if rec is not None]
    if not filled:
        return None, None, 0, 0, 0
    latest_date = max(_record_date(rec) for rec in filled)
    latest_rec = max(
        (rec for rec in filled if _record_date(rec) == latest_date),
        key=lambda rec: (recency_rank(rec), str(rec.get("out_path", ""))),
    )
    legacy = sum(1 for rec in filled if _is_legacy(rec))
    partial = sum(1 for rec in filled if rec.get("status") == "partial")
    return latest_rec, latest_date, len(filled), legacy, partial


def _load_records(data_dir: Path) -> tuple[list[dict], int]:
    """레코드를 읽고 v3 검증 ERROR 건수와 함께 반환한다."""
    records: list[dict] = []
    rejected = 0
    for path in sorted(data_dir.rglob("*.json")):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            # cron(LLM)이 깨진 JSON을 쓴 회차 1건이 빌드 전체를 죽이지 않게 skip.
            print(f"⚠️  건너뜀(JSON 파싱 실패): {path} — {e}", file=sys.stderr)
            rejected += 1
            continue
        if not isinstance(rec, dict):
            print(f"⚠️  건너뜀(최상위 JSON이 dict 아님): {path}", file=sys.stderr)
            rejected += 1
            continue
        try:
            errors = [f for f in verify_record(rec) if f.severity == Severity.ERROR]
        except Exception:
            print(f"⚠️  건너뜀(검증 예외): {path}", file=sys.stderr)
            rejected += 1
            continue
        if errors:
            print(f"⚠️  건너뜀(검증 ERROR {len(errors)}건): {path}", file=sys.stderr)
            rejected += 1
            continue
        rec["_src"] = str(path)  # 디버그용(어느 파일에서 왔는지)
        records.append(rec)
    # 최신순: 날짜 내림차순 → 같은 날은 생성 시각 순위(KR장전<KR마감<US장전<US마감 익일) 내림차순.
    records.sort(
        key=lambda r: (_record_date(r), recency_rank(r)),
        reverse=True,
    )
    return records, rejected


def load_records(data_dir: Path) -> list:
    """data_dir 하위의 모든 *.json 브리프 레코드를 읽어 최신순으로 돌려준다.

    @param data_dir 브리프 JSON 루트(예: <repo>/data)
    @returns dict 리스트. date 내림차순 → 생성 시각 순위(recency_rank) 내림차순 정렬(최신이 맨 앞).
        깨진 JSON 레코드는 stderr 경고 후 skip(한 회차 결함이 전체 빌드를 막지 않게).
    """
    records, _ = _load_records(data_dir)
    return records


def _brief_page_parts(path: Path) -> tuple[str, str, str, str] | None:
    """데이터가 생성하는 YYYY/MM/DD/*.html 경로만 식별한다."""
    parts = path.parts
    if (len(parts) != 4 or not all(part.isdigit() for part in parts[:3])
            or (len(parts[0]), len(parts[1]), len(parts[2])) != (4, 2, 2)
            or path.suffix != ".html"):
        return None
    return parts


def _remove_orphan_brief_pages(records: list[dict], site_root: Path) -> None:
    """검증된 데이터에 없는 날짜형 브리프 HTML만 제거한다."""
    root = site_root.resolve()
    expected = {
        parts for rec in records
        if isinstance(rec.get("out_path"), str)
        if (parts := _brief_page_parts(Path(rec["out_path"]))) is not None
    }
    for year in root.iterdir():
        if year.is_symlink() or not year.is_dir() or len(year.name) != 4 or not year.name.isdigit():
            continue
        for month in year.iterdir():
            if month.is_symlink() or not month.is_dir() or len(month.name) != 2 or not month.name.isdigit():
                continue
            for day in month.iterdir():
                if day.is_symlink() or not day.is_dir() or len(day.name) != 2 or not day.name.isdigit():
                    continue
                for page in day.glob("*.html"):
                    if page.is_symlink() or not page.is_file():
                        continue
                    if page.relative_to(root).parts not in expected:
                        page.unlink()


def write_brief_pages(records: list, site_root: Path) -> int:
    """각 레코드를 render() 로 HTML 문서로 만들어 out_path 에 쓴다.

    out_path 는 데이터(cron이 생성)이므로 site_root 밖으로 탈출하지 못하게 가드한다.
    out_path 가 비어 있으면(누락) 그 레코드만 skip — 절대경로/.. 탈출은 보안상 raise.
    @returns 쓴 페이지 수
    """
    count = 0
    root = site_root.resolve()
    page_records = [r for r in records if r.get("out_path")]
    for index, rec in enumerate(page_records):
        rel = rec.get("out_path")
        if not rel:                                     # out_path 누락 → KeyError 대신 skip
            print(f"⚠️  건너뜀(out_path 없음): {rec.get('_src', rec.get('date', '?'))}",
                  file=sys.stderr)
            continue
        out = (site_root / rel).resolve()               # 예: 2026/06/23/korea-close.html
        if not out.is_relative_to(root):                # 절대경로/.. 로 site_root 밖 탈출 차단
            raise ValueError(f"out_path가 site_root를 벗어남: {rec.get('out_path')!r}")
        out.parent.mkdir(parents=True, exist_ok=True)
        current_dir = posixpath.dirname(str(rel)) or "."

        def adjacent(target: dict | None) -> dict | None:
            """현재 페이지 기준 인접 페이지 상대 링크를 만든다."""
            if not target:
                return None
            return {
                "title": target.get("title", ""),
                "href": posixpath.relpath(str(target["out_path"]), current_dir),
            }

        context = {
            "canonical_url": f"{SITE_URL}/{str(rel).lstrip('/')}",
            "newer": adjacent(page_records[index - 1] if index else None),
            "older": adjacent(page_records[index + 1] if index + 1 < len(page_records) else None),
        }
        css_rel = posixpath.relpath("assets/brief.css", current_dir)
        index_rel = posixpath.relpath("index.html", current_dir)
        out.write_text(render(rec, css_rel=css_rel, index_rel=index_rel, page_context=context), encoding="utf-8")
        count += 1
    return count


def _archive_card(rec: dict) -> str:
    """index 의 아카이브 카드 <li> 하나를 만든다.

    - meta = '시장 · 윈도' 라벨(라이브/샘플 공통).
    - 우측 배지로 live/sample 을 명시 → 샘플을 라이브로 착각하지 않게.
    """
    market = MARKET_LABEL.get(rec.get("market_code", ""), rec.get("market", ""))
    window = WINDOW_LABEL.get(rec.get("window_code", ""), rec.get("window", ""))
    return (
        f'<li data-market="{esc(rec.get("market_code",""))}" '
        f'data-window="{esc(rec.get("window_code",""))}" '
        f'data-status="{esc(rec.get("status",""))}">'
        f'<a href="{esc(_public_href(rec.get("out_path","")))}">'
        f'<span class="ar-date">{esc(_record_date(rec))}</span>'
        f'<span class="ar-title">{esc(rec.get("title",""))}</span>'
        f'<span class="ar-meta">{esc(market)} · {esc(window)} {status_badge(rec)}</span>'
        f'</a></li>'
    )


def _latest_card(market: str, window: str, rec: dict | None, latest_date: str | None) -> str:
    """첫 화면의 최신 고정 슬롯 카드 하나와 상대 최신성 라벨을 만든다.

    @param market 시장 코드(KR 또는 US)
    @param window 세션 코드(preopen 또는 close)
    @param rec 해당 슬롯에서 선택된 최신 레코드
    @param latest_date 전체 슬롯 중 가장 최근 기준일
    @returns 최신성 상태와 기존 카드 정보를 포함한 HTML 문자열
    """
    market_label = MARKET_LABEL[market]
    window_label = WINDOW_LABEL[window]
    slot = f"{market}-{window}"
    if rec is None:
        return (
            f'<article class="latest-card empty" data-slot="{slot}" data-freshness="missing">'
            f'<p class="latest-market">{market_label} · {window_label}</p>'
            '<span class="stale-text missing">기록 없음</span>'
            '<p class="empty-title">아직 기록 없음</p><p class="latest-empty">검증된 세션이 생성되면 표시됩니다.</p>'
            '</article>'
        )
    date = _record_date(rec)
    freshness = "latest" if date == latest_date else "older"
    freshness_label = "가장 최근 기준일" if freshness == "latest" else "이전 기준일"
    metrics = rec.get("metrics", [])[:3]
    metric_html = "".join(
        f'<li><span>{esc(m.get("label", m.get("name", "지표")))}</span>'
        f'<strong>{esc(m.get("value", "미확인"))}</strong></li>'
        for m in metrics if isinstance(m, dict)
    )
    return (
        f'<article class="latest-card {freshness}" data-slot="{slot}" data-freshness="{freshness}">'
        f'<p class="latest-market">{market_label} · {window_label}</p>'
        f'<time class="latest-date" datetime="{esc(date)}">{esc(date)}</time>'
        f'<span class="stale-text {freshness}" data-stale-date="{esc(date)}" data-freshness="{freshness}">{freshness_label} · {esc(date)}</span>'
        f'<h3><a href="{esc(_public_href(rec.get("out_path", "")))}">{esc(rec.get("title", "시장 브리프"))}</a></h3>'
        f'<ul class="latest-metrics">{metric_html}</ul>'
        f'<div class="latest-status">{status_badge(rec)}</div>'
        f'<a class="card-permalink" href="{esc(_public_href(rec.get("out_path", "")))}" aria-label="{esc(rec.get("title", "시장 브리프"))} 브리프 읽기 →">브리프 읽기 →</a>'
        '</article>'
    )


def _archive_groups(records: list) -> str:
    """날짜별 아카이브 그룹 HTML을 만든다."""
    grouped: dict[str, list[dict]] = {}
    for rec in records:
        grouped.setdefault(_record_date(rec), []).append(rec)
    return "".join(
        f'<section class="archive-group" data-date="{esc(date)}"><h3>{esc(date)}</h3>'
        f'<ul class="archive-list">{"".join(_archive_card(rec) for rec in grouped[date])}</ul></section>'
        for date in sorted(grouped, reverse=True)
    )


def build_index_html(records: list) -> str:
    """레코드들로 정직한 카드형 아카이브 index.html 문자열을 만든다.

    - 히어로 Status = 'N live · M sample' (live/sample 개수를 데이터에서 계산)
    - 시장(US/KR)·윈도(장전/마감) 필터 (no-JS 환경에선 전부 표시)
    @param records 검증을 통과한 브리프 레코드 목록
    @returns 현재 읽기 패널과 아카이브를 포함한 index HTML
    """
    live = sum(1 for r in records if is_published(r))
    sample = sum(1 for r in records if r.get("status") == "sample")
    status_value = f"공개 {live}개 · 샘플 {sample}개"
    latest_rec, latest_date, filled, legacy, partial = _latest_summary(records)
    latest = "".join(
        _latest_card(market, window, rec, latest_date)
        for market, window, rec in latest_slots(records)
    )
    if latest_rec is None:
        latest_focus = (
            '<section class="latest-focus empty" id="latest-focus" aria-labelledby="latest-focus-title">'
            '<p class="focus-kicker">가장 최근 기록</p>'
            '<h2 id="latest-focus-title">아직 읽을 검증 기록 없음</h2>'
            '<p class="focus-note">검증된 세션이 생성되면 이곳에서 먼저 확인할 수 있습니다.</p>'
            '</section>'
        )
    else:
        focus_href = _public_href(latest_rec.get("out_path", ""))
        coverage = [f"기준일 {latest_date}", f"4개 창구 중 {filled}개 기록"]
        if legacy:
            coverage.append(f"{legacy}개 레거시 미검증")
        if partial:
            coverage.append(f"{partial}개 부분 공개")
        latest_focus = (
            '<section class="latest-focus" id="latest-focus" aria-labelledby="latest-focus-title">'
            '<p class="focus-kicker">가장 최근 기록</p>'
            f'<h2 id="latest-focus-title"><a href="{esc(focus_href)}">{esc(latest_rec.get("title", "시장 브리프"))}</a></h2>'
            f'<div class="focus-meta"><time datetime="{esc(latest_date or "")}">기준일 {esc(latest_date or "")}</time>{status_badge(latest_rec)}</div>'
            f'<p class="coverage-summary">{esc(" · ".join(coverage))}</p>'
            f'<a class="focus-action" href="{esc(focus_href)}">가장 최근 브리프 읽기 →</a>'
            '</section>'
        )
    groups = _archive_groups(records)

    return f'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Noah Market Briefs</title>
<meta name="description" content="미국·한국 시장 전·마감 브리핑을 날짜별로 누적하는 정적 아카이브. 숫자에는 반드시 출처와 날짜를 붙인다."/>
<meta property="og:type" content="website"/>
<meta property="og:title" content="Noah Market Briefs"/>
<meta property="og:description" content="미국·한국 시장 전·마감 브리핑을 날짜별로 누적하는 정적 아카이브. 숫자에는 반드시 출처와 날짜를 붙인다."/>
<meta property="og:url" content="{SITE_URL}"/>
<meta property="og:image" content="{OG_IMAGE_URL}"/>
<meta name="twitter:card" content="summary_large_image"/>
<link rel="canonical" href="{SITE_URL}"/>
<link rel="alternate" type="application/rss+xml" title="Noah Market Briefs RSS" href="{_public_href("rss.xml")}"/>
<link rel="icon" type="image/svg+xml" href="{_public_href("assets/favicon.svg")}"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin/>
<link rel="stylesheet" href="{_public_href("assets/brief.css")}"/>
</head>
<body>
<a class="skip-link" href="#latest-focus">최신 브리프로 건너뛰기</a>
<main class="shell home-shell">
<header class="masthead compact-masthead"><a class="wordmark" href="{_public_href("index.html")}">Noah <span class="tag">Market Briefs</span></a><nav class="site-nav" aria-label="주요 탐색"><a href="#latest-focus">최신</a><a href="#archive">아카이브</a><a href="{VERIFY_URL}">방법론·검증 코드</a></nav></header>
<section class="compact-hero" aria-labelledby="home-title"><div><p class="eyebrow">Evidence-first market journal</p><h1 id="home-title">확인된 기록부터 읽는 시장 브리프</h1></div><p class="status-strip">{esc(status_value)} · 정적 생성 · 투자 권유 아님</p></section>
<p class="home-note">가설 기반 시장 읽기 · 경로 YYYY / MM / DD / 시점</p>
{latest_focus}
<section class="latest-section" id="latest" aria-labelledby="latest-title"><div class="section-head"><h2 id="latest-title">창구별 최신 기록</h2><p>한국 장전 → 한국 마감 → 미국 장전 → 미국 마감 고정 순서</p></div><div class="latest-grid">{latest}</div></section>
<section class="section archive-section" id="archive">
<div class="section-head"><h2>날짜별 아카이브</h2><p id="archive-result-count" role="status" aria-live="polite">{len(records)}개 기록</p></div>
<div class="filterbar"><select id="f-market" aria-label="시장 필터"><option value="">전체 시장</option><option value="KR">한국</option><option value="US">미국</option></select><select id="f-window" aria-label="윈도 필터"><option value="">전체 시점</option><option value="preopen">장 시작 전</option><option value="close">장 마감</option></select></div>
<div class="archive-groups">{groups}</div>
</section>
<footer class="footer"><span>data/ JSON에서 자동 생성.</span><a href="{VERIFY_URL}">방법론·검증 코드</a></footer>
</main>
<script>
(function(){{
  var m=document.getElementById('f-market'), w=document.getElementById('f-window');
  var items=[].slice.call(document.querySelectorAll('.archive-list li'));
  var groups=[].slice.call(document.querySelectorAll('.archive-group'));
  var count=document.getElementById('archive-result-count');
  function apply(){{
    var shown=0;
    items.forEach(function(li){{
      var ok=(!m.value||li.dataset.market===m.value)&&(!w.value||li.dataset.window===w.value);
      li.hidden=!ok;if(ok) shown+=1;
    }});
    groups.forEach(function(group){{var visible=group.querySelectorAll('li:not([hidden])').length;group.hidden=visible===0;}});
    count.textContent=shown+'개 기록';
  }}
  m.addEventListener('change',apply); w.addEventListener('change',apply);
  document.querySelectorAll('[data-stale-date]').forEach(function(node){{
    var label=node.dataset.freshness==='latest'?'가장 최근 기준일':'이전 기준일';
    node.textContent=label+' · '+node.dataset.staleDate;
  }});
}})();
</script>
</body>
</html>'''


def _has_linked_evidence(rec: dict) -> bool:
    """피드 요약을 허용할 confirmed source-linked 공개 근거가 있는지 확인한다."""
    sources = rec.get("sources")
    if not isinstance(sources, list):
        return False
    source_ids = {source.get("source_id") for source in sources
                  if (isinstance(source, dict) and source.get("status") == "confirmed"
                      and isinstance(source.get("source_id"), str))}
    if not source_ids:
        return False
    for field in LINKED_EVIDENCE_FIELDS:
        for item in rec.get(field, []) if isinstance(rec.get(field), list) else []:
            refs = item.get("source_ids") if isinstance(item, dict) else None
            if (isinstance(item, dict) and item.get("evidence_status") == "confirmed"
                    and isinstance(refs, list)
                    and any(isinstance(ref, str) and ref in source_ids for ref in refs)):
                return True
    return False


def _feed_item(rec: dict) -> dict:
    """v3 피드에 허용된 공개 메타데이터만 복사한다."""
    item = {
        "market": rec.get("market_code", ""),
        "window": rec.get("window_code", ""),
        "date": _record_date(rec),
        "title": rec.get("title", ""),
        "path": rec.get("out_path", ""),
        "status": rec.get("status", ""),
        "evidence_status": _evidence_status(rec),
    }
    if (rec.get("status") in {"published", "corrected"}
            and rec.get("evidence_status") == "confirmed" and rec.get("summary")
            and _has_linked_evidence(rec)):
        item["summary"] = rec["summary"]
    return item


def build_latest_json(records: list) -> str:
    """고정 4개 최신 슬롯 JSON을 결정론적으로 만든다."""
    items = []
    for market, window, rec in latest_slots(records):
        if rec and rec.get("schema_version") == 3:
            items.append(_feed_item(rec))
        else:
            legacy = bool(rec and _is_legacy(rec))
            items.append({
                "market": market,
                "window": window,
                "status": "legacy_unverified" if legacy else "missing",
                "evidence_status": "legacy_unverified" if legacy else "not_proven",
            })
    return json.dumps({"version": 1, "items": items}, ensure_ascii=False, indent=2) + "\n"


def build_rss_xml(records: list) -> str:
    """검증을 통과한 같은 레코드 목록으로 안전한 RSS 2.0을 만든다."""
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    for tag, value in (("title", "Noah Market Briefs"), ("link", SITE_URL),
                       ("description", "근거 상태를 함께 공개하는 정적 시장 브리프"),
                       ("language", "ko")):
        ET.SubElement(channel, tag).text = value
    for rec in records:
        if rec.get("schema_version") != 3:
            continue
        safe = _feed_item(rec)
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = str(safe["title"])
        url = f"{SITE_URL}/{str(safe['path']).lstrip('/')}"
        ET.SubElement(item, "link").text = url
        ET.SubElement(item, "guid", {"isPermaLink": "true"}).text = url
        ET.SubElement(item, "category").text = str(safe["status"])
        ET.SubElement(item, "category").text = str(safe["evidence_status"])
        ET.SubElement(item, "description").text = str(safe.get("summary", safe["evidence_status"]))
    ET.indent(rss, space="  ")
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(rss, encoding="unicode") + "\n"


def build(repo_root: Path = REPO) -> dict:
    """data/ → 브리프 HTML + index.html 전체 빌드. 요약 dict 반환."""
    records, rejected = _load_records(repo_root / "data")
    _remove_orphan_brief_pages(records, repo_root)
    pages = write_brief_pages(records, repo_root)
    (repo_root / "index.html").write_text(build_index_html(records), encoding="utf-8")
    (repo_root / "latest.json").write_text(build_latest_json(records), encoding="utf-8")
    (repo_root / "rss.xml").write_text(build_rss_xml(records), encoding="utf-8")
    if rejected:
        print(f"build rejected {rejected} record(s) due to parse or verification ERROR", file=sys.stderr)
    return {
        "live": sum(1 for r in records if is_published(r)),
        "sample": sum(1 for r in records if r.get("status") == "sample"),
        "pages": pages,
    }


def main():
    summary = build()
    print(f"built {summary['pages']} brief page(s): "
          f"{summary['live']} live · {summary['sample']} sample → index.html")


if __name__ == "__main__":
    main()
