#!/usr/bin/env bash
# publish_brief.sh — verify --strict 통과 후보를 피처 브랜치+PR+squash merge로 올린다.
# G1–G9는 기록만. verify 실패는 발행을 막는다. Slack/카카오/이메일은 보내지 않는다.
set -euo pipefail

canonical_basename() {
  local market="${1:-}" window="${2:-}"
  market=$(printf '%s' "$market" | tr '[:lower:]' '[:upper:]')
  window=$(printf '%s' "$window" | tr '[:upper:]' '[:lower:]')
  case "$market-$window" in
    KR-preopen) echo korea-preopen.json ;;
    KR-close) echo korea-close.json ;;
    US-preopen) echo us-preopen.json ;;
    US-close) echo us-close.json ;;
    *) return 1 ;;
  esac
}

allowed_stage_path() {
  local p="${1:-}"
  case "$p" in
    data/[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]/*.json) return 0 ;;
    [0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]/*.html) return 0 ;;
    index.html|latest.json|rss.xml) return 0 ;;
    *) return 1 ;;
  esac
}

forbidden_staged() {
  local p="${1:-}"
  case "$p" in
    scripts/*|docs/*|tests/*|AGENTS.md|README.md|.github/*) return 0 ;;
    *) return 1 ;;
  esac
}

resolve_dest() {
  local candidate="$1" market window date dest_name y m d
  read -r market window date < <(python3 -c 'import json,sys; j=json.load(open(sys.argv[1])); print(j["market_code"], j["window_code"], j["market_session_date"])' "$candidate")
  dest_name=$(canonical_basename "$market" "$window") || {
    echo "알 수 없는 시장/윈도: $market $window" >&2
    return 1
  }
  y=${date%%-*}; rest=${date#*-}; m=${rest%%-*}; d=${rest#*-}
  echo "data/$y/$m/$d/$dest_name"
}

publish_main() {
  local dry_run=0 calendar="" now="" candidate=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --dry-run) dry_run=1; shift ;;
      --calendar) calendar="${2:-}"; shift 2 ;;
      --now) now="${2:-}"; shift 2 ;;
      --) shift; break ;;
      -*) echo "usage: $0 [--dry-run] --calendar open|closed|unknown [--now UTC-Z] <candidate>" >&2; return 2 ;;
      *) candidate="$1"; shift ;;
    esac
  done
  [ -n "${1:-}" ] && [ -z "$candidate" ] && candidate="$1"
  if [ -z "$candidate" ] || [ -z "$calendar" ]; then
    echo "usage: $0 [--dry-run] --calendar open|closed|unknown [--now UTC-Z] <candidate>" >&2
    return 2
  fi
  case "$calendar" in
    open|closed|unknown) ;;
    *) echo "--calendar 는 open|closed|unknown" >&2; return 2 ;;
  esac
  [ -n "$now" ] || now=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  local script_dir repo
  script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
  repo="${PUBLISH_REPO:-$(CDPATH= cd -- "$script_dir/.." && pwd)}"
  candidate=$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$candidate")
  [ -f "$candidate" ] || { echo "후보 없음: $candidate" >&2; return 1; }

  local dest_rel dest
  dest_rel=$(resolve_dest "$candidate") || return 1
  dest="$repo/$dest_rel"

  echo "canonical dest=$dest_rel"
  echo "source=$candidate"

  if [ "$dry_run" -eq 1 ]; then
    echo "DRY-RUN would place $dest_rel"
    python3 "$repo/scripts/verify_brief.py" --strict "$candidate"
    set +e
    python3 "$repo/scripts/gate_check.py" "$candidate" --now "$now" --calendar "$calendar" --repo "$repo"
    local gate_rc=$?
    set -e
    [ "$gate_rc" -eq 2 ] && { echo "gate_check 사용법 오류" >&2; return 2; }
    echo "PLAN branch=data/${dest_rel#data/}"
    echo "PLAN verify --strict 통과 후 build + PR + gh pr merge --squash"
    echo "PLAN leftover delete only after origin/main has $dest_rel"
    return 0
  fi

  python3 "$repo/scripts/verify_brief.py" --strict "$candidate"
  set +e
  python3 "$repo/scripts/gate_check.py" "$candidate" --now "$now" --calendar "$calendar" --repo "$repo"
  local gate_rc=$?
  set -e
  [ "$gate_rc" -eq 2 ] && { echo "gate_check 사용법 오류" >&2; return 2; }
  echo "gate_check exit=$gate_rc (기록만 — 발행 계속)"

  local y m d rest date_hyphen window_slug branch
  rest=${dest_rel#data/}
  y=${rest%%/*}; rest=${rest#*/}; m=${rest%%/*}; rest=${rest#*/}; d=${rest%%/*}
  window_slug=${dest_rel##*/}; window_slug=${window_slug%.json}
  date_hyphen="$y-$m-$d"
  branch="data/${date_hyphen}-${window_slug}"

  cd "$repo"
  git fetch origin
  git checkout -B "$branch" origin/main

  mkdir -p "$(dirname "$dest")"
  if [ "$candidate" != "$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$dest")" ]; then
    if [ "$(dirname "$candidate")" = "$(dirname "$dest")" ]; then
      mv -- "$candidate" "$dest"
    else
      cp -- "$candidate" "$dest"
    fi
  fi

  python3 "$repo/scripts/verify_brief.py" --strict "$dest"
  python3 "$repo/scripts/build.py"

  git add -- "$dest_rel"
  local html_rel year_dir
  html_rel=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("out_path",""))' "$dest")
  [ -n "$html_rel" ] && [ -f "$html_rel" ] && git add -- "$html_rel"
  # P0: 해당 기준일 4창구 상태 카드. 다음 슬롯 publish가 갱신한다.
  [ -f "$y/$m/$d/index.html" ] && git add -- "$y/$m/$d/index.html"
  [ -f index.html ] && git add -- index.html
  [ -f latest.json ] && git add -- latest.json
  [ -f rss.xml ] && git add -- rss.xml
  # CI는 build.py 후 git diff --exit-code. 끼워 넣은 날짜는 이웃 adjacent-nav도 바꾼다.
  git add -u -- index.html latest.json rss.xml
  shopt -s nullglob
  for year_dir in [0-9][0-9][0-9][0-9]; do
    git add -u -- "$year_dir"
  done
  shopt -u nullglob

  local staged
  staged=$(git diff --cached --name-only)
  [ -n "$staged" ] || { echo "staged 없음 — 발행할 파일이 없다" >&2; return 1; }
  while IFS= read -r path; do
    [ -z "$path" ] && continue
    if forbidden_staged "$path"; then
      echo "거부: staged에 파이프라인 파일이 있다: $path" >&2
      git reset -q HEAD --
      return 1
    fi
    if ! allowed_stage_path "$path"; then
      echo "거부: 허용 밖 staged: $path" >&2
      git reset -q HEAD --
      return 1
    fi
  done <<< "$staged"

  git commit -m "$(cat <<EOF
data: ${date_hyphen} ${window_slug} 브리프 발행

EOF
)"
  git push -u origin HEAD
  gh pr create --base main --title "data: ${date_hyphen} ${window_slug}" --body "$(cat <<EOF
## Summary
- ${date_hyphen} ${window_slug} 브리프를 아카이브에 올린다.
- G1–G9는 기록만. verify --strict 통과.

## Test plan
- [ ] CI verify (3.11/3.12/3.13) 통과
- [ ] production에 해당 날짜 HTML이 보인다
EOF
)"
  # 이 repo는 enablePullRequestAutoMerge 가 꺼져 있다. --auto 실패 시 CI 대기 후 squash.
  # --admin 금지. required check 가 아직 안 뜨면 --required 는 즉시 실패한다.
  if ! gh pr merge --squash --auto --delete-branch; then
    echo "auto-merge 불가 — CI 대기 후 squash"
    sleep 8
    gh pr checks --watch --interval 10
    gh pr merge --squash --delete-branch
  fi
  echo "safe to reap leftover after origin/main has $dest_rel"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  publish_main "$@"
fi
