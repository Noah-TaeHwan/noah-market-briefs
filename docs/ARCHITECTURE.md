# Noah Market Briefs 아키텍처

이 문서는 **내부 리서치와 공개 아카이브 사이의 경계**를 정의합니다. 현재 저장된 65건은 v1/v2 레거시이며,
아래 PublicBriefV3 계약은 다음 브리프부터 적용할 공개 형식입니다.

## 1. 책임 경계

```text
TradingCodex operate plane
  현재-run의 인증된 Source/Snapshot/Dataset/Artifact/Calculation
                │
                │ 공개 가능한 근거만 선별·요약
                ▼
PublicBriefV3 JSON
  내부 ID/경로, 개인 보유, Investor Context, 실거래 정보 제거
                │
                ▼
verify_brief.py ── ERROR ──▶ 해당 레코드 공개 빌드 제외
                │ OK
                ▼
build.py + render_market_brief.py (Python stdlib)
                │
                ├── index.html + YYYY/MM/DD/*.html
                ├── latest.json
                └── rss.xml
                         │
                         ▼
              사람의 diff·receipt 승인
                         │
                         ▼
                 Git/Vercel 공개 배포
```

| 주체 | 소유하는 것 | 소유하지 않는 것 |
|---|---|---|
| TradingCodex | 내부 current-run provenance, evidence acceptance, research artifacts | 이 저장소만으로 생기는 공개·실거래 권한 |
| Public projection | 공개 가능한 최소 필드와 출처 참조 | 내부 Artifact/Snapshot/Dataset/Calculation ID, 개인 문맥, credential |
| verifier | 스키마, 타입, 시각, source 참조, 공개 금지 패턴 | 원출처 진위, 해석 타당성, 라이선스 승인, receipt 재계산 |
| static builder | 검증을 통과한 레코드의 결정적 HTML/JSON/RSS 생성 | 자동 commit, push, deploy, 외부 전송 |
| 사람 승인자 | diff, 출처 권리, 배포 receipt, 링크 미리보기 확인 | 자연어만으로 우회되는 정책·실거래 권한 |

TradingCodex의 인증된 내부 근거와 공개 payload는 같은 것이 아닙니다. 내부 증거를 통째로 복사하지 않고,
최소 공개 claim과 SourceRef만 projection합니다. 선택된 Strategy/Brain/Investor Context는 공개 권한이나
실거래 권한을 만들지 않으며, 개인 Investor Context는 이 공개 프로젝트에 사용하지 않습니다.

## 2. 디렉터리와 생성물

```text
data/YYYY/MM/DD/<window>.json  # 입력, 브리프 1건
scripts/verify_brief.py        # v1/v2 호환 + PublicBriefV3 공개 경계
scripts/build.py               # 입력 탐색, 검증, 페이지/피드 생성
scripts/render_market_brief.py # 상세 페이지 렌더링
assets/brief.css               # 공통 반응형 스타일
YYYY/MM/DD/<window>.html       # 생성된 상세 페이지
index.html                     # 최신 4개 + 날짜별 아카이브
latest.json                    # 최신 V3 4개 공개 메타데이터
rss.xml                        # 검증 통과 V3 공개 메타데이터
```

HTML과 피드는 손으로 수정하지 않습니다. 입력 JSON 또는 렌더러를 고친 뒤 전체 빌드를 다시 실행합니다.
런타임 외부 의존성은 없고 Python 표준 라이브러리만 사용합니다.

## 3. PublicBriefV3 계약

V3는 **닫힌(closed) 공개 스키마**입니다. 정의되지 않은 최상위·중첩 필드는 ERROR입니다.

### 3.1 필수 메타데이터

| 필드 | 계약 |
|---|---|
| `schema_version` | 정수 `3` |
| `brief_id` | 공개 브리프 식별자. 내부 workflow/artifact ID를 사용하지 않음 |
| `market_code` | `KR` 또는 `US` |
| `window_code` | `preopen` 또는 `close` |
| `market_session_date` | 실제 시장일 `YYYY-MM-DD` |
| `generated_at_utc` | `Z` 접미사 UTC ISO-8601 |
| `cutoff_at_utc` | 데이터 cutoff. `generated_at_utc`보다 늦을 수 없음 |
| `market_timezone` | 유효한 IANA 시간대(예: `Asia/Seoul`, `America/New_York`) |
| `status` | 공개 상태 enum |
| `evidence_status` | 전체 근거 상태 enum |
| `methodology_version` | 공개 방법론 버전 |
| `public_receipt_sha256` | 공개 handoff preimage receipt 식별자, 64자리 소문자 hex |
| `out_path` | 세션 날짜와 일치하는 정규 상대 경로 `YYYY/MM/DD/<lowercase-safe>.html` |
| `title` | 공개 제목 |
| `sources` | 공개 SourceRef 목록 |

`public_receipt_sha256`는 TCX 내부 evidence 인증과 별개입니다. 현재 verifier는 **형식만 검사**하며 payload에서
해시를 재계산하거나 값의 진위를 인증하지 않습니다. 특정 run의 무결성 주장은 해당 current-run 서비스 증거와
receipt preimage를 함께 대조한 경우에만 가능합니다.

### 3.2 상태

`status`:

- `published`: 사람이 공개를 승인한 일반 브리프
- `partial`: 일부 근거만 확보된 기록
- `skipped_market_closed`: 휴장으로 생성하지 않은 사실을 남기는 기록
- `failed`: 생성·검증 실패 기록
- `corrected`: 이전 공개 레코드를 정정하는 기록

`evidence_status`와 SourceRef/claim별 근거 상태:

- `confirmed`: 허용된 현재-run 근거에 연결됨
- `partial`: 필요한 근거의 일부만 확인됨
- `not_proven`: 현재 증거로 확인하지 못함

전체 `evidence_status=confirmed`는 `status=confirmed`인 SourceRef를
`evidence_status=confirmed`인 공개 근거 항목이 참조할 때만 유효합니다. 단순히 ID가 연결됐거나
부분·미검증 근거만 있는 경우에는 전체 confirmed로 승격할 수 없습니다.

상태는 표현 정보이지 자동 공개 권한이 아닙니다. `partial`, `failed`, `skipped_market_closed`도 감사용 페이지로
렌더될 수 있으므로, production에 실제 포함할지는 사람의 발행 검토에서 확인합니다.

### 3.3 공개 SourceRef

각 `sources[]` 항목은 다음 필드만 허용합니다.

```json
{
  "source_id": "source-public-id",
  "publisher": "공개 발행자",
  "title": "자료 제목",
  "url": "https://example.org/source",
  "as_of": "2026-08-15T00:00:00Z",
  "retrieved_at": "2026-08-15T00:05:00Z",
  "source_type": "market_data",
  "status": "confirmed"
}
```

- URL은 HTTPS여야 합니다.
- `as_of`와 `retrieved_at`을 분리해 **자료의 기준 시각과 수집 시각**을 보존합니다.
- `source_id`는 payload 안에서 유일해야 합니다.
- 공개 SourceRef는 내부 Snapshot/Artifact ID의 별칭이 아닙니다.

### 3.4 주장·수치·가설

| 목록 | 필수 공개 필드 |
|---|---|
| `claims[]` | `claim_id`, `kind`, `text`, `as_of`, `source_ids`, `evidence_status` |
| `metrics[]` | `metric_id`, `label`, `value`, `unit`, `delta`, `as_of`, `source_ids`, `evidence_status` |
| `changes[]` | `dir`, `text`, `source_ids`, `evidence_status` |
| `drivers[]` | `label`, `text`, `source_ids`, `evidence_status` |
| `counterevidence[]` | `text`, `source_ids`, `evidence_status` |
| `hypotheses[]` | `hypothesis_id`, `text`, `observable`, `invalidation`, `horizon`, `source_ids`, `evidence_status` |
| `reviews[]` | `review_id`, `hypothesis_id`, `verdict`, `evidence`, `reason`, `lesson`, `source_ids`, `evidence_status` |
| `missing_data[]` | `label`, `reason`, `evidence_status` |
| `quality[]` | `label`, `value` |

`claims.kind`는 `fact`, `analysis`, `hypothesis` 중 하나입니다. `source_ids`는 비어 있지 않은 문자열 목록이며
같은 payload의 실제 `sources[].source_id`를 가리켜야 합니다. 숫자나 해석을 출처와 분리하지 않습니다.

선택 문자열은 `summary`, `next_handoff`이고, `today_learning`은 문자열 또는 문자열 목록입니다.
공개 위험 설명은 `risks[]`로 남길 수 있습니다.
개인 보유명, 계좌, 포지션, Strategy/Investor Context, 내부 workflow/artifact/snapshot/dataset/calculation ID,
로컬 경로와 `.tradingcodex` 경로는 공개 필드에 허용하지 않습니다.

## 4. 검증과 실패 폐쇄

`scripts/verify_brief.py`는 다음을 검사합니다.

1. 닫힌 V3 필드와 타입, enum
2. 실제 세션 날짜, UTC 시각, IANA timezone, cutoff 순서
3. HTTPS SourceRef와 source ID 중복
4. 모든 claim/metric/분석 항목의 source 참조
5. 공개 payload의 내부 식별자·경로·개인정보 패턴
6. 정정 상태의 필수 정정 필드

`scripts/build.py`는 JSON 파싱 실패 또는 verifier ERROR가 있는 레코드를 **출력에서 제외**하고 stderr에 거부 수를
기록합니다. 한 레코드가 전체 아카이브 생성을 중단시키지는 않지만, 그 레코드가 조용히 공개되는 일도 없습니다.
CI는 별도 verifier 명령을 먼저 실행하므로 저장소 안의 ERROR 레코드가 있으면 작업을 실패시킵니다.

이 fail-closed 경계가 확인하는 것은 공개 payload의 구조입니다. 출처가 진짜인지, 인용이 정확한지,
해석이 합리적인지, 데이터 재배포 권리가 있는지는 별도의 source review와 사람 승인이 필요합니다.

## 5. 공개 UI와 피드

- `index.html`: 한국 장전, 한국 마감, 미국 장전, 미국 마감의 최신 4개를 고정 순서로 보여줍니다.
- 상세 페이지: 상태 → 요약 → 수치 → 변화 → 동인 → 근거가 연결된 주장 → 반대 근거 → 학습/리스크 → 가설/검토 → 출처 순으로 점진 공개합니다.
- 레거시 v1/v2: HTML 아카이브에서는 `레거시 미검증`으로 표시하지만 머신 피드에는 내보내지 않습니다.
- `latest.json`: 각 슬롯의 최신 V3 공개 메타데이터만 포함합니다. V3가 없으면 `legacy_unverified` placeholder를 냅니다.
- `rss.xml`: 검증을 통과한 V3의 제목, 영구 링크, 상태, 근거 상태와 공개 요약만 제공합니다. V3가 없으면 item 없는 channel입니다.
- 상세 공유 버튼: Web Share API를 우선하고, 사용할 수 없으면 URL 복사로 폴백합니다.
- canonical/OG 메타데이터: production 상세 URL과 링크 미리보기를 위한 값입니다. 실제 production 배포와 카카오톡 unfurl은 별도 실측 대상입니다.

## 6. 정정

`status: "corrected"`인 V3 레코드는 다음 필드를 모두 가져야 합니다.

- `correction_note`: 무엇이 왜 바뀌었는지
- `corrected_at`: UTC 정정 시각
- `supersedes`: 대체하는 공개 브리프 식별자

원본을 설명 없이 덮어쓰지 않습니다. 정정 레코드도 같은 verifier, build, 사람 승인 경로를 거칩니다.
가설이 틀린 것은 데이터 오류와 구분하고 `reviews[]`의 학습 기록으로 남깁니다.

## 7. 배포 경계

빌드는 파일만 만듭니다. commit, push, Vercel deploy, 카카오톡·Slack 전송을 수행하지 않습니다.
공개 전에는 최소한 다음 증거가 필요합니다.

1. 전체 테스트와 verifier 통과
2. 빌드 전후 결정성 확인
3. 현재 트리와 모든 Git ref의 민감정보 스캔 0건
4. source rights review
5. reviewable diff에 대한 사용자 승인
6. commit SHA와 연결된 production deployment receipt
7. production URL 및 카카오톡 unfurl 실측

현재 과거 공개 Git 히스토리에 민감정보가 남아 있으므로 이 경로는 3번에서 **BLOCKED**입니다.
[재출시 체크리스트](RELAUNCH-CHECKLIST.md)의 clean-room 절차를 완료하기 전에는 push·deploy하지 않습니다.
