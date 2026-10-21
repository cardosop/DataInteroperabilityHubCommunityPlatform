#!/usr/bin/env bash
# drill_merge_back.sh — W0.4b (S4) post-rewrite merge-back drill + public
# repo cleanup plan.
#
# Two modes:
#
# 1. LOCAL END-TO-END DRILL (default): a synthetic DCO'd community PR
#    travels public -> private -> publish, entirely against a LOCAL
#    public-sim bare repo and a clone of this (private) repository:
#      - seeds a public-sim main (DCO'd commit) when none is provided
#      - creates the synthetic commit on a branch (CORE paths only)
#      - runs the REAL scripts/check_dco.sh over the PR range (a commit
#        without a Signed-off-by is refused before anything is pulled)
#      - runs the REAL scripts/pull_public_pr.sh (paid-path refusal,
#        cherry-pick -x, GATE-29 re-run)
#      - runs the REAL scripts/publish_public.sh into the public-sim
#        (mirror/public-core + vYYYY.MM.DD tag land in the sim)
#    The REAL github.com public repo is never touched in this mode.
#
# 2. --cleanup-plan <owner/repo>: prints (READ-ONLY) the gh commands to
#    clean up the public remote after the rewrite — close every open
#    dependabot PR, delete its branch, and set branch protection on main
#    (the public main is currently UNPROTECTED). Nothing is executed.
#
# Usage:
#   scripts/drill_merge_back.sh [--workdir DIR] [--public-sim PATH]
#                               [--pr-ref REF] [--skip-publish]
#   scripts/drill_merge_back.sh --cleanup-plan <owner/repo>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

CLEANUP_REPO=""
WORKDIR_ARG=""
PUBLIC_SIM_ARG=""
PR_REF_ARG=""
SKIP_PUBLISH=0

usage() {
  echo "usage: $0 [--workdir DIR] [--public-sim PATH] [--pr-ref REF] [--skip-publish]"
  echo "       $0 --cleanup-plan <owner/repo>"
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cleanup-plan) CLEANUP_REPO="${2:-}"; shift 2 ;;
    --workdir) WORKDIR_ARG="${2:-}"; shift 2 ;;
    --public-sim) PUBLIC_SIM_ARG="${2:-}"; shift 2 ;;
    --pr-ref) PR_REF_ARG="${2:-}"; shift 2 ;;
    --skip-publish) SKIP_PUBLISH=1; shift ;;
    *) echo "drill: unknown flag: $1" >&2; usage ;;
  esac
done

log() { echo "[drill] $*"; }

# ---------------------------------------------------------------------------
# Mode 2 — cleanup plan for the REAL public repo (read-only)
# ---------------------------------------------------------------------------
if [[ -n "$CLEANUP_REPO" ]]; then
  echo "# public-repo cleanup plan — $CLEANUP_REPO (READ-ONLY; nothing executed)"
  PROTECTION="$(gh api "repos/$CLEANUP_REPO/branches/main/protection" 2>&1 || true)"
  if grep -q "Branch not protected" <<<"$PROTECTION"; then
    echo "# main is currently NOT PROTECTED — the rewrite-era protection must be re-established"
  else
    echo "# main protection (current):"; echo "$PROTECTION" | head -5 | sed 's/^/#   /'
  fi
  echo "# 1. close every open dependabot PR + delete its branch:"
  if PRS="$(gh pr list --repo "$CLEANUP_REPO" --state open --json number,headRefName 2>/dev/null)"; then
    while IFS=$'\t' read -r NUM BRANCH; do
      case "$BRANCH" in
        dependabot/*)
          echo "gh pr close --repo $CLEANUP_REPO $NUM --comment \"closing: rewrite-era dependabot PR (W0.4b cleanup)\" # branch: $BRANCH"
          echo "gh api -X DELETE repos/$CLEANUP_REPO/git/refs/heads/$BRANCH # branch: $BRANCH"
          ;;
      esac
    done < <(echo "$PRS" | jq -r '.[] | [.number, .headRefName] | @tsv')
  else
    echo "#   (gh pr list failed — is gh authenticated?)"
  fi
  echo "# 2. re-establish branch protection on main (protected, no status-check requirements —"
  echo "#    the public CI status checks are the broken rewrite-era ones; the DCO check is the"
  echo "#    enforcement backstop via scripts/check_dco.sh):"
  cat <<EOF
gh api -X PUT repos/$CLEANUP_REPO/branches/main/protection --input - <<'BODY'
{
  "required_status_checks": null,
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
BODY
EOF
  exit 0
fi

# ---------------------------------------------------------------------------
# Mode 1 — local end-to-end drill
# ---------------------------------------------------------------------------
WORK="${WORKDIR_ARG:-$(mktemp -d /tmp/drill-merge-back.XXXXXX)}"
mkdir -p "$WORK"
PRIVATE="$WORK/private"
SIM="${PUBLIC_SIM_ARG:-$WORK/public-sim.git}"
PR_REF="${PR_REF_ARG:-community/synthetic-fix}"
REMOTE_NAME="sim"

log "workdir: $WORK"

# 1. seed the public-sim when none was provided
if [[ -z "$PUBLIC_SIM_ARG" ]]; then
  SEED="$WORK/seed"
  mkdir -p "$SEED"
  git -C "$SEED" init -q -b main
  git -C "$SEED" config user.email "drill@meshant.com"
  git -C "$SEED" config user.name "Drill Probe"
  git -C "$SEED" config commit.gpgsign false
  echo "# Public main (drill seed)" >"$SEED/README.md"
  git -C "$SEED" add .
  git -C "$SEED" commit -qm "seed public main" -s
  git init --bare -q "$SIM"
  git -C "$SEED" remote add "$REMOTE_NAME" "$SIM"
  git -C "$SEED" push -q "$REMOTE_NAME" main
  # synthetic community commit — CORE paths only, DCO signed
  git -C "$SEED" checkout -qb "$PR_REF"
  mkdir -p "$SEED/docs"
  echo "- synthetic community fix — drill probe (W0.4b S4)" >>"$SEED/docs/USER_GUIDE.md"
  git -C "$SEED" add .
  git -C "$SEED" commit -qm "synthetic community fix — drill probe" -s
  git -C "$SEED" push -q "$REMOTE_NAME" "$PR_REF"
  log "seeded public-sim $SIM with main + $PR_REF"
fi

# 2. private clone (never the live checkout)
log "cloning private repo (branch prepro01) into $PRIVATE"
git clone -q -b prepro01 "$REPO_ROOT" "$PRIVATE"
git -C "$PRIVATE" remote add "$REMOTE_NAME" "$SIM"

# 3. DCO gate BEFORE the pull-back (the public CI's own checker)
log "DCO check over $REMOTE_NAME/main..$REMOTE_NAME/$PR_REF"
git -C "$PRIVATE" fetch -q "$REMOTE_NAME" main
git -C "$PRIVATE" fetch -q "$REMOTE_NAME" "$PR_REF"
if ! bash "$PRIVATE/scripts/check_dco.sh" "$REMOTE_NAME/main..$REMOTE_NAME/$PR_REF"; then
  log "DCO check FAILED — refusing the drill PR"
  exit 1
fi

# 4. pull-back through the REAL integration script
log "pull-back via scripts/pull_public_pr.sh"
if ! (cd "$PRIVATE" && bash scripts/pull_public_pr.sh "$REMOTE_NAME" "$PR_REF"); then
  log "pull-back refused the drill PR"
  exit 1
fi

# 5. landed-commit verification
LANDED="$(git -C "$PRIVATE" log -1 --format=%B)"
grep -qE '^Signed-off-by: .+ <.+@.+\..+>' <<<"$LANDED" \
  || { log "landed commit lacks Signed-off-by"; exit 1; }
grep -q "cherry picked from commit" <<<"$LANDED" \
  || { log "landed commit lacks cherry-pick provenance"; exit 1; }
log "landed commit verified: Signed-off-by + cherry-pick provenance"

# 6. publish into the public-sim (the REAL publish script)
if [[ "$SKIP_PUBLISH" = "1" ]]; then
  log "--skip-publish: publish step skipped"
  exit 0
fi
# P2-3 provision: the publish's copyleft gate resolves the npm closure
# from node_modules — the drill's fresh private clone has none. The
# drill proves the FLOW, not the license audit (that runs on the real
# checkout's closure), so symlink the real node_modules in when present.
if [[ -d "$REPO_ROOT/frontend/node_modules" && ! -e "$PRIVATE/frontend/node_modules" ]]; then
  ln -s "$REPO_ROOT/frontend/node_modules" "$PRIVATE/frontend/node_modules"
  log "linked the real frontend/node_modules into the drill clone (copyleft closure)"
fi
PUBLIC_CHECKOUT="$WORK/public-checkout"
log "publish via scripts/publish_public.sh into $SIM"
git clone -q "$SIM" "$PUBLIC_CHECKOUT"
git -C "$PUBLIC_CHECKOUT" remote rename origin "$REMOTE_NAME" 2>/dev/null || true
if ! (cd "$PRIVATE" && PUBLIC_REMOTE="$REMOTE_NAME" PUBLIC_REPO_DIR="$PUBLIC_CHECKOUT" \
    PUBLISH_PROTECTION_REPO="cardosop/DataInteroperabilityHubCommunityPlatform" \
    bash scripts/publish_public.sh); then
  log "publish FAILED"
  exit 1
fi
git --git-dir="$SIM" rev-parse --verify "refs/heads/mirror/public-core" >/dev/null \
  || { log "mirror/public-core missing in the sim after publish"; exit 1; }
git --git-dir="$SIM" tag -l "v20*" | grep -q . \
  || { log "no vYYYY.MM.DD tag in the sim after publish"; exit 1; }

log "DRILL PASSED: synthetic PR travelled public -> private -> publish"
