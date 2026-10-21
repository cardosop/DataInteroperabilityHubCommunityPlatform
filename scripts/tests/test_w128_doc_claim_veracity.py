"""W12.8 (oss-release-remediation) — doc-claim veracity pins.

The named liars fixed this pass (claim → fix → pin):

  * ``plan_defaults.py`` docstring named ``PersonalTenantService`` as an
    importer — it never imported the catalog.  Corrected; pinned by
    ``hub/apps/tenants/tests/test_plan_defaults_doc_claims.py``.
  * ``.github/workflows/CI_CD_SUMMARY.md`` claimed "Total Workflows: 6"
    vs the ~79 shipped yml files.  DELETED (GATE-61 STUB-008 now watches
    the real path).
  * README quickstart `make` claims — every advertised target and every
    compose/port claim must be real (the pre-fix assessment found
    boundary-check/publish-check missing; they exist now and stay
    pinned here).
  * The reviewer checklist — ``docs/OSS_CONTRIBUTION.md`` now carries
    the P4 rule: contract/doc claims must cite a test or gate.
  * The RLS "tests re-documented to bless absent middleware" class —
    the request-path arming middleware exists (W1.20); a scan pin makes
    any prose claiming its absence flip RED.

All pins run against the REAL tree — no mocks, no stubs.  The full
claim→verdict ledger lives in
``docs/audits/doc-claim-veracity-2026-10-15.md``.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _makefile_targets() -> set[str]:
    targets: set[str] = set()
    for makefile in ("Makefile", "Makefile.core"):
        text = (REPO_ROOT / makefile).read_text(encoding="utf-8")
        targets |= set(re.findall(r"^([a-zA-Z0-9_-]+):", text, re.M))
    return targets


# ── README / quickstart claims ──────────────────────────────────────────────


def test_readme_make_targets_exist():
    """Every `make <target>` the README tells a contributor to run must be
    a real Makefile/Makefile.core target."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    targets = _makefile_targets()
    missing = []
    for target in re.findall(r"`make ([a-z0-9-]+)`", readme):
        # `make setup` is named only as REMOVED — asserted separately.
        if target == "setup":
            continue
        if target not in targets:
            missing.append(target)
    assert not missing, (
        f"README advertises make target(s) that do not exist: {missing}"
    )


def test_readme_setup_removal_claim_is_true():
    """README claims the bare-metal `setup.sh` / `make setup` flow is
    removed — there must be no root setup.sh and no `setup` target."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "setup.sh" in readme
    assert "removed" in readme
    assert not (REPO_ROOT / "setup.sh").exists(), (
        "README claims setup.sh is removed, but it ships at the repo root"
    )
    assert "setup" not in _makefile_targets(), (
        "README claims `make setup` is removed, but the target exists"
    )


def test_quickstart_compose_services_exist():
    """The quickstart target boots postgres, four redis services, minio,
    api, worker, frontend, traefik — every service it names must exist
    in the compose file, and the redis count must really be 4."""
    quickstart = (REPO_ROOT / "Makefile.core").read_text(encoding="utf-8")
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    services = re.findall(
        r"postgres|redis-[a-z]+|minio|api-service|worker-service|frontend|traefik",
        quickstart,
    )
    for service in set(services):
        assert re.search(rf"^  {service}:", compose, re.M), (
            f"quickstart names compose service {service!r}, but "
            f"docker-compose.yml has no such service"
        )
    redis_services = sorted({s for s in services if s.startswith("redis-")})
    assert len(redis_services) == 4, (
        "README claims four redis services; quickstart boots "
        f"{redis_services}"
    )


def test_quickstart_dependency_files_exist():
    """The quickstart steps reference real scripts/commands: the .env
    generator, the shared/ mirror, the demo seed command."""
    quickstart = (REPO_ROOT / "Makefile.core").read_text(encoding="utf-8")
    assert "scripts/make_dev_env.py" in quickstart
    assert "frontend/scripts/sync-shared.sh" in quickstart
    assert "seed_demo_data" in quickstart
    for rel in (
        "scripts/make_dev_env.py",
        "frontend/scripts/sync-shared.sh",
        "hub/apps/core/management/commands/seed_demo_data.py",
    ):
        assert (REPO_ROOT / rel).is_file(), f"quickstart depends on {rel}"


def test_readme_port_claims_match_compose():
    """README ports — API :8000, UI :3000, traefik :80/:443, worker
    health :8092 — must match the compose default mappings."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "API `:8000`" in readme
    assert "UI `:3000`" in readme
    assert "`:80/:443`" in readme
    assert "`:8092`" in readme
    for mapping in (
        "${API_PORT:-8000}:8000",
        "${FRONTEND_PORT:-3000}:8080",
        "${WORKER_HEALTH_PORT:-8092}:8080",
        "${TRAEFIK_PORT:-80}:80",
        "${TRAEFIK_SECURE_PORT:-443}:443",
    ):
        assert mapping in compose, (
            f"README port claim has no compose mapping for {mapping!r}"
        )


# ── CI_CD_SUMMARY "6 workflows" liar ────────────────────────────────────────


def test_stale_workflow_count_summary_is_gone():
    """The 'Total Workflows: 6' summary shipped under .github/workflows/
    is deleted; no shipped workflow doc may carry the stale count."""
    liar = REPO_ROOT / ".github" / "workflows" / "CI_CD_SUMMARY.md"
    assert not liar.exists(), (
        "the stale CI_CD_SUMMARY.md ('Total Workflows: 6') must stay deleted "
        "(GATE-61 STUB-008)"
    )
    workflows_readme = (
        REPO_ROOT / ".github" / "workflows" / "README.md"
    ).read_text(encoding="utf-8")
    assert "Total Workflows: 6" not in workflows_readme


def test_no_code_references_the_deleted_summary():
    """After the deletion, no script/test may reference the deleted file
    by name (dead-reference hygiene, W12.1 class)."""
    offenders = []
    for rel in (
        "scripts/review_cicd_workflows.py",
        "tests/ci/test_cicd_pipeline_comprehensive_validation.py",
    ):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        if "CI_CD_SUMMARY.md" in text:
            offenders.append(rel)
    assert not offenders, f"dead references to CI_CD_SUMMARY.md in {offenders}"


# ── Reviewer checklist (P4 operationalized) ─────────────────────────────────


def test_reviewer_checklist_carries_the_p4_claim_rule():
    """The OSS reviewer checklist must carry the P4 rule: doc/contract
    claims must cite a test or gate that proves them."""
    checklist = (REPO_ROOT / "docs" / "OSS_CONTRIBUTION.md").read_text(
        encoding="utf-8"
    )
    assert "must cite a test or gate" in checklist, (
        "docs/OSS_CONTRIBUTION.md reviewer checklist must carry the P4 rule: "
        "claims must cite a test or gate that proves them"
    )


def test_readme_points_at_the_reviewer_checklist():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "OSS_CONTRIBUTION.md" in readme
    assert "reviewer checklist" in readme


# ── RLS request-path arming: no prose may bless its absence ─────────────────


def test_no_prose_claims_rls_arming_absent():
    """The W1.20 middleware arms RLS per request.  The original liar class
    ('tests re-documented to bless absent RLS middleware') must stay
    gone: no hub Python file may claim the arming middleware does not
    exist / is never armed."""
    false_patterns = (
        "RLS middleware does not exist",
        "RLS middleware doesn't exist",
        "no RLS middleware",
        "RLS is not armed",
        "RLS is never armed",
        "RLS arming does not exist",
    )
    offenders = []
    for path in REPO_ROOT.glob("hub/**/*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in false_patterns:
            if pattern.lower() in text.lower():
                offenders.append(
                    f"{path.relative_to(REPO_ROOT)}: {pattern!r}"
                )
    assert not offenders, (
        "prose claiming absent RLS request-path arming still present in:\n"
        + "\n".join(offenders)
    )


def test_rls_arming_machinery_exists():
    """The positive half of the same claim: the middleware, the master
    kill switch, and the paired-GUC pin all exist."""
    middleware = (
        REPO_ROOT / "hub" / "apps" / "auth" / "middleware.py"
    ).read_text(encoding="utf-8")
    settings = (REPO_ROOT / "hub" / "settings.py").read_text(encoding="utf-8")
    assert "class TenantScopingMiddleware" in middleware
    assert "SET LOCAL" in middleware
    assert (
        'RLS_REQUEST_PATH_ENABLED = env.bool("RLS_REQUEST_PATH_ENABLED",'
        " default=True)" in settings
    )
    assert (
        REPO_ROOT
        / "hub"
        / "apps"
        / "auth"
        / "tests"
        / "test_rls_request_path_arming.py"
    ).is_file()


# ── Ledger ──────────────────────────────────────────────────────────────────


def test_w128_veracity_ledger_exists():
    """The claim→verdict ledger for this pass must be committed (G10
    convention: the claude-veracity ledger)."""
    ledger = REPO_ROOT / "docs" / "audits" / "doc-claim-veracity-2026-10-15.md"
    assert ledger.is_file(), "the W12.8 claim→verdict ledger must be committed"
    text = ledger.read_text(encoding="utf-8")
    for marker in ("plan_defaults", "CI_CD_SUMMARY", "quickstart", "P4"):
        assert marker in text, f"ledger missing the {marker} claim row"
