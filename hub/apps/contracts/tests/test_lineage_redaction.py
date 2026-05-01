"""
Phase 228 X (228.X.5 / REQ-LIN-X-005) — PII redaction tests.

Spec scenarios:

  * Cross-tenant viewer + matching pattern → field name redacted.
  * Own-tenant viewer + matching pattern → NOT redacted (228.X.5.3).
  * Empty pattern list → no redaction (legacy).
  * Malformed regex → skipped, no crash.
"""
from __future__ import annotations


def _edge(**overrides):
    base = {
        "source_contract": "src",
        "target_contract": "tgt",
        "source_model": "m",
        "source_field": "ssn",
        "target_model": "m2",
        "target_field": "ok_field",
        "edge_type": "reference",
    }
    base.update(overrides)
    return base


class TestPIIRedaction:

    def test_cross_tenant_with_matching_pattern_redacts(self):
        from hub.apps.contracts.lineage_redaction import (
            REDACTED_PLACEHOLDER,
            redact_edges_for_cross_tenant_viewer,
        )

        edges = [_edge(source_field="ssn", target_field="email")]
        out = redact_edges_for_cross_tenant_viewer(
            edges=edges,
            viewer_tenant_id="viewer-uuid",
            owner_tenant_id="owner-uuid",
            patterns=[r"^ssn$", r"email"],
        )
        assert out[0]["source_field"] == REDACTED_PLACEHOLDER
        assert out[0]["target_field"] == REDACTED_PLACEHOLDER

    def test_own_tenant_does_not_redact(self):
        """Spec 228.X.5.3: own-tenant viewers see unredacted fields."""
        from hub.apps.contracts.lineage_redaction import (
            redact_edges_for_cross_tenant_viewer,
        )

        edges = [_edge(source_field="ssn", target_field="email")]
        out = redact_edges_for_cross_tenant_viewer(
            edges=edges,
            viewer_tenant_id="same-uuid",
            owner_tenant_id="same-uuid",
            patterns=[r"^ssn$", r"email"],
        )
        assert out[0]["source_field"] == "ssn"
        assert out[0]["target_field"] == "email"

    def test_empty_patterns_short_circuit(self):
        from hub.apps.contracts.lineage_redaction import (
            redact_edges_for_cross_tenant_viewer,
        )

        edges = [_edge(source_field="ssn")]
        out = redact_edges_for_cross_tenant_viewer(
            edges=edges,
            viewer_tenant_id="viewer-uuid",
            owner_tenant_id="owner-uuid",
            patterns=[],
        )
        assert out[0]["source_field"] == "ssn"

    def test_non_matching_field_passes_through(self):
        from hub.apps.contracts.lineage_redaction import (
            redact_edges_for_cross_tenant_viewer,
        )

        edges = [_edge(source_field="age", target_field="role")]
        out = redact_edges_for_cross_tenant_viewer(
            edges=edges,
            viewer_tenant_id="viewer-uuid",
            owner_tenant_id="owner-uuid",
            patterns=[r"^ssn$", r"email"],
        )
        assert out[0]["source_field"] == "age"
        assert out[0]["target_field"] == "role"

    def test_malformed_regex_is_skipped_not_crashed(self):
        """A bad regex on one tenant must NOT crash a cross-tenant
        view of any other tenant."""
        from hub.apps.contracts.lineage_redaction import (
            redact_edges_for_cross_tenant_viewer,
        )

        edges = [_edge(source_field="ssn")]
        out = redact_edges_for_cross_tenant_viewer(
            edges=edges,
            viewer_tenant_id="viewer-uuid",
            owner_tenant_id="owner-uuid",
            patterns=[r"[unclosed", r"^ssn$"],
        )
        assert out[0]["source_field"] == "[REDACTED]", (
            "good pattern still applies; malformed pattern skipped"
        )

    def test_only_field_keys_redacted_not_model_or_edge_type(self):
        """Spec: only ``source_field`` / ``target_field`` are
        candidates for redaction. ``source_model`` / ``edge_type``
        are structural metadata."""
        from hub.apps.contracts.lineage_redaction import (
            redact_edges_for_cross_tenant_viewer,
        )

        edges = [_edge(source_field="ssn", source_model="ssn", edge_type="ssn")]
        out = redact_edges_for_cross_tenant_viewer(
            edges=edges,
            viewer_tenant_id="viewer-uuid",
            owner_tenant_id="owner-uuid",
            patterns=[r"^ssn$"],
        )
        # source_field redacted.
        assert out[0]["source_field"] == "[REDACTED]"
        # source_model NOT redacted.
        assert out[0]["source_model"] == "ssn"
        # edge_type NOT redacted.
        assert out[0]["edge_type"] == "ssn"
