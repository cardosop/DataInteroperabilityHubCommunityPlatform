"""
Phase 277.1.2-3 — Chain atomicity + audit durability tests (P0-2, G7.4).

277.1.2: Step 1 writes audit row, Step 2 returns is_valid=False.
After chain execution, Step 1 audit row was ROLLED BACK (transaction atomic).

277.1.3: RULE_CHAIN_COMPLETED audit row survives rollback because
audit is emitted outside the transaction block per chains.py.
Assert audit row IS present post-chain-failure.

No mocks — real Postgres, real ORM, real transaction isolation.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.db import transaction, connections
from django.test import TestCase

from hub.apps.audit.models import AuditEvent
from hub.apps.core.business_rules.base import RuleExecutionContext, ValidationResult
from hub.apps.core.business_rules.chains import RuleChain
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)


class TestChainAtomicity(TestCase):
    """Phase 277.1.2 — chain step audit row rolled back on failure."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"CA-{uid}", slug=f"ca-{uid}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )

    def _step_write_audit(self, ctx, **kwargs):
        """Step 1: write an audit row inside the transaction."""
        from hub.apps.audit.utils import create_audit_event
        create_audit_event(
            resource_type="TEST",
            action="CHAIN_ATOMICITY_STEP_1",
            actor_user=None,
            tenant=self.tenant,
            resource_id="step-1",
            result="SUCCESS",
        )
        return ValidationResult(is_valid=True)

    def _step_fail(self, ctx, **kwargs):
        """Step 2: always fails."""
        return ValidationResult(is_valid=False, errors=["step_2_failed"])

    def test_step_one_audit_rolled_back_on_chain_failure(self):
        """When chain fails at step 2, step 1's audit row is rolled back."""
        audit_count_before = AuditEvent.objects.filter(
            action="CHAIN_ATOMICITY_STEP_1",
        ).count()

        chain = RuleChain(
            name="test.atomicity",
            steps=[self._step_write_audit, self._step_fail],
            requires_transaction=True,
            short_circuit=True,
        )

        with transaction.atomic():
            result = chain.execute(tenant_id=str(self.tenant.id))
            assert result["outcome"] == "FAIL"

        # Step 1's audit row must NOT exist — transaction rolled back.
        audit_count_after = AuditEvent.objects.filter(
            action="CHAIN_ATOMICITY_STEP_1",
        ).count()
        assert audit_count_after == audit_count_before, (
            f"Step 1 audit row should be rolled back. "
            f"Before={audit_count_before}, After={audit_count_after}"
        )

    def test_step_one_audit_survives_chain_success(self):
        """When chain passes, step 1's audit row is committed."""
        chain = RuleChain(
            name="test.atomicity_pass",
            steps=[self._step_write_audit, self._step_write_audit],
            requires_transaction=True,
            short_circuit=True,
        )

        with transaction.atomic():
            result = chain.execute(tenant_id=str(self.tenant.id))
            assert result["outcome"] == "PASS"

        audit_count = AuditEvent.objects.filter(
            action="CHAIN_ATOMICITY_STEP_1",
        ).count()
        assert audit_count == 2, f"Both step audit rows should exist: got {audit_count}"


class TestChainAuditDurability(TestCase):
    """Phase 277.1.3 — RULE_CHAIN_COMPLETED audit survives rollback."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"CD-{uid}", slug=f"cd-{uid}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )

    def _step_pass(self, ctx, **kwargs):
        return ValidationResult(is_valid=True)

    def _step_fail(self, ctx, **kwargs):
        return ValidationResult(is_valid=False, errors=["fail"])

    def test_chain_completed_audit_survives_rollback(self):
        """RULE_CHAIN_COMPLETED audit is emitted outside the transaction block
        and survives rollback of the business transaction."""
        chain = RuleChain(
            name="test.durability",
            steps=[self._step_pass, self._step_fail],
            requires_transaction=True,
            short_circuit=True,
        )

        audit_before = AuditEvent.objects.filter(
            action="RULE_CHAIN_COMPLETED",
        ).count()

        with transaction.atomic():
            result = chain.execute(tenant_id=str(self.tenant.id))
            assert result["outcome"] == "FAIL"

        # RULE_CHAIN_COMPLETED must exist — audit is outside the atomic block.
        audit_after = AuditEvent.objects.filter(
            action="RULE_CHAIN_COMPLETED",
        ).count()
        assert audit_after > audit_before, (
            "RULE_CHAIN_COMPLETED audit must survive transaction rollback. "
            f"Before={audit_before}, After={audit_after}"
        )

    def test_chain_completed_audit_has_correct_shape(self):
        """The audit event carries the expected fields."""
        chain = RuleChain(
            name="test.shape",
            steps=[self._step_pass],
            requires_transaction=False,  # skip transaction requirement for this test
        )

        result = chain.execute(tenant_id=str(self.tenant.id))

        audit = AuditEvent.objects.filter(
            action="RULE_CHAIN_COMPLETED",
        ).order_by("-created_at").first()
        assert audit is not None
        assert audit.details.get("chain") == "test.shape"
        assert audit.details.get("outcome") == "PASS"
        assert "duration_ms" in audit.details
        assert "steps" in audit.details
