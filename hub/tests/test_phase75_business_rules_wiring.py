"""
Phase 75 — BR-08: Unused Business Rules Cleanup & Social View Fix

Tests confirming that:
75.1  NotificationsBusinessRules are called by send_email_async()
75.2  SearchBusinessRules are called by SearchService.search()
75.3  SocialService.update_community() calls SocialBusinessRules
      and CommunityViewSet.partial_update() no longer calls
      serializer.save() directly
"""
import uuid

import pytest
from django.test import TestCase

from hub.apps.core.services.base import (
    NotFoundError,
    ValidationError as ServiceValidationError,
)
from hub.apps.social.models import Community
from hub.apps.social.services import SocialService
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.testing.billing_support import (
    ensure_tenant_has_active_subscription,
)
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


# ── 75.1  NotificationsBusinessRules wired into tasks ──────────


class NotificationsBusinessRulesWiringTest(TestCase):
    """Confirm NotificationsBusinessRules.validate() is called
    before emails are sent by send_email_async()."""

    def test_send_email_async_rejects_invalid_recipient(self):
        """send_email_async raises ValueError when recipient
        email is clearly invalid (business-rule check)."""
        from hub.apps.notifications.tasks import send_email_async

        with self.assertRaises(ValueError) as cm:
            send_email_async(
                email_type="USER_INVITATION",
                to_email="not-an-email",
                subject="Test",
                template_name=(
                    "notifications/emails/user_invitation.html"
                ),
                context={},
                tenant_id=None,
                user_id=None,
            )
        self.assertIn("validation failed", str(cm.exception).lower())

    def test_send_email_async_rejects_empty_recipient(self):
        """send_email_async raises ValueError when recipient
        email is empty (business-rule check)."""
        from hub.apps.notifications.tasks import send_email_async

        with self.assertRaises(ValueError) as cm:
            send_email_async(
                email_type="USER_INVITATION",
                to_email="",
                subject="Test",
                template_name=(
                    "notifications/emails/user_invitation.html"
                ),
                context={},
            )
        self.assertIn("validation failed", str(cm.exception).lower())

    def test_notifications_business_rules_registered_in_app(self):
        """NotificationsBusinessRules is registered in the
        business-rules registry (wired via apps.py)."""
        from hub.apps.core.business_rules.registry import (
            get_registry,
        )

        registry = get_registry()
        rule = registry.get_rule("notifications_validation")
        self.assertIsNotNone(
            rule,
            "notifications_validation rule must be registered",
        )


# ── 75.2  SearchBusinessRules wired into SearchService ─────────


class SearchBusinessRulesWiringTest(TestCase):
    """Confirm SearchBusinessRules.validate() is called
    by SearchService.search()."""

    def setUp(self):
        # Disconnect semantic signals to prevent timeouts
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import (
                asset_saved,
                contract_saved,
            )

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            pass

        self.tenant = Tenant.objects.create(
            name="Search BR Test",
            slug="search-br-test",
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email="search-br@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_search_service_validates_query_via_business_rules(
        self,
    ):
        """SearchService.search() rejects dangerous queries
        that SearchBusinessRules flags (e.g. SQL injection)."""
        from hub.apps.search.services import SearchService

        service = SearchService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # A query containing SQL DDL should be rejected by
        # SearchBusinessRules._validate_query_security().
        with self.assertRaises(ServiceValidationError):
            service.search(
                tenant_id=str(self.tenant.id),
                query="DROP TABLE users; --",
            )

    def test_search_business_rules_registered_in_app(self):
        """SearchBusinessRules is registered via apps.py."""
        from hub.apps.core.business_rules.registry import (
            get_registry,
        )

        registry = get_registry()
        rule = registry.get_rule("search_validation")
        self.assertIsNotNone(
            rule,
            "search_validation rule must be registered",
        )

    def test_search_service_import_references_business_rules(
        self,
    ):
        """SearchService module imports SearchBusinessRules."""
        import hub.apps.search.services as svc_module
        import inspect

        source = inspect.getsource(svc_module)
        self.assertIn(
            "SearchBusinessRules",
            source,
            "SearchService must import SearchBusinessRules",
        )


# ── 75.3  SocialService.update_community() + view fix ─────────


class SocialUpdateCommunityTest(TestCase):
    """Confirm SocialService.update_community() calls
    SocialBusinessRules.validate() before mutation, and
    CommunityViewSet.partial_update() routes through the
    service (no direct serializer.save())."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Social BR Test",
            slug="social-br-test",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.creator = User.objects.create_user(
            email="creator@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.community = Community.objects.create(
            tenant=self.tenant,
            name="Phase 75 Community",
            created_by=self.creator,
        )
        self.service = SocialService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.creator.id),
        )

    # ── Happy path ──

    def test_update_community_success(self):
        """Creator can update community name and description
        via SocialService.update_community()."""
        updated = self.service.update_community(
            tenant_id=str(self.tenant.id),
            user_id=str(self.creator.id),
            community_id=str(self.community.id),
            update_data={
                "name": "Renamed Community",
                "description": "New description",
            },
        )
        self.assertEqual(updated.name, "Renamed Community")
        self.assertEqual(updated.description, "New description")

    def test_update_community_emits_audit_event(self):
        """update_community() emits a COMMUNITY_UPDATED audit
        event."""
        from hub.apps.audit.models import AuditEvent

        self.service.update_community(
            tenant_id=str(self.tenant.id),
            user_id=str(self.creator.id),
            community_id=str(self.community.id),
            update_data={"name": "Audited Community"},
        )
        events = AuditEvent.objects.filter(
            resource_type="COMMUNITY",
            action="COMMUNITY_UPDATED",
            resource_id=str(self.community.id),
        )
        self.assertEqual(events.count(), 1)

    # ── Business-rule enforcement ──

    def test_update_community_rejects_non_creator(self):
        """Only the community creator can update it."""
        other_service = SocialService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.other_user.id),
        )
        with self.assertRaises(ServiceValidationError) as cm:
            other_service.update_community(
                tenant_id=str(self.tenant.id),
                user_id=str(self.other_user.id),
                community_id=str(self.community.id),
                update_data={"name": "Hijacked"},
            )
        self.assertIn("creator", str(cm.exception).lower())

    def test_update_community_rejects_short_name(self):
        """Name shorter than 3 characters is rejected."""
        with self.assertRaises(ServiceValidationError) as cm:
            self.service.update_community(
                tenant_id=str(self.tenant.id),
                user_id=str(self.creator.id),
                community_id=str(self.community.id),
                update_data={"name": "ab"},
            )
        self.assertIn("3 characters", str(cm.exception))

    def test_update_community_rejects_not_found(self):
        """Non-existent community raises NotFoundError."""
        with self.assertRaises(NotFoundError):
            self.service.update_community(
                tenant_id=str(self.tenant.id),
                user_id=str(self.creator.id),
                community_id=str(uuid.uuid4()),
                update_data={"name": "Ghost"},
            )

    def test_update_community_rejects_long_description(self):
        """Description over 500 characters is rejected."""
        with self.assertRaises(ServiceValidationError) as cm:
            self.service.update_community(
                tenant_id=str(self.tenant.id),
                user_id=str(self.creator.id),
                community_id=str(self.community.id),
                update_data={"description": "x" * 501},
            )
        self.assertIn("500", str(cm.exception))

    def test_update_community_duplicate_name_raises_validation(
        self,
    ):
        """Renaming to a name that already exists in the tenant
        raises ValidationError (not IntegrityError / 500)."""
        Community.objects.create(
            tenant=self.tenant,
            name="Existing Name",
            created_by=self.creator,
        )
        with self.assertRaises(ServiceValidationError) as cm:
            self.service.update_community(
                tenant_id=str(self.tenant.id),
                user_id=str(self.creator.id),
                community_id=str(self.community.id),
                update_data={"name": "Existing Name"},
            )
        self.assertIn("already exists", str(cm.exception).lower())

    def test_update_community_no_creator_rejects_update(self):
        """A community with created_by=None cannot be updated
        by anyone — the business rule should reject it."""
        orphan = Community.objects.create(
            tenant=self.tenant,
            name="Orphan Community",
            created_by=None,
        )
        with self.assertRaises(ServiceValidationError) as cm:
            self.service.update_community(
                tenant_id=str(self.tenant.id),
                user_id=str(self.creator.id),
                community_id=str(orphan.id),
                update_data={"name": "Should Fail"},
            )
        self.assertIn("no creator", str(cm.exception).lower())

    def test_update_community_is_public_toggle(self):
        """is_public field can be toggled via update_community()."""
        self.assertTrue(self.community.is_public)
        updated = self.service.update_community(
            tenant_id=str(self.tenant.id),
            user_id=str(self.creator.id),
            community_id=str(self.community.id),
            update_data={"is_public": False},
        )
        self.assertFalse(updated.is_public)

    # ── View does NOT call serializer.save() ──

    def test_view_partial_update_no_direct_serializer_save(self):
        """CommunityViewSet.partial_update() must not call
        serializer.save() — it routes through the service."""
        import inspect
        from hub.apps.social.views import CommunityViewSet

        source = inspect.getsource(
            CommunityViewSet.partial_update,
        )
        self.assertNotIn(
            "serializer.save()",
            source,
            "partial_update must not call serializer.save() "
            "directly — it should route through "
            "SocialService.update_community()",
        )

    def test_view_partial_update_calls_service(self):
        """CommunityViewSet.partial_update() references
        SocialService.update_community()."""
        import inspect
        from hub.apps.social.views import CommunityViewSet

        source = inspect.getsource(
            CommunityViewSet.partial_update,
        )
        self.assertIn(
            "update_community",
            source,
            "partial_update must delegate to "
            "service.update_community()",
        )
