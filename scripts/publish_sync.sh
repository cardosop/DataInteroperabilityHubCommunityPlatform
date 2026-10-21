#!/usr/bin/env bash
# publish_sync.sh — sync the BUILT tree to the public repo (Phase 313.3.5).
#
# SOURCED by publish_public.sh (the real publish) and by
# scripts/tests/test_p25_public_replacement.py (the P2-5 contract pins).
# Provides:
#
#   sync_to_public STAGING TAG PRIVATE_SHA
#
# Runs with cwd = the public checkout. The P2-5 root fixes (G3):
#
#  1. BOOTSTRAP = ROOT LINEAGE — when the remote has no
#     mirror/public-core ref, the first sync commit is committed as an
#     ORPHAN (no parent). Appending onto a stale local
#     mirror/public-core would fork the replaced (tainted) public
#     lineage and re-publish it on the first push (G3: append-only
#     publishes can never remove tainted history).
#  2. EXACT-TREE COMMITS — the index is rebuilt from scratch
#     (git rm --cached + add of exactly the built tree's files), so
#     checkout litter (untracked files swept in by the old `git add -A`)
#     can never enter a sync commit — the P-1 structural-drift root
#     cause (AGENTS.md/ARCHITECTURE.md/.devcontainer/... litter on the
#     public mirror). A post-commit gate diffs the committed tree
#     against the built tree and fails the sync on any deviation.
#  3. MAIN LANDS — the remote default branch main is fast-forwarded to
#     the SAME commit as mirror/public-core (non-force; the remote main
#     must be absent or an ancestor — anything else refuses fail-closed).
#     The public repo's default branch was previously never synced by
#     the publish script.
#  4. Fail-closed guards: a dirty checkout (tracked changes), a missing
#     remote, and a diverged remote mirror all refuse the sync with a
#     recipe before anything is pushed.
#
# PUBLISH_SYNC_SKIP_VERIFY=1 skips ONLY the post-commit gitleaks /
# GATE-29 / compose re-scan (the fixture checkouts in the contract
# tests carry a minimal tree — those gates are pinned independently in
# test_publish_gates.py and always run at a real publish).

set -euo pipefail

if ! declare -F log >/dev/null 2>&1; then
    log() { echo "[publish-sync] $*"; }
fi

sync_to_public() {
    local staging="${1:?usage: sync_to_public STAGING TAG PRIVATE_SHA}"
    local tag="${2:?usage: sync_to_public STAGING TAG PRIVATE_SHA}"
    local private_sha="${3:?usage: sync_to_public STAGING TAG PRIVATE_SHA}"
    local remote="${PUBLIC_REMOTE:-public}"

    # Guard 1 — the checkout must carry no TRACKED modifications: the
    # sync REPLACES the tracked tree wholesale and a half-edited
    # checkout must not be snapshotted. A fresh empty checkout (no HEAD
    # yet — the clean-room pattern) has nothing to be dirty against and
    # passes.
    if git rev-parse -q --verify HEAD >/dev/null 2>&1; then
        if ! git diff --quiet || ! git diff --cached --quiet; then
            log "ERROR: public checkout has uncommitted TRACKED changes — commit or stash them first"
            return 1
        fi
    fi

    # Guard 2 — the remote must EXIST (a fresh clone of the recreated
    # repo is empty but reachable; a missing remote is a hard error,
    # not "first publish").
    if ! git ls-remote -q "$remote" >/dev/null 2>&1; then
        log "ERROR: $remote remote does not exist or is unreachable"
        return 1
    fi

    local bootstrap=0
    if git fetch -q "$remote" mirror/public-core 2>/dev/null; then
        if git rev-parse -q --verify refs/heads/mirror/public-core >/dev/null 2>&1; then
            if ! git merge-base --is-ancestor FETCH_HEAD mirror/public-core 2>/dev/null; then
                log "ERROR: local mirror/public-core diverged from $remote/mirror/public-core"
                log "       realign:  git checkout main &&"
                log "                 git fetch $remote mirror/public-core &&"
                log "                 git branch -f mirror/public-core FETCH_HEAD &&"
                log "                 git checkout mirror/public-core"
                return 1
            fi
        else
            log "local mirror/public-core missing — creating it at the remote head"
            git branch -q -f mirror/public-core FETCH_HEAD
        fi
    else
        # P2-5 bootstrap: a stale local mirror/public-core forks the
        # replaced lineage — drop it and commit the first sync commit
        # as a ROOT (orphan). Detaching first lets the branch delete; a
        # fresh empty checkout has no branch (and no HEAD) to detach
        # from.
        bootstrap=1
        log "remote has no mirror/public-core — bootstrapping a ROOT lineage (P2-5)"
        if git rev-parse -q --verify refs/heads/mirror/public-core >/dev/null 2>&1; then
            # both steps are CORRECTNESS-CRITICAL: a failed detach or
            # delete would leave the stale branch alive and the orphan
            # checkout would refuse — or worse, a masked failure would
            # commit ON TOP of the tainted lineage. No `|| true` here.
            git checkout -q --detach
            git branch -q -D mirror/public-core
        fi
        git checkout -q --orphan mirror/public-core
    fi
    # Only switch when not already on the branch: on the orphan
    # bootstrap HEAD is UNBORN and `git checkout <branch>` falls back to
    # pathspec resolution ("did not match any file(s)").
    if ! git symbolic-ref -q --short HEAD 2>/dev/null | grep -qx mirror/public-core; then
        git checkout -q mirror/public-core
    fi

    # Replace the tracked content with the new tree.
    git ls-files | while IFS= read -r f; do rm -f "$f"; done
    (cd "$staging" && find . -type f | sed 's|^\./||') | while IFS= read -r f; do
        mkdir -p "$(dirname "$f")"
        cp -p "$staging/$f" "$f"
    done

    # Exact-tree index discipline (P-1 drift root fix): REBUILD the index
    # from scratch. `git read-tree --empty` clears it with no HEAD/stat
    # dependencies (the previous `git rm --cached` silently failed in the
    # real first sync and unioned the old tree into the commit — caught
    # by the post-commit exactness gate; the P2-5 redo's root fix). ONE
    # `git add --pathspec-from-file` call stages exactly the built tree
    # (12k+ files — the per-file loop was a ~20-minute process storm):
    # `--pathspec-file-nul` reads elements LITERALLY (no glob/magic
    # interpretation — bracket paths like odd[file].txt stay exact) and
    # `-f` keeps ignore rules from subtracting content (frontend/shared).
    git read-tree --empty
    local tree_files committed_files
    tree_files="$(mktemp /tmp/publish-sync-files.XXXXXX)"
    committed_files="$(mktemp /tmp/publish-sync-committed.XXXXXX)"
    local verify_dir=""
    trap 'rm -f "$tree_files" "$committed_files"; [ -n "$verify_dir" ] && rm -rf "$verify_dir"' RETURN
    (cd "$staging" && find . -type f -print0 | sed -z 's|^\./||' | LC_ALL=C sort -z) > "$tree_files"
    git add -f --pathspec-from-file="$tree_files" --pathspec-file-nul

    git commit -q -m "sync: core subset @ ${private_sha}" || log "nothing to commit"

    # Post-commit exactness gate: the committed tree MUST be byte- and
    # set-identical to the built tree (the built tree is what the
    # pre-flight gates scanned). One diff each for the file set and the
    # content (the per-file cmp loop was the second process storm).
    git ls-tree -r --name-only HEAD | LC_ALL=C sort > "$committed_files"
    if ! cmp -s <(tr '\0' '\n' < "$tree_files") "$committed_files"; then
        log "ERROR: committed tree file set differs from the built tree:"
        diff <(tr '\0' '\n' < "$tree_files") "$committed_files" | head -20 || true
        return 1
    fi
    verify_dir="$(mktemp -d /tmp/publish-sync-verify.XXXXXX)"
    git archive HEAD | tar -x -C "$verify_dir"
    if ! git diff --no-index --quiet "$verify_dir" "$staging" >/dev/null 2>&1; then
        log "ERROR: committed content differs from the built tree:"
        git diff --no-index --name-status "$verify_dir" "$staging" 2>/dev/null | head -20 || true
        return 1
    fi

    # Post-commit verification IN the public checkout (before any push):
    # GATE-29 + gitleaks + compose config must all pass here. Skipped
    # only by the contract-test fixtures (PUBLISH_SYNC_SKIP_VERIFY=1) —
    # the gates themselves are pinned in test_publish_gates.py.
    if [ "${PUBLISH_SYNC_SKIP_VERIFY:-0}" != "1" ]; then
        log "post-commit verification (public checkout)"
        "$PYTHON" scripts/check_core_boundary.py
        require_gitleaks .
        docker compose -f docker-compose.test.yml -f docker-compose.test.core.yml config -q
    fi

    git push -q "$remote" mirror/public-core

    # Main sync (P2-5 root fix #3): the default branch lands on the
    # SAME commit — non-force, so a divergent remote main refuses here.
    if remote_main="$(git ls-remote -q "$remote" refs/heads/main | cut -f1)" && [ -n "$remote_main" ]; then
        if ! git merge-base --is-ancestor "$remote_main" mirror/public-core 2>/dev/null; then
            log "ERROR: remote main ($remote_main) is not an ancestor of the new sync commit — refusing the main sync"
            return 1
        fi
    fi
    git push -q "$remote" mirror/public-core:main

    # Tags are movable (vYYYY.MM.DD) — force ONLY the tag ref, never the branch.
    git tag -f "$tag"
    git push -q --force "$remote" "$tag"
    log "synced $tag to $remote mirror/public-core + main ($(git rev-parse --short HEAD))"
}
