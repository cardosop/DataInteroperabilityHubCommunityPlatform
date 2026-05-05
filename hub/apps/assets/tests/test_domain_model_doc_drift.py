"""
Phase 250.5.D.1 (closes Gap 6) — regression test pinning the
Asset entity documentation in
[InputDocs/Domain_Model.md](../../../../InputDocs/Domain_Model.md).

Background
----------
The original Phase 0 audit (Gap 6) flagged that
``Asset.source_type`` and ``Asset.data_strategy`` are absent from
the Domain Model spec — the model has shipped these fields since
Phase 230 (federated marketplace) but the spec doc never
documented them, leaving SDK / API consumers + new engineers
without a single source of truth on what the values mean and how
they affect the activation gate.

Phase 250.5.D.1 amends the Domain Model with a dedicated Asset
Entity section containing:

* ``source_type`` field with enum values ``HUB_NATIVE`` /
  ``FEDERATED`` and the activation-gate effect (FEDERATED
  requires ``Tenant.federated_import_enabled=True`` per
  ADR-AST-002 / D250.3).

* ``data_strategy`` field with enum values ``METADATA_ONLY`` /
  ``DOWNLOAD_SELECTIVE`` / ``DOWNLOAD_ALL`` and the activation-
  gate effect (METADATA_ONLY skips DQ but mandates compliance
  per D250.3 / D250.16).

This test is a **doc-content regression pin**. It runs against
the actual file (no fixtures, no parsing of source code) so a
future doc-cleanup that accidentally removes these fields fails
the test.

Why a test instead of relying on review?
----------------------------------------
The original Gap 6 audit found this drift only after several
months of code shipping ahead of the spec. A regression test
catches the drift at PR time (every CI run) instead of on the
next quarterly audit.

TDD doctrine
------------
* Real file read against the real ``InputDocs/Domain_Model.md``
  path. No mocks; no in-memory fixtures.
* The test asserts presence of canonical strings (the enum
  values + key phrases) so prose-level rephrasing is permitted
  but value-level drift is caught.
* If the file is missing, the test fails with a clear message
  pointing at the expected path.
"""
from __future__ import annotations

from pathlib import Path

import pytest


# Canonical project root — three parents up from this test file:
# hub/apps/assets/tests/test_domain_model_doc_drift.py
#  -> hub/apps/assets/tests/  (parents[0])
#  -> hub/apps/assets/        (parents[1])
#  -> hub/apps/               (parents[2])
#  -> hub/                    (parents[3])
#  -> <repo root>             (parents[4])
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DOMAIN_MODEL = _REPO_ROOT / "InputDocs" / "Domain_Model.md"


@pytest.fixture(scope="module")
def domain_model_text() -> str:
    if not _DOMAIN_MODEL.exists():
        pytest.fail(
            f"InputDocs/Domain_Model.md missing at {_DOMAIN_MODEL}. "
            f"Phase 250.5.D.1 requires this file to exist."
        )
    return _DOMAIN_MODEL.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 250.5.D.1 — Asset Entity section exists
# ---------------------------------------------------------------------------


class TestDomainModelAssetSection:
    """The Domain Model MUST contain a dedicated Asset Entity
    section. Pre-Phase-250.5.D the document had only "Asset
    Activation Rules" embedded inside section 2.2 (Contract
    Entity); the new section makes Asset a first-class entity."""

    def test_asset_entity_heading_present(self, domain_model_text):
        """Some heading naming the Asset entity exists."""
        # Permit either ``### N.M Asset Entity`` (canonical
        # phrasing) OR ``### Asset Entity`` (level-only). The
        # exact section number depends on document layout.
        assert "Asset Entity" in domain_model_text, (
            "Domain_Model.md MUST contain an 'Asset Entity' "
            "heading per Phase 250.5.D.1. Existing 'Asset "
            "Activation Rules' fragment is insufficient — the "
            "audit recommendation is a dedicated entity section."
        )


# ---------------------------------------------------------------------------
# 250.5.D.1 — source_type field documented with valid values
# ---------------------------------------------------------------------------


class TestSourceTypeFieldDocumented:
    """``Asset.source_type`` MUST be documented with both enum
    values AND the activation-gate effect."""

    def test_source_type_field_named(self, domain_model_text):
        assert "source_type" in domain_model_text, (
            "source_type field MUST be named in Domain_Model.md."
        )

    def test_source_type_enum_HUB_NATIVE(self, domain_model_text):
        assert "HUB_NATIVE" in domain_model_text

    def test_source_type_enum_FEDERATED(self, domain_model_text):
        assert "FEDERATED" in domain_model_text

    def test_source_type_activation_gate_effect_documented(
        self, domain_model_text,
    ):
        """The activation-gate semantics for FEDERATED — that
        the tenant flag ``federated_import_enabled`` (D250.3)
        gates whether the asset can be activated — MUST be
        documented. Pin the canonical phrase that names the
        flag so a doc rewrite that drops it fails the test."""
        assert "federated_import_enabled" in domain_model_text, (
            "The Tenant.federated_import_enabled flag (D250.3 / "
            "ADR-AST-002) MUST be referenced in the Asset "
            "Entity section so SDK / API consumers know that "
            "FEDERATED requires this opt-in."
        )


# ---------------------------------------------------------------------------
# 250.5.D.1 — data_strategy field documented with valid values
# ---------------------------------------------------------------------------


class TestDataStrategyFieldDocumented:
    """``Asset.data_strategy`` MUST be documented with all three
    enum values AND the activation-gate effect."""

    def test_data_strategy_field_named(self, domain_model_text):
        assert "data_strategy" in domain_model_text

    def test_data_strategy_enum_METADATA_ONLY(self, domain_model_text):
        assert "METADATA_ONLY" in domain_model_text

    def test_data_strategy_enum_DOWNLOAD_SELECTIVE(self, domain_model_text):
        assert "DOWNLOAD_SELECTIVE" in domain_model_text

    def test_data_strategy_enum_DOWNLOAD_ALL(self, domain_model_text):
        assert "DOWNLOAD_ALL" in domain_model_text

    def test_metadata_only_dq_skip_effect_documented(
        self, domain_model_text,
    ):
        """The "DQ skipped for METADATA_ONLY" rule (D250.3 /
        ADR-AST-002 decision #3) MUST be documented in the
        activation-gate section. Pin the canonical phrase that
        couples the two concepts so a rephrasing that drops the
        coupling fails the test."""
        # We accept either uppercase or mixed-case "DQ" /
        # "data quality" since the spec sometimes spells it out.
        text_lower = domain_model_text.lower()
        # Both terms must appear within proximity. The simplest
        # invariant: the substring ``METADATA_ONLY`` is followed
        # within 500 chars by either "DQ" or "data quality" with
        # a "skip" / "skipped" / "not run" qualifier.
        idx = domain_model_text.find("METADATA_ONLY")
        assert idx >= 0
        window = domain_model_text[idx:idx + 800].lower()
        has_dq_term = "dq" in window or "data quality" in window
        has_skip_term = (
            "skip" in window or "skipped" in window
            or "not run" in window or "not required" in window
        )
        assert has_dq_term and has_skip_term, (
            "The activation-gate effect for METADATA_ONLY (DQ "
            "skipped per D250.3) MUST be documented within ~800 "
            "chars of the METADATA_ONLY mention. Got window: "
            f"{window[:200]!r}..."
        )

    def test_compliance_mandatory_for_federated_documented(
        self, domain_model_text,
    ):
        """The "compliance MUST run on every federated import"
        rule (D250.3 / ADR-AST-002 decision #2) MUST be in the
        section so a reader doesn't misread "DQ skipped" as
        "all gates skipped"."""
        text_lower = domain_model_text.lower()
        # Window: find "FEDERATED" and check for "compliance"
        # within 800 chars after.
        idx = domain_model_text.find("FEDERATED")
        assert idx >= 0
        window = domain_model_text[idx:idx + 1200].lower()
        assert "compliance" in window, (
            "The mandatory-compliance rule for FEDERATED imports "
            "MUST be documented near the FEDERATED enum value so "
            "readers don't conflate it with DQ-skip."
        )
