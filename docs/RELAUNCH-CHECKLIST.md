# 공개 재출시 체크리스트

## 현재 판정: 저장소·production은 나갔고, 자동화·카카오 unfurl은 남음

2026-09-03~09-04에 clean-room 공개 저장소 [`Noah-TaeHwan/noah-market-briefs`](https://github.com/Noah-TaeHwan/noah-market-briefs)
(구 이름 `noah-market-briefs-public`, 같은 repo id)에 PR #1·#2·#3이 머지됐고,
[공개 아카이브](https://noah-market-briefs.vercel.app/market-briefs)에 배포됐다. `main` push가 Vercel 배포를 트리거한다.

아래 본문의 **옛 공개 원격 history hit → BLOCKED** 는 그 전환을 막던 당시 기록이다.
그 원격은 지금 [`noah-market-briefs-archived`](https://github.com/Noah-TaeHwan/noah-market-briefs-archived)로 옮겨 아카이브했다.
제품 코드 작업은 archived 레포에서 이어가지 않는다.

아직 READY가 아닌 이유(남은 게이트):

- 카카오톡 production unfurl 실측
- 자동화 스케줄러 활성 증거 — [자동화 운영 계약](AUTOMATION.md)

코드 변경·PR·사람 승인 후 `main` 머지는 이 저장소에서 진행한다.
자동화 재개와 공개 링크 재홍보만 위 게이트에 묶인다. 이 문서에는 실제 이름, 값, 민감 경로를 기록하지 않는다.

## 권장 전략: clean-room 새 public repo

이 전략은 2026-09-03에 실행됐다. 결과물이 현재 저장소다. 같은 절차로 **또 다른** 공개 레포를 만들지 않는다.

history rewrite는 기존 clone, fork, pull request, tag, release, Actions artifact, deployment cache까지 함께 통제할 수
있고 사용자가 그 비용을 명시적으로 승인한 경우에만 대안으로 사용합니다. force push는 기본 선택이 아닙니다.

## 1. 동결과 범위 확인

- [ ] 기존 원격에 대한 자동 commit/push/deploy 작업을 모두 disable했다.
- [ ] Orca와 Codex Scheduled Tasks 양쪽의 현재 상태 증거를 보관했다.
- [ ] 조사 중에는 원격에 push하지 않는 별도 로컬 feature branch를 사용한다.
- [ ] 민감 패턴 denylist를 **저장소 밖의 로컬 파일**로 보관했다.
- [ ] 파일 본문뿐 아니라 commit message, tag, branch, pull request, release, Actions artifact, deployment log도 범위에 넣었다.

## 2. 소스 저장소 all-ref 감사

- [ ] `git for-each-ref`와 `git rev-list --objects --all`로 모든 로컬 ref와 도달 가능한 object 범위를 수집했다.
- [ ] 로컬 denylist로 모든 commit tree와 commit message를 스캔했다.
- [ ] branch/tag 외 dangling object와 reflog를 별도 확인했다.
- [ ] GitHub fork, PR ref, release asset, Actions artifact, Pages/Vercel cache의 잔존 가능성을 확인했다.
- [ ] 스캔 결과에는 민감한 원문을 복사하지 않고 **범위, 도구 버전, 시각, hit count**만 receipt로 남겼다.

당시 이 단계의 기존 공개 history hit가 0이 아니어서 **그 원격에 이어서 재출시하는 경로**는 BLOCKED였다.
그 원격은 archived로 옮겼고, 공개 작업면은 이 clean-room 저장소다.

## 3. clean-room 후보 만들기

- [ ] 검증된 현재 working tree를 `.git`, `.vercel`, cache, local denylist 없이 새 빈 디렉터리로 복사했다.
- [ ] 새 디렉터리에서 예상 파일 allowlist와 실제 파일 목록을 비교했다.
- [ ] `data/`, 생성 HTML, 문서, 이미지, SVG, JSON, XML을 모두 민감정보·credential 관점에서 다시 스캔했다.
- [ ] author 이름·이메일 등 새 Git metadata의 공개 범위를 사용자가 확인했다.
- [ ] 새 저장소의 첫 commit 전에 전체 테스트, verifier, build, `git diff --check`를 통과했다.
- [ ] 첫 commit hash와 파일 manifest hash를 receipt로 남겼다.

## 4. 권리·콘텐츠 검토

- [ ] [출처 및 권리 매트릭스](SOURCES.md)의 source review를 각 공개 브리프에 적용했다.
- [ ] 코드 MIT와 브리프 콘텐츠·인용 데이터 권리를 구분했다.
- [ ] 권리 미확정 콘텐츠는 All rights reserved로 표시하거나 공개 후보에서 제외했다.
- [ ] 브리프에 개인 Investor Context, 보유·계좌·포지션, 내부 TCX ID·경로가 없다.
- [ ] 투자 권유·매매 지시·목표가·자동 실거래 기능으로 오해될 표현이 없다.

## 5. 새 원격과 사용자 승인

- [ ] 새 GitHub public repo 이름, owner, 공개 범위, 기본 branch를 사용자가 승인했다.
- [ ] 기존 원격을 private/archive/delete 중 어떻게 처리할지 사용자가 승인했다.
- [ ] push될 정확한 commit SHA와 diff summary를 사용자에게 제시했다.
- [ ] 사용자가 **push를 명시적으로 승인한 뒤에만** 새 원격에 push한다.
- [ ] branch protection, pull request, CI를 설정하고 main에 직접 push하지 않는다.
- [ ] 원격의 모든 branch/tag를 다시 all-ref 스캔해 hit count 0 receipt를 남겼다.

## 6. production 배포 receipt

- [ ] 배포 대상 commit SHA가 승인된 Git commit과 일치한다.
- [ ] Vercel project/team/domain 연결을 확인했다.
- [ ] production deployment ID, URL, commit SHA, 배포 시각, 상태를 기록했다.
- [ ] `index.html`, 최신 상세 페이지, `latest.json`, `rss.xml`, CSS, 이미지가 production에서 200 응답인지 확인했다.
- [ ] canonical URL, OG title/description/image가 production origin을 가리킨다.
- [ ] 모바일 320px·390px와 데스크톱에서 최신 4개, 필터, 상세, 출처 링크, 공유 버튼을 확인했다.

로컬 `.vercel` 연결이나 URL 문자열만으로 production 배포를 증명하지 않습니다.

## 7. 카카오톡 production unfurl

- [ ] production 상세 URL을 카카오톡의 비공개 테스트 대화에 붙여 넣었다.
- [ ] 링크 제목, 설명, OG 이미지, 도메인, 대상 브리프 날짜가 맞다.
- [ ] 링크를 눌러 실제 production 상세 페이지가 열린다.
- [ ] 캐시된 옛 이미지·설명이 보이면 production 메타데이터와 카카오 캐시 갱신 절차를 확인했다.
- [ ] screenshot, 테스트 시각, URL, deployment ID를 receipt로 남겼다.

로컬 브라우저 미리보기나 다른 메신저의 unfurl은 카카오톡 production 증거로 대체하지 않습니다.

## 8. 자동화 재개

- [ ] [자동화 운영 계약](AUTOMATION.md)의 TradingCodex Stop hook blocker가 공식 core 수정으로 해결됐다.
- [ ] Codex 재시작 후 새 task에서 유효한 Stop JSON과 오류 부재를 실측했다.
- [ ] Orca와 Codex Scheduled Tasks 중 하나만 선택했고 반대편 disabled 증거가 있다.
- [ ] 네 작업의 시간·timezone·프롬프트를 확인했다.
- [ ] 첫 수동 run은 JSON 후보까지만 만들고 자동 commit/push/deploy/send가 없었다.
- [ ] 네 작업을 활성화하는 최종 사용자 승인을 받았다.

## 재출시 완료 기준

공개 저장소와 production 아카이브는 2026-09-03에 나갔다. 아래 7항이 모두 있어야
이 문서의 판정을 `READY`(자동화·재홍보 포함)로 바꾼다.

1. clean-room 원격 all-ref 민감정보 스캔 0건
2. 테스트·verifier·결정적 build receipt
3. source rights 검토 완료
4. 사용자 push/deploy 승인
5. commit SHA와 연결된 production deployment receipt
6. production 브라우저와 카카오톡 unfurl 실측
7. 중복 없는 단일 스케줄러 활성화 receipt

2026-09-04 기준 1–5는 closeout receipt로 채워졌고, **6의 카카오 unfurl과 7의 자동화는 아직 없다.**
그 두 항목이 비어 있다고 코드 PR을 막지 않는다. 자동화 재개와 링크 재홍보만 막는다.
