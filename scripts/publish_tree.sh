#!/usr/bin/env bash
# publish_tree.sh — build the sanitized public tree (Phase 313.3.5).
#
# SOURCED by publish_public.sh and by scripts/tests/test_publish_tree.py
# (via subprocess). Provides:
#
#   build_publish_tree OUT_DIR REPLACE_TEXT_FILE
#
# OUT_DIR           — receives the public tree (created if missing).
# REPLACE_TEXT_FILE — mappings produced by scripts/build_replace_text.py
#                     (the same file the history scrub uses, 313.3.3); the
#                     tree is sanitized with the identical replace pairs.
#
# The public Makefile is single-sourced: Makefile.core is copied to
# OUT_DIR/Makefile AFTER the overlay, so the shipped quickstart can never
# drift from the private definition again (313.DoD.5 — the stale
# hand-maintained overlay copy referenced services and flags that did not
# exist).
#
# NOTE: the tree is extracted from the git INDEX (git ls-files +
# checkout-index), not the working tree — uncommitted edits and untracked
# files never ship. Stage or commit changes before building.
#
# cds to the repo root (a no-op when the caller is already there).

set -euo pipefail

if ! declare -F log >/dev/null 2>&1; then
    log() { echo "[publish] $*"; }
fi

build_publish_tree() {
    local out="${1:?usage: build_publish_tree OUT_DIR REPLACE_TEXT_FILE}"
    local replace_file="${2:?usage: build_publish_tree OUT_DIR REPLACE_TEXT_FILE}"

    local repo_root
    repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    repo_root="$(dirname "$repo_root")"
    cd "$repo_root"

    # Sentinel: the tree must be built from the PRIVATE repo (its CI never
    # ships). Building from a public clone or a wrong cwd would silently
    # publish the wrong source of truth.
    if [ ! -f .github/workflows/ci.yml ]; then
        log "ERROR: not the private repo root (no .github/workflows/ci.yml) —"
        log "       run from the private checkout or source with an absolute path"
        exit 1
    fi

    log "building core tree"
    # Rebuild from scratch: a previous stack boot bind-mounts files OUT of
    # the tree, and docker creates root-owned DIRECTORIES at missing mount
    # sources — those poison a reused output dir (checkout-index silently
    # skips them, leaving traefik to fail with "read /etc/traefik/traefik.yml:
    # is a directory"). Rename the old dir aside — a rename only needs write
    # on the PARENT, so it works even when the old dir holds root-owned
    # docker artifacts that a plain rm -rf cannot remove. Clean rebuilds
    # make repeated quickstart verification deterministic (313.DoD.5 churn
    # root cause).
    if [ -e "$out" ]; then
        mv "$out" "$out.old.$$"
    fi
    mkdir -p "$out"
    # Scratch space mirrors the original layout ($STAGING inside $WORK):
    # files.txt lives NEXT TO the tree so it never ships, and the caller's
    # EXIT trap (publish_public.sh) keeps owning its cleanup.
    local files_list
    files_list="$(dirname "$out")/files.txt"

    # Exclusion entries are file paths or trailing-slash dir prefixes
    # (manifest-generated) — the python filter handles both forms.
    "${PYTHON:-python3}" - "$files_list" <<'PYEOF'
import sys
out_path = sys.argv[1]
excl = [l.strip() for l in open("scripts/publish_paths_exclude.txt") if l.strip() and not l.startswith("#")]
import subprocess
files = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.splitlines()
# "!prefix" entries re-include paths otherwise excluded (e.g. helm/ is
# excluded wholesale, "!helm/community/" ships the community chart).
# Negations may be files (exact match) or dir prefixes (startswith) —
# both forms must match, not only the slash-suffixed ones.
negations = [e[1:] for e in excl if e.startswith("!")]
plain = [e for e in excl if not e.startswith("!")]
keep = []
for f in files:
    excluded = any(f == e or f.startswith(e) for e in plain if e.endswith("/")) or f in plain
    if excluded and not any(f == e or f.startswith(e) for e in negations):
        continue
    keep.append(f)
open(out_path, "w").write("\n".join(keep) + "\n")
PYEOF

    # Extract the INDEX state (not the working tree): the publishable source of
    # truth is the committed/staged content — uncommitted moves/edits must be
    # staged (or committed) before they ship, and untracked files never leak.
    git checkout-index -f --prefix="$out/" --stdin < "$files_list"

    # The frontend prebuild (scripts/sync-shared.sh) requires the repo-root
    # shared/ INSIDE the frontend build context (compose builds frontend with
    # context ./frontend; the private CI copies shared/ in before building).
    # Mirror that here so the public tree's frontend builds out of the box.
    if [ -d "$out/shared" ] && [ -d "$out/frontend" ]; then
        mkdir -p "$out/frontend/shared"
        cp -r "$out/shared/." "$out/frontend/shared/"
    fi

    # overlay (patched worker Dockerfile, license/community files)
    if [ -d scripts/publish_public_overlay ]; then
        cp -r scripts/publish_public_overlay/. "$out/"
    fi

    # Single-source the public Makefile (313.DoD.5): Makefile.core is the
    # definition; the overlay must not ship a duplicate that can drift.
    cp Makefile.core "$out/Makefile"

    # Sanitize the staged tree with the same replace mappings as the history
    # scrub — leaked values + internal hostnames must never enter sync commits.
    "${PYTHON:-python3}" - "$out" "$replace_file" <<'PYEOF'
import sys
from pathlib import Path

staging, replace_file = Path(sys.argv[1]), Path(sys.argv[2])
pairs = []
for line in replace_file.read_text().splitlines():
    if "==>" in line:
        old, _, new = line.partition("==>")
        pairs.append((old, new))
text_suffixes = (".md", ".py", ".yml", ".yaml", ".toml", ".txt", ".json", ".sh", ".ini", ".cfg", ".html", ".js", ".ts", ".tsx", ".cjs", ".mjs", ".css")
for path in staging.rglob("*"):
    if not path.is_file() or not path.suffix.lower() in text_suffixes:
        continue
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    for old, new in pairs:
        content = content.replace(old, new)
    path.write_text(content, encoding="utf-8")
PYEOF

    log "tree built: $(find "$out" -type f | wc -l) files (sanitized)"

    # Best-effort cleanup of the renamed-aside previous build; root-owned
    # docker artifacts inside it may survive and are safe to remove with
    # sudo.
    if [ -e "$out.old.$$" ]; then
        rm -rf "$out.old.$$" 2>/dev/null \
            || log "note: could not fully remove $out.old.$$ (root-owned docker artifacts)"
    fi

    # Authoritative post-build gate: the SANITIZED tree must be clean.
    local hostname_hits
    hostname_hits="$(grep -rIlE 'staging\.hub\.meshant\.com|wiki\.internal|grafana\.internal' "$out" 2>/dev/null || true)"
    if [ -n "$hostname_hits" ]; then
        log "ERROR: internal hostnames remain after sanitization:"
        echo "$hostname_hits"
        exit 1
    fi
}
