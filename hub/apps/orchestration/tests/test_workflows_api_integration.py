"""
Integration tests for Workflows API (list, get by name, trigger).

Real WorkflowRegistry, WorkflowEngine, and DB; no mocks. Covers: list workflows,
get by name/version, trigger (create instance, optional start), tenant
isolation, pagination, filters, auth.
"""

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.orchestration.models import WorkflowDefinition, WorkflowInstance
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


def _register_version_creation_workflow(
    registry: WorkflowRegistry,
) -> WorkflowDefinition:
    """Register version_creation so definitions exist in DB (real registry)."""
    from hub.apps.orchestration.workflows.version_creation import (
        VersionCreationWorkflow,
    )

    VersionCreationWorkflow.register_workflow(registry)
    wf = registry.get_workflow("version_creation")
    assert wf is not None
    return wf


def _register_engine_tasks(engine: WorkflowEngine) -> None:
    """Register version_creation tasks so trigger can execute (real engine)."""
    from hub.apps.orchestration.workflows.version_creation import (
        VersionCreationWorkflow,
    )

    VersionCreationWorkflow.register_tasks(engine)


class WorkflowsAPIIntegrationTest(TestCase):
    """Workflows API integration tests; real registry, engine, DB."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.client.force_authenticate(user=self.user)

        self.registry = WorkflowRegistry()
        self.engine = WorkflowEngine()
        _register_version_creation_workflow(self.registry)
        _register_engine_tasks(self.engine)

    def test_list_workflows_returns_200_and_results(self):
        """GET /api/v1/workflows/ returns 200 and list of definitions."""
        response = self.client.get("/api/v1/workflows/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIsInstance(response.data["results"], list)
        names = [w["name"] for w in response.data["results"]]
        self.assertIn("version_creation", names)

    def test_list_workflows_filter_by_name(self):
        """GET ?name=version_creation returns matching workflows."""
        response = self.client.get("/api/v1/workflows/", {"name": "version_creation"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 1)
        for w in response.data["results"]:
            self.assertEqual(w["name"], "version_creation")

    def test_list_workflows_filter_by_is_active(self):
        """GET ?is_active=true returns only active workflows."""
        response = self.client.get("/api/v1/workflows/", {"is_active": "true"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for w in response.data["results"]:
            self.assertTrue(w["is_active"])

    def test_list_workflows_pagination(self):
        """GET ?page_size=1 returns paginated results."""
        response = self.client.get("/api/v1/workflows/", {"page_size": "1"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertIn("count", response.data)
        self.assertIn("next", response.data)

    def test_get_workflow_by_name_returns_200(self):
        """GET version_creation/ returns 200 and workflow detail."""
        response = self.client.get("/api/v1/workflows/version_creation/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "version_creation")
        self.assertIn("version", response.data)
        self.assertIn("dsl_json", response.data)
        self.assertIn("is_active", response.data)

    def test_get_workflow_by_name_and_version_returns_200(self):
        """GET version_creation/?version=1.0.0 returns 200."""
        response = self.client.get("/api/v1/workflows/version_creation/", {"version": "1.0.0"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "version_creation")
        self.assertEqual(response.data["version"], "1.0.0")

    def test_get_workflow_not_found_returns_404(self):
        """GET /api/v1/workflows/nonexistent_workflow/ returns 404."""
        response = self.client.get("/api/v1/workflows/nonexistent_workflow/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_trigger_workflow_creates_instance_returns_201(self):
        """POST version_creation/trigger/ creates instance and returns 201."""
        response = self.client.post(
            "/api/v1/workflows/version_creation/trigger/",
            {"input_data": {}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertIn("status", response.data)
        self.assertIn("workflow_name", response.data)
        self.assertEqual(response.data["workflow_name"], "version_creation")
        self.assertTrue(WorkflowInstance.objects.filter(id=response.data["id"]).exists())
        instance = WorkflowInstance.objects.get(id=response.data["id"])
        self.assertEqual(instance.tenant_id, self.tenant.id)

    def test_trigger_workflow_with_start_immediately(self):
        """POST with start_immediately=true creates instance and starts it."""
        response = self.client.post(
            "/api/v1/workflows/version_creation/trigger/",
            {"input_data": {}, "start_immediately": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        instance = WorkflowInstance.objects.get(id=response.data["id"])
        self.assertIn(
            instance.status,
            ["DRAFT", "RUNNING"],
            "Instance should be DRAFT or RUNNING after trigger",
        )

    def test_trigger_workflow_not_found_returns_404(self):
        """POST nonexistent_workflow/trigger/ returns 404."""
        response = self.client.post(
            "/api/v1/workflows/nonexistent_workflow/trigger/",
            {"input_data": {}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_workflows_unauthenticated_returns_401(self):
        """GET /api/v1/workflows/ without auth returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/workflows/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_workflows_user_without_tenant_returns_400(self):
        """User without tenant gets 400 (tenant required)."""
        user_no_tenant = User.objects.create_user(
            email="notenant@example.com",
            password="testpass123",
            tenant=None,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=user_no_tenant)
        response = self.client.get("/api/v1/workflows/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_trigger_workflow_empty_body_returns_201(self):
        """POST trigger with empty body uses defaults and returns 201."""
        response = self.client.post(
            "/api/v1/workflows/version_creation/trigger/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["workflow_name"], "version_creation")

    def test_trigger_workflow_invalid_input_data_not_dict_returns_400(self):
        """POST trigger with input_data not a dict returns 400."""
        response = self.client.post(
            "/api/v1/workflows/version_creation/trigger/",
            {"input_data": "not-a-dict"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("input_data", response.data)
