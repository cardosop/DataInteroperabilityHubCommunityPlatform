import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from hub.apps.audit.models import AuditEvent
from hub.apps.audit.utils import create_audit_event, redact_fail_closed_audit_payload
from hub.apps.tenants.models import Tenant
from hub.apps.testing.role_support import ensure_user_has_tenant_admin_role
from hub.apps.users.models import Role, UserRole
from hub.apps.users.models import UserStatus


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class FailClosedAuditRedactionTest(TestCase):
    def test_redaction_hashes_column_names_and_keeps_categories(self) -> None:
        payload = {
            "gate": "compliance",
            "compliance": {
                "column_findings_json": [
                    {
                        "column": "customer_email_address",
                        "categories": ["PII_DIRECT_EMAIL"],
                        "sample_value": "alice@example.com",
                    },
                    {
                        "column_name": "home_phone_number",
                        "categories": ["PII_DIRECT_PHONE"],
                        "sample_data_json": [{"home_phone_number": "+15551234567"}],
                    },
                ],
                "data": {"raw_data": "must_not_leak"},
            },
        }

        redacted = redact_fail_closed_audit_payload(payload)

        findings = redacted["compliance"]["column_findings_json"]
        assert findings[0]["column"] != "customer_email_address"
        assert findings[1]["column_name"] != "home_phone_number"
        assert findings[0]["categories"] == ["PII_DIRECT_EMAIL"]
        assert findings[1]["categories"] == ["PII_DIRECT_PHONE"]
        assert "sample_value" not in findings[0]
        assert "sample_data_json" not in findings[1]
        assert "data" not in redacted["compliance"]

    def test_get_full_details_requires_tenant_admin(self) -> None:
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"Tenant {uid}",
            slug=f"tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        admin = User.objects.create(
            email=f"admin-{uid}@example.com",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        plain = User.objects.create(
            email=f"plain-{uid}@example.com",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        ensure_user_has_tenant_admin_role(admin)

        event = create_audit_event(
            resource_type="ASSET",
            action="ASSET_FAIL_CLOSED_REJECTED",
            actor_user=admin,
            tenant=tenant,
            result="FAILURE",
            details={"gate": "compliance", "column_hashes": ["sha256:deadbeef"]},
            full_details={
                "gate": "compliance",
                "column_findings_json": [{"column": "customer_email_address"}],
            },
        )
        assert isinstance(event, AuditEvent)

        with self.assertRaises(PermissionDenied):
            event.get_full_details(plain)

        full_details = event.get_full_details(admin)
        self.assertEqual(
            full_details["column_findings_json"][0]["column"],
            "customer_email_address",
        )

    def test_get_full_details_denies_platform_admin_without_tenant_admin_role(self) -> None:
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"Tenant {uid}",
            slug=f"tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        admin = User.objects.create(
            email=f"admin2-{uid}@example.com",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        ensure_user_has_tenant_admin_role(admin)
        platform_admin = User.objects.create(
            email=f"platform-{uid}@example.com",
            tenant=None,
            status=UserStatus.ACTIVE,
            is_platform_admin=True,
        )
        event = create_audit_event(
            resource_type="ASSET",
            action="ASSET_FAIL_CLOSED_REJECTED",
            actor_user=admin,
            tenant=tenant,
            result="FAILURE",
            details={"gate": "compliance"},
            full_details={"column_findings_json": [{"column": "raw_column"}]},
        )

        with self.assertRaises(PermissionDenied):
            event.get_full_details(platform_admin)

    def test_get_full_details_denies_other_tenant_admin(self) -> None:
        uid = uuid.uuid4().hex[:8]
        tenant_a = Tenant.objects.create(
            name=f"TenantA {uid}",
            slug=f"tenant-a-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        tenant_b = Tenant.objects.create(
            name=f"TenantB {uid}",
            slug=f"tenant-b-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        owner_admin = User.objects.create(
            email=f"owner-{uid}@example.com",
            tenant=tenant_a,
            status=UserStatus.ACTIVE,
        )
        ensure_user_has_tenant_admin_role(owner_admin)
        other_admin = User.objects.create(
            email=f"other-{uid}@example.com",
            tenant=tenant_b,
            status=UserStatus.ACTIVE,
        )
        role_b, _ = Role.objects.get_or_create(
            tenant=tenant_b,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(
            user=other_admin,
            tenant=tenant_b,
            role=role_b,
        )
        event = create_audit_event(
            resource_type="ASSET",
            action="ASSET_FAIL_CLOSED_REJECTED",
            actor_user=owner_admin,
            tenant=tenant_a,
            result="FAILURE",
            details={"gate": "compliance"},
            full_details={"column_findings_json": [{"column": "raw_column"}]},
        )

        with self.assertRaises(PermissionDenied):
            event.get_full_details(other_admin)
