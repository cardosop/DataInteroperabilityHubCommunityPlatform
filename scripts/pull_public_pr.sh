#!/usr/bin/env bash
# pull_public_pr.sh — integrate a community PR from the public repo (313.5.2).
#
# IMPORTANT ARCHITECTURAL FACT: the public repo's history was rewritten by
# the one-time filter-repo scrub, so the private repo shares NO commits with
# it — a `git merge-base` between the two histories is meaningless. The
# integration therefore bases verification on the PUBLIC main branch:
#
#   1. fetch public main + the PR ref
#   2. verify every commit in `public/main..PR` touches CORE paths only
#      (paid paths are refused loudly — defense in depth even though paid
#      dirs don't exist in the public tree)
#   3. cherry-pick -x each commit, oldest first (provenance recorded)
#   4. re-run GATE-29 — the boundary must stay green after integration
#
# The public branch is NEVER merged into private history.
#
# Usage: scripts/pull_public_pr.sh <public-remote> <pr-ref>
#        scripts/pull_public_pr.sh public community/my-fix

set -euo pipefail
cd "$(dirname "$0")/.."

REMOTE="${1:-public}"
PR_REF="${2:-}"

if [ -z "$PR_REF" ]; then
  echo "usage: $0 <public-remote> <pr-ref>"
  exit 2
fi

PYTHON="${PYTHON:-python3}"
log() { echo "[pull-public] $*"; }

log "fetching $REMOTE main + $PR_REF"
git fetch -q "$REMOTE" main
git fetch -q "$REMOTE" "$PR_REF"

COMMITS="$(git rev-list --reverse "$REMOTE/main..$REMOTE/$PR_REF")"
if [ -z "$COMMITS" ]; then
  log "ERROR: no commits in $REMOTE/$PR_REF beyond $REMOTE/main"
  exit 1
fi
COUNT="$(echo "$COMMITS" | wc -l | tr -d ' ')"
log "integrating $COUNT commit(s)"

log "verifying core-path scope"
PAID_PATTERNS='hub/apps/(semantic|marketplace|billing|baas|rate_limiting|ai|ml|social|graphql|graphql_ld|graphql_graphene)/|services/(semantic-service|dq-service|datacontract-service|compliance-service|prefect-|odh-|webhook-service|observability-service|workflow_engine)/|^infrastructure/|^helm/|^k8s/|^monitoring/'
BAD_PATHS="$(git diff-tree --no-commit-id --name-only -r "$REMOTE/main" "$REMOTE/$PR_REF" | grep -E "$PAID_PATTERNS" || true)"
if [ -n "$BAD_PATHS" ]; then
  log "ERROR: PR touches paid paths — refusing to integrate:"
  echo "$BAD_PATHS"
  exit 1
fi

# The exclusion list is manifest-GENERATED — a hand edit would be
# overwritten by the next regeneration. Point the contributor at the
# generator instead of silently integrating a doomed change.
if git diff-tree --no-commit-id --name-only -r "$REMOTE/main" "$REMOTE/$PR_REF" | grep -qE '^scripts/publish_paths_exclude\.txt$'; then
  log "ERROR: PR edits scripts/publish_paths_exclude.txt — this file is generated;"
  log "       edit scripts/generate_publish_excludes.py instead."
  exit 1
fi

log "cherry-picking with provenance"
for commit in $COMMITS; do
  git cherry-pick -x "$commit"
done

log "re-running GATE-29"
"$PYTHON" scripts/check_core_boundary.py

log "integration complete — run the relevant test suites before pushing"
