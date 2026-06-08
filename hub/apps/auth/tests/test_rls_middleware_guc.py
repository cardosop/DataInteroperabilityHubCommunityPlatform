import pytest
import json
import uuid

from django.db import connection
from django.http import JsonResponse
from django.test import RequestFactory, TestCase, override_settings

from hub.apps.auth.middleware import TenantScopingMiddleware
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User
from hub.apps.users.services import UserTenantMembershipService

pytestmark = pytest.mark.django_db(transaction=True)


def _normalize_guc(value):
    return value or None


def _capture_rls_gucs_response(_request):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
              current_setting('app.current_tenant_id', true),
              current_setting('app.rls_assets_enabled', true),
              current_setting('app.rls_files_enabled', true)
            """
        )
        tenant_id, assets_flag, files_flag = cursor.fetchone()
    return JsonResponse(
        {
            "tenant_id": _normalize_guc(tenant_id),
            "rls_assets_enabled": _normalize_guc(assets_flag),
            "rls_files_enabled": _normalize_guc(files_flag),
        }
    )


class RLSMiddlewareGUCTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = TenantScopingMiddleware(_capture_rls_gucs_response)

        uid = uuid.uuid4().hex[:8]
        self.tenant_a = Tenant.objects.create(
            name=f"RLS Middleware A {uid}",
            slug=f"rls-mid-a-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.tenant_b = Tenant.objects.create(
            name=f"RLS Middleware B {uid}",
            slug=f"rls-mid-b-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(  # type: ignore[attr-defined]  # test: edge-case type exercise
            email=f"rls-mid-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant_a,
        )
        UserTenantMembershipService().add_membership(self.user, self.tenant_a)
        UserTenantMembershipService().add_membership(self.user, self.tenant_b)

    def _json(self, response):
        return json.loads(response.content.decode("utf-8"))

    @pytest.mark.integration
    def test_anonymous_request_keeps_tenant_guc_unset(self):
        request = self.factory.get("/api/v1/assets/")

        response = self.middleware(request)

        payload = self._json(response)
        self.assertIsNone(payload["tenant_id"])

    @pytest.mark.integration
    def test_authenticated_request_sets_tenant_guc_to_request_tenant(self):
        request = self.factory.get("/api/v1/assets/")
        request.user = self.user

        response = self.middleware(request)

        payload = self._json(response)
        self.assertEqual(payload["tenant_id"], str(self.tenant_a.id))

    @pytest.mark.integration
    def test_x_tenant_id_override_sets_tenant_guc_to_header_tenant(self):
        request = self.factory.get(
            "/api/v1/assets/",
            HTTP_X_TENANT_ID=str(self.tenant_b.id),
        )
        request.user = self.user

        response = self.middleware(request)

        payload = self._json(response)
        self.assertEqual(payload["tenant_id"], str(self.tenant_b.id))

    @override_settings(RLS_ASSETS_ENABLED=True, RLS_FILES_ENABLED=False)
    @pytest.mark.integration
    def test_rls_table_flags_are_applied_from_settings(self):
        request = self.factory.get("/api/v1/assets/")
        request.user = self.user

        response = self.middleware(request)

        payload = self._json(response)
        self.assertEqual(payload["rls_assets_enabled"], "on")
        self.assertEqual(payload["rls_files_enabled"], "off")

    @override_settings(RLS_ASSETS_ENABLED=True, RLS_FILES_ENABLED=False)
    @pytest.mark.integration
    def test_rls_table_flags_are_applied_for_anonymous_requests(self):
        request = self.factory.get("/api/v1/assets/")

        response = self.middleware(request)

        payload = self._json(response)
        self.assertIsNone(payload["tenant_id"])
        self.assertEqual(payload["rls_assets_enabled"], "on")
        self.assertEqual(payload["rls_files_enabled"], "off")
