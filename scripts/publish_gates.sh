#!/usr/bin/env bash
# publish_gates.sh — pre-flight gates for publish_public.sh (Phase P.8).
#
# SOURCED by publish_public.sh and by scripts/tests/test_publish_gates.py
# (via subprocess), like publish_tree.sh. Provides:
#
#   require_gitleaks [SCAN_DIR]
#
# A publish is the one place a secret leak is non-recoverable (the public
# mirror is consumed downstream), and the operator running this script is
# precisely the case where CI did NOT run. So a MISSING gitleaks CLI is a
# hard failure, never a logged skip: no binary → no publish. The previous
# behaviour ("gitleaks CLI absent — SKIPPING") published trees with zero
# scan evidence.
#
# cds to the repo root (a no-op when the caller is already there).

set -euo pipefail

if ! declare -F log >/dev/null 2>&1; then
    log() { echo "[publish] $*"; }
fi

require_gitleaks() {
    local scan_dir="${1:-.}"
    if ! command -v gitleaks >/dev/null 2>&1; then
        log "ERROR: gitleaks CLI not found — refusing to publish an unscanned tree."
        log "       A publish is not recoverable: CI's gitleaks-action does not"
        log "       cover local publishes, so the scan must run HERE."
        log "       Install gitleaks: https://github.com/gitleaks/gitleaks#installing"
        return 1
    fi
    # W0.4b root-cause fix: scan the TRACKED tree, never the raw working
    # directory — a raw scan catches untracked local artifacts
    # (__pycache__ bytecode, .ruff_cache, generated site/, local env
    # mirrors) that are NOT published, and the legacy `detect` git mode
    # scanned HISTORY instead of the tree being shipped. Build a temp
    # mirror of `git ls-files` and scan that.
    local staging
    staging="$(mktemp -d /tmp/publish-gitleaks-tree.XXXXXX)"
    trap 'rm -rf "$staging"' RETURN
    local f
    while IFS= read -r f; do
        if [ ! -f "$scan_dir/$f" ]; then
            log "WARN: tracked file missing on disk (excluded from the scan): $f"
            continue
        fi
        mkdir -p "$staging/$(dirname "$f")"
        cp "$scan_dir/$f" "$staging/$f"
    done < <(cd "$scan_dir" && git ls-files)
    # Relative --source: the config's path allowlists match repo-relative
    # paths — an absolute source records absolute paths that never match.
    (cd "$staging" && gitleaks detect --no-git --source . \
        --config "$(cd "$scan_dir" && pwd)/.gitleaks.toml" \
        --redact --no-banner --log-level=warn)
}
