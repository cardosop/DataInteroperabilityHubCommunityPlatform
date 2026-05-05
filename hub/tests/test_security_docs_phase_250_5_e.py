"""
Phase 250.5.E.1 + 250.5.E.3 — structural test asserting the STRIDE
threat-model + pen-test scope docs exist AND cover the spec'd
sections.

This is a DOCS-completeness test (not a security test on its own),
authored TDD-style so the doc structure can't drift away from the
spec: a future contributor who deletes a STRIDE section or pen-test
attack surface fails the test rather than silently shipping an
incomplete threat model.

Why a Python test (vs e.g. a markdown linter): the spec's contract
is SEMANTIC — "covers Spoofing/Tampering/.../EoP" + "covers
SSRF guard bypass / IDOR / cross-tenant URL leakage / ratelimit-
bypass" — not a raw markdown shape. Section-presence + keyword-
coverage assertions match that semantic contract directly. The test
also doubles as a forensic-replay aid: a security reviewer can run
this one test to confirm the threat-model artefact is structurally
complete before signing off.
"""
from __future__ import annotations

import pathlib

import pytest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
THREAT_MODEL_PATH = (
    REPO_ROOT
    / "docs"
    / "security"
    / "threat-model-asset-creation-federated.md"
)
PEN_TEST_SCOPE_PATH = (
    REPO_ROOT / "docs" / "security" / "pen-test-scope-p5.md"
)


# ---------------------------------------------------------------------------
# 250.5.E.1 — STRIDE threat model
# ---------------------------------------------------------------------------


class TestThreatModelStructure:
    """The threat-model doc MUST exist and carry the six STRIDE
    sections (Spoofing / Tampering / Repudiation / Information
    Disclosure / Denial of Service / Elevation of Privilege)."""

    def test_threat_model_doc_exists(self):
        assert THREAT_MODEL_PATH.exists(), (
            f"Phase 250.5.E.1 deliverable missing: {THREAT_MODEL_PATH}"
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
            f"STRIDE section '{section}' missing from threat model"
        )

    def test_threat_model_has_system_under_threat_section(self):
        body = THREAT_MODEL_PATH.read_text(encoding="utf-8")
        assert "## System under threat" in body or "# System under threat" in body
        # Must enumerate at least one endpoint, code path, and capability flag.
        assert "Endpoint" in body
        assert "Code path" in body
        assert "Capability flag" in body or "Trust boundaries" in body

    def test_threat_model_pins_threats_to_test_or_code(self):
        """Per the convention from existing threat models (e.g.
        federation-cross-tenant.md), every threat row carries a
        ``Pinned by`` column referencing a test / code path /
        out-of-scope rationale. Without this column the doc is just
        a wishlist."""
        body = THREAT_MODEL_PATH.read_text(encoding="utf-8")
        assert "Pinned by" in body, (
            "Threat-model rows must carry a 'Pinned by' column "
            "(test / code-path reference) so the mitigation is "
            "auditable, not aspirational."
        )

    # ------------------------------------------------------------------
    # 250.5.E.2 — pre-merge sign-off log
    # ------------------------------------------------------------------

    def test_threat_model_has_sign_off_section(self):
        """Per 250.5.E.2 the threat model SHALL carry a sign-off
        section so the pre-merge review trail is durable. The
        section MUST list the required reviewers + a sign-off
        record (or explicit "PENDING" state) so a CI gate can
        check whether sign-off has happened."""
        body = THREAT_MODEL_PATH.read_text(encoding="utf-8")
        assert "## Sign-off" in body, "Sign-off section missing"
        # Required reviewer roles per the codebase convention
        # (mirrors `docs/security/threat-models/federation-cross-tenant.md`
        # which targets "Platform security, Engineering leads, DPO").
        assert "Platform security" in body
        assert "Engineering" in body
        # The sign-off entry MUST be either "PENDING" (unsigned) or a
        # dated entry. The structural test doesn't enforce signed —
        # that's the human reviewer's job — but does enforce that the
        # state is explicitly captured.
        assert (
            "PENDING" in body
            or "2026-" in body
            or "Status:" in body
        )


# ---------------------------------------------------------------------------
# 250.5.E.3 — pen-test scope doc
# ---------------------------------------------------------------------------


class TestPenTestScopeStructure:
    """The pen-test scope doc MUST exist and cover the five attack
    surfaces called out by the spec."""

    def test_pen_test_scope_doc_exists(self):
        assert PEN_TEST_SCOPE_PATH.exists(), (
            f"Phase 250.5.E.3 deliverable missing: {PEN_TEST_SCOPE_PATH}"
        )

    @pytest.mark.parametrize(
        "surface",
        [
            "Federated-import endpoint",
            "SSRF",
            "IDOR",
            "ExternalResourceReference",
            "Cross-tenant",
            "rate",  # ratelimit-bypass
        ],
    )
    def test_pen_test_scope_covers_surface(self, surface):
        body = PEN_TEST_SCOPE_PATH.read_text(encoding="utf-8")
        assert surface.lower() in body.lower(), (
            f"Pen-test scope missing coverage of '{surface}'"
        )

    def test_pen_test_scope_lists_concrete_test_cases(self):
        """The scope doc MUST list concrete test cases (not just a
        topic-of-interest list) so the pen-test vendor has an
        unambiguous brief. Convention: each surface section carries a
        bullet list with at least one test case."""
        body = PEN_TEST_SCOPE_PATH.read_text(encoding="utf-8")
        # Heuristic: a valid scope has at least one explicit attack
        # technique noun (the most common ones are listed below).
        attack_techniques = [
            "loopback",
            "RFC1918",
            "DNS rebinding",
            "UUID",
            "header",
            "throttle",
        ]
        present = [t for t in attack_techniques if t.lower() in body.lower()]
        assert len(present) >= 3, (
            f"Pen-test scope must list concrete attack techniques "
            f"(found only {present}); the vendor brief should "
            f"specify at least 3 specific techniques per surface."
        )

    # ------------------------------------------------------------------
    # 250.5.E.4 — P5 exit criterion
    # ------------------------------------------------------------------

    def test_pen_test_scope_marks_p5_exit_criterion(self):
        """Per 250.5.E.4 the external pen test is a P5 exit
        criterion. The scope doc MUST capture that explicitly so the
        release-checklist owner doesn't ship P5 without the pen-
        test report."""
        body = PEN_TEST_SCOPE_PATH.read_text(encoding="utf-8")
        assert "P5 exit criterion" in body or "P5 prod-GA" in body, (
            "Pen-test scope must mark the external pen test as a P5 "
            "exit criterion (250.5.E.4 contract)."
        )
