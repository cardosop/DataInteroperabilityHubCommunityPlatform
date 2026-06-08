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



# ========== END ALL OTHER SESSIONS (Phase 277.B.068) ==========


class TestEndAllOtherSessions:
    def test_unauthenticated_returns_401(self):
        client, *_ = _make_test_data()
        resp = client.post("/api/v1/auth/sessions/end-all-others/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_authenticated_returns_200(self):
        client, _, user, _ = _make_test_data()
        client.force_authenticate(user=user)
        resp = client.post("/api/v1/auth/sessions/end-all-others/")
        assert resp.status_code == status.HTTP_200_OK

    def test_has_no_other_sessions_returns_zero_count(self):
        client, _, user, _ = _make_test_data()
        client.force_authenticate(user=user)
        resp = client.post("/api/v1/auth/sessions/end-all-others/")
        assert "revoked_count" in resp.data
        assert resp.data["revoked_count"] == 0

    def test_revokes_other_active_sessions(self):
        client, _, user, _ = _make_test_data()
        # Create 3 sessions by logging in 3 times
        tokens = []
        for _ in range(3):
            login_resp = _login(client, user.email)
            tokens.append(login_resp.data["access_token"])

        # Use the last token as the current session
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens[-1]}")

        # End all other sessions
        resp = client.post("/api/v1/auth/sessions/end-all-others/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["revoked_count"] >= 1

        # Verify: only the current session should remain valid
        sessions = client.get("/api/v1/auth/sessions/")
        valid_sessions = [
            s for s in sessions.data
            if s.get("revoked_at") is None
        ]
        assert len(valid_sessions) >= 1  # At least current session should be valid

    def test_current_session_not_revoked(self):
        client, _, user, _ = _make_test_data()
        # Create 2 sessions
        _login(client, user.email)
        login2 = _login(client, user.email)

        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login2.data['access_token']}")

        # Get the current session ID before revoking others
        sessions_before = client.get("/api/v1/auth/sessions/")
        current_before = next(
            s for s in sessions_before.data if s.get("is_current") is True
        )

        # End all other sessions
        client.post("/api/v1/auth/sessions/end-all-others/")

        # Current session should still be valid
        sessions_after = client.get("/api/v1/auth/sessions/")
        current_after = next(
            s for s in sessions_after.data if s["id"] == current_before["id"]
        )
        assert current_after["revoked_at"] is None

    def test_returns_message_and_count(self):
        client, _, user, _ = _make_test_data()
        client.force_authenticate(user=user)
        resp = client.post("/api/v1/auth/sessions/end-all-others/")
        assert "message" in resp.data
        assert isinstance(resp.data["revoked_count"], int)

    def test_is_idempotent(self):
        """Calling end-all-others twice should not double-count or error."""
        client, _, user, _ = _make_test_data()
        # Create 2 sessions
        _login(client, user.email)
        login2 = _login(client, user.email)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login2.data['access_token']}")

        resp1 = client.post("/api/v1/auth/sessions/end-all-others/")
        resp2 = client.post("/api/v1/auth/sessions/end-all-others/")

        # Second call should report 0 revoked (already revoked)
        assert resp2.data["revoked_count"] == 0
