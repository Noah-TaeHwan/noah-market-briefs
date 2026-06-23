# Market Briefs Static Archive

미국/한국 시장 전·마감 브리핑을 Slack 인라인 요약과 별도로 쌓기 위한 정적 HTML 아카이브 MVP입니다.

## Folder convention

```text
market-briefs/
  index.html
  assets/brief.css
  YYYY/MM/DD/{us-close|us-preopen|korea-close|korea-preopen}.html
```

## Design rule

- Slack: 5줄 요약 + HTML 파일 경로
- HTML: 숫자 스냅샷, 핵심 driver, Noah 보유논지 민감도, 내일 볼 센서
- 숫자는 반드시 `source`, `source_date`, `data_quality`를 같이 둔다.
- 확정 종가가 아니면 `장중`, `프리마켓`, `manual smoke`, `source-limited`를 명시한다.
- 매매 지시·목표가 언어 금지. `Watch`와 `무효화 조건` 중심.

## Prototype status

2026-06-23 파일은 디자인/구조 검증용 MVP입니다. 실제 시장 데이터 파이프라인과 연결되기 전까지 숫자/문장은 샘플로만 취급합니다.
