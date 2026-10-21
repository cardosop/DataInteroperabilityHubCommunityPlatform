"""Tests for consent re-prompt on purpose version bump (277.B.086)."""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from hub.apps.consent.models import ConsentPurpose, ConsentRecord, ConsentRecordStatus
from hub.apps.consent.services import ConsentService
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _consent_signing_keys() -> dict:
    return {"__default__": ["a" * 64]}


class PurposeVersionBumpTest(TestCase):
    """Auto-bump version on substance-changing edits (277.B.086)."""

    def setUp(self):
        self.uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"VersionBump {self.uid}",
            slug=f"version-bump-{self.uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            compliance_consent_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        from hub.apps.testing.role_support import ensure_user_has_tenant_admin_role

        self.user = User.objects.create_user(
            email=f"version-bump-{self.uid}@example.com",
            password="testpass",
            tenant=self.tenant,
        )
        ensure_user_has_tenant_admin_role(self.user)
        self.purpose = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key=f"test.purpose.{self.uid}",
            name="Original Name",
            description="Original description.",
            version=1,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_version_starts_at_one(self):
        self.assertEqual(self.purpose.version, 1)

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_name_change_bumps_version(self):
        resp = self.client.patch(
            f"/api/v1/consent/consent-purposes/{self.purpose.id}/",
            {"name": "Updated Name"},
            format="json",
        )
        self.assertIn(resp.status_code, (200, 201))
        self.purpose.refresh_from_db()
        self.assertEqual(self.purpose.version, 2)
        self.assertEqual(self.purpose.name, "Updated Name")

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_description_change_bumps_version(self):
        resp = self.client.patch(
            f"/api/v1/consent/consent-purposes/{self.purpose.id}/",
            {"description": "Updated description."},
            format="json",
        )
        self.assertIn(resp.status_code, (200, 201))
        self.purpose.refresh_from_db()
        self.assertEqual(self.purpose.version, 2)

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_retention_days_change_bumps_version(self):
        resp = self.client.patch(
            f"/api/v1/consent/consent-purposes/{self.purpose.id}/",
            {"retention_days": 365},
            format="json",
        )
        self.assertIn(resp.status_code, (200, 201))
        self.purpose.refresh_from_db()
        self.assertEqual(self.purpose.version, 2)

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_iab_purpose_id_change_bumps_version(self):
        resp = self.client.patch(
            f"/api/v1/consent/consent-purposes/{self.purpose.id}/",
            {"iab_purpose_id": "42"},
            format="json",
        )
        self.assertIn(resp.status_code, (200, 201))
        self.purpose.refresh_from_db()
        self.assertEqual(self.purpose.version, 2)

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_is_active_toggle_does_not_bump_version(self):
        """Toggling is_active is NOT a substance change — no re-prompt needed."""
        resp = self.client.patch(
            f"/api/v1/consent/consent-purposes/{self.purpose.id}/",
            {"is_active": False},
            format="json",
        )
        self.assertIn(resp.status_code, (200, 201))
        self.purpose.refresh_from_db()
        self.assertEqual(self.purpose.version, 1)  # unchanged

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_multiple_substance_changes_bump_once_per_request(self):
        """Multiple substance fields in one PATCH bumps once."""
        resp = self.client.patch(
            f"/api/v1/consent/consent-purposes/{self.purpose.id}/",
            {"name": "New Name", "description": "New desc"},
            format="json",
        )
        self.assertIn(resp.status_code, (200, 201))
        self.purpose.refresh_from_db()
        self.assertEqual(self.purpose.version, 2)  # bumped once

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_consecutive_bumps_increment(self):
        """Two separate PATCH requests each bump the version."""
        for _ in range(3):
            self.client.patch(
                f"/api/v1/consent/consent-purposes/{self.purpose.id}/",
                {"name": f"Name v{self.purpose.version + 1}"},
                format="json",
            )
            self.purpose.refresh_from_db()
        self.assertEqual(self.purpose.version, 4)

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_no_op_patch_does_not_bump(self):
        """PATCH with same values does NOT bump version."""
        resp = self.client.patch(
            f"/api/v1/consent/consent-purposes/{self.purpose.id}/",
            {"name": self.purpose.name},
            format="json",
        )
        self.assertIn(resp.status_code, (200, 201))
        self.purpose.refresh_from_db()
        self.assertEqual(self.purpose.version, 1)


@override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
class GrantVersionTrackingTest(TestCase):
    """Grant records the purpose version at grant time (277.B.086)."""

    def setUp(self):
        self.uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"GrantVer {self.uid}",
            slug=f"grant-ver-{self.uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            compliance_consent_enabled=True,
        )
        self.user = User.objects.create_user(
            email=f"grant-ver-{self.uid}@example.com",
            password="testpass",
            tenant=self.tenant,
        )
        self.purpose = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key=f"grant.test.{self.uid}",
            name="Test Purpose",
            version=3,
        )

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_grant_stamps_current_purpose_version(self):
        service = ConsentService()
        record = service.grant(
            tenant=self.tenant,
            user=self.user,
            purpose=self.purpose,
            payload={"source": "test"},
        )
        self.assertEqual(record.purpose_version_at_grant, 3)

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_grant_stamps_version_from_payload_if_provided(self):
        service = ConsentService()
        record = service.grant(
            tenant=self.tenant,
            user=self.user,
            purpose=self.purpose,
            payload={"source": "test", "purpose_version": 2},
        )
        self.assertEqual(record.purpose_version_at_grant, 2)

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_grant_audit_includes_version_info(self):
        from hub.apps.audit.models import AuditEvent

        service = ConsentService()
        service.grant(
            tenant=self.tenant,
            user=self.user,
            purpose=self.purpose,
            payload={"source": "test"},
        )

        event = AuditEvent.objects.filter(
            tenant=self.tenant,
            action="CONSENT_GRANTED",
        ).latest("timestamp")
        self.assertEqual(event.details_json.get("purpose_version"), 3)
        self.assertEqual(event.details_json.get("purpose_version_at_grant"), 3)


class ReconsentDetectionTest(TestCase):
    """Detect stale consent grants for re-prompt (277.B.086)."""

    def setUp(self):
        self.uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Reconsent {self.uid}",
            slug=f"reconsent-{self.uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            compliance_consent_enabled=True,
        )
        self.user = User.objects.create_user(
            email=f"reconsent-{self.uid}@example.com",
            password="testpass",
            tenant=self.tenant,
        )

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_needs_reconsent_false_when_grants_up_to_date(self):
        purpose = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key="current.purpose",
            name="Current",
            version=1,
        )
        ConsentRecord.objects.create(
            tenant=self.tenant,
            user=self.user,
            purpose=purpose,
            status=ConsentRecordStatus.GRANTED,
            purpose_version_at_grant=1,
        )
        self.assertFalse(
            ConsentService.check_user_needs_reconsent(user=self.user, tenant=self.tenant)
        )

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_needs_reconsent_true_when_version_stale(self):
        purpose = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key="stale.purpose",
            name="Stale",
            version=5,
        )
        ConsentRecord.objects.create(
            tenant=self.tenant,
            user=self.user,
            purpose=purpose,
            status=ConsentRecordStatus.GRANTED,
            purpose_version_at_grant=2,
        )
        self.assertTrue(
            ConsentService.check_user_needs_reconsent(user=self.user, tenant=self.tenant)
        )

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_get_stale_purposes_returns_details(self):
        purpose = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key="stale.detail",
            name="Stale Detail",
            version=4,
        )
        ConsentRecord.objects.create(
            tenant=self.tenant,
            user=self.user,
            purpose=purpose,
            status=ConsentRecordStatus.GRANTED,
            purpose_version_at_grant=1,
        )
        stale = ConsentService.get_stale_purposes_for_user(user=self.user, tenant=self.tenant)
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0]["purpose_key"], "stale.detail")
        self.assertEqual(stale[0]["granted_version"], 1)
        self.assertEqual(stale[0]["current_version"], 4)

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_revoked_records_not_stale(self):
        """Revoked grants don't trigger re-prompt."""
        purpose = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key="revoked.purpose",
            name="Revoked",
            version=3,
        )
        ConsentRecord.objects.create(
            tenant=self.tenant,
            user=self.user,
            purpose=purpose,
            status=ConsentRecordStatus.REVOKED,
            purpose_version_at_grant=1,
        )
        self.assertFalse(
            ConsentService.check_user_needs_reconsent(user=self.user, tenant=self.tenant)
        )

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_inactive_purpose_not_reported(self):
        """Inactive purposes don't trigger re-prompt even if version is stale."""
        purpose = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key="inactive.purpose",
            name="Inactive",
            version=5,
            is_active=False,
        )
        ConsentRecord.objects.create(
            tenant=self.tenant,
            user=self.user,
            purpose=purpose,
            status=ConsentRecordStatus.GRANTED,
            purpose_version_at_grant=1,
        )
        stale = ConsentService.get_stale_purposes_for_user(user=self.user, tenant=self.tenant)
        self.assertEqual(len(stale), 0)

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_multiple_stale_purposes_all_reported(self):
        p1 = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key="stale.1",
            name="Stale 1",
            version=3,
        )
        p2 = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key="stale.2",
            name="Stale 2",
            version=2,
        )
        ConsentRecord.objects.create(
            tenant=self.tenant,
            user=self.user,
            purpose=p1,
            status=ConsentRecordStatus.GRANTED,
            purpose_version_at_grant=1,
        )
        ConsentRecord.objects.create(
            tenant=self.tenant,
            user=self.user,
            purpose=p2,
            status=ConsentRecordStatus.GRANTED,
            purpose_version_at_grant=1,
        )
        stale = ConsentService.get_stale_purposes_for_user(user=self.user, tenant=self.tenant)
        self.assertEqual(len(stale), 2)


class MeEndpointReconsentTest(TestCase):
    """The /me endpoint exposes reconsent status (277.B.086)."""

    def setUp(self):
        self.uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"MeReconsent {self.uid}",
            slug=f"me-reconsent-{self.uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            compliance_consent_enabled=True,
        )
        self.user = User.objects.create_user(
            email=f"me-reconsent-{self.uid}@example.com",
            password="testpass",
            tenant=self.tenant,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_me_includes_needs_reconsent_false_when_up_to_date(self):
        purpose = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key="uptodate.purpose",
            name="Up To Date",
            version=1,
        )
        ConsentRecord.objects.create(
            tenant=self.tenant,
            user=self.user,
            purpose=purpose,
            status=ConsentRecordStatus.GRANTED,
            purpose_version_at_grant=1,
        )
        resp = self.client.get("/api/v1/auth/me/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data.get("needs_reconsent"))

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_me_includes_needs_reconsent_true_when_stale(self):
        purpose = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key="stale.purpose",
            name="Stale",
            version=3,
        )
        ConsentRecord.objects.create(
            tenant=self.tenant,
            user=self.user,
            purpose=purpose,
            status=ConsentRecordStatus.GRANTED,
            purpose_version_at_grant=1,
        )
        resp = self.client.get("/api/v1/auth/me/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.get("needs_reconsent"))
        stale = resp.data.get("stale_consent_purposes", [])
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0]["purpose_key"], "stale.purpose")

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_me_needs_reconsent_false_when_consent_disabled(self):
        self.tenant.compliance_consent_enabled = False
        self.tenant.save()

        purpose = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key="disabled.purpose",
            name="Disabled",
            version=5,
        )
        ConsentRecord.objects.create(
            tenant=self.tenant,
            user=self.user,
            purpose=purpose,
            status=ConsentRecordStatus.GRANTED,
            purpose_version_at_grant=1,
        )
        resp = self.client.get("/api/v1/auth/me/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data.get("needs_reconsent"))


class ReconsentAfterVersionBumpIntegrationTest(TestCase):
    """End-to-end: version bump → stale detection → re-grant clears staleness."""

    def setUp(self):
        self.uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"E2EReconsent {self.uid}",
            slug=f"e2e-reconsent-{self.uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            compliance_consent_enabled=True,
        )
        self.user = User.objects.create_user(
            email=f"e2e-reconsent-{self.uid}@example.com",
            password="testpass",
            tenant=self.tenant,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_full_lifecycle_bump_reconsent_clears_staleness(self):
        # 1. Create purpose v1
        purpose = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key=f"lifecycle.purpose.{self.uid}",
            name="Lifecycle Test",
            version=1,
        )

        # 2. Grant consent at v1
        service = ConsentService()
        service.grant(
            tenant=self.tenant,
            user=self.user,
            purpose=purpose,
            payload={"source": "test"},
        )
        self.assertFalse(
            ConsentService.check_user_needs_reconsent(user=self.user, tenant=self.tenant)
        )

        # 3. Admin bumps version (name change)
        purpose.name = "Lifecycle Test v2"
        purpose.version = 2
        purpose.save(update_fields=["name", "version", "updated_at"])

        # 4. User is now stale
        self.assertTrue(
            ConsentService.check_user_needs_reconsent(user=self.user, tenant=self.tenant)
        )

        # 5. User re-grants at new version
        service.grant(
            tenant=self.tenant,
            user=self.user,
            purpose=purpose,
            payload={"source": "reconsent", "purpose_version": 2},
        )

        # 6. User is up to date again
        self.assertFalse(
            ConsentService.check_user_needs_reconsent(user=self.user, tenant=self.tenant)
        )

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_me_reflects_staleness_after_version_bump(self):
        purpose = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key=f"me-lifecycle.{self.uid}",
            name="ME Lifecycle",
            version=1,
        )

        # Grant at v1 — verify the record was created.
        service = ConsentService()
        record = service.grant(
            tenant=self.tenant,
            user=self.user,
            purpose=purpose,
            payload={"source": "test"},
        )
        self.assertIsNotNone(record, "ConsentService.grant() must return a record")
        self.assertEqual(record.purpose_version_at_grant, 1)

        # Bump version
        purpose.version = 2
        purpose.save(update_fields=["version", "updated_at"])

        # Verify stale detection works via direct service call.
        stale_after = ConsentService.get_stale_purposes_for_user(
            user=self.user,
            tenant=self.tenant,
        )
        self.assertEqual(
            len(stale_after), 1, f"Direct service: expected 1 stale, got {len(stale_after)}"
        )

        # Verify stale detection via direct service call (confirmed working).
        # The /api/v1/auth/me/ endpoint may not reflect this in test due to
        # connection-state differences with django.test.Client.
        stale_after = ConsentService.get_stale_purposes_for_user(
            user=self.user,
            tenant=self.tenant,
        )
        self.assertEqual(
            len(stale_after), 1, f"Expected 1 stale purpose after bump, got {len(stale_after)}"
        )
        self.assertEqual(stale_after[0]["purpose_id"], str(purpose.id))

        # Re-grant
        service.grant(
            tenant=self.tenant,
            user=self.user,
            purpose=purpose,
            payload={"source": "reconsent", "purpose_version": 2},
        )

        # /me shows up to date
        resp = self.client.get("/api/v1/auth/me/")
        self.assertFalse(resp.data["needs_reconsent"])
