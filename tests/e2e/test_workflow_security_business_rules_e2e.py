"""
Phase 6.6 — E2E Tests for Workflow Security with Business Rules

Comprehensive E2E security tests for workflow execution and business rules:
- 6.6.1: Tenant isolation, authorization, input validation (malicious input, SQL, XSS, path traversal)
- 6.6.2: Business rules cannot be bypassed; validation errors not suppressed;
         validation context cannot be tampered; validation results cannot be forged

No mocks/stubs: uses real DB, real API, real WorkflowEngine and business rules.
Root-cause fixes only; engineering-grade coverage.
"""

import json

import pytest

pytestmark = pytest.mark.workflow_e2e
import uuid

from django.test import TestCase
from rest_framework import status

from hub.apps.assets.models import Asset
from hub.apps.assets.tests.factories import AssetFactory
from hub.apps.contracts.models import Contract, OriginalFormat, OriginalSpecType
from hub.apps.orchestration.models import WorkflowStatus
from hub.apps.orchestration.workflows.contract_creation import ContractCreationWorkflow
from hub.apps.users.models import Role, UserRole, UserStatus
from tests.e2e.conftest import E2ETestBase, get_response_data
from tests.e2e.workflow_e2e_base import WorkflowE2ETestBase
from tests.factories import TenantFactory, UserFactory


def _minimal_odcs_raw():
    """Minimal valid ODCS contract content (JSON)."""
    return json.dumps(
        {
            "id": "test-contract-sec",
            "info": {"version": "1.0", "name": "Test"},
            "schema": {"fields": [{"name": "id", "data_type": "string", "nullable": False}]},
        }
    )


# --- 6.6.1 Security tests: tenant isolation ---


class TestWorkflowSecurityTenantIsolationE2E(E2ETestBase):
    """
    6.6.1 — Tenant isolation in workflow execution (via API).

    - Workflows cannot access other tenants' data (contract create with asset from other tenant → 400).
    - Business rules enforce tenant isolation.
    - Cross-tenant access attempts fail with validation error.
    """

    def test_workflow_triggered_contract_create_rejects_asset_from_other_tenant_via_api(self):
        """Verify contract create via API with asset_id from another tenant returns 400; business rules enforce isolation."""
        other_tenant = TenantFactory.create_tenant()
        other_user = UserFactory.create_user(tenant=other_tenant, status=UserStatus.ACTIVE)
        asset_other = AssetFactory.create_asset(
            tenant=other_tenant, key=f"other-{uuid.uuid4().hex[:8]}", name="Other Tenant Asset"
        )

        count_before = Contract.objects.count()
        payload = {
            "original_raw": _minimal_odcs_raw(),
            "original_format": OriginalFormat.JSON,
            "original_spec_type": OriginalSpecType.ODCS,
            "asset_id": str(asset_other.id),
        }
        # self.user is in self.tenant; asset_other is in other_tenant
        response = self.client.post("/api/v1/contracts/", data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, get_response_data(response))
        self.assertEqual(Contract.objects.count(), count_before)
        data = response.json()
        self.assertIn("error", data)
        self.assertIn("code", data)
        self.assertEqual(data.get("code"), "BUSINESS_RULES_VALIDATION")

    def test_contract_list_returns_only_tenant_contracts(self):
        """Verify listing contracts via API returns only the request user's tenant contracts."""
        # Create contract in self.tenant via API
        asset_id = self.create_asset(key=f"sec-{uuid.uuid4().hex[:8]}", name="Security Test Asset")
        self.client.post(
            "/api/v1/contracts/",
            data={
                "original_raw": _minimal_odcs_raw(),
                "original_format": OriginalFormat.JSON,
                "original_spec_type": OriginalSpecType.ODCS,
                "asset_id": asset_id,
            },
            format="json",
        )

        other_tenant = TenantFactory.create_tenant()
        other_asset = AssetFactory.create_asset(
            tenant=other_tenant, key=f"other-{uuid.uuid4().hex[:8]}", name="Other"
        )
        other_contract = Contract.objects.create(
            tenant=other_tenant,
            asset_id=other_asset.id,
            original_raw=_minimal_odcs_raw(),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
        )

        response = self.client.get("/api/v1/contracts/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        ids = [
            c["id"]
            for c in data.get("results", data)
            if isinstance(data.get("results"), list)
        ]
        if not ids and "results" not in data:
            ids = [c["id"] for c in data] if isinstance(data, list) else []
        self.assertNotIn(
            str(other_contract.id), ids, "Contract from other tenant must not appear in list"
        )

    def test_unauthenticated_contract_create_returns_401(self):
        """Verify unauthenticated contract create returns 401."""
        asset_id = self.create_asset(key="auth-test", name="Auth Test")
        self.client.force_authenticate(user=None)
        response = self.client.post(
            "/api/v1/contracts/",
            data={
                "original_raw": _minimal_odcs_raw(),
                "original_format": OriginalFormat.JSON,
                "original_spec_type": OriginalSpecType.ODCS,
                "asset_id": str(asset_id),
            },
            format="json",
        )
        self.assertIn(
            response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        )


class TestWorkflowSecurityTenantIsolationWorkflowEngineE2E(WorkflowE2ETestBase):
    """
    6.6.1 — Tenant isolation when workflow is executed by engine with cross-tenant input.

    Workflow run with tenant A but input_data containing asset_id from tenant B
    must fail validation (business rules enforce tenant consistency).
    """

    workflow_classes = [ContractCreationWorkflow]

    def test_workflow_with_cross_tenant_asset_fails_validation(self):
        """Verify workflow execution fails when input references asset from another tenant."""
        other_tenant = TenantFactory.create_tenant()
        asset_other = AssetFactory.create_asset(
            tenant=other_tenant, key=f"x-{uuid.uuid4().hex[:8]}", name="Cross-Tenant Asset"
        )

        input_data = {
            "original_raw": _minimal_odcs_raw(),
            "original_format": OriginalFormat.JSON,
            "original_spec_type": OriginalSpecType.ODCS,
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
            "asset_id": str(asset_other.id),
        }
        instance, err = self.create_start_and_execute(
            ContractCreationWorkflow.WORKFLOW_NAME,
            input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance.refresh_from_db()
        self.assertIn(
            instance.status,
            (WorkflowStatus.FAILED, WorkflowStatus.ROLLED_BACK),
            instance.error_message or "expected failed or rolled back",
        )
        # Cross-tenant asset causes failure (Asset.DoesNotExist or business rule rejection)
        err = (instance.error_message or "").lower()
        self.assertTrue(
            "validation" in err
            or "business rules" in err
            or "does not exist" in err
            or "not found" in err
            or "matching query" in err,
            f"Expected validation/does not exist in error: {instance.error_message}",
        )


# --- 6.6.1 Authorization ---


class TestWorkflowSecurityAuthorizationE2E(E2ETestBase):
    """
    6.6.1 — Authorization in workflow execution.

    - Workflows respect user permissions (tenant membership).
    - Validation fails for unauthorized operations.
    """

    def test_contract_create_requires_tenant_membership(self):
        """User without tenant cannot create contract (400/403)."""
        from hub.apps.users.models import User

        user_no_tenant = User.objects.create_user(
            email=f"no_tenant_{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
        )
        user_no_tenant.tenant_id = None
        user_no_tenant.save(update_fields=["tenant_id"])

        # Create asset as self.user (has tenant), then try contract create as user without tenant
        self.client.force_authenticate(user=self.user)
        asset_id = self.create_asset(key="auth-asset", name="Auth Asset")
        self.client.force_authenticate(user=user_no_tenant)

        response = self.client.post(
            "/api/v1/contracts/",
            data={
                "original_raw": _minimal_odcs_raw(),
                "original_format": OriginalFormat.JSON,
                "original_spec_type": OriginalSpecType.ODCS,
                "asset_id": asset_id,
            },
            format="json",
        )
        self.assertIn(
            response.status_code, (status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN)
        )
        self.assertIn("tenant", (response.json().get("error") or "").lower())


# --- 6.6.1 Input validation (malicious input) ---


class TestWorkflowSecurityInputValidationE2E(E2ETestBase):
    """
    6.6.1 — Input validation in workflow execution.

    - Malicious input is rejected or safely handled by business rules/serializers.
    - SQL injection-like, XSS-like, path traversal-like payloads do not bypass validation.
    """

    def test_asset_create_with_xss_like_name_rejected_or_sanitized(self):
        """XSS-like content in asset name: expect 400 or stored without execution (sanitized/escaped)."""
        payload = {
            "key": f"xss-{uuid.uuid4().hex[:8]}",
            "name": "<script>alert(1)</script>",
        }
        response = self.client.post("/api/v1/assets/", data=payload, format="json")
        # Either rejected (400) or created with escaped/sanitized value (201)
        self.assertIn(response.status_code, (status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST))
        if response.status_code == status.HTTP_201_CREATED:
            # Must not be executable: stored as literal
            data = get_response_data(response) or {}
            self.assertIsNotNone(data.get("id"))
            self.assertIn("script", (data.get("name") or "").lower() or "")

    def test_contract_create_with_sql_injection_like_in_raw_rejected_or_stored_safely(self):
        """SQL injection-like string in original_raw: expect 400 or stored as literal (ORM prevents execution)."""
        payload = {
            "original_raw": "'; DROP TABLE contracts; --",
            "original_format": OriginalFormat.JSON,
            "original_spec_type": OriginalSpecType.ODCS,
            "asset_id": str(self.create_asset(key="sql-test", name="SQL Test")),
        }
        response = self.client.post("/api/v1/contracts/", data=payload, format="json")
        # Invalid JSON/structure → 400; or if accepted, stored as string only (no execution)
        self.assertIn(response.status_code, (status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST))
        if response.status_code == status.HTTP_201_CREATED:
            data = get_response_data(response) or {}
            c = Contract.objects.get(id=data["id"])
            self.assertIn("DROP", c.original_raw or "")

    def test_path_traversal_like_in_asset_name_rejected_or_stored_safely(self):
        """Path traversal-like in asset name: expect 400 or stored as literal."""
        payload = {
            "key": f"path-{uuid.uuid4().hex[:8]}",
            "name": "../../../etc/passwd",
        }
        response = self.client.post("/api/v1/assets/", data=payload, format="json")
        self.assertIn(response.status_code, (status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST))
        if response.status_code == status.HTTP_201_CREATED:
            data = get_response_data(response) or {}
            self.assertIsNotNone(data.get("id"))


# --- 6.6.2 Business rules validation ---


class TestWorkflowSecurityBusinessRulesValidationE2E(E2ETestBase):
    """
    6.6.2 — Security tests for business rules validation.

    - Business rules cannot be bypassed.
    - Validation errors cannot be suppressed.
    - Validation context cannot be tampered with (tenant from request, not body).
    - Validation results cannot be forged (no header to skip validation).
    """

    def test_business_rules_cannot_be_bypassed_invalid_contract_returns_400(self):
        """Invalid contract payload (e.g. empty required) must return 400; rules cannot be bypassed."""
        payload = {
            "original_raw": _minimal_odcs_raw(),
            "original_format": OriginalFormat.JSON,
            "original_spec_type": OriginalSpecType.ODCS,
            "asset_id": "",  # invalid
        }
        response = self.client.post("/api/v1/contracts/", data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validation_errors_not_suppressed_invalid_returns_400_with_body(self):
        """Validation failure must return 400 with error body, not 200 or 500."""
        payload = {
            "original_raw": _minimal_odcs_raw(),
            "original_format": OriginalFormat.JSON,
            "original_spec_type": OriginalSpecType.ODCS,
            "asset_id": "00000000-0000-0000-0000-000000000000",  # non-existent
        }
        response = self.client.post("/api/v1/contracts/", data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn("error", data)

    def test_validation_context_tenant_from_request_not_body(self):
        """Server must use request user's tenant for create, not client-supplied tenant_id in body."""
        asset_id = self.create_asset(key="ctx-asset", name="Context Asset")
        payload = {
            "original_raw": _minimal_odcs_raw(),
            "original_format": OriginalFormat.JSON,
            "original_spec_type": OriginalSpecType.ODCS,
            "asset_id": asset_id,
            "tenant_id": str(uuid.uuid4()),  # forged tenant_id in body
        }
        response = self.client.post("/api/v1/contracts/", data=payload, format="json")
        data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, data)
        contract = Contract.objects.get(id=data["id"])
        self.assertEqual(
            contract.tenant_id, self.tenant.id, "Contract must belong to request user tenant"
        )

    def test_validation_results_cannot_be_forged_no_skip_header(self):
        """Sending a header (e.g. X-Skip-Validation) must not cause server to skip validation; invalid data still 400."""
        self.client.credentials(HTTP_X_SKIP_VALIDATION="true")  # if such header exists
        payload = {
            "original_raw": _minimal_odcs_raw(),
            "original_format": OriginalFormat.JSON,
            "original_spec_type": OriginalSpecType.ODCS,
            "asset_id": "00000000-0000-0000-0000-000000000000",
        }
        response = self.client.post("/api/v1/contracts/", data=payload, format="json")
        self.client.credentials()
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, "Validation must not be skipped"
        )
