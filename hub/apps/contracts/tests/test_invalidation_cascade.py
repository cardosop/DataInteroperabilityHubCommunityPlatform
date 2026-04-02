"""
Phase 205: Contract invalidation warnings on linked assets (no mocks).
"""
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit.models import AuditEvent
from hub.apps.contracts.invalidation_cascade import (
    apply_linked_contract_invalidation_warnings,
    persist_contract_validation_job_result,
)
from hub.apps.jobs.models import Job, JobPriority, JobStatus, JobType
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
    ValidationStatus,
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ContractInvalidationCascadeTests(TestCase):
    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Inv Tenant {uid}",
            slug=f"inv-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"inv-user-{uid}@example.com",
            password="x",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_linked_asset_gets_contract_warnings_and_audit(self):
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"a-{uuid.uuid4().hex[:6]}",
            name="Linked",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw="{}",
            validation_status=ValidationStatus.INVALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        affected = apply_linked_contract_invalidation_warnings(
            contract, actor_user=self.user
        )
        self.assertEqual(affected, [str(asset.id)])

        asset.refresh_from_db()
        warnings = (asset.metadata_json or {}).get("contract_warnings") or []
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].get("contract_id"), str(contract.id))
        self.assertEqual(warnings[0].get("warning"), "LINKED_CONTRACT_INVALID")
        self.assertIn("invalidated_at", warnings[0])
        self.assertEqual(asset.status, AssetStatus.DRAFT)

        ev = AuditEvent.objects.filter(action="CONTRACT_INVALIDATED").first()
        self.assertIsNotNone(ev)
        self.assertEqual(str(ev.resource_id), str(contract.id))
        ids = ev.details_json.get("affected_asset_ids") or []
        self.assertEqual(ids, [str(asset.id)])

    def test_unlinked_asset_unaffected(self):
        linked = Asset.objects.create(
            tenant=self.tenant,
            key="linked",
            name="L",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        other = Asset.objects.create(
            tenant=self.tenant,
            key="other",
            name="O",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=linked,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw="{}",
            validation_status=ValidationStatus.INVALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        apply_linked_contract_invalidation_warnings(contract, actor_user=self.user)
        other.refresh_from_db()
        self.assertIsNone(other.metadata_json)

    def test_persist_validation_job_result_invalid_runs_cascade(self):
        """Async-style job outcome: INVALID persisted to Contract + asset warnings."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"job-{uuid.uuid4().hex[:6]}",
            name="JobLinked",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw="{}",
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.COMPLETED,
            priority=JobPriority.NORMAL,
            resource_type="CONTRACT",
            resource_id=contract.id,
            created_by=self.user,
        )
        result = {
            "status": "completed",
            "validation_status": ValidationStatus.INVALID,
            "errors": [{"message": "schema", "severity": "ERROR"}],
            "warnings": [],
            "contract_id": str(contract.id),
            "cli_version": "1.0.0",
        }
        persist_contract_validation_job_result(job, result)

        contract.refresh_from_db()
        self.assertEqual(contract.validation_status, ValidationStatus.INVALID)
        self.assertEqual(len(contract.validation_errors), 1)

        asset.refresh_from_db()
        cw = (asset.metadata_json or {}).get("contract_warnings") or []
        self.assertEqual(len(cw), 1)
        self.assertEqual(cw[0].get("contract_id"), str(contract.id))

        ev = AuditEvent.objects.filter(action="CONTRACT_INVALIDATED").first()
        self.assertIsNotNone(ev)
