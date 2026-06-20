import uuid

import jwt
import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.audit import event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.auth import sso_state
from hub.apps.auth.jwt_utils import JWTTokenGenerator
from hub.apps.observability.cross_tenant_metrics import cross_tenant_denied_total
from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.users.models import User, UserStatus, UserTenantMembership

pytestmark = pytest.mark.django_db(transaction=True)


class SSOStateBindingOIDCTest(TestCase):
    def setUp(self) -> None:
        uid = uuid.uuid4().hex[:8]
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name=f"Tenant {uid}",
            slug=f"tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.other_tenant = Tenant.objects.create(
            name=f"TenantB {uid}",
            slug=f"tenant-b-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        TenantConfig.objects.create(
            tenant=self.tenant,
            sso_config={
                "oidc": {
                    "authorization_endpoint": "https://idp.example.com/auth",
                    "client_id": "client-1",
                    "role_mapping": {},
                }
            },
        )

    def _id_token(self, email: str) -> str:
        return jwt.encode(
            {"sub": f"sub-{email}", "email": email},
            "local-test-secret-with-sufficient-length-for-hs256",
            algorithm="HS256",
        )

    @staticmethod
    def _response_error_text(response) -> str:
        body = response.json()
        if isinstance(body.get("error"), dict):
            err = body["error"]
            return " ".join(
                str(part)
                for part in (
                    err.get("code"),
                    err.get("message"),
                    err.get("detail"),
                )
                if part
            )
        if body.get("error") is not None:
            return str(body.get("error"))
        if body.get("detail") is not None:
            return str(body.get("detail"))
        return str(body)

    @staticmethod
    def _counter_value() -> float:
        labeled = cross_tenant_denied_total.labels(
            endpoint="auth.sso_callback",
            reason="body_tenant_mismatch",
        )
        value = getattr(labeled, "_value", None)
        if value is None or not hasattr(value, "get"):
            return 0.0
        return float(value.get())

    def test_tampered_body_tenant_id_returns_400_and_audit(self) -> None:
        state = sso_state.issue_state(str(self.tenant.id), "private")
        before = AuditEvent.objects.filter(action=event_types.CROSS_TENANT_DENIED).count()
        before_counter = self._counter_value()

        response = self.client.post(
            "/api/v1/auth/sso/oidc/callback/",
            {
                "id_token": self._id_token("tamper@example.com"),
                "state": state,
                "tenant_id": str(self.other_tenant.id),
            },
            format="json",
            REMOTE_ADDR="10.1.2.3",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "SSO_STATE_TENANT_MISMATCH",
            self._response_error_text(response),
        )
        after = AuditEvent.objects.filter(action=event_types.CROSS_TENANT_DENIED).count()
        self.assertEqual(after, before + 1)
        after_counter = self._counter_value()
        self.assertGreaterEqual(after_counter - before_counter, 1.0)

    def test_saml_tampered_body_tenant_id_returns_400_and_audit(self) -> None:
        state = sso_state.issue_state(str(self.tenant.id), "private")
        before = AuditEvent.objects.filter(
            action=event_types.CROSS_TENANT_DENIED,
        ).count()
        before_counter = self._counter_value()

        response = self.client.post(
            "/api/v1/auth/sso/saml/callback/",
            {
                # _extract_unverified_saml_identity supports best-effort
                # extraction from raw text, so an email marker is enough
                # for routing fallback logic.
                "SAMLResponse": "nameid=saml-tamper@example.com",
                "RelayState": state,
                "tenant_id": str(self.other_tenant.id),
            },
            format="json",
            REMOTE_ADDR="10.2.3.4",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "SSO_STATE_TENANT_MISMATCH",
            self._response_error_text(response),
        )
        after = AuditEvent.objects.filter(
            action=event_types.CROSS_TENANT_DENIED,
        ).count()
        self.assertEqual(after, before + 1)
        after_counter = self._counter_value()
        self.assertGreaterEqual(after_counter - before_counter, 1.0)

    def test_valid_state_returns_200_and_token_for_state_tenant(self) -> None:
        state = sso_state.issue_state(str(self.tenant.id), "private")
        response = self.client.post(
            "/api/v1/auth/sso/oidc/callback/",
            {
                "id_token": self._id_token("ok@example.com"),
                "state": state,
            },
            format="json",
            REMOTE_ADDR="10.9.8.7",
        )
        self.assertEqual(response.status_code, 200)
        access_token = response.json().get("access_token")
        self.assertTrue(access_token)
        payload = JWTTokenGenerator.decode_access_token(access_token)
        assert payload is not None
        self.assertEqual(payload.get("tenant_id"), str(self.tenant.id))

    def test_replayed_state_returns_400_sso_state_reused(self) -> None:
        state = sso_state.issue_state(str(self.tenant.id), "private")
        first = self.client.post(
            "/api/v1/auth/sso/oidc/callback/",
            {
                "id_token": self._id_token("replay@example.com"),
                "state": state,
            },
            format="json",
            REMOTE_ADDR="10.0.0.2",
        )
        self.assertEqual(first.status_code, 200)

        second = self.client.post(
            "/api/v1/auth/sso/oidc/callback/",
            {
                "id_token": self._id_token("replay@example.com"),
                "state": state,
            },
            format="json",
            REMOTE_ADDR="10.0.0.2",
        )
        self.assertEqual(second.status_code, 400)
        self.assertIn("SSO_STATE_REUSED", self._response_error_text(second))

    def test_state_with_different_ip_class_returns_400(self) -> None:
        state = sso_state.issue_state(str(self.tenant.id), "private")
        response = self.client.post(
            "/api/v1/auth/sso/oidc/callback/",
            {
                "id_token": self._id_token("ip-mismatch@example.com"),
                "state": state,
            },
            format="json",
            REMOTE_ADDR="8.8.8.8",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("SSO_STATE_IP_MISMATCH", self._response_error_text(response))

    def test_oidc_login_url_contains_signed_state_query_param(self) -> None:
        response = self.client.get(
            "/api/v1/auth/sso/oidc/login-url/",
            {"tenant_id": str(self.tenant.id), "redirect_uri": "https://app.example.com/cb"},
            REMOTE_ADDR="10.0.0.10",
        )
        self.assertEqual(response.status_code, 200)
        login_url = response.json().get("login_url", "")
        self.assertIn("state=", login_url)

    def test_saml_login_url_contains_signed_relay_state(self) -> None:
        TenantConfig.objects.filter(tenant=self.tenant).update(
            sso_config={
                "saml": {"sso_url": "https://idp.example.com/saml", "role_mapping": {}},
                "oidc": {
                    "authorization_endpoint": "https://idp.example.com/auth",
                    "client_id": "client-1",
                    "role_mapping": {},
                },
            }
        )
        response = self.client.get(
            "/api/v1/auth/sso/saml/login-url/",
            {"tenant_id": str(self.tenant.id), "redirect_uri": "https://app.example.com/cb"},
            REMOTE_ADDR="10.0.0.10",
        )
        self.assertEqual(response.status_code, 200)
        login_url = response.json().get("login_url", "")
        self.assertIn("RelayState=", login_url)

    def test_missing_state_with_multi_membership_returns_ambiguous(self) -> None:
        user = User.objects.create(
            email=f"multi-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.get_or_create(user=user, tenant=self.tenant)
        UserTenantMembership.objects.get_or_create(user=user, tenant=self.other_tenant)

        response = self.client.post(
            "/api/v1/auth/sso/oidc/callback/",
            {
                "id_token": self._id_token(user.email),
            },
            format="json",
            REMOTE_ADDR="10.0.0.4",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("SSO_TENANT_AMBIGUOUS", self._response_error_text(response))

    def test_invalid_state_does_not_fallback_to_membership(self) -> None:
        user = User.objects.create(
            email=f"single-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.get_or_create(user=user, tenant=self.tenant)

        response = self.client.post(
            "/api/v1/auth/sso/oidc/callback/",
            {
                "id_token": self._id_token(user.email),
                "state": "invalid-state",
            },
            format="json",
            REMOTE_ADDR="10.0.0.5",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("SSO_STATE_INVALID", self._response_error_text(response))

    def test_missing_state_with_single_membership_falls_back(self) -> None:
        user = User.objects.create(
            email=f"fallback-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.get_or_create(user=user, tenant=self.tenant)

        response = self.client.post(
            "/api/v1/auth/sso/oidc/callback/",
            {"id_token": self._id_token(user.email)},
            format="json",
            REMOTE_ADDR="10.0.0.6",
        )
        self.assertEqual(response.status_code, 200)
        access_token = response.json().get("access_token")
        self.assertTrue(access_token)
        payload = JWTTokenGenerator.decode_access_token(access_token)
        assert payload is not None
        self.assertEqual(payload.get("tenant_id"), str(self.tenant.id))
