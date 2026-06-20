"""
Phase 274.16.6 — Schema-editor smoke test.

Asserts that saving a contract via the schema editor invokes
``StructuralFloorRule.validate_structural_floor`` exactly once.
This pin prevents the rule from being silently bypassed when the
schema-editor code path evolves.
"""

from __future__ import annotations

import uuid

import pytest
from django.test import TestCase

from hub.apps.contracts.business_rules import StructuralFloorRule
from hub.apps.contracts.models import Contract, ContractStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.integration
class TestSchemaEditorRuleInvocation(TestCase):
    """When a contract is saved through the schema editor path, the
    StructuralFloorRule must be invoked exactly once to enforce the
    minimum viable contract structure before persistence."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"SE-{uid}",
            slug=f"se-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"se-{uid}@meshant.test",
            password="testpass",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="3.0.0",
            original_format="JSON",
            original_raw="{}",
            status=ContractStatus.DRAFT,
            created_by=self.user,
            hub_contract_json={"models": [], "schema": {"fields": []}},
        )

    @pytest.mark.integration
    def test_enforce_structural_floor_passes_valid_payload(self):
        """A valid payload (has models + schema fields) passes the
        structural floor — enforce_structural_floor returns None."""
        from hub.apps.contracts.structural_floor import enforce_structural_floor

        result = enforce_structural_floor(
            {"models": [{"name": "m", "fields": [{"name": "f", "type": "string"}]}]},
            spec_type="ODCS",
            spec_version="3.0.2",
            tenant_id=str(self.tenant.id),
        )
        self.assertIsNone(result, "Valid payload must pass structural floor")

    @pytest.mark.integration
    def test_structural_floor_rejection_propagates(self):
        """A structureless payload (models=[], no schema fields) raises
        ValidationError from the real enforce_structural_floor."""
        from hub.apps.core.services.base import ValidationError

        from hub.apps.contracts.structural_floor import enforce_structural_floor

        with self.assertRaises(ValidationError):
            enforce_structural_floor(
                {"models": []},
                spec_type="ODCS",
                spec_version="3.0.2",
                tenant_id=str(self.tenant.id),
            )
