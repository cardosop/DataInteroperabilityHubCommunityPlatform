"""
Phase 227 L10 — documentation coverage tests.

These tests guard the documentation surface that ships with Phase 227:

* Every doc that other docs link to actually exists at the referenced path
  (broken cross-references make the rollout package internally inconsistent
  and break the email/runbook workflow during the structureless-contract
  triage windows).
* Every Phase-227 error code emitted by production code is documented in
  the public error catalog, and every documented subcode is defined as a
  constant in :mod:`hub.apps.contracts.structural_floor`. This catches
  drift between the catalog and the runtime in either direction.
"""

import re
from pathlib import Path

from django.test import SimpleTestCase

from hub.apps.contracts import structural_floor

REPO_ROOT = Path(__file__).resolve().parents[4]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class Phase227DocsExistTest(SimpleTestCase):
    """Every Phase-227 doc referenced by other Phase-227 docs must exist."""

    REQUIRED_DOCS = [
        "CHANGELOG.md",
        "docs/CONTRACTS.md",
        "docs/ARCHITECTURE.md",
        "docs/mvpdocs/reference/error-codes.md",
        "docs/mvpdocs/use-cases/UC-AM-001.md",
        "docs/mvpdocs/journeys/JOURNEY-DE-001.md",
        "docs/migration-guides/structureless-contracts-deprecation.md",
        "docs/runbooks/structureless-contracts.md",
        "monitoring/grafana/dashboards/structureless-contract-rollout.json",
        "hub/apps/contracts/migrations/0023_migration_checkpoint.py",
        "hub/apps/contracts/migrations/0024_unrevert_structureless_assets.py",
        "hub/apps/notifications/templates/notifications/emails/asset_contract_structureless_pending.html",
    ]

    def test_phase_227_docs_present_on_disk(self):
        missing = [relpath for relpath in self.REQUIRED_DOCS if not (REPO_ROOT / relpath).exists()]
        self.assertEqual(
            missing,
            [],
            f"Missing Phase-227 doc(s) referenced by the rollout package: {missing}",
        )


class Phase227CrossReferencesResolveTest(SimpleTestCase):
    """Markdown links inside Phase-227 docs must point at files that exist.

    We only check the relative-path links that the rollout owns. External
    HTTP(S) links and anchors-only references (`#section`) are out of
    scope — those decay through unrelated changes.
    """

    LINK_RE = re.compile(r"\[[^\]]+\]\(([^)#\s]+)(?:#[^)]*)?\)")

    DOCS_TO_CHECK = [
        ("CHANGELOG.md", REPO_ROOT),
        ("docs/CONTRACTS.md", REPO_ROOT / "docs"),
        (
            "docs/migration-guides/structureless-contracts-deprecation.md",
            REPO_ROOT / "docs" / "migration-guides",
        ),
        ("docs/mvpdocs/reference/error-codes.md", REPO_ROOT / "docs" / "mvpdocs" / "reference"),
        ("docs/runbooks/structureless-contracts.md", REPO_ROOT / "docs" / "runbooks"),
    ]

    def _resolve(self, base: Path, link: str) -> Path:
        if link.startswith("/"):
            return REPO_ROOT / link.lstrip("/")
        return (base / link).resolve()

    def test_relative_links_resolve(self):
        broken = []
        for relpath, base in self.DOCS_TO_CHECK:
            text = _read(REPO_ROOT / relpath)
            for match in self.LINK_RE.finditer(text):
                target = match.group(1)
                if target.startswith(("http://", "https://", "mailto:", "tel:")):
                    continue
                if target.startswith("#"):
                    continue
                resolved = self._resolve(base, target)
                if not resolved.exists():
                    broken.append((relpath, target, str(resolved)))
        self.assertEqual(
            broken,
            [],
            f"Phase-227 docs contain broken relative links: {broken}",
        )


class Phase227ErrorCodeCatalogConsistencyTest(SimpleTestCase):
    """Documented subcodes must match the runtime constants 1:1."""

    def setUp(self):
        self.catalog = _read(REPO_ROOT / "docs" / "mvpdocs" / "reference" / "error-codes.md")
        self.contracts_doc = _read(REPO_ROOT / "docs" / "CONTRACTS.md")
        self.runtime_subcodes = {
            structural_floor.SUBCODE_ODPS_NO_PORTS,
            structural_floor.SUBCODE_ODCS_NO_SCHEMA,
            structural_floor.SUBCODE_CYCLIC_PORTS,
            structural_floor.SUBCODE_GENERIC,
        }

    def test_every_runtime_subcode_in_catalog(self):
        missing = [s for s in self.runtime_subcodes if s not in self.catalog]
        self.assertEqual(
            missing,
            [],
            f"Subcodes emitted at runtime but not documented in error-codes.md: {missing}",
        )

    def test_every_runtime_subcode_in_contracts_doc(self):
        missing = [s for s in self.runtime_subcodes if s not in self.contracts_doc]
        self.assertEqual(
            missing,
            [],
            f"Subcodes emitted at runtime but not documented in CONTRACTS.md: {missing}",
        )

    def test_catalog_subcodes_match_runtime(self):
        """Catalog must not document subcodes that no runtime path emits."""
        # Every uppercase identifier in the catalog that starts with
        # ``STRUCTURELESS_`` must be either ``STRUCTURELESS_CONTRACT`` (the
        # top-level error code) or one of the runtime subcodes.
        documented = set(re.findall(r"STRUCTURELESS_[A-Z_]+", self.catalog))
        documented.discard("STRUCTURELESS_CONTRACT")  # top-level code, not a subcode
        unknown = documented - self.runtime_subcodes
        self.assertEqual(
            unknown,
            set(),
            f"Catalog documents STRUCTURELESS_* identifiers with no runtime emitter: {unknown}",
        )

    def test_top_level_error_code_documented(self):
        """The top-level STRUCTURELESS_CONTRACT code must be in the catalog."""
        self.assertIn("STRUCTURELESS_CONTRACT", self.catalog)

    def test_etag_concurrency_code_documented(self):
        """PRECONDITION_FAILED is the wire code for ETag/If-Match drift."""
        self.assertIn("PRECONDITION_FAILED", self.catalog)

    def test_payload_too_large_code_documented(self):
        """PAYLOAD_TOO_LARGE is the wire code for the 2 MB body cap."""
        self.assertIn("PAYLOAD_TOO_LARGE", self.catalog)

    def test_schema_too_deep_code_documented(self):
        """SCHEMA_TOO_DEEP is the wire code for nested-properties walker overflow."""
        self.assertIn("SCHEMA_TOO_DEEP", self.catalog)


class Phase227DocumentedCodesAreEmittedAtRuntimeTest(SimpleTestCase):
    """Audit-3 follow-up: every top-level Phase-227 wire code in the
    error catalog must have at least one runtime emit site.

    Pre-L10 audit, ``INVALID_YAML`` was documented in the catalog and
    in the ``@extend_schema`` OpenAPI annotation but no production
    path actually raised it — every YAML parse error was bucketed as
    ``NORMALIZATION_FAILED``. Customers branching on
    ``error.code == "INVALID_YAML"`` would never hit the branch. This
    test prevents that drift from recurring: any future code added to
    the catalog table must also have a corresponding runtime emit
    site (greppable by literal string), and any documented code whose
    runtime emitter is removed during refactoring fails the test.
    """

    PHASE_227_TOP_LEVEL_CODES = [
        "STRUCTURELESS_CONTRACT",
        "VALIDATION_ERROR",
        "NORMALIZATION_FAILED",
        "SCHEMA_TOO_DEEP",
        "INVALID_YAML",
        "PRECONDITION_FAILED",
        "PAYLOAD_TOO_LARGE",
    ]

    SOURCE_DIRS = [
        REPO_ROOT / "hub" / "apps" / "contracts",
        REPO_ROOT / "hub" / "apps" / "marketplace",
        REPO_ROOT / "hub" / "apps" / "assets",
    ]

    def _greppable_emit_sites(self, code: str) -> list:
        """Return relative paths of source files (excluding tests +
        backups) that mention the literal code string. We require the
        code to appear *somewhere* in a non-test source file — the
        narrowest universal predicate that catches the drift without
        false positives from docstrings or comments."""
        hits = []
        for source_dir in self.SOURCE_DIRS:
            if not source_dir.exists():
                continue
            for path in source_dir.rglob("*.py"):
                rel = path.relative_to(REPO_ROOT).as_posix()
                # Exclude tests, backups, and migration files (data
                # migrations sometimes carry historical code names).
                if "/tests/" in rel or rel.endswith(".backup"):
                    continue
                if "/migrations/" in rel:
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except Exception:
                    continue
                if code in text:
                    hits.append(rel)
        return hits

    def test_every_documented_code_has_runtime_emit_site(self):
        missing = []
        for code in self.PHASE_227_TOP_LEVEL_CODES:
            sites = self._greppable_emit_sites(code)
            if not sites:
                missing.append(code)
        self.assertEqual(
            missing,
            [],
            "Documented Phase-227 wire codes with NO runtime emit site "
            "in hub/apps/{contracts,marketplace,assets}/*.py "
            f"(excluding tests/migrations): {missing}. "
            "Every code documented in error-codes.md must be raised by "
            "at least one production path — otherwise SDK consumers "
            "branching on the code never hit the branch.",
        )


class Phase227RunbookHeadingsPresentTest(SimpleTestCase):
    """Spot-check structural sections of the operator runbook.

    The doc is referenced from the heads-up email template (Wave 0) and
    from CONTRACTS.md / migration guide / CHANGELOG. Operators land on
    these section anchors during a rejection incident — if they move, the
    cross-referenced links break silently.
    """

    def setUp(self):
        self.runbook = _read(REPO_ROOT / "docs" / "runbooks" / "structureless-contracts.md")

    def test_runbook_mentions_phase_227(self):
        self.assertIn("Phase 227", self.runbook)

    def test_runbook_documents_renormalize_command(self):
        self.assertIn("renormalize_contracts", self.runbook)

    def test_runbook_documents_apply_asset_revert_flag(self):
        self.assertIn("--apply-asset-revert", self.runbook)
