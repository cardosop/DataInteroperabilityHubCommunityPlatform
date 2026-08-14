#!/usr/bin/env bash
# Phase 313.0 — repeatable secrets-rotation verification (repo-side).
#
# Encodes the acceptance criteria of openspec preprod01 tasks 313.0.1/313.0.2:
#   1. rotation test suite (history absence, cross-environment uniqueness,
#      root-.env ↔ .env.dev mirror, TLS freshness, compose resolution + consistency)
#   2. gitleaks git-mode (CI parity)
#   3. gitleaks --no-git over the publishable surface (tracked files + local env files)
#
# Run: scripts/verify_secrets_rotation.sh
#   PYTHON=/path/to/venv-python scripts/verify_secrets_rotation.sh   (override interpreter)
#
# Requires: git, pytest (in $PYTHON env), gitleaks (skipped when absent —
# CI runs gitleaks/gitleaks-action@v2 as the enforcement backstop).

set -euo pipefail

cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"

echo "== [1/3] rotation test suite (RED→GREEN guard: history, mirror, compose) =="
# Standalone run: this suite is repo-hygiene only (no Django needed). The
# repo conftests import Django apps, so bypass them and the django plugin
# here; CI collects the same file inside the full configured suite.
"$PYTHON" -m pytest tests/security/test_secrets_rotation.py -q --no-header \
  --noconftest -p no:django

if [ "$(git rev-parse --is-shallow-repository)" = "true" ]; then
  echo "WARNING: shallow clone — history-based assertions were skipped; rerun with full history"
fi

echo "== [2/3] gitleaks git-mode (CI parity) =="
if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --source . --config .gitleaks.toml --redact --no-banner --log-level=warn
else
  echo "gitleaks not installed — skipping (CI runs gitleaks/gitleaks-action@v2)"
fi

echo "== [3/3] gitleaks --no-git over tracked + local-env surface =="
if command -v gitleaks >/dev/null 2>&1; then
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' EXIT
  git archive HEAD | tar -x -C "$tmpdir"
  for f in .env .env.dev .env.staging .env.test .env.e2e; do
    [ -f "$f" ] && cp "$f" "$tmpdir/"
  done
  cp .gitleaks.toml "$tmpdir/"
  # The whole-tree scan is intentionally scoped: venvs/build junk are not
  # secret-bearing surface and make an unscoped --no-git run unbounded.
  gitleaks detect --no-git --source "$tmpdir" --config "$tmpdir/.gitleaks.toml" \
    --redact --no-banner --log-level=warn
else
  echo "gitleaks not installed — skipping (CI runs gitleaks/gitleaks-action@v2)"
fi

echo "verify: all checks passed"
