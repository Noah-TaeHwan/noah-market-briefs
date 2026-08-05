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
import sys
from pathlib import Path

# render_market_brief 는 같은 scripts/ 디렉토리의 형제 모듈이다. 어디서 실행하든
# (다른 cwd, 모듈 import 등) 형제를 찾도록 scripts/ 를 모듈 검색 경로 맨 앞에 넣는다.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_market_brief import render, esc  # noqa: E402

# 레포 루트 = 이 파일(scripts/build.py)의 두 단계 위.
REPO = Path(__file__).resolve().parent.parent

# 머신 코드 → 사람이 읽는 라벨 (index 카드/필터용)
MARKET_LABEL = {"US": "미국", "KR": "한국"}
WINDOW_LABEL = {"preopen": "장 시작 전", "close": "장 마감"}
# 시장 모르는 레코드(합성/레거시) 폴백: preopen < close
WINDOW_RANK = {"preopen": 0, "close": 1}

# 같은 '세션 날짜' 안에서 리포트가 실제 생성되는 시각 순서(이른→늦은, 숫자가 클수록 최신).
# cron 스케줄(KST) 근거: KR 장전 08:30 → KR 마감 16:30 → US 장전 22:00 → US 마감 익일 06:00.
# 정렬은 (date, 이 랭크) 내림차순 → 한/미·장전/마감을 실제 발표 시각 순으로 최신이 맨 위.
# (date 만으로 정렬하면 같은 날 KR/US 마감이 묶여 가장 오래된 KR 마감이 위로 오는 문제 교정.)
GEN_ORDER_RANK = {
    ("KR", "preopen"): 0,
    ("KR", "close"): 1,
    ("US", "preopen"): 2,
    ("US", "close"): 3,
}


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


def load_records(data_dir: Path) -> list:
    """data_dir 하위의 모든 *.json 브리프 레코드를 읽어 최신순으로 돌려준다.

    @param data_dir 브리프 JSON 루트(예: <repo>/data)
    @returns dict 리스트. date 내림차순 → 생성 시각 순위(recency_rank) 내림차순 정렬(최신이 맨 앞).
        깨진 JSON 레코드는 stderr 경고 후 skip(한 회차 결함이 전체 빌드를 막지 않게).
    """
    records = []
    for path in sorted(data_dir.rglob("*.json")):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            # cron(LLM)이 깨진 JSON을 쓴 회차 1건이 빌드 전체를 죽이지 않게 skip.
            print(f"⚠️  건너뜀(JSON 파싱 실패): {path} — {e}", file=sys.stderr)
            continue
        rec["_src"] = str(path)  # 디버그용(어느 파일에서 왔는지)
        records.append(rec)
    # 최신순: 날짜 내림차순 → 같은 날은 생성 시각 순위(KR장전<KR마감<US장전<US마감 익일) 내림차순.
    records.sort(
        key=lambda r: (r.get("date", ""), recency_rank(r)),
        reverse=True,
    )
    return records


def write_brief_pages(records: list, site_root: Path) -> int:
    """각 레코드를 render() 로 HTML 문서로 만들어 out_path 에 쓴다.

    out_path 는 데이터(cron이 생성)이므로 site_root 밖으로 탈출하지 못하게 가드한다.
    out_path 가 비어 있으면(누락) 그 레코드만 skip — 절대경로/.. 탈출은 보안상 raise.
    @returns 쓴 페이지 수
    """
    count = 0
    root = site_root.resolve()
    for rec in records:
        rel = rec.get("out_path")
        if not rel:                                     # out_path 누락 → KeyError 대신 skip
            print(f"⚠️  건너뜀(out_path 없음): {rec.get('_src', rec.get('date', '?'))}",
                  file=sys.stderr)
            continue
        out = (site_root / rel).resolve()               # 예: 2026/06/23/korea-close.html
        if not out.is_relative_to(root):                # 절대경로/.. 로 site_root 밖 탈출 차단
            raise ValueError(f"out_path가 site_root를 벗어남: {rec.get('out_path')!r}")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(rec), encoding="utf-8")
        count += 1
    return count


def _archive_card(rec: dict) -> str:
    """index 의 아카이브 카드 <li> 하나를 만든다.

    - meta = '시장 · 윈도' 라벨(라이브/샘플 공통).
    - 우측 배지로 live/sample 을 명시 → 샘플을 라이브로 착각하지 않게.
    """
    is_sample = rec.get("status") == "sample"
    market = MARKET_LABEL.get(rec.get("market_code", ""), rec.get("market", ""))
    window = WINDOW_LABEL.get(rec.get("window_code", ""), rec.get("window", ""))
    badge = ('<span class="ar-badge sample">샘플</span>' if is_sample
             else '<span class="ar-badge live">공개</span>')
    return (
        f'<li data-market="{esc(rec.get("market_code",""))}" '
        f'data-window="{esc(rec.get("window_code",""))}" '
        f'data-status="{esc(rec.get("status",""))}">'
        f'<a href="{esc(rec.get("out_path",""))}">'
        f'<span class="ar-date">{esc(rec.get("date",""))}</span>'
        f'<span class="ar-title">{esc(rec.get("title",""))}</span>'
        f'<span class="ar-meta">{esc(market)} · {esc(window)} {badge}</span>'
        f'</a></li>'
    )


def build_index_html(records: list) -> str:
    """레코드들로 정직한 카드형 아카이브 index.html 문자열을 만든다.

    - 히어로 Status = 'N live · M sample' (live/sample 개수를 데이터에서 계산)
    - 시장(US/KR)·윈도(장전/마감) 필터 (no-JS 환경에선 전부 표시)
    """
    live = sum(1 for r in records if r.get("status") == "live")
    sample = sum(1 for r in records if r.get("status") == "sample")
    status_value = f"공개 {live}개 · 샘플 {sample}개"
    cards = "".join(_archive_card(r) for r in records)

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
<meta name="twitter:card" content="summary"/>
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin/>
<link rel="stylesheet" href="assets/brief.css"/>
</head>
<body>
<main class="shell">
<header class="masthead"><span class="wordmark">Noah <span class="tag">Market Briefs</span></span><div class="masthead-meta"><span class="live-dot" aria-hidden="true"></span><span><span class="stamp">정적 시장 일지 · 장 마감 후에도</span><span class="stamp"><b>출처 확인 · 2026</b></span></span></div></header>
<section class="hero">
<div class="kicker"><span class="badge">정적 아카이브</span><span class="badge">미국 · 한국</span><span class="badge">장 시작 전 · 장 마감</span></div>
<h1>날짜별 시장 일지와<br/>가설 기반 시장 읽기.</h1>
<p class="takeaway" data-label="소개">Slack에는 핵심 요약만, 여기에는 날짜별 시장 일지와 가설 검증을 누적합니다. 숫자에는 반드시 출처와 날짜를 붙이고, 확정 종가가 아니면 그대로 명시합니다.</p>
<div class="meta-grid"><div class="meta-card"><div class="label">경로</div><div class="value">YYYY / MM / DD / 시점</div></div><div class="meta-card"><div class="label">시장</div><div class="value">미국 · 한국</div></div><div class="meta-card"><div class="label">시점</div><div class="value">장 시작 전 · 장 마감</div></div><div class="meta-card"><div class="label">상태</div><div class="value">{esc(status_value)}</div></div></div>
</section>
<section class="section">
<h2>브리프 목록</h2>
<div class="filterbar"><select id="f-market" aria-label="시장 필터"><option value="">전체 시장</option><option value="KR">한국</option><option value="US">미국</option></select><select id="f-window" aria-label="윈도 필터"><option value="">전체 시점</option><option value="preopen">장 시작 전</option><option value="close">장 마감</option></select></div>
<ul class="archive-list">{cards}</ul>
</section>
<footer class="footer"><span>data/ JSON에서 자동 생성.</span><span>출처 없는 거시 수치는 공개 브리프에 사용하지 않습니다.</span></footer>
</main>
<script>
(function(){{
  var m=document.getElementById('f-market'), w=document.getElementById('f-window');
  var items=[].slice.call(document.querySelectorAll('.archive-list li'));
  function apply(){{
    items.forEach(function(li){{
      var ok=(!m.value||li.dataset.market===m.value)&&(!w.value||li.dataset.window===w.value);
      li.style.display=ok?'':'none';
    }});
  }}
  m.addEventListener('change',apply); w.addEventListener('change',apply);
}})();
</script>
</body>
</html>'''


def build(repo_root: Path = REPO) -> dict:
    """data/ → 브리프 HTML + index.html 전체 빌드. 요약 dict 반환."""
    records = load_records(repo_root / "data")
    pages = write_brief_pages(records, repo_root)
    (repo_root / "index.html").write_text(build_index_html(records), encoding="utf-8")
    return {
        "live": sum(1 for r in records if r.get("status") == "live"),
        "sample": sum(1 for r in records if r.get("status") == "sample"),
        "pages": pages,
    }


def main():
    summary = build()
    print(f"built {summary['pages']} brief page(s): "
          f"{summary['live']} live · {summary['sample']} sample → index.html")


if __name__ == "__main__":
    main()
