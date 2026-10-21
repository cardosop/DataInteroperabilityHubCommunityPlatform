#!/usr/bin/env bash
# =============================================================================
# scripts/tests/test_drill_merge_back.sh
#
# TDD contract suite for scripts/drill_merge_back.sh — the oss-release-
# remediation W0.4b (S4) post-rewrite merge-back drill. The drill must:
#
#   1. build a LOCAL public-sim bare repo (main seeded with a DCO'd commit)
#   2. create the synthetic PR commit on a branch — CORE paths only
#   3. refuse a synthetic commit that touches PAID paths (exit 1, "paid")
#   4. refuse a synthetic commit WITHOUT a Signed-off-by (exit 1, "DCO")
#   5. pull the branch back into a clone of the private repo via the REAL
#      scripts/pull_public_pr.sh (cherry-pick -x, GATE-29 re-run)
#   6. verify the landed commit carries BOTH the Signed-off-by trailer and
#      the "(cherry picked from commit" provenance line
#   7. publish via the REAL scripts/publish_public.sh into the public-sim
#      (mirror/public-core branch + vYYYY.MM.DD tag exist afterwards)
#   8. --cleanup-plan <owner/repo> prints the gh cleanup commands for the
#      REAL public repo: dependabot PR closes, dependabot branch deletes,
#      and a branch-protection PUT for main (read-only — never executes)
#   9. unknown flags are rejected (exit 2)
#
# The REAL github.com public repo is only READ by the cleanup plan; every
# mutating step runs against the local sim. No mocks.
#
# Usage: bash scripts/tests/test_drill_merge_back.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DRILL="${REPO_ROOT}/scripts/drill_merge_back.sh"

if [[ ! -f "${DRILL}" ]]; then
  echo "FAILED: ${DRILL} does not exist (write it first — TDD RED)"
  exit 1
fi

WORK="$(mktemp -d /tmp/test-drill-merge-back.XXXXXX)"
trap 'rm -rf "${WORK}"' EXIT
FAILS=0

fail() { echo "FAILED: $*" >&2; FAILS=$((FAILS + 1)); }

echo "--- 1. end-to-end drill: public -> private -> publish"
if bash "${DRILL}" --workdir "${WORK}/drill" >"${WORK}/drill.out" 2>&1; then
  echo "     drill exit 0"
  PRIVATE="${WORK}/drill/private"
  LANDED="$(git -C "${PRIVATE}" log -1 --format=%B)"
  grep -qE '^Signed-off-by: .+ <.+@.+\..+>' <<<"${LANDED}" \
    || fail "landed commit lacks the Signed-off-by trailer"
  grep -q "cherry picked from commit" <<<"${LANDED}" \
    || fail "landed commit lacks the cherry-pick provenance line"
  grep -q "synthetic community fix" <<<"${LANDED}" \
    || fail "the synthetic commit did not land"
  PUBLIC_SIM="${WORK}/drill/public-sim.git"
  git --git-dir="${PUBLIC_SIM}" rev-parse --verify refs/heads/mirror/public-core \
    >/dev/null 2>&1 || fail "publish did not push mirror/public-core"
  git --git-dir="${PUBLIC_SIM}" tag -l "v20[0-9][0-9].*" | grep -q . \
    || fail "publish did not tag the public-sim"
else
  echo "--- drill output:"; sed 's/^/    /' "${WORK}/drill.out" | tail -12
  fail "drill exited non-zero"
fi

echo "--- 2. paid-path synthetic commit is refused"
PAID_SIM="${WORK}/paid-sim.git"
mkdir -p "${WORK}/paid-seed"
git -C "${WORK}/paid-seed" init -q -b main
git -C "${WORK}/paid-seed" config user.email drill@test
git -C "${WORK}/paid-seed" config user.name Drill
git -C "${WORK}/paid-seed" config commit.gpgsign false
echo "public main" >"${WORK}/paid-seed/README.md"
git -C "${WORK}/paid-seed" add .
git -C "${WORK}/paid-seed" commit -qm "seed" -s
git init --bare -q "${PAID_SIM}"
git -C "${WORK}/paid-seed" remote add sim "${PAID_SIM}"
git -C "${WORK}/paid-seed" push -q sim main
git -C "${WORK}/paid-seed" checkout -qb community/bad
mkdir -p "${WORK}/paid-seed/hub/apps/billing"
echo "paid edit" >"${WORK}/paid-seed/hub/apps/billing/x.py"
git -C "${WORK}/paid-seed" add .
git -C "${WORK}/paid-seed" commit -qm "synthetic paid edit" -s
git -C "${WORK}/paid-seed" push -q sim community/bad
if bash "${DRILL}" --workdir "${WORK}/paid-drill" --public-sim "${PAID_SIM}" \
    --pr-ref community/bad >"${WORK}/paid.out" 2>&1; then
  fail "drill accepted a paid-path PR"
else
  grep -qi "paid" "${WORK}/paid.out" || fail "refusal did not name the paid path"
  echo "     refused with the paid-path message"
fi

echo "--- 3. DCO-missing synthetic commit is refused"
NO_DCO_SIM="${WORK}/nodco-sim.git"
mkdir -p "${WORK}/nodco-seed"
git -C "${WORK}/nodco-seed" init -q -b main
git -C "${WORK}/nodco-seed" config user.email drill@test
git -C "${WORK}/nodco-seed" config user.name Drill
git -C "${WORK}/nodco-seed" config commit.gpgsign false
echo "public main" >"${WORK}/nodco-seed/README.md"
git -C "${WORK}/nodco-seed" add .
git -C "${WORK}/nodco-seed" commit -qm "seed" -s
git init --bare -q "${NO_DCO_SIM}"
git -C "${WORK}/nodco-seed" remote add sim "${NO_DCO_SIM}"
git -C "${WORK}/nodco-seed" push -q sim main
git -C "${WORK}/nodco-seed" checkout -qb community/unsigned
echo "core docs edit" >>"${WORK}/nodco-seed/CONTRIBUTING.md"
git -C "${WORK}/nodco-seed" add .
git -C "${WORK}/nodco-seed" commit -qm "unsigned core edit"  # no -s
git -C "${WORK}/nodco-seed" push -q sim community/unsigned
if bash "${DRILL}" --workdir "${WORK}/nodco-drill" --public-sim "${NO_DCO_SIM}" \
    --pr-ref community/unsigned >"${WORK}/nodco.out" 2>&1; then
  fail "drill accepted a commit without a Signed-off-by"
else
  grep -qi "dco" "${WORK}/nodco.out" || fail "refusal did not name the DCO check"
  echo "     refused with the DCO message"
fi

echo "--- 4. cleanup plan for the REAL public repo (read-only)"
PLAN="${WORK}/plan.out"
if ! bash "${DRILL}" --cleanup-plan cardosop/DataInteroperabilityHubCommunityPlatform \
    >"${PLAN}" 2>&1; then
  fail "cleanup plan exited non-zero"
fi
grep -q "gh pr close" "${PLAN}" || fail "plan lists no dependabot PR closes"
grep -q "gh api -X DELETE repos/cardosop/DataInteroperabilityHubCommunityPlatform/git/refs/heads/dependabot/" "${PLAN}" \
  || fail "plan lists no dependabot branch deletes"
grep -q "PUT repos/cardosop/DataInteroperabilityHubCommunityPlatform/branches/main/protection" "${PLAN}" \
  || fail "plan lists no branch-protection PUT for main"
grep -qi "not protected" "${PLAN}" \
  || fail "plan does not record the current unprotected state"
echo "     plan names $(grep -c 'gh pr close' "${PLAN}") dependabot PRs to close"

echo "--- 5. unknown flags are rejected"
if bash "${DRILL}" --definitely-not-a-flag >/dev/null 2>&1; then
  fail "drill accepted an unknown flag"
else
  echo "     unknown flag rejected"
fi

echo
if [ "${FAILS}" -ne 0 ]; then
  echo "${FAILS} drill contract test(s) FAILED"
  exit 1
fi
echo "ALL drill contract tests passed"
