#!/usr/bin/env bash
# 0.4 — DCO check for the PUBLIC repo's pull requests.
#
# Every commit in the given range MUST carry a ``Signed-off-by:``
# trailer (Developer Certificate of Origin). Exit codes:
#   0 — all commits signed off
#   1 — missing script usage (empty range) or one or more unsigned commits
#
# Usage: bash scripts/check_dco.sh <git-range>   (e.g. "HEAD~1..HEAD",
#        or the default github.event.pull_request range set by the caller)
set -u

RANGE="${1:-}"
if [ -z "$RANGE" ]; then
  echo "❌ DCO check: no commit range provided" >&2
  echo "   usage: bash scripts/check_dco.sh <git-range>" >&2
  exit 1
fi

FAIL=0
# Read commits oldest-first so the FIRST unsigned commit is reported.
while IFS= read -r commit; do
  subject=$(git log -1 --format=%s "$commit" 2>/dev/null || true)
  body=$(git log -1 --format=%B "$commit" 2>/dev/null || true)
  if ! grep -qE '^Signed-off-by: .+ <.+@.+\..+>' <<<"$body"; then
    echo "❌ DCO: commit '$subject' ($commit) is missing a Signed-off-by trailer" >&2
    echo "   amend with: git commit -s --amend" >&2
    FAIL=1
  fi
done < <(git rev-list --reverse "$RANGE" 2>/dev/null)

if [ "$FAIL" -ne 0 ]; then
  echo "DCO check FAILED — see the commits above." >&2
  exit 1
fi
echo "✅ DCO: all commits in '$RANGE' carry a Signed-off-by trailer"
exit 0
