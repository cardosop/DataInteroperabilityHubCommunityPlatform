"""
Phase TR.B — API integration test (relocated from E2E browser spec).

Tests the scheduled export API endpoint.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TestApiLogic:
    """API logic for scheduled export endpoints."""

    def test_scheduled_export_list_returns_200(self):
        """GET /api/v1/scheduled-exports/ returns paginated results."""
        tenant = Tenant.objects.create(
            name=f"SE Test {uuid.uuid4().hex[:8]}",
            slug=f"se-test-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        user = User.objects.create_user(
            email=f"se-{uuid.uuid4().hex[:8]}@example.com",
            password="SecurePass123!",
            tenant=tenant,
        )

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get("/api/v1/scheduled-exports/")

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.data}"
        )
        assert "results" in response.data, "Response should be paginated with 'results' key"
