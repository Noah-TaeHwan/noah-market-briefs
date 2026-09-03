# 출처와 데이터 권리 매트릭스

최종 확인일: **2026-08-15**

이 문서는 법률 자문이 아니라 공개 브리프의 source gate입니다. **무료 열람 가능**, **API 사용 가능**,
**수치 인용 가능**, **원문·시세 재배포 가능**은 서로 다른 권리입니다. 조건이 불명확하면 공개 payload에 넣지 않고
`not_proven` 또는 `missing_data`로 남깁니다.

## 원칙

1. 공식 1차 출처를 우선합니다.
2. `as_of`와 `retrieved_at`을 UTC로 따로 기록합니다.
3. 자료 제목, 발행자, 원문 HTTPS URL을 보존합니다.
4. 원문·전체 표·실시간 피드를 복제하지 않고 필요한 최소 수치와 자체 해석만 공개합니다.
5. 각 출처의 이용약관, attribution, 호출 제한, 지연 조건을 실제 사용 전에 다시 확인합니다.
6. 유료·계정·API key가 필요한 취득은 별도 사용자 승인과 canonical connector 경로가 필요합니다.
7. raw credential은 저장소, 프롬프트, 로그, 브리프 JSON에 저장하지 않습니다.

## 공식 출처 매트릭스

| 출처 | 적합한 용도 | 공식 문서 | 공개 브리프 기본 자세 | 활성화 전 확인 |
|---|---|---|---|---|
| KRX Data Marketplace | 한국 지수·종목·거래·수급 통계 | [데이터 포털](https://data.krx.co.kr/contents/MDC/MAIN/main/index.cmd), [정보이용정책 PDF](https://data.krx.co.kr/inc/datasale/Market%20Data%20Usage%20Polices_ko.pdf) | 공식 화면의 최소 지연 수치 인용 후보. 실시간·대량·재분배는 허용으로 가정하지 않음 | 데이터 상품·사용자 유형별 라이선스, 지연, 표시·재분배 범위 |
| OpenDART | 한국 상장사 공시, 재무·지분·주요사항 | [OpenDART](https://opendart.fss.or.kr/), [개발 가이드](https://opendart.fss.or.kr/guide/main.do), [인증키 약관](https://opendart.fss.or.kr/uss/umt/EgovMberInsertView.do) | 공시 URL과 최소 사실 인용 후보. API key는 승인된 connector에서만 사용 | 인증키 약관, 호출 제한, 공시 원문/첨부의 별도 권리 |
| SEC EDGAR | 미국 발행사 공식 filings와 XBRL | [Search Filings](https://www.sec.gov/search-filings), [Developer Resources·Fair Access](https://www.sec.gov/about/developer-resources) | filing 원문 링크와 최소 사실 인용 후보 | 자동 요청 식별, 요청률, 최신 Fair Access 정책, 문서별 제3자 저작물 |
| U.S. BLS | 고용·물가·임금 등 공식 노동통계 | [Public Data API](https://www.bls.gov/audience/developers.htm), [API Terms](https://www.bls.gov/developers/termsOfService.htm), [Copyright](https://www.bls.gov/opub/copyright-information.htm) | 출처·access date와 요구 disclaimer를 표시해 최소 수치 공개 가능 후보 | API 약관의 인용 문구와 호출 제한; BLS 로고 사용 금지 |
| FRED | 거시 시계열 탐색·비교 | [FRED](https://fred.stlouisfed.org/), [API Overview](https://fred.stlouisfed.org/docs/api/fred/overview.html), [API Terms](https://fred.stlouisfed.org/docs/api/terms_of_use.html), [Legal](https://fred.stlouisfed.org/legal/) | **시리즈별 권리 확인 전 공개 재배포 보류.** 공식 원발행자 링크를 우선 | API key 승인, FRED 고지문, 각 series의 원소유자·라이선스·attribution |
| NYSE | 미국 거래소 일정·상품·시장 구조, proprietary data | [Data Products](https://www.nyse.com/data-products/), [Market Data Documents](https://www.nyse.com/market-data/documents) | 일정·공식 공지 링크 후보. proprietary 시세·피드 재배포는 라이선스 전 금지 | 상품별 계약, 실시간/지연 구분, display·non-display·redistribution 권리 |

### BLS 표시 문구

BLS API 사용 시 공식 Terms가 요구하는 access/retrieval date와 다음 고지를 공개 페이지에 포함합니다.
“BLS.gov cannot vouch for the data or analyses derived from these data after the data have been retrieved from BLS.gov.”
BLS 상표·로고는 사용하지 않습니다.

### FRED 주의

FRED는 여러 원출처의 시계열을 모읍니다. FRED에서 조회할 수 있다는 사실만으로 각 series의 재배포 권리가
생기지 않습니다. 공개 전에는 series metadata의 원출처와 권리를 확인하고, 필요한 FRED 고지문과 Terms 링크를
표시합니다. 확인 전에는 내부 비교 또는 원발행자 탐색에만 사용합니다.

FRED API를 공개 제품에 사용한다면 공식 Terms가 요구하는 다음 고지도 표시합니다.
“This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis.”

## 애그리게이터와 라이브러리

| 도구 | 허용 기본값 | 공개 전 필요한 것 |
|---|---|---|
| OpenBB | 내부 교차검증·원출처 탐색만 | 실제 provider, 원데이터 권리, attribution, 호출·저장·재배포 조건을 provider별로 확인 |
| yfinance | 내부 비교·이상치 탐지만 | upstream 데이터의 약관과 공개 재배포 권리를 별도로 확인. 라이브러리 사용 가능성과 데이터 권리를 혼동하지 않음 |

OpenBB나 yfinance가 반환한 값을 단독으로 `confirmed` 공개 근거로 승격하지 않습니다. 같은 시점의 공식 1차 출처가
확보되면 공개 SourceRef는 공식 출처를 가리키고, 애그리게이터 결과는 내부 비교 증거로만 남깁니다.

## 유료·credential source gate

다음 중 하나라도 해당하면 자동화에 넣기 전에 별도 승인을 받습니다.

- 구독, 과금, 거래소 라이선스 또는 사용자별 계약이 필요함
- API key, 계정, 쿠키, OAuth 또는 기타 credential이 필요함
- 원문 저장·캐시·재분배 범위가 불명확함
- 실시간 또는 non-display 권리 구분이 있음
- 호출이 private/local network 또는 실거래 connector에 닿음

승인 후에도 raw secret은 환경·공식 connector의 secret store에만 두고 TradingCodex children, 저장소,
PublicBriefV3, 빌드 산출물, 로그에 전달하지 않습니다. 실거래 API는 이 리서치 파이프라인에서 직접 호출하지 않습니다.

## 브리프별 source review

공개 전 각 V3 레코드에 대해 다음을 확인합니다.

- [ ] SourceRef가 공식 HTTPS 원문을 가리킨다.
- [ ] `as_of`와 `retrieved_at`이 실제 UTC 시각이다.
- [ ] 각 claim/metric의 `source_ids`가 해당 주장을 직접 뒷받침한다.
- [ ] attribution·disclaimer·링크 요구사항을 지켰다.
- [ ] 인용 범위가 최소이며 원문/전체 데이터셋을 재배포하지 않는다.
- [ ] 권리 불명확 항목을 `confirmed`로 표시하지 않았다.
- [ ] credential과 내부 ID·경로가 공개 payload에 없다.
