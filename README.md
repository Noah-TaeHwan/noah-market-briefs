# Noah Market Briefs

미국·한국 시장의 장전/마감 브리핑을 **날짜별 정적 아카이브**로 누적하는 프로젝트입니다.
매일 수집한 시장 스냅샷을 JSON으로 적재하고, 빌드 스크립트가 동일한 디자인의 HTML로 렌더합니다.

현재 65건(2026-06-23 ~ 2026-07-17), 4개 윈도(한국 장전/마감 · 미국 장전/마감)로 누적돼 있습니다.

## 설계 원칙

이 저장소의 핵심은 디자인이 아니라 **출처 규율(source discipline)** 입니다.

- **모든 숫자에 출처와 시각을 붙인다.** `source`, `generated`, `data_quality`가 없는 수치는 렌더하지 않습니다.
- **모르는 것은 "미확인"으로 남긴다.** 값이 없으면 추정하지 않고 해당 항목을 비웁니다.
- **시점을 섞지 않는다.** 정규장 종가와 야간 선물처럼 기준 시각이 다르면 분리해 표기합니다.
- **매매 지시·목표가를 쓰지 않는다.** 관찰 가능한 `가설`과 `무효화 조건` 중심으로 씁니다.

## 아키텍처 — 데이터/화면 분리

```
data/YYYY/MM/DD/<window>.json     입력: 브리프 1건 = JSON 1개 (단일 진실 원천)
          │
   python3 scripts/build.py       표준 라이브러리만 — 설치 의존성 0
          ▼
YYYY/MM/DD/<window>.html          출력: 브리프 페이지
index.html                        출력: 아카이브 인덱스
```

HTML은 손으로 쓰지 않습니다. 데이터를 고치고 빌드를 다시 돌리면 65건 전체에 같은 디자인이 일관되게 적용됩니다.
빌드는 결정적(deterministic)이라, 같은 입력으로 다시 돌리면 diff가 발생하지 않습니다.

| 경로 | 역할 |
|---|---|
| `data/` | 브리프 레코드(JSON). 스키마는 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) 참고 |
| `scripts/build.py` | `data/**/*.json` → 브리프 HTML + 인덱스 생성 |
| `scripts/render_market_brief.py` | JSON 1건 → 브리프 HTML 1장 |
| `scripts/render_slack_brief.py` | JSON 1건 → Slack 요약 |
| `scripts/verify_brief.py` | 레코드 검증 |
| `assets/brief.css` | 디자인 시스템(단일 소스) |
| `tests/` | 회귀 테스트 |

스키마는 **추가 필드를 전부 선택(optional)** 으로 두고 렌더러가 `.get(key, default)`로 읽습니다.
덕분에 스키마가 v1 → v3로 확장되는 동안 옛 레코드가 한 건도 깨지지 않았습니다.

## 실행

의존성 설치가 필요 없습니다. Python 3.11+ 표준 라이브러리만 사용합니다.

```bash
python3 scripts/build.py              # data/ → 사이트 전체 재생성
python3 -m unittest discover -s tests # 회귀 테스트 (70 tests)
```

## 데이터 출처

CNBC quote cache, 네이버 금융, 하나은행 고시환율, 연합뉴스 경제 RSS.

각 브리프의 `source` 필드에 수집 시각과 함께 출처를 명시합니다.
원문을 재배포하지 않고, 공개된 수치를 인용해 자체 해석을 붙이는 방식입니다.

## 면책

이 저장소의 브리프는 **투자 권유나 매매 지시가 아닙니다.** 금리·환율·유동성·변동성 민감도를 기록하고
스스로의 시장 해석 프레임을 검증하기 위한 개인 기록입니다. 투자 판단과 그 결과의 책임은 투자자 본인에게 있습니다.

## 라이선스

- **코드**(`scripts/`, `tests/`, `assets/`): [MIT](LICENSE)
- **브리프 콘텐츠**(`data/`, `2026/`): 저작권자 보유 — 무단 복제·재배포를 허용하지 않습니다.
