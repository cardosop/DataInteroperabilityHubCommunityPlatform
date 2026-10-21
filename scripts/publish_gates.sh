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
    local config_abs
    if git -C "$scan_dir" rev-parse --git-dir >/dev/null 2>&1; then
        # W0.4b root-cause fix: scan the TRACKED tree, never the raw
        # working directory — a raw scan catches untracked local
        # artifacts (__pycache__ bytecode, .ruff_cache, generated site/,
        # local env mirrors) that are NOT published, and the legacy
        # `detect` git mode scanned HISTORY instead of the tree being
        # shipped. Build a temp mirror of `git ls-files` and scan that.
        config_abs="$(cd "$scan_dir" && git rev-parse --show-toplevel)/.gitleaks.toml"
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
        scan_dir="$staging"
    else
        # The built publish tree is NOT a git repo — it already IS the
        # exact content being shipped (exclusions + replace-text applied
        # by the tree builder), so scan it directly. Config from the
        # caller's checkout (publish_public.sh cd's to the repo root).
        config_abs="$(git rev-parse --show-toplevel 2>/dev/null || pwd)/.gitleaks.toml"
    fi
    # Relative --source: the config's path allowlists match repo-relative
    # paths — an absolute source records absolute paths that never match.
    (cd "$scan_dir" && gitleaks detect --no-git --source . \
        --config "$config_abs" \
        --redact --no-banner --log-level=warn)
}

require_copyleft() {
    # G7 (close-oss-release-conditions P0-13): the published tree must
    # carry zero hard-copyleft (GPL/AGPL/SSPL) or license-unresolvable
    # dependencies in the SHIPPED closures — python (requirements +
    # pyproject extras + CLI deps) AND npm (frontend + sdk/js). Fail-closed:
    # the checker itself refuses on missing tooling or missing node_modules
    # (a publish with no license evidence is refused, never assumed clean —
    # same philosophy as require_gitleaks).
    local python_bin="${PYTHON:-python3}"
    log "copyleft audit (G7): shipped py + npm closures"
    "$python_bin" scripts/check_copyleft.py
}

require_push_protection() {
    # G12 (close-oss-release-conditions P0-9): the public remote must
    # have secret-scanning push protection ENABLED before ANY sync —
    # "public BEFORE the first re-sync — never during the window".
    # Fail-closed: the checker exits non-zero when the state is off OR
    # when it cannot be verified (missing gh, API error) — a publish
    # with no push-protection evidence is refused, never warned.
    local remote="${1:-public}"
    local python_bin="${PYTHON:-python3}"
    log "push-protection gate (G12): $remote must have secret-scanning push protection ENABLED"
    # P2-3 drill hook: a LOCAL sim remote has no GitHub URL to resolve —
    # PUBLISH_PROTECTION_REPO overrides the checked slug (the drill
    # simulates the public repo by checking the REAL one's state; the
    # gate still refuses whenever that state is not enabled). The
    # checker CLI treats --remote and --repo as mutually exclusive.
    if [[ -n "${PUBLISH_PROTECTION_REPO:-}" ]]; then
        "$python_bin" scripts/check_push_protection.py check \
            --repo "$PUBLISH_PROTECTION_REPO" --expect enabled
    else
        "$python_bin" scripts/check_push_protection.py check \
            --remote "$remote" --expect enabled
    fi
}
