#!/usr/bin/env bash
# pull_public_pr.sh — integrate a community PR from the public repo (313.3.6).
#
# Contract:
#   1. fetch the public remote's main
#   2. verify every commit in the PR touches CORE paths only
#      (git diff-tree; paid paths are rejected loudly)
#   3. cherry-pick -x onto the current private branch (provenance recorded)
#   4. re-run GATE-29 — the boundary must stay green after integration
#
# The public branch is NEVER merged into private history.
#
# Usage: scripts/pull_public_pr.sh <public-remote> <pr-branch-or-sha>
#        scripts/pull_public_pr.sh public origin/main   # shorthand

set -euo pipefail
cd "$(dirname "$0")/.."

REMOTE="${1:-public}"
REF="${2:-main}"

log() { echo "[pull-public] $*"; }

log "fetching $REMOTE $REF"
git fetch -q "$REMOTE" "$REF"

MERGE_BASE="$(git merge-base HEAD "$REMOTE/$REF")"
if [ -z "$MERGE_BASE" ]; then
  log "ERROR: no merge base — is $REMOTE/$REF related to this history?"
  exit 1
fi

log "verifying core-path scope for commits: $MERGE_BASE..$REMOTE/$REF"
PAID_PATTERNS='hub/apps/(semantic|marketplace|billing|baas|rate_limiting|ai|ml|social|graphql|graphql_ld|graphql_graphene)/|services/(semantic-service|dq-service|datacontract-service|compliance-service|prefect-|odh-|webhook-service|observability-service|workflow_engine)/|^infrastructure/|^helm/|^k8s/|^monitoring/'
BAD_PATHS="$(git diff-tree --no-commit-id --name-only -r "$MERGE_BASE".."$REMOTE/$REF" | grep -E "$PAID_PATTERNS" || true)"
if [ -n "$BAD_PATHS" ]; then
  log "ERROR: PR touches paid paths — refusing to integrate:"
  echo "$BAD_PATHS"
  exit 1
fi

log "cherry-picking with provenance"
git cherry-pick -x "$MERGE_BASE".."$REMOTE/$REF"

log "re-running GATE-29"
python scripts/check_core_boundary.py

log "integration complete — run the relevant test suites before pushing"
