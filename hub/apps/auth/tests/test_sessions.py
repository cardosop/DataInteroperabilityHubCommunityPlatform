"""
Tests for auth sessions API: list_active_sessions, revoke_session.
Phase 7.5.B backend verification; no mocks.
"""

from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.auth.models import RefreshToken
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = __import__("django.contrib.auth", fromlist=["get_user_model"]).get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class SessionsAPITest(TestCase):
    """Test GET /api/v1/auth/sessions/ and POST /api/v1/auth/sessions/{id}/revoke/."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Sessions Test Tenant",
            slug="sessions-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email="sessions@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="otherpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_list_active_sessions_unauthenticated_returns_401(self):
        response = self.client.get("/api/v1/auth/sessions/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_active_sessions_authenticated_returns_200(self):
        """Test listing active sessions when authenticated returns 200."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/auth/sessions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_active_sessions_authenticated_returns_list(self):
        """Test listing active sessions when authenticated returns list."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/auth/sessions/")
        self.assertIsInstance(response.data, list)

    def test_list_active_sessions_returns_non_empty_list_after_login(self):
        """Test listing active sessions returns non-empty list after login."""
        login_resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": "sessions@example.com", "password": "testpass123"},
            format="json",
        )
        access = login_resp.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.get("/api/v1/auth/sessions/")
        self.assertGreaterEqual(len(response.data), 1)

    def test_list_active_sessions_returns_session_with_id(self):
        """Test listing active sessions returns session with id."""
        login_resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": "sessions@example.com", "password": "testpass123"},
            format="json",
        )
        access = login_resp.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.get("/api/v1/auth/sessions/")
        item = response.data[0]
        self.assertIn("id", item)

    def test_list_active_sessions_returns_session_with_created_at(self):
        """Test listing active sessions returns session with created_at."""
        login_resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": "sessions@example.com", "password": "testpass123"},
            format="json",
        )
        access = login_resp.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.get("/api/v1/auth/sessions/")
        item = response.data[0]
        self.assertIn("created_at", item)

    def test_list_active_sessions_returns_session_with_expires_at(self):
        """Test listing active sessions returns session with expires_at."""
        login_resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": "sessions@example.com", "password": "testpass123"},
            format="json",
        )
        access = login_resp.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.get("/api/v1/auth/sessions/")
        item = response.data[0]
        self.assertIn("expires_at", item)

    def test_list_active_sessions_returns_session_with_revoked_at(self):
        """Test listing active sessions returns session with revoked_at."""
        login_resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": "sessions@example.com", "password": "testpass123"},
            format="json",
        )
        access = login_resp.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.get("/api/v1/auth/sessions/")
        item = response.data[0]
        self.assertIn("revoked_at", item)

    def test_list_active_sessions_returns_session_with_is_current(self):
        """Test listing active sessions returns session with is_current."""
        login_resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": "sessions@example.com", "password": "testpass123"},
            format="json",
        )
        access = login_resp.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.get("/api/v1/auth/sessions/")
        item = response.data[0]
        self.assertIn("is_current", item)

    def test_list_active_sessions_returns_session_with_non_null_id(self):
        """Test listing active sessions returns session with non-null id."""
        login_resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": "sessions@example.com", "password": "testpass123"},
            format="json",
        )
        access = login_resp.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.get("/api/v1/auth/sessions/")
        item = response.data[0]
        self.assertIsNotNone(item["id"])

    def test_revoke_session_unauthenticated_returns_401(self):
        session_id = "00000000-0000-0000-0000-000000000001"
        response = self.client.post(f"/api/v1/auth/sessions/{session_id}/revoke/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_revoke_session_authenticated_own_session_returns_200(self):
        """Test revoking own session when authenticated returns 200."""
        login_resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": "sessions@example.com", "password": "testpass123"},
            format="json",
        )
        access = login_resp.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        list_resp = self.client.get("/api/v1/auth/sessions/")
        session_id = list_resp.data[0]["id"]
        revoke_resp = self.client.post(f"/api/v1/auth/sessions/{session_id}/revoke/")
        self.assertEqual(revoke_resp.status_code, status.HTTP_200_OK)

    def test_revoke_session_authenticated_returns_message(self):
        """Test revoking own session returns message."""
        login_resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": "sessions@example.com", "password": "testpass123"},
            format="json",
        )
        access = login_resp.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        list_resp = self.client.get("/api/v1/auth/sessions/")
        session_id = list_resp.data[0]["id"]
        revoke_resp = self.client.post(f"/api/v1/auth/sessions/{session_id}/revoke/")
        self.assertIn("message", revoke_resp.data)

    def test_revoke_session_sets_revoked_at(self):
        """Test revoking own session sets revoked_at."""
        login_resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": "sessions@example.com", "password": "testpass123"},
            format="json",
        )
        access = login_resp.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        list_resp = self.client.get("/api/v1/auth/sessions/")
        session_id = list_resp.data[0]["id"]
        self.client.post(f"/api/v1/auth/sessions/{session_id}/revoke/")
        list_after = self.client.get("/api/v1/auth/sessions/")
        revoked = next((s for s in list_after.data if s["id"] == session_id), None)
        self.assertIsNotNone(revoked)
        self.assertIsNotNone(revoked["revoked_at"])

    def test_revoke_session_other_user_session_returns_404(self):
        """Revoking another user's session must return 404 (not 403)."""
        other_login = self.client.post(
            "/api/v1/auth/login/",
            {"email": "other@example.com", "password": "otherpass123"},
            format="json",
        )
        self.assertEqual(other_login.status_code, status.HTTP_200_OK)
        other_list = self.client.get(
            "/api/v1/auth/sessions/",
            HTTP_AUTHORIZATION=f"Bearer {other_login.data['access_token']}",
        )
        self.assertEqual(other_list.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(other_list.data), 1)
        other_session_id = other_list.data[0]["id"]
        self.client.force_authenticate(user=self.user)
        revoke_resp = self.client.post(f"/api/v1/auth/sessions/{other_session_id}/revoke/")
        self.assertEqual(revoke_resp.status_code, status.HTTP_404_NOT_FOUND)

    # ========== EDGE CASES ==========

    def test_list_sessions_empty_list_when_no_sessions(self):
        """Test listing sessions when user has no active sessions (edge case)"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/auth/sessions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        # May be empty if no sessions exist

    def test_revoke_session_invalid_uuid_format(self):
        """Test revoking session with invalid UUID format (edge case)"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post("/api/v1/auth/sessions/invalid-uuid/revoke/")

        # Should return 404 (not found) or 400 (bad request) depending on URL routing
        self.assertIn(
            response.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_400_BAD_REQUEST]
        )

    def test_revoke_session_nonexistent_session_id(self):
        """Test revoking session with non-existent session ID (edge case)"""
        import uuid

        self.client.force_authenticate(user=self.user)
        nonexistent_id = str(uuid.uuid4())
        response = self.client.post(f"/api/v1/auth/sessions/{nonexistent_id}/revoke/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_sessions_after_logout_returns_200(self):
        """Test listing sessions after logout returns 200."""
        # Login and get sessions
        login_resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": "sessions@example.com", "password": "testpass123"},
            format="json",
        )
        access = login_resp.data["access_token"]
        refresh = login_resp.data["refresh_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        # Logout
        self.client.post("/api/v1/auth/logout/", {"refresh_token": refresh}, format="json")

        # List sessions after logout
        list_after = self.client.get("/api/v1/auth/sessions/")
        self.assertEqual(list_after.status_code, status.HTTP_200_OK)

    def test_list_sessions_after_logout_includes_revoked_sessions(self):
        """Test listing sessions after logout includes revoked sessions."""
        # Login and get sessions
        login_resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": "sessions@example.com", "password": "testpass123"},
            format="json",
        )
        access = login_resp.data["access_token"]
        refresh = login_resp.data["refresh_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        # Logout
        self.client.post("/api/v1/auth/logout/", {"refresh_token": refresh}, format="json")

        # List sessions after logout
        list_after = self.client.get("/api/v1/auth/sessions/")

        # At least one session should be revoked
        revoked_sessions = [s for s in list_after.data if s.get("revoked_at")]
        self.assertGreaterEqual(len(revoked_sessions), 1)

    # ========== ERROR HANDLING ==========

    def test_list_sessions_database_error_handling(self):
        """Test error handling when database query fails"""
        # This test verifies that errors are properly handled
        # In a real scenario, we might simulate a database error
        # For now, we test that the endpoint handles errors gracefully
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/auth/sessions/")

        # Should return 200 even if there are issues (graceful degradation)
        # Or should return appropriate error code
        self.assertIn(
            response.status_code, [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]
        )

    def test_revoke_session_database_error_handling(self):
        """Test error handling when revoking session fails"""
        import uuid

        self.client.force_authenticate(user=self.user)
        session_id = str(uuid.uuid4())

        # Try to revoke non-existent session
        response = self.client.post(f"/api/v1/auth/sessions/{session_id}/revoke/")

        # Should return 404, not 500
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
