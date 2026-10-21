"""W9.3 (oss-release-remediation) — community docs + CLAUDE.md veracity pins.

Two contracts, both TDD with the REAL tree (no mocks):

1. **Community docs** — CODE_OF_CONDUCT.md, GOVERNANCE.md (with the
   maintenance model: release cadence, support matrix, OSS
   security-update SLA), and issue templates for bugs + features must
   exist and be wired into the contributor surface.
2. **CLAUDE.md veracity (G10)** — every named claim is checked against
   the code it describes: the DRF-3.16 throttled() claim (the known
   liar — DRF 3.16.1 RETAINS the hook; the repo's `_on_throttled`
   pattern and the two LIVE view overrides coexist), the business-rules
   chain table (vs the real ``@register_chain`` registrations), the RLS
   arming prose (vs the middleware/settings), the
   ENFORCE_JWT_SCOPES settings comment (W7.5), and the 274.16.13
   retraction.  The full claim→verification ledger lives in
   docs/audits/claude-veracity-2026-10-14.md.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CLAUDE = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")

# ── 1. community docs ──────────────────────────────────────────────────────


def test_code_of_conduct_exists():
    coc = REPO_ROOT / "CODE_OF_CONDUCT.md"
    assert coc.is_file(), "CODE_OF_CONDUCT.md must exist"
    text = coc.read_text(encoding="utf-8")
    assert "Contributor Covenant" in text
    assert "Enforcement" in text


def test_governance_and_maintenance_model_exist():
    gov = REPO_ROOT / "GOVERNANCE.md"
    assert gov.is_file(), "GOVERNANCE.md must exist"
    text = gov.read_text(encoding="utf-8")
    # The maintenance model section: release cadence + support matrix +
    # OSS security-update SLA.
    for marker in ("Release cadence", "Support matrix", "Security-update SLA"):
        assert (
            marker.lower() in text.lower()
        ), f"GOVERNANCE.md missing maintenance-model marker: {marker}"


def test_issue_templates_exist_and_are_typed():
    templates = REPO_ROOT / ".github" / "ISSUE_TEMPLATE"
    for name in ("bug_report.yml", "feature_request.yml"):
        path = templates / name
        assert path.is_file(), f".github/ISSUE_TEMPLATE/{name} must exist"
        text = path.read_text(encoding="utf-8")
        assert "name:" in text
        assert "description:" in text
        assert "labels:" in text


def test_contributor_surface_references_the_new_docs():
    contributing = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "CODE_OF_CONDUCT" in contributing
    assert "GOVERNANCE" in contributing


# ── 2. CLAUDE.md veracity (G10) ────────────────────────────────────────────


def test_drf_316_throttled_claim_is_true():
    """The named liar: DRF 3.16 did NOT remove the throttled() hook.
    DRF 3.16.1 retains it (APIView.check_throttles calls it; the base
    raises Throttled) — verified against the installed source this
    session.  The repo's `_on_throttled` pattern is the chosen
    single-point audit mechanism; the two view-level `throttled()`
    overrides are LIVE and must raise."""
    assert "DRF 3.16 REMOVED the" not in CLAUDE
    assert "throttled() override is dead code" not in CLAUDE
    assert "retains the" in CLAUDE.lower()
    assert "throttled()" in CLAUDE.lower()
    # The mechanism-level facts the corrected claim cites:
    requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert re.search(r"djangorestframework==3\.16\.[0-9]+", requirements)
    throttles = (REPO_ROOT / "hub" / "apps" / "search" / "throttles.py").read_text()
    assert "def _on_throttled" in throttles
    for view, cls, terminal in (
        # graphql_ld: audit-emitting override that raises directly.
        ("hub/apps/graphql_ld/views.py", "def throttled", "raise"),
        # search: dispatcher forwarding to per-throttle hooks, then
        # super().throttled() — the DRF base — which raises Throttled.
        ("hub/apps/search/views.py", "def throttled", "super().throttled"),
    ):
        text = (REPO_ROOT / view).read_text(encoding="utf-8")
        assert cls in text, f"{view}: the live throttled() override must exist"
        idx = text.rfind(cls)
        assert (
            terminal in text[idx : idx + 2500]
        ), f"{view}: the throttled() override must end in {terminal!r}"


def test_no_false_drf_claim_lingers_anywhere():
    """The false 'hook was removed' claim must be gone from EVERY file —
    docstrings, comments, and test prose alike."""
    false_patterns = (
        "throttled() override hook was removed",
        "DRF 3.16 removed the throttled",
        "throttled() override is dead",
    )
    offenders = []
    for path in REPO_ROOT.glob("hub/apps/**/*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in false_patterns:
            if pattern in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {pattern!r}")
    assert not offenders, "false DRF claim still present in:\n" + "\n".join(offenders)


def test_chain_table_matches_registered_chains():
    """Every chain name in the CLAUDE.md table must be a real
    @register_chain registration (source-level, CI-safe)."""
    table_names = set(re.findall(r"`([a-z][a-z0-9_]*\.[a-z][a-z0-9_.]*)`\|", CLAUDE))
    registered: set[str] = set()
    for chains_py in list(REPO_ROOT.glob("hub/apps/**/chains.py")) + list(
        REPO_ROOT.glob("hub/apps/**/business_rules/**/*.py")
    ):
        registered |= set(
            re.findall(r'register_chain\("([a-z][a-z0-9_.]+)"\)', chains_py.read_text())
        )
    missing = table_names - registered
    assert not missing, f"CLAUDE.md chain table names not registered: {sorted(missing)}"
    assert {
        "contract.publish",
        "asset.activate",
        "governance.approval.advance",
    } <= registered


def test_rls_arming_prose_matches_the_code():
    settings = (REPO_ROOT / "hub" / "settings.py").read_text(encoding="utf-8")
    middleware = (REPO_ROOT / "hub" / "apps" / "auth" / "middleware.py").read_text()
    assert (
        'RLS_REQUEST_PATH_ENABLED = env.bool("RLS_REQUEST_PATH_ENABLED", default=True)'
        in settings
    )
    assert "SET LOCAL" in middleware
    assert "transaction.atomic" in middleware
    assert "Transaction-local GUCs are mandatory" in CLAUDE
    assert "fails closed" in CLAUDE
    assert (REPO_ROOT / "hub" / "apps" / "auth" / "db_aliases.py").is_file()
    assert (
        REPO_ROOT / "hub" / "apps" / "auth" / "tests" / "test_rls_guc_settings_sync.py"
    ).is_file()


def test_enforce_jwt_scopes_settings_comment_is_current():
    settings = (REPO_ROOT / "hub" / "settings.py").read_text(encoding="utf-8")
    assert 'env.bool("ENFORCE_JWT_SCOPES", default=True)' in settings
    assert "W7.5" in settings.split("ENFORCE_JWT_SCOPES")[0][-1200:]


def test_retracted_per_tenant_chain_claim_stays_retracted():
    assert "274.16.13) — RETRACTED" in CLAUDE
    assert "there is no per-tenant chain switch" in CLAUDE


def test_veracity_ledger_exists():
    ledger = REPO_ROOT / "docs" / "audits" / "claude-veracity-2026-10-14.md"
    assert ledger.is_file(), "the claim→verification ledger must be committed"
    text = ledger.read_text(encoding="utf-8")
    assert "DRF 3.16" in text
    assert "chain table" in text.lower()
    assert "RLS request-path arming" in text
