"""
Phase 260.2.I.1 + 260.2.I.3 — structural tests for STRIDE threat model + pen-test
scope docs (datasets/files).

TDD / documentation contract: prevents accidental deletion of STRIDE sections,
sign-off block, or P2 exit-criterion language without CI failure.

Mirrors the pattern in ``hub/tests/test_security_docs_phase_250_5_e.py``.
"""

from __future__ import annotations

import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
THREAT_MODEL_PATH = REPO_ROOT / "docs" / "security" / "threat-model-datasets-files.md"
PEN_TEST_SCOPE_PATH = REPO_ROOT / "docs" / "security" / "pen-test-scope-260.md"


class TestThreatModelDatasetsFilesStructure:
    """260.2.I.1 — STRIDE threat model."""

    def test_threat_model_doc_exists(self):
        assert THREAT_MODEL_PATH.exists(), (
            f"Phase 260.2.I.1 deliverable missing: {THREAT_MODEL_PATH}"
        )

    @pytest.mark.parametrize(
        "section",
        [
            "S — Spoofing",
            "T — Tampering",
            "R — Repudiation",
            "I — Information",
            "D — Denial of service",
            "E — Elevation of privilege",
        ],
    )
    def test_threat_model_has_stride_section(self, section):
        body = THREAT_MODEL_PATH.read_text(encoding="utf-8")
        assert section.lower() in body.lower(), (
            f"STRIDE section '{section}' missing from {THREAT_MODEL_PATH.name}"
        )

    def test_threat_model_has_system_under_threat_section(self):
        body = THREAT_MODEL_PATH.read_text(encoding="utf-8")
        assert "## System under threat" in body or "# System under threat" in body
        assert "Endpoint" in body
        assert "Code path" in body
        assert "Capability flag" in body or "Trust boundaries" in body

    def test_threat_model_pinned_backend_tests_exist(self):
        """Pinned-by rows MUST reference modules that exist (doc–code contract)."""
        repo = REPO_ROOT
        must_exist = [
            "hub/apps/files/tests/security/test_idor.py",
            "hub/apps/files/tests/test_file_metadata_view_audit.py",
            "hub/apps/files/tests/test_file_init_rate_limits.py",
            "hub/apps/files/tests/test_abandoned_multipart_cleanup.py",
            "hub/apps/files/tests/test_file_size_limits.py",
            "hub/apps/datasets/tests/test_dataset_malware_gate.py",
        ]
        missing = [rel for rel in must_exist if not (repo / rel).is_file()]
        assert not missing, (
            "Threat model references missing test modules (fix Pinned by paths): "
            + ", ".join(missing)
        )

    def test_threat_model_pins_threats_to_test_or_code(self):
        body = THREAT_MODEL_PATH.read_text(encoding="utf-8")
        assert "Pinned by" in body

    def test_threat_model_has_sign_off_section(self):
        body = THREAT_MODEL_PATH.read_text(encoding="utf-8")
        assert "## Sign-off" in body
        assert "Platform security" in body
        assert "Engineering" in body
        assert "PENDING" in body or "2026-" in body or "Status:" in body

    def test_threat_model_requires_security_sign_off_worded(self):
        body = THREAT_MODEL_PATH.read_text(encoding="utf-8")
        lower = body.lower()
        assert "sign-off" in lower and "security" in body

    def test_threat_model_requires_pre_merge_sign_off(self):
        body = THREAT_MODEL_PATH.read_text(encoding="utf-8")
        lower = body.lower()
        assert "pre-merge" in lower and "sign-off" in lower


class TestPenTestScope260Structure:
    """260.2.I.3 — pen-test scope."""

    def test_pen_test_scope_doc_exists(self):
        assert PEN_TEST_SCOPE_PATH.exists(), (
            f"Phase 260.2.I.3 deliverable missing: {PEN_TEST_SCOPE_PATH}"
        )

    @pytest.mark.parametrize(
        "surface",
        [
            "Federated-import-disabled",
            "IDOR",
            "magic-byte",
            "multipart",
            "Rate-limit",
            "ratelimit-bypass",
        ],
    )
    def test_pen_test_scope_covers_surface(self, surface):
        body = PEN_TEST_SCOPE_PATH.read_text(encoding="utf-8")
        assert surface.lower() in body.lower(), f"Pen-test scope missing coverage of '{surface}'"

    def test_pen_test_scope_lists_concrete_test_cases(self):
        body = PEN_TEST_SCOPE_PATH.read_text(encoding="utf-8")
        attack_techniques = [
            "UUID",
            "Retry-After",
            "header",
            "presign",
            "multipart",
            "429",
        ]
        present = [t for t in attack_techniques if t.lower() in body.lower()]
        assert len(present) >= 3, f"Pen-test scope needs concrete techniques; found only {present}"

    def test_pen_test_scope_marks_p2_exit_criterion(self):
        body = PEN_TEST_SCOPE_PATH.read_text(encoding="utf-8")
        assert "P2 exit criterion" in body or "P2 prod-GA" in body
        assert "external" in body.lower(), (
            "Pen-test scope must state the engagement is external / release exit "
            "criterion, not only internal QA."
        )

    def test_pen_test_scope_defines_report_artifact_location(self):
        body = PEN_TEST_SCOPE_PATH.read_text(encoding="utf-8")
        assert "pen-test-reports" in body
        assert "p2-260" in body.lower()
