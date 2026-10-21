"""
Phase 228 X (228.X.4 / REQ-LIN-X-004) — data residency tests.

Pins:

* The pure-function policy (``check_residency_allowed``).
* Consent-header parsing.
* The audit-action constant ``LINEAGE_VIEWED_CROSS_REGION_CONSENTED``
  is in the registry tuple.
"""

from __future__ import annotations


class TestResidencyPolicy:
    """Pure function — no DB."""

    def test_owner_no_residency_rule_always_allows(self):
        from hub.apps.contracts.lineage_residency import (
            ResidencyOutcome,
            check_residency_allowed,
        )

        outcome = check_residency_allowed(
            viewer_region="us-east-1",
            owner_region=None,
            consent=False,
        )
        assert outcome == ResidencyOutcome.ALLOW

    def test_same_region_allows(self):
        from hub.apps.contracts.lineage_residency import (
            ResidencyOutcome,
            check_residency_allowed,
        )

        outcome = check_residency_allowed(
            viewer_region="eu-west-1",
            owner_region="eu-west-1",
            consent=False,
        )
        assert outcome == ResidencyOutcome.ALLOW

    def test_cross_region_no_consent_blocks(self):
        from hub.apps.contracts.lineage_residency import (
            ResidencyOutcome,
            check_residency_allowed,
        )

        outcome = check_residency_allowed(
            viewer_region="us-east-1",
            owner_region="eu-west-1",
            consent=False,
        )
        assert outcome == ResidencyOutcome.BLOCK

    def test_cross_region_with_consent_allows(self):
        from hub.apps.contracts.lineage_residency import (
            ResidencyOutcome,
            check_residency_allowed,
        )

        outcome = check_residency_allowed(
            viewer_region="us-east-1",
            owner_region="eu-west-1",
            consent=True,
        )
        assert outcome == ResidencyOutcome.ALLOW_WITH_CONSENT

    def test_viewer_null_cross_region_blocks_without_consent(self):
        """Defensive — a NULL viewer-region against a non-NULL owner
        region MUST block; we don't fail-open just because the
        viewer-side tenant is legacy."""
        from hub.apps.contracts.lineage_residency import (
            ResidencyOutcome,
            check_residency_allowed,
        )

        outcome = check_residency_allowed(
            viewer_region=None,
            owner_region="eu-west-1",
            consent=False,
        )
        assert outcome == ResidencyOutcome.BLOCK


class TestConsentFromRequest:
    def _build(self, *, header=None, query=None):
        class _R:
            META = {}
            query_params = None
            GET = None

        r = _R()
        if header is not None:
            r.META = {"HTTP_X_LINEAGE_CROSS_REGION_CONSENT": header}
        if query is not None:

            class _Q(dict):
                def get(self, k, d=None):
                    return super().get(k, d)

            q = _Q()
            q["cross_region_consent"] = query
            r.query_params = q
        return r

    def test_header_true_yields_consent(self):
        from hub.apps.contracts.lineage_residency import consent_from_request

        assert consent_from_request(self._build(header="true")) is True
        assert consent_from_request(self._build(header="1")) is True
        assert consent_from_request(self._build(header="yes")) is True

    def test_header_false_yields_no_consent(self):
        from hub.apps.contracts.lineage_residency import consent_from_request

        assert consent_from_request(self._build(header="false")) is False
        assert consent_from_request(self._build(header="")) is False

    def test_query_fallback(self):
        from hub.apps.contracts.lineage_residency import consent_from_request

        assert consent_from_request(self._build(query="true")) is True
        assert consent_from_request(self._build(query="false")) is False


class TestAuditConstantRegistered:
    def test_constant_in_audit_actions_tuple(self):
        from hub.apps.audit.models import (
            LINEAGE_AUDIT_ACTIONS,
            LINEAGE_VIEWED_CROSS_REGION_CONSENTED,
        )

        assert LINEAGE_VIEWED_CROSS_REGION_CONSENTED in LINEAGE_AUDIT_ACTIONS
