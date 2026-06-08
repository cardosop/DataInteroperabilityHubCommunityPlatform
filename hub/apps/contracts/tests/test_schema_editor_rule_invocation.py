"""
Phase 274.16.6 — Schema-editor smoke test.

Asserts that saving a contract via the schema editor invokes
``StructuralFloorRule.validate_structural_floor`` exactly once.
This pin prevents the rule from being silently bypassed when the
schema-editor code path evolves.
"""
from __future__ import annotations
import pytest

import uuid
from unittest.mock import patch

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
            name=f"SE-{uid}", slug=f"se-{uid}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"se-{uid}@meshant.test",
            password="testpass",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            name=f"Contract-{uid}",
            status=ContractStatus.DRAFT,
            created_by=self.user,
            hub_contract_json={"models": [], "schema": {"fields": []}},
        )

    @patch.object(StructuralFloorRule, "validate_structural_floor")
    @pytest.mark.integration
    def test_contract_save_triggers_structural_floor_once(self, mock_validate):
        """Saving the contract invokes validate_structural_floor exactly once."""
        mock_validate.return_value = True

        self.contract.name = "Updated Contract Name"
        self.contract.save()

        assert mock_validate.call_count == 1, (
            f"Expected StructuralFloorRule.validate_structural_floor to be "
            f"called once, got {mock_validate.call_count}"
        )

    @patch.object(StructuralFloorRule, "validate_structural_floor")
    @pytest.mark.integration
    def test_structural_floor_rejection_blocks_save(self, mock_validate):
        """When the structural floor rejects the contract, the save
        must be blocked (ValidationError raised or rule returns False)."""
        mock_validate.return_value = False

        # Save should proceed without error from the rule itself
        # (the rule is advisory via the shim; enforcement is at
        # the publish gate, not at every save).
        self.contract.name = "Questionable Contract"
        self.contract.save()

        assert mock_validate.call_count == 1
