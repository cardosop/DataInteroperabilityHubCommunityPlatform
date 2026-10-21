"""TDD suite for Phase 9 task 9.5 — the docs reconciliation pins.

Pins the FOUR doc surfaces' contracts against the LANDED reality (the
code, not the prose): the marketplace connector doc's PULL-only +
``host``/``token`` shape, the REAL_MARKETPLACE_E2E SKIP→PASS retirement,
the operator-facing control-plane user guide's P0-P9 surface map, and
the egress + credential-rotation runbook (OIDC trust setup, the egress
allowlist, the rotation cadence). Every pin is a pure on-disk assertion
— no mocks, no network, no Django — so the suite runs in any pytest
context (the tree's full contract and CI alike).

The honesty pin: the runbook's SKIP retirement must NOT fabricate a
green run — the row carries the migration marker + the evidence
procedure, and a concrete PASS date is stamped only by the armed
nightly's report.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS = REPO_ROOT / "docs"

MARKETPLACE_DOC = DOCS / "MARKETPLACE_AND_CONNECTORS.md"
E2E_RUNBOOK = DOCS / "runbooks" / "REAL_MARKETPLACE_E2E.md"
USER_GUIDE = DOCS / "user-guides" / "databricks-control-plane.md"
EGRESS_ROTATION_RUNBOOK = DOCS / "runbooks" / "RB-SEC-003-databricks-egress-credential-rotation.md"
SEC001 = DOCS / "runbooks" / "RB-SEC-001-credential-rotation.md"
RUNBOOK_INDEX = DOCS / "runbooks" / "INDEX.md"
WORKFLOW_NAME = "databricks-e2e-nightly.yml"

STALE_KEYS = ("workspace_url", "personal_access_token")


def _read(path: Path) -> str:
    if not path.is_file():
        pytest.fail(f"RED: {path.relative_to(REPO_ROOT)} does not exist")
    return path.read_text()


def _databricks_section(doc: str) -> str:
    """The DATABRICKS vendor-guide section (up to the next guide header)."""
    marker = "\n### DATABRICKS\n"
    idx = doc.find(marker)
    assert idx != -1, "### DATABRICKS section not found"
    rest = doc[idx + len(marker) :]
    end = re.search(r"\n### DATARADE", rest)
    return rest[: end.start()] if end else rest


def _table_row(text: str, first_cell: str) -> str:
    """The markdown table row whose first cell is ``first_cell``."""
    for line in text.splitlines():
        if line.startswith(f"| {first_cell}"):
            return line
    pytest.fail(f"table row {first_cell!r} not found")
    raise AssertionError  # pragma: no cover — pytest.fail raises


def _local_references(text: str, source: Path) -> list[tuple[Path, str]]:
    """Repo-local references: markdown links + repo-path code spans,
    each tagged with the file that carries it (for file-relative resolution)."""
    refs: list[tuple[Path, str]] = []
    for link in re.findall(r"\]\(([^)#]+)", text):
        if not link.startswith(("http://", "https://", "mailto:")):
            refs.append((source, link))
    refs += [
        (source, ref)
        for ref in re.findall(r"`((?:hub|helm|scripts|tests|docs|\.github)/[^`\s]+)`", text)
    ]
    return refs


def _resolve(ref: str, source_file: Path) -> Path:
    """Resolve a reference: repo-path code spans anchor at the repo root;
    markdown links anchor at the referencing file's directory."""
    if ref.startswith(("hub/", "helm/", "scripts/", "tests/", ".github/", "docs/")):
        return REPO_ROOT / ref
    return (source_file.parent / ref).resolve()


class TestMarketplaceConnectorDoc:
    """`docs/MARKETPLACE_AND_CONNECTORS.md` — the Databricks guide section
    must match the LANDED connector: harvest-only (PULL) with the
    required `host`/`token` key shape."""

    def test_databricks_section_declares_pull_only(self):
        section = _databricks_section(_read(MARKETPLACE_DOC))
        assert "PULL" in section, "the section must declare the PULL direction"
        assert "PUSH" not in section, (
            "the connector is harvest-only — no PUSH claims may remain "
            "(hub/apps/integrations/connectors/databricks_connector.py "
            "get_sync_directions() returns [SyncDirection.PULL])"
        )

    def test_databricks_section_required_keys_are_host_and_token(self):
        section = _databricks_section(_read(MARKETPLACE_DOC))
        for key in ("`host`", "`token`"):
            assert key in section, f"the required config key {key} must be documented"
        for stale in STALE_KEYS:
            assert stale not in section, f"the stale key {stale!r} must be gone"

    def test_no_stale_credential_keys_anywhere_in_the_doc(self):
        doc = _read(MARKETPLACE_DOC)
        for stale in STALE_KEYS:
            assert stale not in doc, (
                f"{stale!r} is the retired key shape — the landed connector reads host/token only"
            )

    def test_no_dead_databricks_guide_link(self):
        doc = _read(MARKETPLACE_DOC)
        assert "MARKETPLACE_DATABRICKS_GUIDE.md" not in doc, (
            "the vendor-guide link was dead (the file lives under "
            "deprecated-doc/) — the doc must reference the control-plane "
            "user guide instead"
        )
        assert "user-guides/databricks-control-plane.md" in doc


class TestMarketplaceE2ERunbook:
    """`docs/runbooks/REAL_MARKETPLACE_E2E.md` — the Databricks SKIP record
    is retired: the validation-table row and the skip-reasons row now
    point at the landed nightly workflow, and the per-provider section is
    definitively PULL-only."""

    def test_databricks_row_retires_the_skip(self):
        row = _table_row(_read(E2E_RUNBOOK), "Databricks")
        assert "Credentials unavailable" not in row, (
            "the SKIP record is retired — the nightly workflow is the Databricks E2E mechanism"
        )
        assert WORKFLOW_NAME in row, "the row must reference the nightly workflow"

    def test_databricks_row_does_not_fabricate_a_green_run(self):
        row = _table_row(_read(E2E_RUNBOOK), "Databricks")
        assert not re.search(r"20\d\d-\d\d-\d\d", row), (
            "no green-run date may be claimed — the PASS stamp is the armed "
            "nightly's outcome, recorded by the operator with the report "
            "evidence (never fabricated in the reconciliation)"
        )
        assert "SKIP → PASS" in row, "the row carries the migration marker"

    def test_databricks_section_is_definitive_pull_only(self):
        text = _read(E2E_RUNBOOK)
        marker = "### Databricks Marketplace\n"
        idx = text.find(marker)
        assert idx != -1, "Databricks section not found"
        section = text[idx : text.find("\n### ", idx + len(marker))]
        assert "PULL only" in section, (
            "the section must state the definitive direction (the hedge "
            "'may raise NotImplementedError' is retired — the connector "
            "raises it, always)"
        )
        assert "`host`" in section
        assert "`token`" in section
        assert WORKFLOW_NAME in section, (
            "the per-provider section must point at the nightly workflow as the E2E path"
        )

    def test_skip_reasons_table_points_at_the_nightly(self):
        row = _table_row(_read(E2E_RUNBOOK), "**Databricks**")
        assert "No management command support" not in row, (
            "the retired skip reason — the nightly workflow IS the E2E path"
        )
        assert WORKFLOW_NAME in row


class TestControlPlaneUserGuide:
    """`docs/user-guides/databricks-control-plane.md` — the operator-facing
    P0-P9 guide, keeping the BYO App-connection + GCP fallback content."""

    def test_guide_covers_the_phase_surfaces(self):
        guide = _read(USER_GUIDE)
        for phase in ("P0 ", "P0b", "P1 ", "P2 ", "P3 ", "P4 ", "P5 ", "P6 ", "P7 ", "P8 ", "P9 "):
            assert phase in guide, f"the {phase.strip()} surface must be covered"
        for retained in ("App connection", "GCP fallback"):
            assert retained in guide, f"the {retained} content must be retained"

    def test_guide_links_the_operations_runbooks(self):
        guide = _read(USER_GUIDE)
        assert "RB-SEC-003-databricks-egress-credential-rotation.md" in guide
        assert "REAL_MARKETPLACE_E2E.md" in guide


class TestEgressCredentialRotationRunbook:
    """`docs/runbooks/RB-SEC-003-*.md` — the egress allowlist, the OIDC
    trust setup, and the rotation cadence for the nightly + BYO estate."""

    def test_runbook_documents_the_oidc_trust_setup(self):
        text = _read(EGRESS_ROTATION_RUNBOOK)
        assert "OIDC" in text
        assert WORKFLOW_NAME in text, "the runbook must reference the workflow"
        assert "databricks-e2e" in text, "the GitHub Environment must be named"
        for secret in ("DATABRICKS_E2E_ACCOUNT_ID", "DATABRICKS_E2E_ACCOUNT_TOKEN"):
            assert secret in text, f"the {secret} secret must be documented"

    def test_runbook_documents_the_egress_allowlist(self):
        text = _read(EGRESS_ROTATION_RUNBOOK)
        for suffix in (
            ".cloud.databricks.com",
            ".azuredatabricks.net",
            ".gcp.databricks.com",
            ".databricks.us",
        ):
            assert suffix in text, f"the egress suffix {suffix} must be documented"
        assert "helm/templates/networkpolicy/allow-warehouse-egress.yaml" in text
        assert "hub/apps/databricks_admin/validation.py" in text

    def test_runbook_documents_the_rotation_cadence(self):
        text = _read(EGRESS_ROTATION_RUNBOOK)
        assert "/rotate/" in text, "the tenant-credential rotate endpoint must be documented"
        assert "90 days" in text, "the rotation cadence must be stated"


class TestRunbookRegistrationAndCrossLinks:
    """The index registers the new runbook; RB-SEC-001's Databricks row
    uses the landed key shape and cross-links the new runbook."""

    def test_index_registers_the_new_runbook(self):
        index = _read(RUNBOOK_INDEX)
        assert "RB-SEC-003-databricks-egress-credential-rotation.md" in index

    def test_sec001_databricks_row_uses_the_landed_key_shape(self):
        text = _read(SEC001)
        marker = "### Databricks\n"
        idx = text.find(marker)
        assert idx != -1, "RB-SEC-001 Databricks section not found"
        section = text[idx : text.find("\n### ", idx + len(marker))]
        assert "personal_access_token" not in section, (
            "the warehouse credential config stores `token` (+ `host`) — "
            "the retired key name must go"
        )
        assert "`token`" in section
        assert "`host`" in section
        assert "RB-SEC-003" in section, (
            "the Databricks section must cross-link the egress + OIDC rotation runbook"
        )


class TestReconciledDocsReferenceOnlyExistingSurfaces:
    """The spec's closing clause: the new/changed docs reference only
    surfaces that exist on disk (dead links fail the run)."""

    def test_all_local_references_resolve(self):
        # The reconciliation delta only — the Databricks section of the
        # marketplace doc, the runbook's Databricks rows/section (the file
        # carries pre-existing dead links outside the 9.5 scope), and the
        # two new/rewritten doc surfaces.
        section = _databricks_section(_read(MARKETPLACE_DOC))
        runbook = _read(E2E_RUNBOOK)
        marker = "### Databricks Marketplace\n"
        idx = runbook.find(marker)
        assert idx != -1, "Databricks section not found"
        runbook_delta = (
            runbook[idx : runbook.find("\n### ", idx + len(marker))]
            + "\n"
            + _table_row(runbook, "Databricks")
            + "\n"
            + _table_row(runbook, "**Databricks**")
        )
        refs = (
            _local_references(section, MARKETPLACE_DOC)
            + _local_references(runbook_delta, E2E_RUNBOOK)
            + _local_references(_read(USER_GUIDE), USER_GUIDE)
            + _local_references(_read(EGRESS_ROTATION_RUNBOOK), EGRESS_ROTATION_RUNBOOK)
        )
        assert refs, "the reconciliation must carry at least one local reference"
        missing = [ref for source, ref in refs if not _resolve(ref, source).exists()]
        assert missing == [], f"dead references in the reconciled docs: {missing}"


class TestDocsMirrorSync:
    """The tracked docs/docs mirror must stay byte-identical for the files
    the reconciliation touches (the repo's mirror discipline)."""

    MIRRORED = (
        "MARKETPLACE_AND_CONNECTORS.md",
        "runbooks/REAL_MARKETPLACE_E2E.md",
        "runbooks/RB-SEC-001-credential-rotation.md",
        "runbooks/RB-SEC-003-databricks-egress-credential-rotation.md",
        "runbooks/INDEX.md",
    )

    @pytest.mark.parametrize("relative", MIRRORED)
    def test_mirror_copy_is_identical(self, relative: str):
        canonical = DOCS / relative
        mirror = DOCS / "docs" / relative
        assert mirror.is_file(), f"the mirror copy {mirror} is missing"
        assert mirror.read_bytes() == canonical.read_bytes(), (
            f"the mirror copy of {relative} diverged — sync it"
        )
