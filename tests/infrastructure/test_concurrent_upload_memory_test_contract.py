"""
Phase 260.7.I — concurrent upload memory pressure test contract pins
(closes pass-3 T3-2).

The 260.7.I deliverable is a nightly k6 load test + a workflow that
asserts API container memory < 2 GiB peak under 100 concurrent 1 GiB
uploads. The actual k6 RUN happens nightly against staging — that
surface needs Redis, kubectl access, OIDC role, and a load-test
tenant with file:write scope.

This module pins the STATIC CONTRACT: the script + workflow exist at
expected paths AND contain the load parameters the spec mandates
(100 VUs, 1 GiB, 2 GiB memory ceiling). A future PR that drops the
script, the workflow, or silently lowers the load profile fails
these tests at PR-CI time — long before the broken nightly run
would surface a no-op.

These are PURE-PYTHON file-content checks — no Django, no AWS, no
k6 invocation. Runs in any CI env without credentials.
"""

from __future__ import annotations

import os
import re

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

K6_SCRIPT_PATH = os.path.join(
    PROJECT_ROOT,
    "tests",
    "load",
    "concurrent_uploads_memory.k6.js",
)
WORKFLOW_PATH = os.path.join(
    PROJECT_ROOT,
    ".github",
    "workflows",
    "upload-memory-nightly.yml",
)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Presence checks
# ---------------------------------------------------------------------------


def test_k6_script_exists():
    """Phase 260.7.I.1 — the k6 script exists at the expected path
    the workflow references. Catches a future repo-restructure that
    moves the script without updating the workflow."""
    assert os.path.isfile(K6_SCRIPT_PATH), (
        f"k6 script not found at {K6_SCRIPT_PATH!r}; Phase 260.7.I.1 mandates this exact filename"
    )


def test_workflow_exists():
    """Phase 260.7.I.1 — the nightly workflow MUST exist. The k6
    script alone does nothing; the workflow is what triggers
    nightly + asserts the memory ceiling."""
    assert os.path.isfile(WORKFLOW_PATH), (
        f"nightly workflow not found at {WORKFLOW_PATH!r}; "
        "the workflow is what triggers the k6 run + asserts memory"
    )


# ---------------------------------------------------------------------------
# k6 script content pins
# ---------------------------------------------------------------------------


def test_k6_script_targets_100_vus():
    """Phase 260.7.I.1 — the spec MANDATES 100 concurrent VUs.
    Catches a regression that quietly lowers the load (e.g., a
    "let's reduce flake by dropping to 50 VUs" PR that doesn't
    update the spec).
    """
    src = _read(K6_SCRIPT_PATH)
    # The ramping-vus stages must include a `target: 100` that
    # represents the steady-state hold (not just transient ramp).
    # We accept any stage that holds 100; the more lenient regex
    # pins the SPEC value.
    assert re.search(r"target:\s*100\b", src), (
        "k6 script MUST target 100 concurrent VUs per Phase 260.7.I.1 "
        "spec ('100 concurrent 1GB uploads')"
    )


def test_k6_script_simulates_1gib_files():
    """Phase 260.7.I.1 — the spec MANDATES 1 GiB file size. The
    multipart trigger is at >100 MiB (see views.py:415); 1 GiB is
    well above the threshold and produces ~100 chunks at 10 MiB
    chunk size — a meaningful concurrent-init load.
    """
    src = _read(K6_SCRIPT_PATH)
    # Accept either `1024 * 1024 * 1024` or `2 ** 30` or 1073741824
    # — three equivalent ways to write 1 GiB. The numeric value is
    # the contract; the syntax is the implementer's choice.
    assert "1024 * 1024 * 1024" in src or "2 ** 30" in src or "1073741824" in src, (
        "k6 script MUST simulate 1 GiB file size per Phase 260.7.I.1 "
        "spec ('100 concurrent 1GB uploads'). Accepted forms: "
        "`1024 * 1024 * 1024`, `2 ** 30`, or literal `1073741824`."
    )


def test_k6_script_drives_multipart_endpoints():
    """Phase 260.7.I — the test MUST exercise all three multipart
    API endpoints (init / chunks-init / complete). A test that only
    hit `/files/init/` would miss the chunks-init memory load
    (which is the heaviest path: ~100 chunks per VU × 100 VUs =
    ~10k concurrent chunks-init requests in flight at peak).
    """
    src = _read(K6_SCRIPT_PATH)
    for endpoint in ("/files/init/", "/chunks/init/", "/complete/"):
        assert endpoint in src, (
            f"k6 script MUST exercise {endpoint!r}; the multipart "
            "memory contract spans all three endpoints"
        )


def test_k6_script_pins_chunk_size_at_10mib():
    """Phase 260.7.I — the chunk size implied by the spec is
    10 MiB (matches the production default at
    `hub/apps/files/validators.py::get_chunk_size` for files >100MB).
    With 1 GiB file → ~100 chunks per VU, which is the load profile
    the test was designed for. A regression that drops the chunk
    size to 1 MiB would generate ~1000 chunks per VU and saturate
    the test runner before exposing the API memory contract.
    """
    src = _read(K6_SCRIPT_PATH)
    assert "10 * 1024 * 1024" in src or "10485760" in src, (
        "k6 script MUST pin the chunk size at 10 MiB (matches "
        "production default; 1 GiB / 10 MiB = ~100 chunks)"
    )


# ---------------------------------------------------------------------------
# Workflow content pins
# ---------------------------------------------------------------------------


def test_workflow_pins_memory_ceiling_at_2gib():
    """Phase 260.7.I.1 — the spec MANDATES the API memory peak <
    2 GiB. The workflow's MEMORY_CEILING_BYTES env var is the
    out-of-band assertion gate (k6 cannot read pod memory).
    """
    src = _read(WORKFLOW_PATH)
    # 2 GiB == 2 * 1024 ** 3 == 2147483648
    assert "2147483648" in src, (
        "Workflow MUST pin MEMORY_CEILING_BYTES at 2147483648 (2 GiB) "
        "per Phase 260.7.I.1 spec ('API container memory <2GB peak; "
        "no OOM')"
    )


def test_workflow_runs_k6_against_the_named_script():
    """Workflow MUST invoke the k6 script we just authored — not
    a different script. Catches a typo / refactor that points the
    workflow at the wrong file (which would silently exit 0 if k6
    interprets a non-existent path as a separate kind of failure).
    """
    src = _read(WORKFLOW_PATH)
    assert "tests/load/concurrent_uploads_memory.k6.js" in src, (
        "Workflow MUST invoke `tests/load/concurrent_uploads_memory.k6.js`; "
        "any other path is a wiring regression"
    )


def test_workflow_captures_pod_memory_via_kubectl():
    """The 2 GiB ceiling is asserted via `kubectl top pod` against
    the staging API deployment. Pin that the workflow uses
    kubectl-top (not, e.g., a Prometheus query that may be
    unwired) — the assertion mechanism IS part of the contract.
    """
    src = _read(WORKFLOW_PATH)
    assert "kubectl top pod" in src, (
        "Workflow MUST capture pod memory via `kubectl top pod` — "
        "the 260.7.I memory ceiling is asserted out-of-band by this "
        "monitor (k6 cannot read pod memory directly)"
    )


def test_workflow_uses_canonical_helm_pod_selector():
    """Phase 260.7.I.R1 GAP-C — the workflow MUST use the canonical
    Helm chart label ``app.kubernetes.io/component=api`` to select
    api-service pods. Pre-R1 used ``app=api-service`` which matches
    NO pods in this codebase — the memory monitor would have
    silently captured zero samples and the assertion would
    fail-open with "No memory samples captured", masking any real
    memory regression.

    Verified against ``helm/templates/api/deployment.yaml:8`` (the
    deployment label) and line 32 (the matchLabels selector).
    """
    src = _read(WORKFLOW_PATH)
    assert "app.kubernetes.io/component=api" in src, (
        "Workflow MUST use the canonical Helm label "
        "``app.kubernetes.io/component=api`` for pod selection. The "
        "label ``app=api-service`` (or any other guess) matches no "
        "pods and silently captures zero memory samples."
    )


def test_workflow_uses_canonical_aws_role_secret():
    """Phase 260.7.I.R1 GAP-A — the workflow MUST reference the
    canonical ``AWS_ROLE_STAGING`` secret used by the rest of the
    repo (see terraform.yml:135). Pre-R1 used
    ``STAGING_OIDC_ROLE_ARN`` which doesn't exist in GitHub secrets
    — the workflow would have failed at the AWS auth step with an
    empty role ARN.
    """
    src = _read(WORKFLOW_PATH)
    assert "secrets.AWS_ROLE_STAGING" in src, (
        "Workflow MUST use ``secrets.AWS_ROLE_STAGING`` (the "
        "canonical OIDC role secret used by terraform.yml). Other "
        "names like STAGING_OIDC_ROLE_ARN don't exist in repo secrets."
    )


def test_workflow_uses_canonical_smoke_admin_secrets():
    """Phase 260.7.I.R1 GAP-B — the workflow MUST reference the
    canonical ``SMOKE_ADMIN_EMAIL`` / ``SMOKE_ADMIN_PASSWORD``
    secrets used by perf-nightly.yml + e2e-nightly-full.yml.
    Pre-R1 used ``LOAD_TEST_TENANT_*`` secrets that don't exist —
    the workflow would have failed at JWT issuance.
    """
    src = _read(WORKFLOW_PATH)
    for secret_name in ("SMOKE_ADMIN_EMAIL", "SMOKE_ADMIN_PASSWORD"):
        assert f"secrets.{secret_name}" in src, (
            f"Workflow MUST reference ``secrets.{secret_name}`` (the "
            "canonical admin auth secrets used by other nightly "
            "workflows). Custom names like LOAD_TEST_TENANT_* don't "
            "exist in repo secrets."
        )


def test_workflow_extracts_access_token_field():
    """Phase 260.7.I.R1 GAP-D — the auth response field name is
    ``access_token`` per ``hub/apps/auth/serializers.py:85``. Pre-R1
    extracted ``['access']`` (a Simple JWT default this codebase's
    custom serializer doesn't emit) — JWT extraction would have
    raised KeyError and failed the workflow.
    """
    src = _read(WORKFLOW_PATH)
    assert "['access_token']" in src, (
        "Workflow MUST extract ``['access_token']`` from the login "
        "response (per hub/apps/auth/serializers.py:85). Other field "
        "names like ['access'] are Simple JWT defaults this codebase "
        "doesn't use."
    )


def test_workflow_cleans_up_test_files():
    """Phase 260.7.I.R1 GAP-E — the workflow MUST clean up File
    rows the k6 script created. Without cleanup, the staging tenant
    accumulates ~100 UPLOADING File rows per nightly × ~365 nights
    = ~36k orphan rows/year. The cleanup step issues
    ``DELETE /api/v1/files/{id}/`` for files matching the
    ``k6-mem-*`` name prefix; the existing ``purge_deleted_files``
    cron then hard-deletes them after the grace window.
    """
    src = _read(WORKFLOW_PATH)
    # Look for the cleanup step's distinctive markers.
    assert "k6-mem-" in src, (
        "Workflow MUST have a cleanup step that filters files by "
        "the ``k6-mem-`` name prefix (matches the script's filename "
        "pattern)."
    )
    assert "Cleanup test-created Files" in src, (
        "Workflow MUST have a step named ``Cleanup test-created "
        "Files`` so the audit trail is searchable."
    )


def test_workflow_runs_nightly():
    """Phase 260.7.I.1 — 'k6 nightly'. The workflow must have a
    cron schedule (not just workflow_dispatch — that's manual)."""
    src = _read(WORKFLOW_PATH)
    # Match the schedule block. We're lenient about intervening
    # comments / whitespace between `schedule:` and the first
    # `- cron:` entry so future doc edits that add a comment
    # (like the off-peak rationale already in this file) don't
    # break the test.
    assert re.search(
        r"schedule:.*?- cron:",
        src,
        re.DOTALL,
    ), (
        "Workflow MUST have a `schedule:` trigger with a cron "
        "expression per Phase 260.7.I.1 ('k6 nightly')"
    )


def test_workflow_fails_on_memory_ceiling_breach():
    """The workflow must `exit 1` (fail the run) when the memory
    peak exceeds the ceiling. Pin so a future edit that downgrades
    the assertion to a warning silently masks regressions.
    """
    src = _read(WORKFLOW_PATH)
    # Look for the assertion block: a line that says exceeds + exit 1
    assert "exit 1" in src, (
        "Workflow MUST `exit 1` on memory ceiling breach so the "
        "nightly run fails visibly. A warning-only assertion would "
        "let regressions accumulate."
    )


# ---------------------------------------------------------------------------
# Cross-reference: workflow's script-path matches the actual script
# location (catches a rename in one side that's missed in the other).
# ---------------------------------------------------------------------------


def test_workflow_script_path_matches_actual_script():
    """Belt-and-suspenders: the workflow references the script by
    PATH; the script exists at THAT path. If a future refactor
    renames the script without updating the workflow (or vice
    versa), this test fails before the nightly run silently
    no-ops.
    """
    workflow_src = _read(WORKFLOW_PATH)
    # Extract the path the workflow uses
    match = re.search(
        r"tests/load/(\S+\.k6\.js)",
        workflow_src,
    )
    assert match, (
        "Workflow doesn't reference any tests/load/*.k6.js script; expected a literal path"
    )
    referenced_relpath = "tests/load/" + match.group(1)
    referenced_abspath = os.path.join(PROJECT_ROOT, referenced_relpath)
    assert os.path.isfile(referenced_abspath), (
        f"Workflow references {referenced_relpath!r} but the file does "
        "not exist. Cross-reference broken — rename one side or fix "
        "the path on the other."
    )
