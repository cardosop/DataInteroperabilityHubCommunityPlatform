#!/usr/bin/env bash
# fork_smoke_pr.sh — W7.3 fork smoke: fork the PUBLIC repo, push a DCO-
# signed PR branch from the fork, open a PR to upstream main, and watch
# the PR checks go green — proving a fork contributor's CI path works
# with NO repository secrets.
#
# HARD PREREQUISITE: a SECOND GitHub account. The repo owner cannot fork
# their own repository (GitHub forbids it), and the owner account holds
# no orgs — the live fork-PR half of W7.3 needs an external contributor
# account (or an org). Until then the machine-verifiable half stands:
# GATE-56 (scripts/check_fork_guards.py, 18 pins) proves every
# secret-using pull_request path is fork-guarded / self-skipping, so a
# fork PR is green by construction.
#
# Usage (run from a machine logged into the FORK owner's account):
#   FORK_OWNER=<gh-user> bash scripts/fork_smoke_pr.sh
#
# Requirements: gh CLI (authed as the fork owner), git, gitleaks.

set -euo pipefail
cd "$(dirname "$0")/.."

UPSTREAM="cardosop/DataInteroperabilityHubCommunityPlatform"
FORK_OWNER="${FORK_OWNER:?set FORK_OWNER=<github-user> (the second account)}"
BRANCH="w73-fork-smoke-$(date +%Y%m%d%H%M%S)"

log() { echo "[fork-smoke] $*"; }

# 1. The fork must exist (or be created) under the second account.
if ! gh repo view "$FORK_OWNER/DataInteroperabilityHubCommunityPlatform" >/dev/null 2>&1; then
  log "creating fork under $FORK_OWNER (this may ask for the fork owner's gh auth)"
  gh repo fork "$UPSTREAM" --clone=false || {
    log "ERROR: cannot fork — fork your own repo? (owner can't). Use a second account."
    exit 1
  }
fi

# 2. Fresh fork clone, branch, DCO-signed commit, push.
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
gh repo clone "$FORK_OWNER/DataInteroperabilityHubCommunityPlatform" "$WORK/fork"
cd "$WORK/fork"
git remote add upstream "git@github.com:$UPSTREAM.git" 2>/dev/null || true
git fetch -q upstream main
git checkout -q -b "$BRANCH" upstream/main
# Trivial, harmless change: the smoke proves the CI PATH, not the patch.
printf '\n# Fork-smoke note (W7.3)\n' >> README.md
git add README.md
git commit -q -s -m "chore: W7.3 fork smoke — CI path from a fork PR"
git push -q -u origin "$BRANCH"

# 3. No-secrets proof on the fork tree (the publish pre-flight scans the
#    built tree; this re-proves it on the fork's own clone).
if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --no-git --source . --redact --no-banner --log-level=warn \
    || log "WARNING: gitleaks findings on the fork tree"
fi

# 4. PR to upstream + wait for checks.
PR_URL="$(gh pr create --repo "$UPSTREAM" --head "$FORK_OWNER:$BRANCH" \
  --base main --title "W7.3 fork smoke" \
  --body "Fork-PR CI smoke (oss-release-remediation W7.3): proves the fork contributor path is green with no repository secrets. Do not merge.")"
log "PR opened: $PR_URL"

if gh pr checks --repo "$UPSTREAM" --watch; then
  log "FORK SMOKE GREEN: all PR checks passed from the fork"
else
  log "ERROR: fork PR checks are RED — triage required"
  exit 1
fi

# 5. Cleanup: close the smoke PR (never merge it).
gh pr close "$PR_URL" --repo "$UPSTREAM" --delete-branch || true
log "smoke PR closed: $PR_URL"
