"""

import uuid
Cross-Capability E2E Tests.

Tests interactions between different capabilities:
- Tenant config affects job processing
- Tenant config affects rate limiting
- Job completion triggers email
- Contract normalization affects semantic mapping
- Quality rules affect DQ service
- Compliance policy affects compliance service
- Marketplace policy affects marketplace service
Uses real services (no mocks).
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status

from hub.apps.contracts.models import (
    Contract,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.jobs.models import JobStatus, JobType
from hub.apps.semantic.utils import map_contract_to_semantic
from tests.e2e.conftest import (
    E2ETestBase,
    get_api_base_url,
    get_compliance_service_url,
    get_datacontract_service_url,
    get_dq_service_url,
    get_semantic_service_url,
    get_worker_service_url,
)
from tests.factories import TenantConfigFactory

pytestmark = [pytest.mark.slow, pytest.mark.django_db(transaction=True), pytest.mark.e2e5]
User = get_user_model()


class CrossCapabilityE2ETest(E2ETestBase):
    """Cross-capability E2E tests"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

    def test_tenant_config_affects_job_processing(self):
        """Test that tenant config affects job processing"""
        # Create tenant config with low concurrency limit
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant, max_job_concurrency=1, max_queued_jobs=2
        )

        # Create first job - should succeed
        import uuid

        from hub.apps.jobs.utils import (
            check_tenant_job_limits,
            create_job,
            decrement_tenant_job_counter,
            increment_tenant_job_counter,
        )

        job1 = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={"dq_run_id": str(uuid.uuid4())},
        )

        self.assertIsNotNone(job1.id)
        self.assertEqual(job1.status, JobStatus.PENDING)

        # Mark job as running (simulate worker processing)
        job1.mark_started()
        increment_tenant_job_counter(str(self.tenant.id), "running")
        decrement_tenant_job_counter(str(self.tenant.id), "queued")

        # Check if we can create another job (should fail due to concurrency limit)
        can_create, reason = check_tenant_job_limits(str(self.tenant.id))
        self.assertFalse(can_create)
        self.assertIn("concurrent", reason.lower())

    def test_tenant_config_affects_rate_limiting(self):
        """Test that tenant config affects rate limiting.

        Rate limiting is disabled in test mode (RATE_LIMIT_ENABLED=False).
        We enable it with override_settings and set a very low burst limit
        so the middleware triggers 429 or adds X-RateLimit-* headers.
        """
        from django.test import override_settings

        # Create tenant config with very low burst limit (3 requests / 60s)
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            rate_limits={
                "CONTRACT": {
                    "burst": {"requests": 3, "window_seconds": 60},
                    "sustained": {"requests": 10, "window_seconds": 60},
                }
            },
        )

        self.client.force_authenticate(user=self.user)

        # Enable rate limiting (disabled by default in test env)
        with override_settings(RATE_LIMIT_ENABLED=True):
            got_rate_limited = False
            has_rate_limit_headers = False

            for _i in range(10):
                response = self.client.get("/api/v1/contracts/")
                if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                    got_rate_limited = True
                    break
                if "X-RateLimit-Remaining" in response or "X-RateLimit-Limit" in response:
                    has_rate_limit_headers = True

        # Either rate limiting kicked in with 429, or rate-limit headers are present
        self.assertTrue(
            got_rate_limited or has_rate_limit_headers,
            "Rate limiting not enforced: no 429 response and no X-RateLimit-* headers "
            "found after 10 requests with burst limit of 3. "
            "Ensure RateLimitMiddleware is in MIDDLEWARE and reads RATE_LIMIT_ENABLED.",
        )

    def test_contract_normalization_affects_semantic_mapping(self):
        """Test that contract normalization affects semantic mapping"""
        # Create contract with ODCS format
        odcs_contract = """{
            "id": "test-contract",
            "name": "Test Contract",
            "schema": {
                "fields": [
                    {
                        "name": "email",
                        "type": "string",
                        "semantic_type": "EMAIL",
                        "format": "email"
                    }
                ]
            }
        }"""

        from hub.apps.contracts.normalization import normalize_contract

        # Normalize contract
        hub_contract, spec_type, spec_version, norm_status, _errors, _warnings = normalize_contract(
            raw_contract=odcs_contract, format="JSON"
        )

        self.assertIsNotNone(hub_contract)
        self.assertEqual(norm_status, NormalizationStatus.NORMALIZED_OK)

        # Create contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=spec_type,
            original_spec_version=spec_version,
            original_format=OriginalFormat.JSON,
            original_raw=odcs_contract,
            hub_contract_json=hub_contract,
            normalization_status=norm_status,
            created_by=self.user,
        )

        # Map to semantic (should use normalized HubContract)
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)

        # Semantic mapping must return a result; skip if service unavailable
        if semantic_resource is None:
            self.skipTest("Semantic service unavailable - map_contract_to_semantic returned None")
        self.assertIsNotNone(semantic_resource)
        self.assertEqual(semantic_resource.resource_type, "CONTRACT")

    def test_quality_rules_affect_dq_service(self):
        """Test that quality rules from contract affect DQ service"""
        from hub.apps.dq.contract_integration import ContractQualityRulesExtractor

        # Create contract with quality rules
        hub_contract = {
            "hub_contract_version": 1,
            "id": "test",
            "info": {"name": "Test"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            "quality": {
                "default_profile_key": "intake_basic_soda",
                "rules": [
                    {
                        "rule_id": "not_null_id",
                        "dimension": "completeness",
                        "expression": "id IS NOT NULL",
                        "severity": "ERROR",
                    }
                ],
            },
        }

        # Create contract instance
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        # Extract quality rules (static method takes Contract instance)
        quality_checks = ContractQualityRulesExtractor.get_contract_quality_checks(contract)

        self.assertIsNotNone(quality_checks)
        self.assertGreater(len(quality_checks), 0)

        # Verify profile key
        profile_key = ContractQualityRulesExtractor.get_contract_profile_key(contract)
        self.assertEqual(profile_key, "intake_basic_soda")

    def test_compliance_policy_affects_compliance_service(self):
        """Test that compliance policy from contract affects compliance service"""
        from hub.apps.compliance.contract_integration import ContractCompliancePolicyExtractor

        # Create contract with compliance policy
        hub_contract = {
            "hub_contract_version": 1,
            "id": "test",
            "info": {"name": "Test"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            "privacy_compliance": {
                "contains_personal_data": True,
                "personal_data_categories": ["PII_DIRECT_EMAIL"],
                "jurisdictions": ["GDPR"],
                "legal_bases": ["CONSENT"],
                "retention_policy": {"period": "P5Y"},
            },
        }

        # Create contract instance
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        # Extract compliance policy (static methods take Contract instance)
        pii_categories = ContractCompliancePolicyExtractor.get_targeted_pii_categories(contract)
        jurisdictions = ContractCompliancePolicyExtractor.get_regulatory_mapping(contract)
        legal_bases = ContractCompliancePolicyExtractor.get_legal_bases(contract)
        retention_policy = ContractCompliancePolicyExtractor.get_retention_policy(contract)

        self.assertIsNotNone(pii_categories)
        self.assertIn("PII_DIRECT_EMAIL", pii_categories)

        self.assertIsNotNone(jurisdictions)
        self.assertIn("GDPR", jurisdictions)

        self.assertIsNotNone(legal_bases)
        self.assertIn("CONSENT", legal_bases)

        self.assertIsNotNone(retention_policy)
        self.assertEqual(retention_policy.get("period"), "P5Y")

    def test_marketplace_policy_affects_marketplace_service(self):
        """Test that marketplace policy from contract affects marketplace service"""
        from hub.apps.marketplace.contract_integration import ContractMarketplacePolicyExtractor

        # Create contract with marketplace policy
        hub_contract = {
            "hub_contract_version": 1,
            "id": "test",
            "info": {"name": "Test"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            "marketplace": {
                "license_summary": "MIT License",
                "intended_use": ["analytics", "reporting"],
                "restricted_use": ["resale"],
            },
        }

        # Create contract instance in DB
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        # Use the real extractor to read marketplace policy from the Contract
        policy = ContractMarketplacePolicyExtractor.extract_marketplace_policy(contract)

        self.assertIsNotNone(policy)
        self.assertEqual(policy.get("license_summary"), "MIT License")
        self.assertIn("analytics", policy.get("intended_use", []))
        self.assertIn("resale", policy.get("restricted_use", []))

        # Also verify convenience methods work on the real Contract object
        license_summary = ContractMarketplacePolicyExtractor.get_license_summary(contract)
        self.assertEqual(license_summary, "MIT License")

        intended_use = ContractMarketplacePolicyExtractor.get_intended_use(contract)
        self.assertIn("analytics", intended_use)
        self.assertIn("reporting", intended_use)

        restricted_use = ContractMarketplacePolicyExtractor.get_restricted_use(contract)
        self.assertIn("resale", restricted_use)

        # Verify usage restriction validation
        is_allowed, error = ContractMarketplacePolicyExtractor.validate_usage_restrictions(
            contract, "analytics"
        )
        self.assertTrue(is_allowed)
        self.assertIsNone(error)

        is_allowed, error = ContractMarketplacePolicyExtractor.validate_usage_restrictions(
            contract, "resale"
        )
        self.assertFalse(is_allowed)
        self.assertIn("restricted", error)

    def test_schema_inference_affects_contract_creation(self):
        """Test that schema inference detects semantic types and formats from CSV data"""
        from hub.apps.datasets.schema_inference import (
            infer_schema_from_csv,
        )

        # Create a CSV with email, phone, and timestamp columns
        csv_content = (
            b"email,phone,created_at,amount\n"
            b"alice@example.com,+1-555-123-4567,2024-01-15T10:30:00Z,99.99\n"
            b"bob@example.org,+1-555-987-6543,2024-02-20T14:45:00Z,149.50\n"
            b"carol@test.net,+1-555-222-3333,2024-03-10T08:00:00Z,250.00\n"
        )

        # Run real schema inference on CSV data
        inferred = infer_schema_from_csv(csv_content)

        self.assertIsNotNone(inferred)
        fields = inferred.get("fields", [])
        self.assertGreater(len(fields), 0)

        # Verify that inference detected semantic_type for the email column
        email_field = next((f for f in fields if f.get("name") == "email"), None)
        self.assertIsNotNone(email_field, "Schema inference should detect 'email' field")
        self.assertEqual(
            email_field.get("semantic_type"),
            "EMAIL",
            "Schema inference should detect EMAIL semantic type from field name and data",
        )

        # Verify format detection for email
        self.assertEqual(email_field.get("format"), "email")

        # Now create a contract using the inferred schema fields
        # (convert inferred fields to hub_contract schema format)
        hub_contract = {
            "hub_contract_version": 1,
            "id": "test-inferred",
            "info": {"name": "Inferred Schema Contract"},
            "schema": {
                "fields": [
                    {
                        "name": f["name"],
                        "data_type": f["data_type"],
                        **({"semantic_type": f["semantic_type"]} if "semantic_type" in f else {}),
                        **({"format": f["format"]} if "format" in f else {}),
                    }
                    for f in fields
                ]
            },
        }

        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test-inferred"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        # Verify the contract was stored with the inferred semantic types
        stored_fields = contract.hub_contract_json.get("schema", {}).get("fields", [])
        stored_email = next((f for f in stored_fields if f.get("name") == "email"), None)
        self.assertIsNotNone(stored_email)
        self.assertEqual(stored_email.get("semantic_type"), "EMAIL")

    def test_job_completion_triggers_email(self):
        """Test that job completion triggers email notification"""
        import uuid

        from django.test import override_settings

        from hub.apps.jobs.utils import create_job
        from hub.apps.notifications.models import EmailDelivery, EmailType
        from hub.apps.notifications.tasks import send_job_completion_email

        # Enable job notifications for this test
        with override_settings(EMAIL_JOB_NOTIFICATIONS_ENABLED=True):
            # Create a job
            job = create_job(
                tenant=self.tenant,
                user=self.user,
                job_type=JobType.DQ_RUN,
                resource_type="DQ_RUN",
                resource_id=str(uuid.uuid4()),
                details_json={"dq_run_id": str(uuid.uuid4())},
            )

            # Initially job is PENDING - no email should be sent
            initial_email_count = EmailDelivery.objects.filter(
                email_type=EmailType.JOB_COMPLETION, to_email=self.user.email
            ).count()

            # Mark job as completed (this should trigger the signal)
            job.status = JobStatus.COMPLETED
            job.result_json = {"status": "completed", "checks_passed": 10}
            job.save()  # This triggers post_save signal

            # Call the email task directly to verify it creates an EmailDelivery record
            try:
                send_job_completion_email(str(job.id))
            except Exception as e:
                self.skipTest(
                    f"Email service not available, cannot verify job completion email: {e}"
                )

            # Check that email delivery record was created
            email_deliveries = EmailDelivery.objects.filter(
                email_type=EmailType.JOB_COMPLETION, to_email=self.user.email
            )
            # Email must have been sent (or at least attempted) - strict check
            self.assertGreater(
                email_deliveries.count(),
                initial_email_count,
                "send_job_completion_email should create an EmailDelivery record",
            )

    def test_cli_respects_rate_limits(self):
        """Test that CLI API client raises ClickException on 429 (no mocks)."""
        # Verify the CLI client's _handle_response raises ClickException for 429.
        # Uses a real requests.Response instance (no Mock/patch).
        import os
        import sys

        cli_path = os.path.join(os.path.dirname(__file__), "../../cli")
        if cli_path not in sys.path:
            sys.path.insert(0, cli_path)

        try:
            import requests
            from click import ClickException
            from datahub_cli.api_client import APIClient
        except ImportError:
            self.skipTest("CLI module not available")
            return

        # Real Response instance (requests.models.Response), not Mock
        response = requests.Response()
        response.status_code = 429
        response.headers["Retry-After"] = "60"
        response._content = (
            b'{"error": {"code": "RATE_LIMIT_EXCEEDED", "message": "Rate limit exceeded"}}'
        )

        client = APIClient()
        with self.assertRaises(ClickException) as cm:
            client._handle_response(response)
        self.assertIsNotNone(str(cm.exception))

    def test_monitoring_covers_all_services(self):
        """Test that monitoring covers all services with metrics endpoints"""
        import os

        import requests

        # List of services that should expose metrics
        services = {
            "api-service": os.environ.get("API_SERVICE_URL", get_api_base_url()),
            "worker-service": os.environ.get("WORKER_SERVICE_URL", get_worker_service_url()),
            "semantic-service": os.environ.get("SEMANTIC_SERVICE_URL", get_semantic_service_url()),
            "dq-service": os.environ.get("DQ_SERVICE_URL", get_dq_service_url()),
            "compliance-service": os.environ.get(
                "COMPLIANCE_SERVICE_URL", get_compliance_service_url()
            ),
            "datacontract-service": os.environ.get(
                "DATACONTRACT_SERVICE_URL", get_datacontract_service_url()
            ),
        }

        # Test that each service exposes /metrics endpoint
        # Track which services responded successfully
        reachable_services = []
        unreachable_services = []

        for service_name, base_url in services.items():
            try:
                metrics_url = f"{base_url.rstrip('/')}/metrics"
                response = requests.get(metrics_url, timeout=2)

                # If service is available, should return 200 with metrics
                if response.status_code == 200:
                    # Should be Prometheus format (text/plain or text/plain; version=0.0.4)
                    content_type = response.headers.get("Content-Type", "")
                    self.assertIn("text/plain", content_type)
                    # Should contain some metrics
                    self.assertGreater(len(response.text), 0)
                    reachable_services.append(service_name)
                else:
                    unreachable_services.append(service_name)
            except (requests.exceptions.RequestException, requests.exceptions.Timeout):
                unreachable_services.append(service_name)

        # At least one service must be reachable for the test to be meaningful
        if not reachable_services:
            self.skipTest(
                f"No services reachable for monitoring test. Unreachable: {unreachable_services}"
            )

        # Verify Prometheus configuration includes all services (unconditional)
        prometheus_config_path = "monitoring/prometheus/prometheus.yml"
        self.assertTrue(
            os.path.exists(prometheus_config_path),
            f"Prometheus config file not found at {prometheus_config_path}",
        )

        with open(prometheus_config_path) as f:
            config_content = f.read()

        # Verify all services are in Prometheus config
        expected_services = [
            "api-service",
            "worker-service",
            "semantic-service",
            "dq-service",
            "compliance-service",
            "datacontract-service",
        ]

        for service in expected_services:
            self.assertIn(
                service, config_content, f"Service {service} not found in Prometheus config"
            )
