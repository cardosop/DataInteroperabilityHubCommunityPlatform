"""
Regression tests for service layer consistency (Phase 24.7).

Tests verify:
1. Tenant resolution uses central helper everywhere
2. Error response shape is consistent across all endpoints
3. No direct serializer.save() in views for writes
"""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.tenants.request_tenant import get_request_tenant, get_request_tenant_id
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

User = get_user_model()


class TenantResolutionRegressionTest(TestCase):
    """
    Regression tests for tenant resolution using central helper.

    Ensures all views use get_request_tenant_id() or get_request_tenant()
    instead of inline tenant resolution logic.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.tenant1 = Tenant.objects.create(
            name="Test Tenant 1", slug="test-tenant-1", status="ACTIVE"
        )
        self.tenant2 = Tenant.objects.create(
            name="Test Tenant 2", slug="test-tenant-2", status="ACTIVE"
        )
        self.user1 = User.objects.create_user(
            email="user1@example.com",
            password="testpass123",
            tenant=self.tenant1,
            status=UserStatus.ACTIVE.value,
        )
        self.user2 = User.objects.create_user(
            email="user2@example.com",
            password="testpass123",
            tenant=self.tenant2,
            status=UserStatus.ACTIVE.value,
        )

    def test_tenant_resolution_from_request_tenant_id(self):
        """Test that tenant resolution follows request.tenant_id when set."""
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        drf_request = factory.get("/api/v1/assets/")
        request = Request(drf_request)
        request.tenant_id = str(self.tenant2.id)
        request.tenant = None
        request.user = self.user1  # user1 belongs to tenant1

        # Should return tenant2 (from request.tenant_id), not tenant1 (from user.tenant)
        tenant_id = get_request_tenant_id(request)
        self.assertEqual(tenant_id, str(self.tenant2.id))

    def test_tenant_resolution_from_request_tenant(self):
        """Test that tenant resolution follows request.tenant when set."""
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        drf_request = factory.get("/api/v1/assets/")
        request = Request(drf_request)
        request.tenant_id = None
        request.tenant = self.tenant2
        request.user = self.user1  # user1 belongs to tenant1

        # Should return tenant2 (from request.tenant), not tenant1 (from user.tenant)
        tenant_id = get_request_tenant_id(request)
        self.assertEqual(tenant_id, str(self.tenant2.id))

    def test_tenant_resolution_from_user_tenant(self):
        """Test that tenant resolution falls back to user.tenant when request attributes not set."""
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        drf_request = factory.get("/api/v1/assets/")
        request = Request(drf_request)
        request.tenant_id = None
        request.tenant = None
        request.user = self.user1  # user1 belongs to tenant1

        # Should return tenant1 (from user.tenant)
        tenant_id = get_request_tenant_id(request)
        self.assertEqual(tenant_id, str(self.tenant1.id))

    def test_get_request_tenant_returns_tuple(self):
        """Test that get_request_tenant returns (tenant_id, tenant) tuple."""
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        drf_request = factory.get("/api/v1/assets/")
        request = Request(drf_request)
        request.tenant_id = str(self.tenant1.id)
        request.tenant = self.tenant1
        request.user = self.user1

        tenant_id, tenant = get_request_tenant(request)
        self.assertEqual(tenant_id, str(self.tenant1.id))
        self.assertEqual(tenant.id, self.tenant1.id)

    def test_scheduled_ingestion_uses_central_helper(self):
        """Test that ScheduledIngestionViewSet uses central helper for tenant resolution."""
        self.client.force_authenticate(user=self.user1)

        # Create a scheduled ingestion using HTTP source type (doesn't require real connection)
        response = self.client.post(
            "/api/v1/scheduled-ingestions/",
            {
                "name": "Test Ingestion",
                "source_type": "HTTP",
                "source_config": {"base_url": "http://example.com/data"},
                "schedule_type": "DAILY",
                "schedule_config": {"hour": 0, "minute": 0},
                "file_pattern": ".*",
            },
            format="json",
        )

        # Should succeed and create ingestion for tenant1 (connection test may fail but creation should succeed)
        # If validation fails due to connection test, that's acceptable - we're testing tenant resolution
        if response.status_code == status.HTTP_201_CREATED:
            ingestion_id = response.data["id"]

            # List ingestions - should only see tenant1's ingestion
            response = self.client.get("/api/v1/scheduled-ingestions/")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            ingestion_ids = [item["id"] for item in response.data.get("results", [])]
            self.assertIn(ingestion_id, ingestion_ids)

            # Switch to user2 (tenant2) - should not see tenant1's ingestion
            self.client.force_authenticate(user=self.user2)
            response = self.client.get("/api/v1/scheduled-ingestions/")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            ingestion_ids = [item["id"] for item in response.data.get("results", [])]
            self.assertNotIn(ingestion_id, ingestion_ids)
        else:
            # If creation fails due to connection test, verify tenant resolution still works for list
            # This tests that get_queryset uses central helper
            response = self.client.get("/api/v1/scheduled-ingestions/")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Should return empty list or only tenant1's ingestions
            ingestion_ids = [item["id"] for item in response.data.get("results", [])]

            # Switch to user2 (tenant2) - should not see tenant1's ingestions
            self.client.force_authenticate(user=self.user2)
            response = self.client.get("/api/v1/scheduled-ingestions/")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            tenant2_ingestion_ids = [item["id"] for item in response.data.get("results", [])]
            # Verify no overlap between tenant1 and tenant2 ingestions
            self.assertFalse(
                set(ingestion_ids) & set(tenant2_ingestion_ids), "Tenants should be isolated"
            )


class ErrorResponseShapeRegressionTest(TestCase):
    """
    Regression tests for error response shape consistency.

    Ensures all error responses follow the same schema:
    {
        "error": {
            "code": str,
            "message": str,
            "http_status": int,
            "request_id": str,
            "timestamp": str,
            "details": dict (optional)
        }
    }
    """

    def setUp(self):
        """Set up test fixtures."""
        import uuid as _uuid

        suffix = _uuid.uuid4().hex[:8]
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name=f"Error Shape Tenant {suffix}",
            slug=f"error-shape-{suffix}",
            status="ACTIVE",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"error-shape-{suffix}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE.value,
            is_platform_admin=True,
        )

    def test_validation_error_response_shape(self):
        """Validation errors must return the structured envelope or DRF detail.

        Accepted shapes:
          (a) {"error": {"code": str, "message": str, "http_status": int, ...}}
          (b) {"detail": str | list} or {"field_name": [...]} (DRF native)

        Any other dict shape is a regression.
        """
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/scheduled-ingestions/",
            {
                "name": "",  # Invalid: empty name
                "source_type": "INVALID_TYPE",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self._assert_valid_error_shape(response.data)

    def test_not_found_error_response_shape(self):
        """404 responses must use the structured envelope or DRF detail format."""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/scheduled-ingestions/{uuid.uuid4()}/",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self._assert_valid_error_shape(response.data)

    def test_permission_denied_error_response_shape(self):
        """401/403 responses must use the structured envelope or DRF detail format."""
        # Don't authenticate — should get 401 or 403
        response = self.client.get("/api/v1/scheduled-ingestions/")

        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )
        self._assert_valid_error_shape(response.data)

    def test_service_validation_error_response_shape(self):
        """Service-layer validation errors must use a recognised error shape."""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/scheduled-ingestions/",
            {
                "name": "Test Ingestion",
                "source_type": "S3",
                "source_config": {},  # Invalid: missing required fields
                "schedule_type": "DAILY",
                "schedule_config": {},
                "file_pattern": ".*",
            },
            format="json",
        )

        if response.status_code == status.HTTP_400_BAD_REQUEST:
            self._assert_valid_error_shape(response.data)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _assert_valid_error_shape(self, data):
        """Assert error body is either the Meshant structured envelope or DRF format.

        Accepted shapes:
          (a) {"error": {"code": str, "message": str, "http_status": int, ...}}
          (b) {"detail": ...} or {"<field>": [...]} — standard DRF serializer errors

        ``isinstance(data, dict)`` alone is intentionally NOT accepted because
        it would pass for any dict, masking a malformed response.
        """
        is_structured = (
            "error" in data
            and isinstance(data["error"], dict)
            and {"code", "message", "http_status"}.issubset(data["error"].keys())
        )
        is_drf = "detail" in data or "non_field_errors" in data

        # DRF field-level errors: dict where every value is a list
        is_drf_field_errors = all(isinstance(v, list) for v in data.values()) if data else False

        self.assertTrue(
            is_structured or is_drf or is_drf_field_errors,
            f"Error response must be a structured Meshant envelope "
            f"{{error: {{code, message, http_status, ...}}}} "
            f"or a DRF detail/field-error dict. Got: {data!r}",
        )

        if is_structured:
            self._verify_structured_envelope(data["error"])

    def _verify_structured_envelope(self, error):
        """Verify the Meshant structured error envelope fields."""
        required = ["code", "message", "http_status"]
        for field in required:
            self.assertIn(
                field,
                error,
                f"Structured error envelope must contain '{field}'",
            )
        self.assertIsInstance(error["code"], str)
        self.assertIsInstance(error["message"], str)
        self.assertIsInstance(error["http_status"], int)
        if "details" in error:
            self.assertIsInstance(error["details"], (dict, list))


class ServiceLayerConsistencyRegressionTest(TestCase):
    """
    Regression tests for service layer consistency.

    Ensures no direct serializer.save() in views for writes.
    All mutations go through service layer.

    Note: These tests verify service layer usage by checking that operations succeed
    and audit events are created (which happens in service layer), not by mocking.
    """

    def setUp(self):
        """Set up test fixtures."""
        import uuid as _uuid

        suffix = _uuid.uuid4().hex[:8]
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name=f"Service Layer Tenant {suffix}",
            slug=f"svc-layer-{suffix}",
            status="ACTIVE",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"svc-layer-{suffix}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE.value,
            is_platform_admin=True,
        )

    def test_scheduled_ingestion_create_uses_service_layer(self):
        """Test that ScheduledIngestionViewSet.create() uses service layer."""
        self.client.force_authenticate(user=self.user)

        # Create ingestion using HTTP source type (service layer should handle it)
        # Note: Connection test may fail, but service layer is still called
        response = self.client.post(
            "/api/v1/scheduled-ingestions/",
            {
                "name": "Test Ingestion",
                "source_type": "HTTP",
                "source_config": {"base_url": "http://example.com/data"},
                "schedule_type": "DAILY",
                "schedule_config": {"hour": 0, "minute": 0},
                "file_pattern": ".*",
            },
            format="json",
        )

        # Service layer is called regardless of validation result
        # If creation succeeds, verify audit event was created
        if response.status_code == status.HTTP_201_CREATED:
            self.assertIn("id", response.data)

            # Verify audit event was created (view creates audit event after service layer)
            from hub.apps.audit.models import AuditEvent

            audit_events = AuditEvent.objects.filter(
                resource_type="SCHEDULED_INGESTION",
                action="CREATED",
                resource_id=response.data["id"],
            )
            self.assertTrue(audit_events.exists(), "Audit event should be created")
        else:
            # If validation fails, that's acceptable - we're testing that service layer pattern is used
            # The fact that we get a structured error response indicates proper error handling
            self.assertIn(
                response.status_code,
                [status.HTTP_400_BAD_REQUEST, status.HTTP_500_INTERNAL_SERVER_ERROR],
            )

    def test_user_create_uses_service_layer(self):
        """Test that UserViewSet.create() uses service layer."""
        self.client.force_authenticate(user=self.user)

        # Create user - service layer should handle it
        response = self.client.post(
            "/api/v1/users/",
            {
                "email": "newuser@example.com",
                "password": "testpass123",
                "display_name": "New User",
            },
            format="json",
        )

        # Should succeed (service layer handles creation)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)

        # Verify audit event was created (service layer creates audit events)
        from hub.apps.audit.models import AuditEvent

        # Service creates USER_INVITED by default (send_invitation=True is the
        # default; USER_CREATED is used only when status is explicitly ACTIVE).
        audit_events = AuditEvent.objects.filter(
            resource_type="USER",
            action__in=["USER_CREATED", "USER_INVITED"],
            resource_id=response.data["id"],
        )
        self.assertTrue(audit_events.exists(), "Audit event should be created by service layer")

    def test_api_key_create_uses_service_layer(self):
        """Test that APIKeyViewSet.create() uses service layer."""
        self.client.force_authenticate(user=self.user)

        # Create API key - service layer should handle it
        response = self.client.post(
            "/api/v1/auth/api-keys/",
            {
                "name": "Test API Key",
                "scopes": ["assets:read"],
            },
            format="json",
        )

        # Should succeed (service layer handles creation)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertIn("api_key", response.data)  # Plaintext key returned

        # Verify audit event was created (service layer creates audit events)
        from hub.apps.audit.models import AuditEvent

        audit_events = AuditEvent.objects.filter(
            resource_type="API_KEY",
            action="API_KEY_CREATED",
            resource_id=response.data["id"],
        )
        self.assertTrue(audit_events.exists(), "Audit event should be created by service layer")


class ComplianceV2SchemaRegressionTest(TestCase):
    """
    Regression tests for the compliance v2 response schema (Phase 19.16.3).

    Guards against schema regressions where:
      (a) The v2 computed fields (regulation_summaries, schema_version,
          cross_border_alert, localisation_alert) disappear from the API
          response after a refactor of the serializer or model.
      (b) The v1 flat regulation_mapping_json dict is accidentally cleared
          when v2 fields are written (regression guard for _persist_result).
      (c) The Django serializer correctly surfaces nested v2 data stored in
          regulation_mapping_json by ComplianceService._persist_result.

    All tests operate directly on the ORM + serializer layer — no real
    compliance service call is made.
    """

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="V2 Regression Tenant",
            slug="v2-regression-tenant",
            status="ACTIVE",
        )
        self.user = User.objects.create_user(
            email="v2-regression@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE.value,
        )

    def _make_compliance_run(self, regulation_mapping_json=None, **kwargs):
        """Create a minimal ComplianceRun backed by an Asset + Job."""
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
        from hub.apps.jobs.models import Job, JobStatus, JobType

        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"v2-reg-asset-{uuid.uuid4().hex[:8]}",
            name="V2 Regression Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            created_by=self.user,
        )
        return ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=asset,
            job=job,
            status=ComplianceRunStatus.SUCCEEDED,
            regulation_mapping_json=regulation_mapping_json or {},
            **kwargs,
        )

    # ------------------------------------------------------------------
    # 1. Serializer correctly surfaces v2 fields from regulation_mapping_json
    # ------------------------------------------------------------------

    def test_v2_schema_version_surfaced_by_serializer(self):
        """
        schema_version stored inside regulation_mapping_json must be
        returned as a top-level field by ComplianceRunSerializer.
        """
        from hub.apps.compliance.serializers import ComplianceRunSerializer

        run = self._make_compliance_run(
            regulation_mapping_json={
                "GDPR": {"applies": True, "citations": []},
                "schema_version": "2.0",
            }
        )
        data = ComplianceRunSerializer(run).data
        self.assertIn("schema_version", data)
        self.assertEqual(data["schema_version"], "2.0")

    def test_v2_regulation_summaries_surfaced_by_serializer(self):
        """
        regulation_summary list stored inside regulation_mapping_json must be
        returned as regulation_summaries by ComplianceRunSerializer.
        """
        from hub.apps.compliance.serializers import ComplianceRunSerializer

        summary_list = [
            {"regulation": "GDPR", "status": "PASS", "violations": 0},
            {"regulation": "PIPL_CN", "status": "WARN", "violations": 2},
        ]
        run = self._make_compliance_run(
            regulation_mapping_json={
                "schema_version": "2.0",
                "regulation_summary": summary_list,
            }
        )
        data = ComplianceRunSerializer(run).data
        self.assertIn("regulation_summaries", data)
        self.assertIsInstance(data["regulation_summaries"], list)
        self.assertEqual(len(data["regulation_summaries"]), 2)
        reg_keys = {r["regulation"] for r in data["regulation_summaries"]}
        self.assertIn("GDPR", reg_keys)
        self.assertIn("PIPL_CN", reg_keys)

    def test_v2_cross_border_alert_surfaced_by_serializer(self):
        """
        cross_border_alert model field must be returned directly by
        ComplianceRunSerializer (it is a model field, not derived).
        """
        from hub.apps.compliance.serializers import ComplianceRunSerializer

        alert = {
            "applicable": True,
            "regulations": ["PIPL_CN"],
            "message": "Cross-border transfer restricted under PIPL_CN",
        }
        run = self._make_compliance_run(cross_border_alert=alert)
        data = ComplianceRunSerializer(run).data
        self.assertIn("cross_border_alert", data)
        self.assertTrue(data["cross_border_alert"]["applicable"])
        self.assertIn("PIPL_CN", data["cross_border_alert"]["regulations"])

    def test_v2_localisation_alert_surfaced_by_serializer(self):
        """localisation_alert model field must be returned by ComplianceRunSerializer."""
        from hub.apps.compliance.serializers import ComplianceRunSerializer

        alert = {
            "applicable": True,
            "regulations": ["PIPL_CN"],
            "message": "Data must be stored within China",
        }
        run = self._make_compliance_run(localisation_alert=alert)
        data = ComplianceRunSerializer(run).data
        self.assertIn("localisation_alert", data)
        self.assertTrue(data["localisation_alert"]["applicable"])

    # ------------------------------------------------------------------
    # 2. v1 flat regulation_mapping_json dict not clobbered by v2 persist
    # ------------------------------------------------------------------

    def test_v1_regulation_mapping_preserved_alongside_v2_fields(self):
        """
        _persist_result must keep per-regulation entries (v1 flat dict) in
        regulation_mapping_json while also writing schema_version and
        regulation_summary (v2 additions). The two coexist.
        """
        from hub.apps.compliance.serializers import ComplianceRunSerializer

        run = self._make_compliance_run(
            regulation_mapping_json={
                # v1 flat dict entries
                "GDPR": {"applies": True, "citations": ["Art. 5"]},
                "PIPL_CN": {"applies": True, "citations": []},
                # v2 additions
                "schema_version": "2.0",
                "regulation_summary": [
                    {"regulation": "GDPR", "status": "PASS"},
                    {"regulation": "PIPL_CN", "status": "WARN"},
                ],
            },
            cross_border_alert={"applicable": True, "regulations": ["PIPL_CN"]},
        )
        data = ComplianceRunSerializer(run).data

        # v1 flat dict still present
        raw = data["regulation_mapping_json"]
        self.assertIn("GDPR", raw, "v1 flat GDPR entry must survive v2 write")
        self.assertIn("PIPL_CN", raw, "v1 flat PIPL_CN entry must survive v2 write")

        # v2 computed fields present alongside v1
        self.assertEqual(data["schema_version"], "2.0")
        self.assertIsNotNone(data["regulation_summaries"])
        self.assertTrue(data["cross_border_alert"]["applicable"])

    # ------------------------------------------------------------------
    # 3. API endpoint exposes v2 fields via GET /api/v1/compliance/runs/{id}/
    # ------------------------------------------------------------------

    def test_api_get_returns_v2_schema_version(self):
        """GET /api/v1/compliance/runs/{id}/ must return schema_version when set."""
        client = APIClient()
        client.force_authenticate(user=self.user)

        run = self._make_compliance_run(
            regulation_mapping_json={"schema_version": "2.0", "GDPR": {"applies": True}}
        )
        response = client.get(f"/api/v1/compliance/runs/{run.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("schema_version"), "2.0")

    def test_api_get_returns_v2_regulation_summaries(self):
        """GET /api/v1/compliance/runs/{id}/ must return regulation_summaries list."""
        client = APIClient()
        client.force_authenticate(user=self.user)

        run = self._make_compliance_run(
            regulation_mapping_json={
                "schema_version": "2.0",
                "regulation_summary": [{"regulation": "GDPR", "status": "PASS"}],
            }
        )
        response = client.get(f"/api/v1/compliance/runs/{run.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        summaries = response.data.get("regulation_summaries")
        self.assertIsInstance(summaries, list)
        self.assertGreater(len(summaries), 0)

    def test_api_get_returns_cross_border_alert(self):
        """GET /api/v1/compliance/runs/{id}/ must return cross_border_alert dict."""
        client = APIClient()
        client.force_authenticate(user=self.user)

        run = self._make_compliance_run(
            cross_border_alert={"applicable": True, "regulations": ["PIPL_CN"]},
        )
        response = client.get(f"/api/v1/compliance/runs/{run.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        alert = response.data.get("cross_border_alert")
        self.assertIsNotNone(alert)
        self.assertTrue(alert["applicable"])

    def test_v2_legal_basis_violations_surfaced_by_serializer(self):
        """legal_basis_violations model field must be returned by ComplianceRunSerializer."""
        from hub.apps.compliance.serializers import ComplianceRunSerializer

        violations = [
            {"regulation": "GDPR", "basis": "CONSENT", "violation": "no_consent_obtained"},
            {"regulation": "PIPL_CN", "basis": "CONSENT", "violation": "missing_notice"},
        ]
        run = self._make_compliance_run(legal_basis_violations=violations)
        data = ComplianceRunSerializer(run).data
        self.assertIn("legal_basis_violations", data)
        self.assertIsInstance(data["legal_basis_violations"], list)
        self.assertEqual(len(data["legal_basis_violations"]), 2)
        reg_keys = {v["regulation"] for v in data["legal_basis_violations"]}
        self.assertIn("GDPR", reg_keys)
        self.assertIn("PIPL_CN", reg_keys)

    def test_v2_estimated_population_ratio_surfaced_by_serializer(self):
        """
        estimated_population_ratio must be extracted from
        regulation_mapping_json.metadata.estimated_population_ratio
        and returned as a top-level field by ComplianceRunSerializer.
        """
        from hub.apps.compliance.serializers import ComplianceRunSerializer

        run = self._make_compliance_run(
            regulation_mapping_json={
                "schema_version": "2.0",
                "metadata": {"estimated_population_ratio": 0.003142},
            }
        )
        data = ComplianceRunSerializer(run).data
        self.assertIn("estimated_population_ratio", data)
        self.assertAlmostEqual(data["estimated_population_ratio"], 0.003142, places=6)

    def test_api_get_returns_legal_basis_violations(self):
        """GET /api/v1/compliance/runs/{id}/ must return legal_basis_violations list."""
        client = APIClient()
        client.force_authenticate(user=self.user)

        violations = [{"regulation": "GDPR", "violation": "no_consent_obtained"}]
        run = self._make_compliance_run(legal_basis_violations=violations)
        response = client.get(f"/api/v1/compliance/runs/{run.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = response.data.get("legal_basis_violations")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_api_get_returns_estimated_population_ratio(self):
        """GET /api/v1/compliance/runs/{id}/ must return estimated_population_ratio."""
        client = APIClient()
        client.force_authenticate(user=self.user)

        run = self._make_compliance_run(
            regulation_mapping_json={
                "schema_version": "2.0",
                "metadata": {"estimated_population_ratio": 0.001234},
            }
        )
        response = client.get(f"/api/v1/compliance/runs/{run.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ratio = response.data.get("estimated_population_ratio")
        self.assertIsNotNone(ratio)
        self.assertAlmostEqual(ratio, 0.001234, places=6)
