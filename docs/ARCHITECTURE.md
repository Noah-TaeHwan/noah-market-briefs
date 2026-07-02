# noah-market-briefs — 아키텍처 (데이터/화면 분리)

> 한 줄: **`data/` 에 JSON을 넣고 `python3 scripts/build.py` 를 돌리면 사이트가 나온다.**
> HTML을 손으로 짜지 않는다. 데이터(재료)와 화면(요리)을 분리한다.

## 흐름

```
cron 에이전트(LLM)  ──▶  data/2026/06/23/korea-close.json   (데이터만 append)
                                   │
                  python3 scripts/build.py  (표준 라이브러리만, 설치 0)
                                   │
                                   ▼
        index.html + 2026/06/23/*.html   (화면 = 빌드 결과물)
                                   │
                                Vercel (공개) ──▶ Slack 링크
```

- **`data/`** = 단일 진실 원천(source of truth). 브리프 1건 = JSON 파일 1개.
- **`scripts/build.py`** = `data/**/*.json` 을 읽어 ⓐ 각 브리프 HTML + ⓑ 정직한 카드 index 를 생성.
- **`scripts/render_market_brief.py`** = JSON payload 1건 → 브리프 HTML 1장 (디자인 시스템 `assets/brief.css` 사용).
- 렌더된 HTML은 git에 커밋된다(현재 방식). Vercel은 그 정적 파일을 서빙.

## 디렉토리

```
data/YYYY/MM/DD/<window>.json     # 입력(데이터). <window>=korea-close|korea-preopen|us-close|us-preopen
2026/MM/DD/<window>.html          # 출력(build.py가 생성)
index.html                        # 출력(build.py가 생성)
assets/brief.css                  # 디자인 시스템(단일 소스)
assets/favicon.svg
scripts/render_market_brief.py    # JSON → 브리프 HTML
scripts/build.py                  # data/ → 사이트 전체
tests/test_build.py               # 회귀 테스트(python3 tests/test_build.py)
```

## 브리프 추가하는 법 (수동 — 학습/직접 작성)

1. `data/2026/MM/DD/<window>.json` 작성 (아래 필드 참고, 기존 레코드 복사가 쉽다)
2. `python3 scripts/build.py` 실행 → HTML/index 재생성
3. `git diff` 로 바뀐 HTML 확인 → commit

## JSON 레코드 필드

**index 메타** (build.py가 사용):

| 필드 | 예 | 설명 |
|---|---|---|
| `date` | `"2026-06-23"` | 브리프가 다루는 시장일(정렬·표시) |
| `market_code` | `"KR"` / `"US"` | 시장(필터) |
| `window_code` | `"close"` / `"preopen"` | 윈도(필터) |
| `status` | `"live"` / `"sample"` | **샘플은 index에서 `Sample` 로 표기** — 샘플을 라이브로 착각 금지 |
| `out_path` | `"2026/06/23/korea-close.html"` | 렌더 결과 HTML 경로 |

**렌더 payload** (render_market_brief.py가 사용): `title`, `market`, `window`, `note`(선택, 히어로 배지), `generated`, `source`, `data_quality`, `use`(선택), `takeaway`, `metrics[]`{name,value,tone(`up`/`down`/`flat`/`warn`),note}, `drivers[]`{label,text}, `changes[]`{dir,text}(선택), `hypothesis_review[]`{previous_hypothesis,verdict,evidence,reason,lesson}(선택), `next_hypotheses[]`{hypothesis,observable,invalidation,horizon}(선택), `theses[]`{name,signal,`level`(선택 1~3 → ●○○ 핀),`lead`(선택 굵은 리드),body}(선택·기본 미사용), `watch[]`, `risks[]`, `quality[]`{label,value}(선택).

> 확장 규칙: 새 필드는 **선택(optional)으로 추가**. 렌더러는 `.get(key, default)` 라 빠진 필드는 빈 값으로 우아하게 처리 → 옛 레코드가 깨지지 않는다.

## 배포

- **현재:** 로컬에서 `python3 scripts/build.py` → 생성된 HTML/index 를 commit/push → Vercel 자동 배포.
- **후속 옵션(미적용):** `vercel.json` 에 `buildCommand: "python3 scripts/build.py"` 를 넣으면, `data/*.json` push 만으로 Vercel이 빌드해 배포(로컬 build 불필요). 도입 시 렌더 HTML은 `.gitignore` 로 빼고 `data/`+`scripts/` 만 추적.

---

## Part B — cron 전환 계약 (⚠️ Noah가 적용, 아직 미적용)

지금 cron 에이전트은 **HTML을 직접 손으로 작성**한다 → 디자인이 매번 흔들리고, 디커플링이 완성되지 않는다. 아래로 바꾸면 "다음 cron 브리프도 자동으로 같은 디자인"이 **진짜로** 성립한다.

**대상 잡:** macro-analyst 프로필 cron — `<job-id:KR-close>`(KR close), `<job-id:US-close>`(US close), `<job-id:KR-preopen>`(KR preopen), `<job-id:US-preopen>`(US preopen).

**프롬프트 변경 (각 잡의 'Static HTML archive requirement' 블록):**
- 기존: "`2026/MM/DD/<window>.html` 에 HTML 작성 + `index.html` 갱신 + 둘 다 git add/commit/push"
- 신규: "브리프를 **JSON**으로 `data/2026/MM/DD/<window>.json` 에 작성한다 (스키마 = 위 '렌더 payload' + `date`/`market_code`/`window_code`/`status:"live"`/`out_path`). **HTML·index.html은 직접 쓰지 않는다.** 그다음 `cd <repo> && python3 scripts/build.py` 로 사이트를 생성한다."

**git 단계 (allowlist 확장):**
```
git add -- data/YYYY/MM/DD/<window>.json YYYY/MM/DD/<window>.html index.html
git commit -m "Add market brief YYYY-MM-DD <window>"
git pull --rebase --autostash || git rebase --abort
git push
```
(Slack 링크 형식은 그대로 — Vercel URL이 같은 HTML 경로를 가리킨다.)

**🔴 durability 경고:** 위 cron 프롬프트는 `<cron 러너 설정 파일>`(**버전관리 안 됨**)에 산다 → 러너 재배포·재시작 때 지워질 수 있다. 따라서 이 계약을 적용한 뒤:
1. **이 문서(`docs/ARCHITECTURE.md`)가 정본** — 지워지면 여기서 다시 적용.
2. `recurring-market-briefings` 스킬의 `SKILL.md` 에도 같은 계약을 미러링.
3. bg/자동 세션에서는 `<cron 러너 설정>` 직접 수정이 classifier로 막힐 수 있어, **Noah가 직접** `러너 설정 편집` 로 적용.

**전환 순서(안전):** ① build.py·렌더러가 main에 머지된 뒤 → ② cron 프롬프트를 JSON 방식으로 전환 → ③ 한 번 수동 실행해 `data/*.json` 생성 + build + push + Vercel 확인 → ④ 정상 확인 후 다음 자동 실행에 맡김.

## Part B v2 — 투자 렌즈 + 어제 대비 변화 (template v2)

브리프를 보유종목 비의존 **"투자 관점 읽기"** + **"어제 대비 변화"**로 재구성. render는 신·구 스키마를 모두 렌더한다(**백워드 호환** — 새 필드 없으면 해당 요소만 미표시).

### 스키마 추가(전부 선택)
- 최상위 `changes`: `[{ "dir": "up"|"down"|"flat", "text": "..." }]` — 직전 같은 (market,window) 브리프 대비 시장 변화 2~3개.
- `theses[]` item에 `delta`: `{ "dir": "up"|"down"|"flat", "text": "어제 대비 한 줄" }`.
- `theses[]` 내용 = **투자 렌즈**(보유종목 아님): `위험선호` / `금리·duration` / `환율·달러(원화)` / `변동성·헤지` (+필요시 `섹터·브레드스`). 각 = `{name(렌즈), signal(오늘 읽기), level 1-3, delta, body}`.

### 렌더 동작
- `changes[]` → 히어로 다음 "어제 대비 변화" 섹션(방향 칩 ▲▼=).
- `theses` → "투자 관점 읽기" 섹션, 각 카드에 delta 한 줄.
- watch 제목은 `window_code` 로 자동: `preopen`→"오늘 볼 센서", 그 외→"내일 볼 센서".

### cron 프롬프트 애드덤 (4개 잡에 추가 — Noah가 `<cron 러너 설정>` 적용)
> **투자 렌즈 + 어제 대비 변화 (template v2):**
> - `theses[]` 를 **투자 관점 렌즈**로 채운다(보유종목 아님): 위험선호 / 금리·duration / 환율·달러(원화) / 변동성·헤지 (+필요시 섹터·브레드스). 각 렌즈 = `{name, signal(오늘 읽기), level 1-3, delta:{dir:up|down|flat, text:"어제 대비 한 줄"}, body}`. 데이터 근거 없으면 `미확인`.
> - `changes[]` (2-3개): **직전 같은 (market,window) 브리프**(data/ 에서 가장 최근 같은 윈도 JSON)를 읽어 시장이 뭐가 바뀌었나. 각 = `{dir, text}`. 직전 브리프 없으면 changes 생략.
> - 윈도 프레이밍: **장전 = 오늘 닥칠 환경(예측)**, **마감 = 오늘 받은 결과(회고)**. (watch 제목은 렌더가 window_code로 자동 전환.)
> - 소스 디시플린(미확인·출처·날짜·추론 금지) 그대로.

스펙: `docs/specs/2026-06-24-investing-brief-market-lenses-design.md`. **Phase 2**(다음 증분): build.py 가 (market,window,렌즈)별 레벨 히스토리를 집계해 ● 추이·스트릭(시장 흐름 저널).

## Part B v3 — 가설 검증 루프 (hypothesis learning loop)

브리프의 `오늘/내일 볼 센서`를 단순 체크리스트가 아니라 **가설 → 다음 회차 검증 → 학습 → 다음 가설** 루프로 고도화한다. 목적은 예측 맞히기 게임이 아니라, 매일의 시장 해석 프레임을 소스 기반으로 개선하는 것이다.

### 스키마 추가(전부 선택)
- `hypothesis_review`: 직전 같은 `(market_code, window_code)` 브리프의 `next_hypotheses[]`를 이번 데이터로 검증한 결과. 각 item = `{previous_hypothesis, verdict, evidence, reason, lesson}`. `verdict`는 `적중` / `부분 적중` / `반증` / `미검증`처럼 짧게 쓴다.
- `next_hypotheses`: 다음 같은 윈도 브리프에서 검증할 관찰 가능한 가설. 각 item = `{hypothesis, observable, invalidation, horizon}`. 가설은 방향성 단정이 아니라 검증 가능한 if/then 또는 watchpoint로 쓴다.

### 렌더 동작
- `hypothesis_review[]` → "이전 가설 검증" 섹션. 근거·판단·학습을 분리해 표시.
- `next_hypotheses[]` → "다음 체크 가설" 섹션. 관찰값·반증 조건·검증 시점을 분리해 표시.
- `watch[]`는 보조 체크리스트로 남길 수 있지만, 기본 운영의 주된 다음 회차 상태는 `next_hypotheses[]`다.

### cron 프롬프트 애드덤 (4개 잡 공통)
> **가설 검증 루프 (template v3):**
> - 직전 같은 `(market_code, window_code)` 브리프 JSON을 읽고, 그 안의 `next_hypotheses[]`를 이번 데이터로 검증해 `hypothesis_review[]`를 작성한다. 직전 가설이 없으면 `hypothesis_review`는 생략.
> - 각 검증은 `previous_hypothesis`, `verdict`, `evidence`, `reason`, `lesson`을 포함한다. 숫자·근거는 이번 run의 source-backed 데이터만 사용하고, 데이터가 부족하면 `미검증`으로 둔다.
> - 이번 브리프 끝에는 다음 같은 윈도에서 확인할 `next_hypotheses[]` 2~3개를 만든다. 각 가설은 `hypothesis`, `observable`, `invalidation`, `horizon`을 포함한다.
> - Slack에는 `이전 가설 검증` 1~2줄 + `오늘의 학습` 1줄 + `다음 체크 가설` 1~2개만 간결히 넣고, HTML에는 JSON 필드가 렌더되게 한다.
> - 특정 보유명(비상장 커머스/미국 온라인 게이밍/글로벌 증권사 등)은 Noah가 명시하지 않으면 쓰지 않는다. 가설은 시장 구조·환율·금리·유동성·변동성·섹터 breadth 중심으로 작성한다.
