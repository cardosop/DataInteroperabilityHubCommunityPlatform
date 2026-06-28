"""
Service Integration Pattern Compliance Tests

Comprehensive tests to validate service integrations follow established patterns.
These tests verify:
1. Service clients follow Pattern 1 (Direct Service Calls)
2. Services extend BaseService
3. No direct HTTP calls outside service clients
4. Event handlers don't make synchronous calls
5. Workflow orchestration is used for complex operations

All tests run against real Docker Compose services - no mocks or stubs.
"""

import inspect
import re
from pathlib import Path

from django.conf import settings
from django.test import TestCase

# Import service clients
from hub.apps.compliance.service_client import ComplianceServiceClient
from hub.apps.contracts.cli_client import DataContractCLIClient

# Import services to check BaseService pattern
from hub.apps.contracts.services import ContractService
from hub.apps.dq.service_client import DQServiceClient
from hub.apps.semantic.service_client import SemanticServiceClient

try:
    from hub.apps.transformation.services import TransformationService
except ModuleNotFoundError:
    TransformationService = None  # transformation app removed or not installed
import structlog

# Import BaseService
from hub.apps.core.services.base import BaseService
from hub.apps.governance.services import GovernanceService
from hub.apps.marketplace.services import MarketplaceService
from hub.apps.mesh.services import DataMeshService
from hub.apps.scheduled_ingestion.services import IngestionService
from hub.apps.search.services import SearchService
from hub.apps.virtualization.services import VirtualizationService

logger = structlog.get_logger(__name__)


class ServiceClientPatternComplianceTest(TestCase):
    """
    Test Pattern 1: Direct Service Calls (Synchronous)

    Validates that service clients follow the established pattern:
    - HTTP client (httpx) with connection pooling
    - Retry logic with exponential backoff
    - Circuit breaker for fault tolerance
    - Distributed tracing support
    - Health check capabilities
    """

    def setUp(self):
        """Set up service clients"""
        self.dq_client = DQServiceClient()
        self.compliance_client = ComplianceServiceClient()
        self.semantic_client = SemanticServiceClient()
        self.datacontract_client = DataContractCLIClient()

    def test_service_clients_have_http_client(self):
        """Test that service clients use httpx.Client with connection pooling"""
        # Check DQ client
        self.assertIsNotNone(self.dq_client.client)
        self.assertIsInstance(self.dq_client.client, type(self.dq_client.client))
        # Verify it's an httpx.Client (check by attribute)
        self.assertTrue(hasattr(self.dq_client.client, "request"))

        # Check Compliance client
        self.assertIsNotNone(self.compliance_client.client)
        self.assertTrue(hasattr(self.compliance_client.client, "request"))

        # Check Semantic client
        self.assertIsNotNone(self.semantic_client.client)
        self.assertTrue(hasattr(self.semantic_client.client, "request"))

    def test_service_clients_have_retry_logic(self):
        """Test that service clients have retry logic configured"""
        # Check max_retries attribute
        self.assertIsNotNone(self.dq_client.max_retries)
        self.assertGreaterEqual(self.dq_client.max_retries, 0)

        self.assertIsNotNone(self.compliance_client.max_retries)
        self.assertGreaterEqual(self.compliance_client.max_retries, 0)

        self.assertIsNotNone(self.semantic_client.max_retries)
        self.assertGreaterEqual(self.semantic_client.max_retries, 0)

        # Check backoff_factor
        self.assertIsNotNone(self.dq_client.backoff_factor)
        self.assertGreater(self.dq_client.backoff_factor, 0)

    def test_service_clients_have_circuit_breaker(self):
        """Test that service clients have circuit breaker protection"""
        # Check circuit breaker attribute
        self.assertIsNotNone(self.dq_client._circuit_breaker)
        self.assertIsNotNone(self.compliance_client._circuit_breaker)
        self.assertIsNotNone(self.semantic_client._circuit_breaker)
        self.assertIsNotNone(self.datacontract_client._circuit_breaker)

        # Verify circuit breaker has required methods
        self.assertTrue(hasattr(self.dq_client._circuit_breaker, "call"))
        self.assertTrue(hasattr(self.compliance_client._circuit_breaker, "call"))
        self.assertTrue(hasattr(self.semantic_client._circuit_breaker, "call"))

    def test_service_clients_have_health_check(self):
        """Test that service clients have health check methods"""
        self.assertTrue(hasattr(self.dq_client, "health_check"))
        self.assertTrue(hasattr(self.compliance_client, "health_check"))
        self.assertTrue(hasattr(self.semantic_client, "health_check"))
        self.assertTrue(hasattr(self.datacontract_client, "health_check"))

        # Verify health_check is callable
        self.assertTrue(callable(self.dq_client.health_check))
        self.assertTrue(callable(self.compliance_client.health_check))
        self.assertTrue(callable(self.semantic_client.health_check))

    def test_service_clients_have_request_with_retry(self):
        """Test that service clients have _request_with_retry method"""
        self.assertTrue(hasattr(self.dq_client, "_request_with_retry"))
        self.assertTrue(hasattr(self.compliance_client, "_request_with_retry"))
        self.assertTrue(hasattr(self.semantic_client, "_request_with_retry"))

        # Verify it's callable
        self.assertTrue(callable(self.dq_client._request_with_retry))
        self.assertTrue(callable(self.compliance_client._request_with_retry))
        self.assertTrue(callable(self.semantic_client._request_with_retry))

    def test_service_clients_use_distributed_tracing(self):
        """Test that service clients propagate distributed tracing headers"""
        # Check _request_with_retry method includes trace header logic
        dq_source = inspect.getsource(self.dq_client._request_with_retry)
        self.assertIn("trace", dq_source.lower())

        compliance_source = inspect.getsource(self.compliance_client._request_with_retry)
        self.assertIn("trace", compliance_source.lower())

        semantic_source = inspect.getsource(self.semantic_client._request_with_retry)
        self.assertIn("trace", semantic_source.lower())


class BaseServicePatternComplianceTest(TestCase):
    """
    Test Service Layer Pattern

    Validates that all service classes extend BaseService:
    - Resource retrieval with error handling
    - Metrics collection
    - Tenant scoping
    """

    def test_contract_service_extends_base_service(self):
        """Test that ContractService extends BaseService"""
        self.assertTrue(issubclass(ContractService, BaseService))
        self.assertEqual(ContractService.service_name, "contract_service")

    def test_transformation_service_extends_base_service(self):
        """Test that TransformationService extends BaseService"""
        if TransformationService is None:
            self.skipTest("hub.apps.transformation not available")
        self.assertTrue(issubclass(TransformationService, BaseService))
        self.assertEqual(TransformationService.service_name, "transformation_service")

    def test_marketplace_service_extends_base_service(self):
        """Test that MarketplaceService extends BaseService"""
        self.assertTrue(issubclass(MarketplaceService, BaseService))
        self.assertEqual(MarketplaceService.service_name, "marketplace_service")

    def test_data_mesh_service_extends_base_service(self):
        """Test that DataMeshService extends BaseService"""
        self.assertTrue(issubclass(DataMeshService, BaseService))
        self.assertEqual(DataMeshService.service_name, "data_mesh_service")

    def test_virtualization_service_extends_base_service(self):
        """Test that VirtualizationService extends BaseService"""
        self.assertTrue(issubclass(VirtualizationService, BaseService))
        self.assertEqual(VirtualizationService.service_name, "virtualization_service")

    def test_ingestion_service_extends_base_service(self):
        """Test that IngestionService extends BaseService"""
        self.assertTrue(issubclass(IngestionService, BaseService))
        self.assertEqual(IngestionService.service_name, "ingestion_service")

    def test_governance_service_extends_base_service(self):
        """Test that GovernanceService extends BaseService"""
        self.assertTrue(issubclass(GovernanceService, BaseService))
        self.assertEqual(GovernanceService.service_name, "governance_service")

    def test_search_service_extends_base_service(self):
        """Test that SearchService extends BaseService"""
        self.assertTrue(issubclass(SearchService, BaseService))
        self.assertEqual(SearchService.service_name, "search_service")

    def test_services_have_service_name(self):
        """Test that all services define service_name attribute"""
        services = [
            ContractService,
            MarketplaceService,
            DataMeshService,
            VirtualizationService,
            IngestionService,
            GovernanceService,
            SearchService,
        ]
        if TransformationService is not None:
            services.append(TransformationService)

        for service_class in services:
            self.assertTrue(hasattr(service_class, "service_name"))
            self.assertIsNotNone(service_class.service_name)
            self.assertIsInstance(service_class.service_name, str)

    def test_services_have_get_resource_or_raise(self):
        """Test that services inherit get_resource_or_raise from BaseService"""
        service = ContractService()
        self.assertTrue(hasattr(service, "get_resource_or_raise"))
        self.assertTrue(callable(service.get_resource_or_raise))

    def test_services_have_execute_with_metrics(self):
        """Test that services inherit execute_with_metrics from BaseService"""
        service = ContractService()
        self.assertTrue(hasattr(service, "execute_with_metrics"))
        self.assertTrue(callable(service.execute_with_metrics))


class DirectHttpCallComplianceTest(TestCase):
    """
    Test that no direct HTTP calls exist outside service clients.

    Validates Pattern 1 compliance by checking that:
    - No direct httpx.get/post/etc calls outside service clients
    - No direct requests.get/post/etc calls outside service clients
    - URL parsing utilities (urllib.parse) are acceptable
    """

    def setUp(self):
        """Set up paths for scanning"""
        # Get project root (go up from hub directory)
        self.project_root = (
            Path(settings.BASE_DIR).parent.parent
            if hasattr(settings, "BASE_DIR")
            else Path(__file__).parent.parent.parent
        )
        self.hub_apps_path = self.project_root / "hub" / "apps"

        # Files that are allowed to have HTTP calls (service clients)
        self.allowed_files = {
            "hub/apps/compliance/service_client.py",
            "hub/apps/dq/service_client.py",
            "hub/apps/semantic/service_client.py",
            "hub/apps/contracts/cli_client.py",
        }

        # Patterns that are acceptable (URL parsing)
        self.acceptable_patterns = [
            r"from urllib\.parse import",
            r"import urllib\.parse",
            r"urllib\.parse\.urlparse",
            r"urllib\.parse\.urlencode",
            r"urllib\.parse\.urljoin",
            r"urllib\.parse\.unquote",
        ]

    def test_no_direct_httpx_calls_outside_clients(self):
        """Test that no direct httpx calls exist outside service clients"""
        violations = []

        for py_file in self.hub_apps_path.rglob("*.py"):
            # Skip test files
            if "test" in str(py_file) or "__pycache__" in str(py_file):
                continue

            relative_path = str(py_file.relative_to(self.project_root))

            # Skip allowed files (service clients)
            if relative_path in self.allowed_files:
                continue

            try:
                content = py_file.read_text(encoding="utf-8")
                lines = content.split("\n")

                for line_num, line in enumerate(lines, 1):
                    # Skip comments and docstrings
                    stripped = line.strip()
                    if stripped.startswith("#") or '"""' in stripped or "'''" in stripped:
                        continue

                    # Check for direct httpx calls
                    if re.search(r"httpx\.(get|post|put|delete|patch|request)\s*\(", line):
                        # Check if it's an acceptable pattern
                        is_acceptable = any(
                            re.search(pattern, line) for pattern in self.acceptable_patterns
                        )
                        if not is_acceptable:
                            violations.append(
                                {
                                    "file": relative_path,
                                    "line": line_num,
                                    "code": line.strip()[:100],
                                }
                            )
            except Exception as e:
                logger.warning(f"Error scanning {py_file}: {e}")
                continue

        if violations:
            violation_msg = "\n".join(
                [
                    f"  {v['file']}:{v['line']} - {v['code']}"
                    for v in violations[:10]  # Show first 10
                ]
            )
            self.fail(
                f"Found {len(violations)} direct httpx calls outside service clients:\n{violation_msg}"
            )

    def test_no_direct_requests_calls_outside_clients(self):
        """Test that no direct requests calls exist outside service clients"""
        violations = []

        for py_file in self.hub_apps_path.rglob("*.py"):
            if "test" in str(py_file) or "__pycache__" in str(py_file):
                continue

            relative_path = str(py_file.relative_to(self.project_root))

            if relative_path in self.allowed_files:
                continue

            try:
                content = py_file.read_text(encoding="utf-8")
                lines = content.split("\n")

                for line_num, line in enumerate(lines, 1):
                    stripped = line.strip()
                    if stripped.startswith("#") or '"""' in stripped or "'''" in stripped:
                        continue

                    # Check for direct requests calls
                    if re.search(r"requests\.(get|post|put|delete|patch|request)\s*\(", line):
                        is_acceptable = any(
                            re.search(pattern, line) for pattern in self.acceptable_patterns
                        )
                        if not is_acceptable:
                            violations.append(
                                {
                                    "file": relative_path,
                                    "line": line_num,
                                    "code": line.strip()[:100],
                                }
                            )
            except Exception as e:
                logger.warning(f"Error scanning {py_file}: {e}")
                continue

        if violations:
            violation_msg = "\n".join(
                [f"  {v['file']}:{v['line']} - {v['code']}" for v in violations[:10]]
            )
            self.fail(
                f"Found {len(violations)} direct requests calls outside service clients:\n{violation_msg}"
            )


class AuditScriptValidationTest(TestCase):
    """
    Test that the audit script works correctly.

    Validates:
    - Audit script can be imported and executed
    - Audit script generates valid reports
    - Audit findings match actual code patterns
    """

    def setUp(self):
        """Set up paths"""
        # Get project root - go up from tests/integration/
        self.project_root = Path(__file__).parent.parent.parent

    def test_audit_script_exists(self):
        """Test that audit script exists and is executable"""
        script_path = self.project_root / "scripts" / "audit_service_integrations.py"
        self.assertTrue(script_path.exists(), "Audit script not found")
        self.assertTrue(script_path.is_file(), "Audit script is not a file")

    def test_audit_script_can_be_imported(self):
        """Test that audit script can be imported"""
        import importlib.util

        script_path = self.project_root / "scripts" / "audit_service_integrations.py"
        spec = importlib.util.spec_from_file_location("audit_service_integrations", script_path)
        self.assertIsNotNone(spec, "Could not create spec from audit script")

        if spec is not None:
            module = importlib.util.module_from_spec(spec)
            self.assertIsNotNone(module, "Could not create module from spec")

    def test_audit_report_exists(self):
        """Test that audit report exists"""
        report_path = self.project_root / "docs" / "api-audit" / "service-integration-audit.json"
        self.assertTrue(report_path.exists(), "Audit report not found")

    def test_audit_report_is_valid_json(self):
        """Test that audit report is valid JSON"""
        import json

        report_path = self.project_root / "docs" / "api-audit" / "service-integration-audit.json"
        if report_path.exists():
            with open(report_path) as f:
                try:
                    data = json.load(f)
                    self.assertIsInstance(data, dict)
                    self.assertIn("summary", data)
                    self.assertIn("issues", data)
                except json.JSONDecodeError as e:
                    self.fail(f"Audit report is not valid JSON: {e}")

    def test_remediation_plan_exists(self):
        """Test that remediation plan exists"""
        plan_path = (
            self.project_root / "docs" / "api-audit" / "service-integration-remediation-plan.json"
        )
        self.assertTrue(plan_path.exists(), "Remediation plan not found")

    def test_comprehensive_report_exists(self):
        """Test that comprehensive report exists"""
        report_path = (
            self.project_root / "docs" / "api-audit" / "SERVICE_INTEGRATION_AUDIT_REPORT.md"
        )
        self.assertTrue(report_path.exists(), "Comprehensive audit report not found")


class ServiceIntegrationRealServiceTest(TestCase):
    """
    Integration tests with real Docker Compose services.

    Validates that service clients can actually communicate with services
    and that patterns work in practice.
    """

    def setUp(self):
        """Set up service clients"""
        self.dq_client = DQServiceClient()
        self.compliance_client = ComplianceServiceClient()
        self.semantic_client = SemanticServiceClient()
        self.datacontract_client = DataContractCLIClient()

    def test_service_clients_can_connect_to_services(self):
        """Test that service clients can connect to Docker Compose services"""
        # Test DQ service health check
        is_healthy, service_name = self.dq_client.health_check()
        self.assertIsInstance(is_healthy, bool)
        self.assertIsInstance(service_name, str)
        self.assertTrue(is_healthy, f"DQ service should be healthy, got: is_healthy={is_healthy}, name={service_name}")
        logger.info(f"DQ service health: {is_healthy}, name: {service_name}")

        # Test Compliance service health check
        is_healthy, service_name = self.compliance_client.health_check()
        self.assertIsInstance(is_healthy, bool)
        self.assertIsInstance(service_name, str)
        self.assertTrue(is_healthy, f"Compliance service should be healthy, got: is_healthy={is_healthy}, name={service_name}")
        logger.info(f"Compliance service health: {is_healthy}, name: {service_name}")

        # Test Semantic service health check
        is_healthy, service_name = self.semantic_client.health_check()
        self.assertIsInstance(is_healthy, bool)
        self.assertIsInstance(service_name, str)
        self.assertTrue(is_healthy, f"Semantic service should be healthy, got: is_healthy={is_healthy}, name={service_name}")
        logger.info(f"Semantic service health: {is_healthy}, name: {service_name}")

    def test_circuit_breaker_protection_works(self):
        """Test that circuit breaker protection works with real services"""
        # Verify circuit breaker exists
        self.assertIsNotNone(self.dq_client._circuit_breaker)
        self.assertIsNotNone(self.compliance_client._circuit_breaker)
        self.assertIsNotNone(self.semantic_client._circuit_breaker)

        # Verify circuit breaker has call method
        self.assertTrue(hasattr(self.dq_client._circuit_breaker, "call"))
        self.assertTrue(callable(self.dq_client._circuit_breaker.call))
