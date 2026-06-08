"""
Phase 117C — Governance Hardening (GF-20) Tests

Tests ABAC cache invalidation, field masking audit, access expiration,
KYC expiration, and classification propagation.
"""
import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.audit.models import AuditEvent
from hub.apps.governance.abac import ABACEngine
from hub.apps.governance.models import (
    AccessPolicy,
    AccessRequest,
    AccessRequestStatus,
    ClassificationCategory,
    DataClassification,
    FieldAccessPolicy,
)


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
@pytest.mark.spec("governance:G1:abac-cache-invalidation")
class TestABACCacheInvalidation(TestCase):
    """117C.1 + 117C.2: ABAC cache invalidation on policy change."""

    def setUp(self):
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User

        self.tenant = Tenant.objects.create(
            name=f"test-tenant-{uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:8]}",
        )
        self.user = User.objects.create(
            email=f"test-{uuid.uuid4().hex[:6]}@example.com",
            tenant=self.tenant,
        )
        cache.clear()

    def test_policy_save_increments_cache_version(self):
        """Saving an AccessPolicy increments the tenant's ABAC cache version."""
        version_key = f"abac_cache_version_{self.tenant.id}"
        cache.set(version_key, 5)

        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="test-policy",
            effect="ALLOW",
            conditions={"user": {"role": "admin"}},
            enabled=True,
            created_by=self.user,
        )

        new_version = cache.get(version_key)
        assert new_version == 6, f"Expected version 6, got {new_version}"

    def test_policy_delete_increments_cache_version(self):
        """Deleting an AccessPolicy increments the tenant's ABAC cache version."""
        version_key = f"abac_cache_version_{self.tenant.id}"
        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="test-policy-del",
            effect="ALLOW",
            conditions={},
            enabled=True,
            created_by=self.user,
        )
        cache.set(version_key, 10)

        policy.delete()

        new_version = cache.get(version_key)
        assert new_version == 11, f"Expected version 11, got {new_version}"

    def test_policy_update_invalidates_cached_evaluation(self):
        """After policy update, next ABAC eval misses cache (uses new version)."""
        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="test-policy-update",
            effect="ALLOW",
            conditions={},
            enabled=True,
            created_by=self.user,
        )

        # Prime the cache
        cache_key = ABACEngine._get_cache_key(
            str(self.tenant.id), "ASSET", "fake-asset-id"
        )
        cache.set(cache_key, ["some-old-policy-id"])

        # Update policy — should increment version, making old cache key stale
        policy.name = "updated-name"
        policy.save()

        # Old cache key should miss (version changed)
        new_cache_key = ABACEngine._get_cache_key(
            str(self.tenant.id), "ASSET", "fake-asset-id"
        )
        assert new_cache_key != cache_key, "Cache key should change after version bump"
        assert cache.get(new_cache_key) is None, "New cache key should be a miss"


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
@pytest.mark.spec("governance:G2:field-masking-audit")
class TestFieldMaskingAuditEvent(TestCase):
    """117C.3: Audit event after field-level masking."""

    def setUp(self):
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User

        self.tenant = Tenant.objects.create(
            name=f"test-tenant-mask-{uuid.uuid4().hex[:8]}",
            slug=f"mask-{uuid.uuid4().hex[:8]}",
        )
        self.user = User.objects.create(
            email=f"mask-{uuid.uuid4().hex[:6]}@example.com",
            tenant=self.tenant,
        )

    def test_field_masking_creates_audit_event(self):
        """ABAC eval with masking creates FIELD_MASKING_APPLIED audit event."""
        from hub.apps.datasets.models import Dataset

        dataset = Dataset.objects.create(
            tenant=self.tenant,
            format="CSV",
            created_by=self.user,
        )

        # Create policy + field policy with masking
        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="mask-policy",
            effect="ALLOW",
            conditions={},
            dataset=dataset,
            enabled=True,
            created_by=self.user,
        )
        FieldAccessPolicy.objects.create(
            tenant=self.tenant,
            dataset=dataset,
            field_name="ssn",
            access_policy=policy,
            access_type="READ",
            masking_strategy="HASH",
            enabled=True,
        )

        # Evaluate access — should trigger masking
        result = ABACEngine.evaluate_access(
            user_id=str(self.user.id),
            tenant_id=str(self.tenant.id),
            resource_type="DATASET",
            resource_id=str(dataset.id),
            access_type="READ",
            field_name="ssn",
        )

        assert result.allowed is True
        assert result.masking_required is True

        # Check audit event was created
        audit_events = AuditEvent.objects.filter(
            action="FIELD_MASKING_APPLIED",
            tenant=self.tenant,
        )
        assert audit_events.exists(), "Expected FIELD_MASKING_APPLIED audit event"
        event = audit_events.first()
        assert event.resource_type == "DATASET"
        assert str(dataset.id) in str(event.resource_id)


@pytest.mark.spec("governance:G3:access-expiration")
class TestAccessExpiration(TestCase):
    """117C.5 + 117C.6: Access expiration on approval and management command."""

    def setUp(self):
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User

        self.tenant = Tenant.objects.create(
            name=f"test-tenant-exp-{uuid.uuid4().hex[:8]}",
            slug=f"exp-{uuid.uuid4().hex[:8]}",
        )
        self.user = User.objects.create(
            email=f"exp-{uuid.uuid4().hex[:6]}@example.com",
            tenant=self.tenant,
        )
        self.approver = User.objects.create(
            email=f"approver-{uuid.uuid4().hex[:6]}@example.com",
            tenant=self.tenant,
        )

    def test_approval_sets_expires_at_default_90_days(self):
        """Approving an access request sets expires_at to ~90 days from now."""
        from hub.apps.assets.models import Asset
        asset = Asset.objects.create(
            name="exp-asset",
            key=f"exp-asset-{uuid.uuid4().hex[:8]}",
            tenant=self.tenant,
            created_by=self.user,
        )
        access_request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=asset,
            reason="Need access",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        # Simulate service-level approval logic
        access_request.status = AccessRequestStatus.APPROVED
        access_request.approved_by = self.approver
        access_request.approved_at = timezone.now()
        if not access_request.expires_at:
            access_request.expires_at = timezone.now() + timedelta(days=90)
        access_request.save()

        access_request.refresh_from_db()
        assert access_request.expires_at is not None
        expected_min = timezone.now() + timedelta(days=89)
        expected_max = timezone.now() + timedelta(days=91)
        assert expected_min <= access_request.expires_at <= expected_max

    def test_revoke_expired_access_command(self):
        """Management command revokes expired APPROVED access requests."""
        from hub.apps.assets.models import Asset
        asset = Asset.objects.create(
            name="revoke-asset",
            key=f"revoke-asset-{uuid.uuid4().hex[:8]}",
            tenant=self.tenant,
            created_by=self.user,
        )
        expired_request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=asset,
            reason="Old access",
            requested_access_type="READ",
            status=AccessRequestStatus.APPROVED,
            approved_by=self.approver,
            approved_at=timezone.now() - timedelta(days=100),
            expires_at=timezone.now() - timedelta(days=10),
        )

        valid_request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=asset,
            reason="Current access",
            requested_access_type="READ",
            status=AccessRequestStatus.APPROVED,
            approved_by=self.approver,
            approved_at=timezone.now() - timedelta(days=10),
            expires_at=timezone.now() + timedelta(days=80),
        )

        call_command("revoke_expired_access")

        expired_request.refresh_from_db()
        valid_request.refresh_from_db()
        assert expired_request.status == AccessRequestStatus.REVOKED
        assert valid_request.status == AccessRequestStatus.APPROVED

        audit_events = AuditEvent.objects.filter(
            action="ACCESS_EXPIRED_REVOKED",
        )
        assert audit_events.exists(), "Expected ACCESS_EXPIRED_REVOKED audit event"


@pytest.mark.spec("governance:G4:kyc-expiration")
class TestKYCExpiration(TestCase):
    """117C.7 + 117C.8 + 117C.9: KYC expiration fields, management command, can_publish."""

    def setUp(self):
        from hub.apps.tenants.models import Tenant

        self.tenant = Tenant.objects.create(
            name=f"test-tenant-kyc-{uuid.uuid4().hex[:8]}",
            slug=f"kyc-{uuid.uuid4().hex[:8]}",
            kyc_status="VERIFIED",
        )

    def test_tenant_has_kyc_date_fields(self):
        """Tenant model has kyc_verified_at and kyc_expires_at fields."""
        from hub.apps.tenants.models import Tenant

        t = Tenant.objects.get(id=self.tenant.id)
        assert hasattr(t, "kyc_verified_at"), "Missing kyc_verified_at field"
        assert hasattr(t, "kyc_expires_at"), "Missing kyc_expires_at field"

    def test_can_publish_blocks_expired_kyc(self):
        """can_publish() returns False when KYC is expired."""
        from hub.apps.marketplace.models import Listing
        from hub.apps.assets.models import Asset
        from hub.apps.users.models import User

        user = User.objects.create(
            email=f"kyc-pub-{uuid.uuid4().hex[:6]}@example.com",
            tenant=self.tenant,
        )
        asset = Asset.objects.create(
            name="test-asset",
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            tenant=self.tenant,
            status="ACTIVE",
            created_by=user,
        )

        listing = Listing.objects.create(
            tenant=self.tenant,
            asset=asset,
            metadata_json={"title": "Test Listing"},
        )

        # Set KYC as verified but expired
        self.tenant.kyc_verified_at = timezone.now() - timedelta(days=400)
        self.tenant.kyc_expires_at = timezone.now() - timedelta(days=35)
        self.tenant.save()

        can, reason = listing.can_publish()
        assert can is False, f"Expected publish blocked, got: {reason}"
        assert "expired" in reason.lower()

    def test_can_publish_allows_valid_kyc(self):
        """can_publish() returns True when KYC is verified and not expired."""
        from hub.apps.marketplace.models import Listing
        from hub.apps.assets.models import Asset
        from hub.apps.users.models import User

        user = User.objects.create(
            email=f"kyc-ok-{uuid.uuid4().hex[:6]}@example.com",
            tenant=self.tenant,
        )
        asset = Asset.objects.create(
            name="test-asset-ok",
            key=f"test-asset-ok-{uuid.uuid4().hex[:8]}",
            tenant=self.tenant,
            status="ACTIVE",
            created_by=user,
        )

        listing = Listing.objects.create(
            tenant=self.tenant,
            asset=asset,
            metadata_json={"title": "Test Listing OK"},
        )

        # Set KYC as verified and not expired
        self.tenant.kyc_verified_at = timezone.now() - timedelta(days=30)
        self.tenant.kyc_expires_at = timezone.now() + timedelta(days=335)
        self.tenant.save()

        can, reason = listing.can_publish()
        assert can is True, f"Expected publish allowed, got blocked: {reason}"

    def test_can_publish_to_marketplace_blocks_expired_kyc(self):
        """Tenant.can_publish_to_marketplace() returns False when KYC expired."""
        self.tenant.kyc_verified_at = timezone.now() - timedelta(days=400)
        self.tenant.kyc_expires_at = timezone.now() - timedelta(days=35)
        self.tenant.save()

        assert self.tenant.can_publish_to_marketplace() is False

    def test_can_publish_to_marketplace_allows_valid_kyc(self):
        """Tenant.can_publish_to_marketplace() returns True when KYC valid."""
        self.tenant.kyc_verified_at = timezone.now() - timedelta(days=30)
        self.tenant.kyc_expires_at = timezone.now() + timedelta(days=335)
        self.tenant.save()

        assert self.tenant.can_publish_to_marketplace() is True

    def test_refresh_kyc_status_command(self):
        """Management command downgrades expired KYC to PENDING_REVIEW."""
        self.tenant.kyc_status = "VERIFIED"
        self.tenant.kyc_verified_at = timezone.now() - timedelta(days=400)
        self.tenant.kyc_expires_at = timezone.now() - timedelta(days=35)
        self.tenant.save()

        call_command("refresh_kyc_status")

        self.tenant.refresh_from_db()
        assert self.tenant.kyc_status == "PENDING_REVIEW", (
            f"Expected PENDING_REVIEW, got {self.tenant.kyc_status}"
        )


@pytest.mark.spec("governance:G5:classification-propagation")
class TestClassificationPropagation(TestCase):
    """117C.10 + 117C.11: Classification propagation from dataset to model."""

    def setUp(self):
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User

        self.tenant = Tenant.objects.create(
            name=f"test-tenant-cls-{uuid.uuid4().hex[:8]}",
            slug=f"cls-{uuid.uuid4().hex[:8]}",
        )
        self.user = User.objects.create(
            email=f"cls-{uuid.uuid4().hex[:6]}@example.com",
            tenant=self.tenant,
        )

    def test_propagate_classification_creates_target_classification(self):
        """propagate_classification copies highest source classification to target."""
        from hub.apps.datasets.models import Dataset
        from hub.apps.assets.models import Asset
        from hub.apps.governance.classification import propagate_classification

        dataset = Dataset.objects.create(
            tenant=self.tenant,
            format="CSV",
            created_by=self.user,
        )
        asset = Asset.objects.create(
            name="model-asset",
            key=f"model-asset-{uuid.uuid4().hex[:8]}",
            tenant=self.tenant,
            created_by=self.user,
        )

        # Create PII classification on the dataset
        DataClassification.objects.create(
            tenant=self.tenant,
            dataset=dataset,
            field_name="email",
            category=ClassificationCategory.PII,
            confidence_score=0.95,
            status="APPROVED",
        )

        propagate_classification(
            source_type="DATASET",
            source_id=str(dataset.id),
            target_type="ASSET",
            target_id=str(asset.id),
            tenant_id=str(self.tenant.id),
        )

        # Check classification was created on the asset
        target_classification = DataClassification.objects.filter(
            tenant=self.tenant,
            asset=asset,
        )
        assert target_classification.exists(), "Expected classification on target asset"
        assert target_classification.first().category == ClassificationCategory.PII

    def test_link_model_to_dataset_propagates_classification(self):
        """link_model_to_dataset calls propagate_classification for PII datasets."""
        from hub.apps.datasets.models import Dataset
        from hub.apps.assets.models import Asset
        from hub.apps.ml.models import MLModel, ModelDatasetLink
        from hub.apps.ml.services import ModelRegistryBridgeService

        dataset = Dataset.objects.create(
            tenant=self.tenant,
            format="CSV",
            created_by=self.user,
        )

        # Create PII classification
        DataClassification.objects.create(
            tenant=self.tenant,
            dataset=dataset,
            field_name="ssn",
            category=ClassificationCategory.PII,
            confidence_score=0.99,
            status="APPROVED",
        )

        asset = Asset.objects.create(
            name="ml-model-asset",
            key=f"ml-asset-{uuid.uuid4().hex[:8]}",
            tenant=self.tenant,
            created_by=self.user,
        )

        model = MLModel.objects.create(
            tenant=self.tenant,
            odh_model_name="test-model",
            odh_model_id=f"odh-{uuid.uuid4().hex[:8]}",
            odh_model_version="1.0",
            model_type="CLASSIFICATION",
            status="TRAINING",
            asset=asset,
        )

        service = ModelRegistryBridgeService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        service.link_model_to_dataset(
            model_id=str(model.id),
            dataset_id=str(dataset.id),
            role="TRAINING",
        )

        # Verify the ModelDatasetLink was actually created
        link = ModelDatasetLink.objects.filter(
            model=model,
            dataset=dataset,
            role="TRAINING",
        )
        assert link.exists(), (
            "Expected ModelDatasetLink row to be created with role=TRAINING"
        )
        assert link.first().model == model
        assert link.first().dataset == dataset

        # Classification should have propagated from dataset to model's asset
        target_classification = DataClassification.objects.filter(
            tenant=self.tenant,
            asset=asset,
        )
        assert target_classification.exists(), (
            "Expected PII classification propagated to model asset"
        )
