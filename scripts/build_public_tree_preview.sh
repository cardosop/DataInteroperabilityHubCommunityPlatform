#!/usr/bin/env bash
# Phase Q review (2026-08-23) — build the public tree from the WORKING tree.
#
# publish_tree.sh builds from the git INDEX (checkout-index) — correct for
# the real publish flow (only committed content ships), but useless for
# pre-commit local verification of UNCOMMITTED fixes: the public tree would
# silently contain HEAD's versions of every edited file (the Q review found
# this the hard way — GATE-29 looked red on the public tree for sites that
# were already fixed and allowlisted in the working tree).
#
# This preview builder runs the REAL builder first, then overlays the
# working-tree versions of every modified/untracked file that ships, and
# re-applies the same scrub sanitization. Never used by CI or publish —
# strictly a local verification tool.
#
# Usage: bash scripts/build_public_tree_preview.sh <out-dir>
set -euo pipefail

OUT="${1:?usage: build_public_tree_preview.sh <out-dir>}"
REPLACE_FILE="${2:-/tmp/public_replace_text.txt}"
cd "$(dirname "$0")/.."

source scripts/publish_tree.sh
"${PYTHON:-python3}" scripts/build_replace_text.py --out "$REPLACE_FILE"
rm -rf "$OUT" && mkdir -p "$OUT"
build_publish_tree "$OUT" "$REPLACE_FILE"

# Working-tree delta: tracked-but-modified + untracked-but-not-gitignored.
git diff --name-only > /tmp/preview_delta.txt
git ls-files --others --exclude-standard >> /tmp/preview_delta.txt

"${PYTHON:-python3}" - "$OUT" "$REPLACE_FILE" <<'PYEOF'
import subprocess
import sys
from pathlib import Path

out, replace_file = Path(sys.argv[1]), Path(sys.argv[2])
pairs = []
for line in replace_file.read_text().splitlines():
    if "==>" in line:
        old, _, new = line.partition("==>")
        pairs.append((old, new))

# Mirror the publish exclusion semantics so the preview matches the
# post-commit publish tree (exact paths + trailing-slash dir prefixes,
# with "!" negations).
excl = [l.strip() for l in open("scripts/publish_paths_exclude.txt") if l.strip() and not l.startswith("#")]
negations = [e[1:] for e in excl if e.startswith("!")]
plain = [e for e in excl if not e.startswith("!")]

def excluded(rel: str) -> bool:
    hit = any(rel == e or (e.endswith("/") and rel.startswith(e)) for e in plain)
    if hit and not any(rel == e or rel.startswith(e) for e in negations):
        return True
    return False

overlaid = 0
for rel in subprocess.run(["git", "diff", "--name-only"], capture_output=True, text=True).stdout.splitlines():
    if excluded(rel):
        continue
    dst = out / rel
    if dst.exists():
        dst.write_text(Path(rel).read_text(encoding="utf-8"))
        overlaid += 1
# Untracked files: after the batch commits they SHIP (the index builder
# never includes them — this preview simulates the post-commit tree).
for rel in subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], capture_output=True, text=True).stdout.splitlines():
    if excluded(rel):
        continue
    dst = out / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(Path(rel).read_text(encoding="utf-8"))
    overlaid += 1

text_suffixes = (".md", ".py", ".yml", ".yaml", ".toml", ".txt", ".json", ".sh", ".ini", ".cfg", ".html", ".js", ".ts", ".tsx", ".cjs", ".mjs", ".css")
for path in out.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in text_suffixes:
        continue
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    for old, new in pairs:
        content = content.replace(old, new)
    path.write_text(content, encoding="utf-8")

print(f"overlaid {overlaid} working-tree files; sanitized")
PYEOF
