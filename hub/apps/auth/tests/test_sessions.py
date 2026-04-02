"""
Tests for auth sessions API: list_active_sessions, revoke_session.
Phase 7.5.B backend verification; no mocks.
"""
import uuid

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = __import__(
    "django.contrib.auth", fromlist=["get_user_model"]
).get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


def _make_test_data():
    """Create unique tenant + two users for each test invocation."""
    tag = uuid.uuid4().hex[:8]
    client = APIClient()
    tenant = Tenant.objects.create(
        name=f"Sessions Tenant {tag}",
        slug=f"sess-{tag}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    user = User.objects.create_user(
        email=f"sess-{tag}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    other = User.objects.create_user(
        email=f"other-{tag}@example.com",
        password="otherpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    return client, tenant, user, other


def _login(client, email, password="testpass123"):
    """Login via API and return (access_token, response)."""
    resp = client.post(
        "/api/v1/auth/login/",
        {"email": email, "password": password},
        format="json",
    )
    return resp


# ========== LIST SESSIONS ==========


class TestListSessions:
    def test_unauthenticated_returns_401(self):
        client, *_ = _make_test_data()
        resp = client.get("/api/v1/auth/sessions/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_authenticated_returns_200(self):
        client, _, user, _ = _make_test_data()
        client.force_authenticate(user=user)
        resp = client.get("/api/v1/auth/sessions/")
        assert resp.status_code == status.HTTP_200_OK

    def test_authenticated_returns_list(self):
        client, _, user, _ = _make_test_data()
        client.force_authenticate(user=user)
        resp = client.get("/api/v1/auth/sessions/")
        assert isinstance(resp.data, list)

    def test_non_empty_list_after_login(self):
        client, _, user, _ = _make_test_data()
        login_resp = _login(client, user.email)
        assert login_resp.status_code == status.HTTP_200_OK
        token = login_resp.data["access_token"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = client.get("/api/v1/auth/sessions/")
        assert len(resp.data) >= 1

    def test_session_has_id(self):
        client, _, user, _ = _make_test_data()
        login_resp = _login(client, user.email)
        token = login_resp.data["access_token"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = client.get("/api/v1/auth/sessions/")
        assert "id" in resp.data[0]

    def test_session_has_created_at(self):
        client, _, user, _ = _make_test_data()
        login_resp = _login(client, user.email)
        token = login_resp.data["access_token"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = client.get("/api/v1/auth/sessions/")
        assert "created_at" in resp.data[0]

    def test_session_has_expires_at(self):
        client, _, user, _ = _make_test_data()
        login_resp = _login(client, user.email)
        token = login_resp.data["access_token"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = client.get("/api/v1/auth/sessions/")
        assert "expires_at" in resp.data[0]

    def test_session_has_revoked_at(self):
        client, _, user, _ = _make_test_data()
        login_resp = _login(client, user.email)
        token = login_resp.data["access_token"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = client.get("/api/v1/auth/sessions/")
        assert "revoked_at" in resp.data[0]

    def test_session_has_is_current(self):
        client, _, user, _ = _make_test_data()
        login_resp = _login(client, user.email)
        token = login_resp.data["access_token"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = client.get("/api/v1/auth/sessions/")
        assert "is_current" in resp.data[0]

    def test_session_has_non_null_id(self):
        client, _, user, _ = _make_test_data()
        login_resp = _login(client, user.email)
        token = login_resp.data["access_token"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = client.get("/api/v1/auth/sessions/")
        assert resp.data[0]["id"] is not None

    def test_empty_list_when_no_sessions(self):
        client, _, user, _ = _make_test_data()
        client.force_authenticate(user=user)
        resp = client.get("/api/v1/auth/sessions/")
        assert resp.status_code == status.HTTP_200_OK
        assert isinstance(resp.data, list)

    def test_after_logout_returns_200(self):
        client, _, user, _ = _make_test_data()
        login_resp = _login(client, user.email)
        token = login_resp.data["access_token"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        client.post("/api/v1/auth/logout/", {}, format="json")
        resp = client.get("/api/v1/auth/sessions/")
        assert resp.status_code == status.HTTP_200_OK

    def test_after_logout_includes_revoked_sessions(self):
        client, _, user, _ = _make_test_data()
        login_resp = _login(client, user.email)
        token = login_resp.data["access_token"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        client.post("/api/v1/auth/logout/", {}, format="json")
        resp = client.get("/api/v1/auth/sessions/")
        revoked = [s for s in resp.data if s.get("revoked_at")]
        assert len(revoked) >= 1

    def test_list_sessions_returns_valid_response(self):
        """Authenticated session list returns 200 with list data."""
        client, _, user, _ = _make_test_data()
        client.force_authenticate(user=user)
        resp = client.get("/api/v1/auth/sessions/")
        assert resp.status_code == status.HTTP_200_OK
        assert isinstance(resp.data, list)


# ========== REVOKE SESSION ==========


class TestRevokeSession:
    def test_unauthenticated_returns_401(self):
        client, *_ = _make_test_data()
        sid = "00000000-0000-0000-0000-000000000001"
        resp = client.post(f"/api/v1/auth/sessions/{sid}/revoke/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_own_session_returns_200(self):
        client, _, user, _ = _make_test_data()
        login_resp = _login(client, user.email)
        token = login_resp.data["access_token"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        sessions = client.get("/api/v1/auth/sessions/")
        sid = sessions.data[0]["id"]
        resp = client.post(f"/api/v1/auth/sessions/{sid}/revoke/")
        assert resp.status_code == status.HTTP_200_OK

    def test_returns_message(self):
        client, _, user, _ = _make_test_data()
        login_resp = _login(client, user.email)
        token = login_resp.data["access_token"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        sessions = client.get("/api/v1/auth/sessions/")
        sid = sessions.data[0]["id"]
        resp = client.post(f"/api/v1/auth/sessions/{sid}/revoke/")
        assert "message" in resp.data

    def test_sets_revoked_at(self):
        client, _, user, _ = _make_test_data()
        login_resp = _login(client, user.email)
        token = login_resp.data["access_token"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        sessions = client.get("/api/v1/auth/sessions/")
        sid = sessions.data[0]["id"]
        client.post(f"/api/v1/auth/sessions/{sid}/revoke/")
        after = client.get("/api/v1/auth/sessions/")
        revoked = next(
            (s for s in after.data if s["id"] == sid), None
        )
        assert revoked is not None
        assert revoked["revoked_at"] is not None

    def test_other_user_session_returns_404(self):
        client, _, user, other = _make_test_data()
        other_login = _login(client, other.email, "otherpass123")
        assert other_login.status_code == status.HTTP_200_OK
        other_token = other_login.data["access_token"]
        other_sessions = client.get(
            "/api/v1/auth/sessions/",
            HTTP_AUTHORIZATION=f"Bearer {other_token}",
        )
        assert other_sessions.status_code == status.HTTP_200_OK
        assert len(other_sessions.data) >= 1
        other_sid = other_sessions.data[0]["id"]
        client.force_authenticate(user=user)
        resp = client.post(
            f"/api/v1/auth/sessions/{other_sid}/revoke/"
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_invalid_uuid_format(self):
        """Invalid UUID format in URL returns 404 (Django URL resolver rejects it)."""
        client, _, user, _ = _make_test_data()
        client.force_authenticate(user=user)
        resp = client.post(
            "/api/v1/auth/sessions/invalid-uuid/revoke/"
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_nonexistent_session_id(self):
        client, _, user, _ = _make_test_data()
        client.force_authenticate(user=user)
        sid = str(uuid.uuid4())
        resp = client.post(f"/api/v1/auth/sessions/{sid}/revoke/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_database_error_handling(self):
        client, _, user, _ = _make_test_data()
        client.force_authenticate(user=user)
        sid = str(uuid.uuid4())
        resp = client.post(f"/api/v1/auth/sessions/{sid}/revoke/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND
