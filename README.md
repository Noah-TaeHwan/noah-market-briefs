<p align="center">
  <img src="assets/brand/logo.svg" width="420" alt="Noah Market Briefs">
</p>

<p align="center"><em>숫자에는 반드시 출처와 시각을.</em></p>

<p align="center">
  <a href="https://github.com/Noah-TaeHwan/noah-market-briefs/actions/workflows/ci.yml"><img src="https://github.com/Noah-TaeHwan/noah-market-briefs/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://noah-market-briefs.vercel.app/market-briefs"><img src="https://img.shields.io/badge/공개%20아카이브-열기-c79a4e" alt="공개 아카이브"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/코드-MIT-blue" alt="코드 라이선스 MIT"></a>
  <img src="https://img.shields.io/badge/python-3.11%20%E2%80%93%203.13-blue" alt="Python 3.11 through 3.13">
  <img src="https://img.shields.io/badge/runtime%20dependencies-0-brightgreen" alt="런타임 의존성 없음">
</p>

한국·미국 시장의 **장전과 마감**을 같은 형식으로 남기는 근거 우선(evidence-first) 정적 아카이브입니다.
독자는 결론만 보는 대신 **기준 시각, 공개 출처, 근거 상태, 반대 근거, 미확인 항목**을 함께 확인할 수 있습니다.

> **현재 상태 (2026-09-06):** 코드 정본은 이 저장소 [`Noah-TaeHwan/noah-market-briefs`](https://github.com/Noah-TaeHwan/noah-market-briefs)입니다.
> 옛 이름 `noah-market-briefs-public`은 같은 레포로 리다이렉트됩니다. 제품 작업은 [`noah-market-briefs-archived`](https://github.com/Noah-TaeHwan/noah-market-briefs-archived)에서 이어가지 않습니다.
> 레거시 v1/v2와 V3가 함께 있습니다. 라이브 V3는 2026-09-03 미국 장전, 2026-09-06 한국 마감, 2026-09-07 한국 장전입니다. 미국 마감 슬롯은 아직 `legacy_unverified` placeholder입니다.
> production은 **[공개 아카이브](https://noah-market-briefs.vercel.app/market-briefs)**에 나와 있습니다. `main` 머지가 Vercel 배포를 트리거합니다.
> 하루 4회 Orca가 후보를 쓰고 `scripts/publish_brief.sh`가 사이트로 올립니다. Slack·카카오톡·이메일은 자동 보내지 않습니다. 카카오톡 unfurl은 여전히 **미검증**입니다.

<p align="center">
  <img src="docs/images/index.png" width="49%" alt="한국·미국 최신 4개 세션과 날짜별 아카이브 화면">
  <img src="docs/images/brief.png" width="49%" alt="근거 상태와 출처를 단계적으로 읽는 브리프 상세 화면">
</p>

## 무엇을 얻나

| 읽는 시간 | 화면에서 얻는 것 |
|---|---|
| **1분** | 한국 장전 → 한국 마감 → 미국 장전 → 미국 마감의 최신 4개, 기준일, 핵심 지표, 공개/근거 상태 |
| **5분** | 변화, 근거가 연결된 주장, 시장 동인, 반대 근거, 오늘의 학습 |
| **10분** | 출처별 기준·수집 시각, 가설과 반증 조건, 이전 검토, 누락 데이터, 정정 기록 |

날짜별 아카이브는 시장과 시점으로 필터링할 수 있습니다. 상세 페이지에는 영구 링크와 공유 버튼이 있고,
인접한 이전·다음 브리프로 이동할 수 있습니다. 브라우저 공유 기능을 지원하면 공유 시트를 열고,
그렇지 않으면 링크를 복사합니다.

## 신뢰 경계

목표 공개 경로는 다음과 같습니다.

```text
공식 1차 출처 직접 조회 (as_of·retrieved_at 기록)
       │  공개 가능한 주장·출처만 선별하고 개인정보/내부 식별자를 제거
       ▼
PublicBriefV3 JSON
       │  scripts/verify_brief.py --strict: 닫힌 스키마·시각·참조·비공개 패턴
       │  scripts/gate_check.py: G1–G9 기록만 (실패해도 발행 계속)
       ▼
scripts/publish_brief.sh: build.py + 피처 브랜치 + required CI + squash merge
       ▼
HTML + index.html + latest.json + rss.xml → production
```

- **직접 조회 세션**은 공식 1차 출처의 조회 결과와 as_of/retrieved_at 기록을 소유합니다. 자연어, 스케줄, 이 저장소는 실거래 권한을 만들지 않습니다.
- **PublicBriefV3**는 공개 handoff 계약입니다. 내부 경로·ID·개인 보유·Investor Context를 공개 payload에 넣지 않습니다.
- **verifier는 사실 판정기가 아닙니다.** 선언된 출처가 실제 주장을 뒷받침하는지까지 인증하지 않고, 형식과 참조 무결성 및 공개 금지 패턴을 검사합니다. `verify --strict` 실패만 발행을 막습니다.
- `public_receipt_sha256`는 공개 handoff preimage를 식별하기 위한 필드입니다. 현재 verifier는 64자리 소문자 hex 형식만 확인하며 값을 재계산하거나 직접 조회 결과를 인증하지 않습니다.
- **당일 브리프 발행은 스크립트**입니다. G1–G9 HUMAN-GATE가 공개를 막지 않습니다. 투자 판단을 뜻하지도 않습니다. Slack·카카오·이메일 전송은 하지 않습니다.

레거시 v1/v2는 호환 렌더링을 유지하지만 UI에서 **레거시 미검증**으로 구분합니다.
라이브 V3는 2026-09-03 미국 장전, 2026-09-06 한국 마감, 2026-09-07 한국 장전입니다. 미국 마감은 아직 placeholder입니다.
머신 피드는 V3만 내보냅니다. 새 브리프는 V3 계약을 따릅니다. 필드와 책임 경계는 [아키텍처](docs/ARCHITECTURE.md)에 있습니다.

## 저장소 구조

```text
data/YYYY/MM/DD/<정본이름>.json  # korea-|us- + preopen|close.json
scripts/verify_brief.py          # 레코드·공개 경계 검증
scripts/gate_check.py            # G1–G9 기록만
scripts/publish_brief.sh         # 검증·빌드·PR·squash merge
scripts/build.py                 # 사이트, latest.json, RSS 생성
scripts/render_market_brief.py   # 상세 HTML 렌더러
assets/brief.css               # 반응형 디자인 시스템
YYYY/MM/DD/<정본이름>.html      # 생성된 상세 페이지
index.html                     # 생성된 아카이브
latest.json                    # 최신 V3 4개 세션의 공개 메타데이터
rss.xml                        # 검증을 통과한 V3 공개 메타데이터 피드
```

Python 표준 라이브러리만 사용하며 런타임 패키지 설치 단계는 없습니다.

## 로컬 실행과 검증

```bash
# 모든 데이터 레코드 검증
python3 scripts/verify_brief.py

# WARNING도 실패로 취급
python3 scripts/verify_brief.py --strict

# 정적 사이트와 공개 피드 생성
python3 scripts/build.py

# 전체 회귀 테스트
python3 -m unittest discover -s tests -v

# 문법과 공백 오류 확인
python3 -m py_compile scripts/*.py
git diff --check
```

결정적 빌드는 같은 입력으로 빌드를 두 번 실행한 뒤, 두 결과의 diff 또는 해시가 같은지 확인합니다.
작업 중인 변경이 있는 브랜치에서는 단순 `git diff --exit-code` 대신 빌드 전후 diff를 별도 파일로 저장해 비교해야 합니다.

[GitHub Actions CI](.github/workflows/ci.yml)는 Python 3.11, 3.12, 3.13에서 회귀 테스트, 레코드 검증,
결정적 빌드를 실행합니다. 공개 소비용 경로는 다음과 같습니다.

- 최신 V3 4개: `https://noah-market-briefs.vercel.app/market-briefs/latest.json`
- V3 RSS: `https://noah-market-briefs.vercel.app/market-briefs/rss.xml`

두 URL은 production에 배포되어 있습니다. 머신 피드는 V3만 내보냅니다. 미국 마감 슬롯은 아직 placeholder입니다.

## 자동화와 공개

정기 발행은 **Orca 한 곳만** 스케줄러로 씁니다. 대안은 Codex Scheduled Tasks이지만
두 스케줄러를 동시에 켜지 않습니다. 한국/미국 장전·마감 4회, 휴장 캘린더, kill-switch는
[자동화 운영 계약](docs/AUTOMATION.md)에 있습니다.

Orca가 후보 JSON을 쓰면 `scripts/publish_brief.sh`가 verify --strict → 빌드 → 피처 브랜치 → required CI → squash merge까지 합니다.
사람 PR 클릭은 없습니다. Slack·카카오톡·이메일은 자동 보내지 않습니다.
코드·문서 변경은 계속 피처 브랜치 + PR입니다. `main` 직접 push와 `--admin` 머지는 금지합니다.

## 카카오톡으로 공유하기

1. 검증된 production 상세 페이지를 엽니다.
2. 페이지 상단의 **공유** 버튼을 누르거나 주소를 복사합니다.
3. 카카오톡 대화에 URL을 붙여 넣습니다.
4. 링크 제목·설명·이미지와 대상 날짜가 맞는지 확인한 뒤 전송합니다.

카카오톡 production unfurl은 아직 미검증입니다. 미리보기 이미지·제목이 맞다는 가정으로 재홍보하지 않습니다.

## 출처와 권리

출처별 허용 범위는 서로 다릅니다. 공개 열람 가능하다는 사실이 재배포 권리를 뜻하지 않습니다.
공식 KRX, OpenDART, SEC, BLS, FRED, NYSE의 사용 조건과 OpenBB/yfinance의 제한은
[출처 및 권리 매트릭스](docs/SOURCES.md)에 정리했습니다.

- **코드와 디자인 자산**: [MIT License](LICENSE)
- **브리프 콘텐츠**(`data/`, 생성된 브리프 본문): 별도 허락이 없는 한 **All rights reserved**
- **인용 데이터**: 각 원출처의 권리와 이용조건을 따름. 저장소의 MIT 라이선스가 데이터 권리를 재허여하지 않음

## 정정 정책

1. 오류를 발견하면 원본 레코드를 조용히 덮어쓰지 않습니다.
2. V3 정정 레코드는 `status: "corrected"`와 `correction_note`, `corrected_at`, `supersedes`를 포함합니다.
3. 근거가 부족하면 `evidence_status: "not_proven"` 또는 `partial`로 낮춥니다.
4. 재검증·재빌드 후 `publish_brief.sh`(브리프) 또는 피처 브랜치+PR(코드)로 공개합니다.
5. 과거 판단이 단순히 빗나간 경우는 오류처럼 소급 수정하지 않고 가설 검토 기록으로 남깁니다.

## 알려진 한계

- 대다수 레코드는 v1/v2 레거시이며 PublicBriefV3 provenance를 갖지 않습니다. 라이브 V3는 부분 공개(`partial`)입니다.
- verifier는 스키마·참조·시각·공개 경계를 확인하지만 원출처의 진위, 데이터 라이선스, 해석의 타당성을 자동 판정하지 않습니다.
- 공개 머신 피드는 레거시를 제외하고 허용된 V3 메타데이터와 V3 요약만 제공합니다.
- 휴장·출처 지연은 `--calendar`와 `partial`/`not_proven`으로 기록하고, verify --strict만 통과하면 그날 글은 발행합니다.
- 카카오톡 unfurl은 미검증입니다. 전송 자동화는 켜지 않습니다.
- 브리프 JSON·생성물은 publish 스크립트가 올립니다. 코드 변경은 feature 브랜치 + PR이고, `main` 머지 뒤에만 production에 반영합니다.

## 면책

이 저장소와 브리프는 **투자 권유, 매매 지시, 목표가 제시 또는 실거래 실행 도구가 아닙니다.**
공개 시장 자료를 시점별로 정리하고 해석 가설을 검토하기 위한 정보 아카이브입니다.
투자 판단과 그 결과의 책임은 이용자 본인에게 있습니다.
