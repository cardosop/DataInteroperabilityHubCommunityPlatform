#!/bin/bash
# P2-4 (close-oss-release-conditions) — the G9 release-please dry-run.
#
# Runs the REAL release-please CLI (the 16.x line the release-please
# workflow's v4 action pins) in --dry-run (prepares, takes no action),
# with an isolated npm cache (a torn shared npx cache breaks the run —
# the 2026-10-20 finding) and the gh token via env (never echoed).
#
# KNOWN BLOCK (2026-10-20, recorded): the live dry-run over the deep
# prepro01 history fails API-side — release-please's GraphQL PR-walk
# (25 commits × PR associations × files per page over 750+ commits)
# returns HTTP 500s and then hangs past the pagination limits. The
# config fetch, the auth and the walk START are proven; the post-window
# retry targets the rewritten main. If the rewritten main hits the same
# wall, the CHANGELOG reconciliation falls back to the local contract
# (scripts/check_tag_main_anchor.py — manifest/VERSION/CHANGELOG agree,
# the tag peels to main HEAD).
#
# Usage: scripts/release_please_dry_run.sh [--target-branch NAME]
#   default target: main (the post-window shape); pre-window rehearsal
#   used prepro01 (the only remote branch carrying the release config).

set -euo pipefail

TARGET_BRANCH="${1:-main}"
if [[ "$1" == "--target-branch" ]]; then
    TARGET_BRANCH="${2:-main}"
fi

REPO_URL="${REPO_URL:-cardosop/DataInteroperabilityHub}"
NPM_CACHE="${NPM_CACHE_DIR:-/tmp/release-please-npm-cache}"

mkdir -p "$NPM_CACHE"

export GITHUB_TOKEN="${GITHUB_TOKEN:-$(gh auth token)}"
export npm_config_cache="$NPM_CACHE"

exec npx -y release-please@16.18.0 release-pr \
    --token "$GITHUB_TOKEN" \
    --repo-url "$REPO_URL" \
    --target-branch "$TARGET_BRANCH" \
    --dry-run \
    --config-file .release-please-config.json \
    --manifest-file .release-please-manifest.json
