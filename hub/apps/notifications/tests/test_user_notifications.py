"""In-app notification tests (Phase 223.1).

Covers the model, utility helper, and all four REST endpoints end-to-end
using the real ORM + DRF stack — no mocks.
"""
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status as http_status
from rest_framework.test import APIClient

from hub.apps.notifications.models import (
    NotificationCategory,
    NotificationType,
    UserNotification,
)
from hub.apps.notifications.utils import create_user_notification
from hub.apps.tenants.models import KYCStatus, Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class UserNotificationUtilTest(TestCase):
    """Unit tests for `create_user_notification`."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {uid}",
            slug=f"t-{uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"u-{uid}@example.com",
            password="x",
            tenant=self.tenant,
        )

    def test_creates_minimal_notification(self):
        row = create_user_notification(
            user=self.user,
            tenant=self.tenant,
            title="Hello",
            message="Test body",
        )
        self.assertIsNotNone(row)
        self.assertEqual(row.user, self.user)
        self.assertEqual(row.tenant, self.tenant)
        self.assertEqual(row.title, "Hello")
        self.assertEqual(row.notification_type, NotificationType.INFO)
        self.assertEqual(row.category, NotificationCategory.SYSTEM)
        self.assertFalse(row.read)
        self.assertIsNone(row.read_at)

    def test_coerces_lowercase_type_and_category(self):
        row = create_user_notification(
            user=self.user,
            tenant=self.tenant,
            title="x",
            message="y",
            notification_type="success",
            category="governance",
        )
        self.assertEqual(row.notification_type, NotificationType.SUCCESS)
        self.assertEqual(row.category, NotificationCategory.GOVERNANCE)

    def test_invalid_type_and_category_fall_back_to_defaults(self):
        row = create_user_notification(
            user=self.user,
            tenant=self.tenant,
            title="x",
            message="y",
            notification_type="PLAID",
            category="MADE_UP",
        )
        self.assertEqual(row.notification_type, NotificationType.INFO)
        self.assertEqual(row.category, NotificationCategory.SYSTEM)

    def test_accepts_uuid_resource_id_as_string(self):
        rid = uuid.uuid4()
        row = create_user_notification(
            user=self.user,
            tenant=self.tenant,
            title="x",
            message="y",
            resource_type="ASSET",
            resource_id=str(rid),
        )
        self.assertEqual(row.resource_id, rid)

    def test_non_uuid_resource_id_is_silently_dropped(self):
        row = create_user_notification(
            user=self.user,
            tenant=self.tenant,
            title="x",
            message="y",
            resource_id="not-a-uuid",
        )
        self.assertIsNotNone(row)
        self.assertIsNone(row.resource_id)

    def test_returns_none_when_user_missing(self):
        self.assertIsNone(
            create_user_notification(
                user=None, tenant=self.tenant, title="t", message="m"
            )
        )

    def test_mark_read_is_idempotent(self):
        row = create_user_notification(
            user=self.user, tenant=self.tenant, title="t", message="m"
        )
        row.mark_read()
        ts = row.read_at
        row.mark_read()  # second call must not bump read_at
        row.refresh_from_db()
        self.assertTrue(row.read)
        self.assertEqual(row.read_at, ts)


class UserNotificationViewSetTest(TestCase):
    """End-to-end tests for the REST endpoints."""

    URL_LIST = "/api/v1/notifications/user-notifications/"
    URL_UNREAD = "/api/v1/notifications/user-notifications/unread-count/"
    URL_READ_ALL = "/api/v1/notifications/user-notifications/read-all/"

    def setUp(self):
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {uid}",
            slug=f"t-{uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.other_tenant = Tenant.objects.create(
            name=f"O {uid}",
            slug=f"o-{uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        # Ensure active subscription so TenantSuspensionMiddleware allows
        # POST/PUT/PATCH/DELETE (required by Phase 25.2.4 billing check).
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        ensure_tenant_has_active_subscription(self.tenant)
        ensure_tenant_has_active_subscription(self.other_tenant)

        self.user = User.objects.create_user(
            email=f"u-{uid}@example.com", password="x", tenant=self.tenant
        )
        self.other_user = User.objects.create_user(
            email=f"o-{uid}@example.com", password="x", tenant=self.other_tenant
        )

    def _mk(self, user=None, tenant=None, read=False, **kw):
        return UserNotification.objects.create(
            user=user or self.user,
            tenant=tenant or self.tenant,
            title=kw.pop("title", "t"),
            message=kw.pop("message", "m"),
            read=read,
            **kw,
        )

    def test_list_requires_authentication(self):
        response = self.client.get(self.URL_LIST)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_list_returns_only_callers_rows(self):
        mine = self._mk()
        self._mk(user=self.other_user, tenant=self.other_tenant)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL_LIST)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        ids = [row["id"] for row in response.data["results"]]
        self.assertIn(str(mine.id), ids)
        self.assertEqual(len(ids), 1)

    def test_list_filter_by_read(self):
        self._mk(read=False, title="unread")
        self._mk(read=True, title="read")
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL_LIST + "?read=false")
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "unread")

    def test_unread_count_counts_only_unread(self):
        self._mk(read=False)
        self._mk(read=False)
        self._mk(read=True)
        self._mk(user=self.other_user, tenant=self.other_tenant)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL_UNREAD)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data, {"count": 2})

    def test_mark_read_flips_single_row(self):
        row = self._mk(read=False)
        self.client.force_authenticate(user=self.user)
        url = f"{self.URL_LIST}{row.id}/read/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertTrue(response.data["read"])
        row.refresh_from_db()
        self.assertTrue(row.read)
        self.assertIsNotNone(row.read_at)

    def test_mark_read_isolation_cross_user_returns_404(self):
        row = self._mk(user=self.other_user, tenant=self.other_tenant, read=False)
        self.client.force_authenticate(user=self.user)
        url = f"{self.URL_LIST}{row.id}/read/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_mark_all_read(self):
        self._mk(read=False)
        self._mk(read=False)
        self._mk(read=True)
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.URL_READ_ALL)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data["updated"], 2)
        self.assertEqual(
            UserNotification.objects.filter(user=self.user, read=False).count(), 0
        )

    def test_mark_all_read_does_not_touch_other_users(self):
        mine = self._mk(read=False)
        theirs = self._mk(user=self.other_user, tenant=self.other_tenant, read=False)
        self.client.force_authenticate(user=self.user)
        self.client.post(self.URL_READ_ALL)
        mine.refresh_from_db()
        theirs.refresh_from_db()
        self.assertTrue(mine.read)
        self.assertFalse(theirs.read)
