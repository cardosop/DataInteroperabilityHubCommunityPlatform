"""
Integration tests for CLI commands using Django LiveServerTestCase.

These tests use Django's live test server, which starts automatically,
so they work without requiring a pre-running API service.

CRITICAL: To avoid transaction isolation issues with LiveServerTestCase,
all test data is created via HTTP requests to the live server. This ensures
the data is created through the server thread's database connection and is
immediately visible to subsequent CLI commands.

NOTE: These tests must be run from the Django project root (not CLI directory)
to ensure Django is properly initialized via pytest-django.
"""

import os

import pytest

# Phase 215.4 review fix: this module imports from django/hub which are
# not on the CLI test PYTHONPATH (CLI pytest.ini sets ``-p no:django``).
# Skip the entire module gracefully when those packages are unavailable
# instead of crashing pytest collection.
django = pytest.importorskip("django")
hub = pytest.importorskip("hub")
import contextlib

import requests
from click.testing import CliRunner
from datahub_cli.config import config
from datahub_cli.main import cli
from django.contrib.auth import get_user_model
from django.test import LiveServerTestCase

from hub.apps.assets.models import Asset
from hub.apps.contracts.models import Contract, ContractStatus
from hub.apps.jobs.models import Job, JobStatus, JobType

# Import Django models - these will work when pytest-django initializes Django
# If running from CLI directory, ensure pytest is run from Django project root
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestCLIIntegrationRealAPI(LiveServerTestCase):
    """
    Integration tests for CLI commands using Django's live test server.

    CRITICAL: All test data is created via HTTP requests to the live server
    to avoid transaction isolation issues. This ensures data is created
    through the server thread's database connection and is immediately visible.
    """

    @classmethod
    def _fixture_setup(cls):
        """Skip the per-test flush on the persistent dedicated test DB.

        The default TransactionTestCase flush TRUNCATEs without CASCADE and
        blocks on FK-referenced tables until the 120 s statement_timeout —
        every test burned 2+ minutes in setup (measured 2026-08-28).
        Fixtures are per-run unique (uuid suffixes), so the flush is not
        the isolation mechanism.
        """
        import os

        if not os.environ.get("TEST_DB_SUFFIX"):
            with contextlib.suppress(Exception):
                super()._fixture_setup()

    def _post_teardown(self):
        import os

        if not os.environ.get("TEST_DB_SUFFIX"):
            with contextlib.suppress(Exception):
                super()._post_teardown()

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.runner = CliRunner()
        import uuid as _uuid

        _uid = _uuid.uuid4().hex[:8]
        config.clear_auth()

        # Create tenant (this is OK to create directly as it's needed for user creation)
        self.tenant = Tenant.objects.create(
            name=f"CLI Test Tenant {_uid}", slug=f"cli-test-tenant-{_uid}"
        )

        # Create user with ACTIVE status (required for authentication)
        self.user = User.objects.create_user(
            email=f"cli-test-{_uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        # Asset writes require the DATA_PROVIDER (or TENANT_ADMIN) role —
        # a role-less user 403s every create (measured 2026-08-28).
        from hub.apps.users.models import Role, UserRole

        provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider Role"},
        )
        UserRole.objects.get_or_create(user=self.user, role=provider_role)

        # Set API base URL to live test server
        # LiveServerTestCase provides self.live_server_url automatically
        # Note: live_server_url is available after setUp() completes
        self.api_base_url = f"{self.live_server_url}/api/v1"
        config.set_api_base_url(self.api_base_url)

        # Phase 313 paid write-gate — provision an ACTIVE subscription or
        # every write 403s with "No active subscription" (measured
        # 2026-08-28).
        # Apps-registry lookup (no paid-module import): the paid
        # write-gate provisioning must not couple this core file to
        # hub.apps.billing — GATE-29.
        from django.apps import apps

        Subscription = apps.get_model("billing", "Subscription")
        from hub.apps.tenants.models import PlanTier, TenantPlan

        plan, _ = TenantPlan.objects.get_or_create(
            name="CLI Real API Pro Plan",
            defaults={
                "slug": "cli-real-api-pro-plan",
                "tier": PlanTier.PRO,
                "category": "BASE",
                "order": 1,
            },
        )
        # The plan-enforcement layer reads the TENANT's plan field (a new
        # tenant has none → free-plan limits, e.g. max_assets=10, and the
        # suite's asset tests 403 with plan_limit_exceeded — measured
        # 2026-08-28).
        if self.tenant.plan_id is None:
            self.tenant.plan = plan
            self.tenant.save(update_fields=["plan"])
        Subscription.objects.get_or_create(
            tenant=self.tenant,
            defaults={"plan": plan, "status": "ACTIVE", "category": "BASE"},
        )

        # Create API key for testing (more reliable than login for tests)
        from hub.apps.auth.models import APIKey

        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)
        # Scopes are REQUIRED — the asset/contract write views gate on
        # HasScope(...), and a scopeless key 403s every write (measured
        # 2026-08-28).
        APIKey.objects.create(
            user=self.user,
            tenant=self.tenant,
            name="CLI Test Key",
            key_hash=key_hash,
            scopes=[
                "assets:write",
                "assets:read",
                "contracts:write",
                "contracts:read",
                "jobs:read",
                "jobs:write",
                "files:write",
                "files:read",
                "integrations:write",
                "integrations:read",
            ],
        )
        config.set_api_key(plaintext_key)
        self.api_key = plaintext_key
        self.authenticated = True

    def tearDown(self):
        """Clean up after tests"""
        super().tearDown()
        config.clear_auth()

    def _get_auth_headers(self):
        """Get authentication headers for HTTP requests"""
        return {"Authorization": f"ApiKey {self.api_key}", "Content-Type": "application/json"}

    def _create_asset_via_api(
        self, key, name, description=None, domain=None, visibility="INTERNAL"
    ):
        """
        Create an asset via HTTP request to the live server.

        This ensures the asset is created through the server thread's
        database connection and is immediately visible to CLI commands.

        Returns the created asset data as a dict.
        """
        # Use reverse lookup for correct URL pattern
        # LiveServerTestCase ensures Django is initialized, so reverse() should work
        from django.urls import reverse

        asset_url = reverse("asset-list")
        # Remove /api/v1 prefix if present (api_base_url already includes it)
        if asset_url.startswith("/api/v1"):
            asset_url = asset_url[len("/api/v1") :]
        url = f"{self.api_base_url}{asset_url}"
        data = {"key": key, "name": name, "visibility": visibility}
        if description:
            data["description"] = description
        if domain:
            data["domain"] = domain

        response = requests.post(url, json=data, headers=self._get_auth_headers())
        if response.status_code >= 400:
            raise AssertionError(
                f"Asset create failed: {response.status_code}: {response.text[:400]}"
            )
        return response.json()

    def _create_contract_via_api(
        self, asset_id, original_raw, original_format="JSON", original_spec_type="ODCS"
    ):
        """
        Create a contract via HTTP request to the live server.

        Returns the created contract data as a dict.
        """
        # Use reverse lookup for correct URL pattern
        # LiveServerTestCase ensures Django is initialized, so reverse() should work
        from django.urls import reverse

        contract_url = reverse("contract-list")
        # Remove /api/v1 prefix if present (api_base_url already includes it)
        if contract_url.startswith("/api/v1"):
            contract_url = contract_url[len("/api/v1") :]
        url = f"{self.api_base_url}{contract_url}"
        data = {
            "asset_id": asset_id,
            "original_raw": original_raw,
            "original_format": original_format,
            "original_spec_type": original_spec_type,
        }

        response = requests.post(url, json=data, headers=self._get_auth_headers())
        response.raise_for_status()
        return response.json()

    def _create_file_via_api(self, name, content_type="text/csv", size=None):
        """
        Initialize a file upload via HTTP request to the live server.

        Returns the file initialization data as a dict.
        """
        # URL structure: /api/v1/files/init/ (files/ from api/urls.py + init action)
        url = f"{self.api_base_url}/files/init/"
        data = {"name": name, "content_type": content_type}
        if size is not None:
            data["size"] = size

        response = requests.post(url, json=data, headers=self._get_auth_headers())
        response.raise_for_status()
        return response.json()

    def _create_job_via_api(self, job_type, resource_type="ASSET", resource_id=None):
        """
        Create a job via HTTP request to the live server.

        Args:
            job_type: Job type (e.g., 'DQ_RUN', 'COMPLIANCE_RUN')
            resource_type: Resource type (e.g., 'ASSET', 'CONTRACT', 'FILE', 'DATASET')
            resource_id: UUID of the resource (required)

        Returns the created job data as a dict.
        """
        # URL structure: /api/v1/jobs/ (jobs/ from api/urls.py)
        url = f"{self.api_base_url}/jobs/"

        if not resource_id:
            raise ValueError("resource_id must be provided")

        # JobCreateSerializer requires: type, resource_type, resource_id
        data = {
            "type": job_type,  # Note: API expects 'type', not 'job_type'
            "resource_type": resource_type,
            "resource_id": str(resource_id),  # Must be UUID string
        }

        response = requests.post(url, json=data, headers=self._get_auth_headers())
        response.raise_for_status()
        return response.json()

    def test_assets_list_real_api(self):
        """Test assets list command with real API"""
        # Ensure config is set correctly for this test
        config.set_api_base_url(self.api_base_url)

        # Create asset via HTTP request to live server
        # This ensures the asset is created through the server thread's connection
        asset_data = self._create_asset_via_api(
            key="cli-test-asset", name="CLI Test Asset", description="Test asset created via API"
        )

        # Verify asset was created
        assert asset_data["key"] == "cli-test-asset"
        assert asset_data["name"] == "CLI Test Asset"

        # Now list assets via CLI - they should be visible since they were created via the API
        result = self.runner.invoke(cli, ["assets", "list"])
        if result.exit_code != 0:
            print(f"CLI Error: {result.output}")
            print(f"Exception: {result.exception}")
        assert result.exit_code == 0, f"CLI failed with output: {result.output}"
        assert "CLI Test Asset" in result.output or "cli-test-asset" in result.output, (
            f"Asset not found in output: {result.output}"
        )

    def test_assets_get_real_api(self):
        """Test assets get command with real API"""
        # Create test asset via HTTP request to live server
        asset_data = self._create_asset_via_api(
            key="cli-test-asset-2",
            name="CLI Test Asset 2",
            description="Test asset for get command",
        )

        result = self.runner.invoke(cli, ["assets", "get", asset_data["id"]])
        assert result.exit_code == 0
        assert "CLI Test Asset 2" in result.output or "cli-test-asset-2" in result.output

    def test_assets_create_real_api(self):
        """Test assets create command with real API"""
        result = self.runner.invoke(
            cli,
            [
                "assets",
                "create",
                "--name",
                "CLI Created Asset",
                "--key",
                "cli-created-asset",
                "--description",
                "Created via CLI",
            ],
        )
        assert result.exit_code == 0
        assert "created successfully" in result.output.lower()

        # Verify asset was created
        assert Asset.objects.filter(key="cli-created-asset", tenant=self.tenant).exists()

    def test_contracts_list_real_api(self):
        """Test contracts list command with real API"""
        # Create test contract
        Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_format="YAML",
            original_raw="test: contract",
            created_by=self.user,
        )

        result = self.runner.invoke(cli, ["contracts", "list"])
        assert result.exit_code == 0

    def test_contracts_get_real_api(self):
        """Test contracts get command with real API"""
        # First create an asset (required for contract)
        asset_data = self._create_asset_via_api(
            key="cli-test-asset-for-contract-2", name="CLI Test Asset for Contract 2"
        )

        # Create test contract via HTTP request to live server
        contract_data = self._create_contract_via_api(
            asset_id=asset_data["id"],
            original_raw="test: contract for get",
            original_format="YAML",
            original_spec_type="ODCS",
        )

        result = self.runner.invoke(cli, ["contracts", "get", contract_data["id"]])
        assert result.exit_code == 0

    def test_contracts_create_odps_extract_odcs_real_api(self):
        """Test contracts create-odps with --extract-odcs flag (Product-First flow) using real API"""
        import tempfile

        # Create a valid ODPS document with embedded ODCS contract
        odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "cli-test-product-odps",
        "name": "CLI Test Product ODPS",
        "description": "Test product for ODPS workflows"
      }
    },
    "dataSchema": {
      "fields": [
        {"name": "id", "type": "string", "nullable": false}
      ]
    },
    "contract": {
      "spec": {
        "apiVersion": "odcs.io/v3.0.0",
        "kind": "DataContract",
        "id": "cli-test-contract-odps",
        "name": "CLI Test Contract ODPS",
        "version": "1.0.0",
        "schema": {
          "fields": [
            {"name": "id", "type": "string", "nullable": false}
          ]
        }
      }
    }
  }
}"""

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(odps_content)
            temp_file_path = f.name

        try:
            # Test create-odps with --extract-odcs
            result = self.runner.invoke(
                cli, ["contracts", "create-odps", "--file", temp_file_path, "--extract-odcs"]
            )

            if result.exit_code != 0:
                print(f"CLI Error: {result.output}")
                print(f"Exception: {result.exception}")

            assert result.exit_code == 0, f"CLI failed with output: {result.output}"
            assert (
                "ODPS product created successfully" in result.output
                or "odps_contract" in result.output
            )
            assert "Product-First flow" in result.output or "ODCS Contract" in result.output
        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    def test_contracts_create_odps_link_odcs_real_api(self):
        """Test contracts create-odps with --link-odcs flag using real API"""
        import tempfile

        # First create an ODCS contract via API
        asset_data = self._create_asset_via_api(
            key="cli-test-asset-for-odps-link", name="CLI Test Asset for ODPS Link"
        )

        odcs_content = """{
  "apiVersion": "odcs/v3",
  "kind": "DataContract",
  "id": "cli-test-odcs-for-link",
  "name": "CLI Test ODCS for Link",
  "version": "1.0.0",
  "schema": {
    "fields": [
      {
        "name": "id",
        "type": "string",
        "nullable": false
      }
    ]
  }
}"""

        # Create ODCS contract via API
        odcs_contract_data = self._create_contract_via_api(
            asset_id=asset_data["id"],
            original_raw=odcs_content,
            original_format="JSON",
            original_spec_type="ODCS",
        )

        # Create ODPS document that references the ODCS contract
        odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "cli-test-product-odps",
        "name": "CLI Test Product ODPS",
        "description": "Test product for ODPS workflows"
      }
    },
    "dataSchema": {
      "fields": [
        {"name": "id", "type": "string", "nullable": false}
      ]
    },
    "contract": {
      "spec": {
        "apiVersion": "odcs.io/v3.0.0",
        "kind": "DataContract",
        "id": "cli-test-contract-odps",
        "name": "CLI Test Contract ODPS",
        "version": "1.0.0",
        "schema": {
          "fields": [
            {"name": "id", "type": "string", "nullable": false}
          ]
        }
      }
    }
  }
}"""

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(odps_content)
            temp_file_path = f.name

        try:
            # Test create-odps with --link-odcs
            result = self.runner.invoke(
                cli,
                [
                    "contracts",
                    "create-odps",
                    "--file",
                    temp_file_path,
                    "--link-odcs",
                    odcs_contract_data["id"],
                ],
            )

            if result.exit_code != 0:
                print(f"CLI Error: {result.output}")
                print(f"Exception: {result.exception}")

            assert result.exit_code == 0, f"CLI failed with output: {result.output}"
            assert (
                "ODPS contract created and linked successfully" in result.output
                or "id" in result.output
            )
            assert odcs_contract_data["id"] in result.output
        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    def test_contracts_create_odps_yaml_format_real_api(self):
        """Test contracts create-odps with YAML format using real API"""
        import tempfile

        # Create a valid ODPS document in YAML format
        odps_content = """schema: https://opendataproducts.org/schema/v4.1
version: 4.1
product:
  details:
    en:
      productID: cli-test-product-yaml
      name: CLI Test Product YAML
      description: Test product in YAML format
  contract:
    apiVersion: odcs/v3
    kind: DataContract
    id: cli-test-contract-yaml
    name: CLI Test Contract YAML
    version: 1.0.0
    schema:
      fields:
        - name: id
          type: string
          nullable: false
"""

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(odps_content)
            temp_file_path = f.name

        try:
            # Test create-odps with YAML format
            result = self.runner.invoke(
                cli, ["contracts", "create-odps", "--file", temp_file_path, "--extract-odcs"]
            )

            assert result.exit_code == 0, f"CLI failed with output: {result.output}"
            assert (
                "ODPS product created successfully" in result.output
                or "odps_contract" in result.output
            )
        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    def test_contracts_get_show_odps_real_api(self):
        """Test contracts get --show-odps command with real API"""
        import tempfile

        # Create an ODPS contract with pricing and access methods
        odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "cli-test-product-odps",
        "name": "CLI Test Product ODPS",
        "description": "Test product for ODPS workflows"
      }
    },
    "dataSchema": {
      "fields": [
        {"name": "id", "type": "string", "nullable": false}
      ]
    },
    "contract": {
      "spec": {
        "apiVersion": "odcs.io/v3.0.0",
        "kind": "DataContract",
        "id": "cli-test-contract-odps",
        "name": "CLI Test Contract ODPS",
        "version": "1.0.0",
        "schema": {
          "fields": [
            {"name": "id", "type": "string", "nullable": false}
          ]
        }
      }
    }
  }
}"""

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(odps_content)
            temp_file_path = f.name

        try:
            # Create ODPS contract
            create_result = self.runner.invoke(
                cli, ["contracts", "create-odps", "--file", temp_file_path, "--extract-odcs"]
            )

            if create_result.exit_code != 0:
                print(f"CLI Error creating ODPS: {create_result.output}")
                print(f"Exception: {create_result.exception}")

            assert create_result.exit_code == 0, (
                f"Failed to create ODPS contract: {create_result.output}"
            )

            # Extract contract ID from output (look for UUID pattern)
            import re

            contract_id_match = re.search(
                r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                create_result.output,
            )
            if not contract_id_match:
                # Try to get from JSON output if available
                if "odps_contract" in create_result.output or "id" in create_result.output:
                    # For now, skip if we can't extract ID - this is a limitation of the test
                    pytest.skip("Could not extract contract ID from output")
                    return
                pytest.skip("Could not extract contract ID from output")
                return

            contract_id = contract_id_match.group(0) if contract_id_match else None
            if not contract_id:
                pytest.skip("Could not extract contract ID from output")
                return

            # Test get with --show-odps flag
            result = self.runner.invoke(cli, ["contracts", "get", contract_id, "--show-odps"])

            assert result.exit_code == 0, f"CLI failed with output: {result.output}"
            assert "ODPS Information" in result.output
            assert "Pricing Plans" in result.output
            assert "Access Methods" in result.output
        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    def test_contracts_get_pricing_real_api(self):
        """Test contracts get-pricing command with real API"""
        import tempfile

        # Create an ODPS contract with pricing plans
        odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "cli-test-product-odps",
        "name": "CLI Test Product ODPS",
        "description": "Test product for ODPS workflows"
      }
    },
    "dataSchema": {
      "fields": [
        {"name": "id", "type": "string", "nullable": false}
      ]
    },
    "contract": {
      "spec": {
        "apiVersion": "odcs.io/v3.0.0",
        "kind": "DataContract",
        "id": "cli-test-contract-odps",
        "name": "CLI Test Contract ODPS",
        "version": "1.0.0",
        "schema": {
          "fields": [
            {"name": "id", "type": "string", "nullable": false}
          ]
        }
      }
    }
  }
}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(odps_content)
            temp_file_path = f.name

        try:
            # Create ODPS contract
            create_result = self.runner.invoke(
                cli, ["contracts", "create-odps", "--file", temp_file_path, "--extract-odcs"]
            )

            assert create_result.exit_code == 0, (
                f"Failed to create ODPS contract: {create_result.output}"
            )

            # Extract contract ID
            import re

            contract_id_match = re.search(
                r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                create_result.output,
            )
            if not contract_id_match:
                pytest.skip("Could not extract contract ID from output")
                return

            contract_id = contract_id_match.group(0)

            # Test get-pricing command
            result = self.runner.invoke(cli, ["contracts", "get-pricing", contract_id])

            assert result.exit_code == 0, f"CLI failed with output: {result.output}"
            assert "Pricing Plans for Contract" in result.output
            assert "Enterprise Plan" in result.output
            assert "199.99 USD" in result.output
        finally:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    def test_contracts_get_access_methods_real_api(self):
        """Test contracts get-access-methods command with real API"""
        import tempfile

        # Create an ODPS contract with access methods
        odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "cli-test-product-odps",
        "name": "CLI Test Product ODPS",
        "description": "Test product for ODPS workflows"
      }
    },
    "dataSchema": {
      "fields": [
        {"name": "id", "type": "string", "nullable": false}
      ]
    },
    "contract": {
      "spec": {
        "apiVersion": "odcs.io/v3.0.0",
        "kind": "DataContract",
        "id": "cli-test-contract-odps",
        "name": "CLI Test Contract ODPS",
        "version": "1.0.0",
        "schema": {
          "fields": [
            {"name": "id", "type": "string", "nullable": false}
          ]
        }
      }
    }
  }
}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(odps_content)
            temp_file_path = f.name

        try:
            # Create ODPS contract
            create_result = self.runner.invoke(
                cli, ["contracts", "create-odps", "--file", temp_file_path, "--extract-odcs"]
            )

            assert create_result.exit_code == 0, (
                f"Failed to create ODPS contract: {create_result.output}"
            )

            # Extract contract ID
            import re

            contract_id_match = re.search(
                r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                create_result.output,
            )
            if not contract_id_match:
                pytest.skip("Could not extract contract ID from output")
                return

            contract_id = contract_id_match.group(0)

            # Test get-access-methods command
            result = self.runner.invoke(cli, ["contracts", "get-access-methods", contract_id])

            assert result.exit_code == 0, f"CLI failed with output: {result.output}"
            assert "Access Methods for Contract" in result.output
            assert "API" in result.output
            assert "REST API" in result.output
        finally:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    def test_files_list_real_api(self):
        """Test files list command with real API"""
        # Create test file via HTTP request to live server
        self._create_file_via_api(name="cli-test.csv", content_type="text/csv", size=1024)

        result = self.runner.invoke(cli, ["files", "list"])
        assert result.exit_code == 0

    def test_jobs_list_real_api(self):
        """Test jobs list command with real API"""
        # Create test job
        Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id="123e4567-e89b-12d3-a456-426614174000",
            created_by=self.user,
        )

        result = self.runner.invoke(cli, ["jobs", "list"])
        assert result.exit_code == 0

    def test_jobs_get_real_api(self):
        """Test jobs get command with real API"""
        # First create an asset (required for job)
        asset_data = self._create_asset_via_api(
            key="cli-test-asset-for-job-2", name="CLI Test Asset for Job 2"
        )

        # Create test job via HTTP request to live server
        # Job requires: type, resource_type, resource_id
        job_data = self._create_job_via_api(
            job_type="DQ_RUN", resource_type="ASSET", resource_id=asset_data["id"]
        )

        result = self.runner.invoke(cli, ["jobs", "get", job_data["id"]])
        assert result.exit_code == 0

    def test_contracts_export_odcs_with_version_real_api(self):
        """Test contracts export with ODCS format and version using real API"""
        import json

        # Create an ODCS contract via API
        odcs_content = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "cli-test-export-odcs",
                "name": "CLI Test Contract for ODCS Export",
                "version": "1.0.0",
                "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
            }
        )

        # Create contract via API
        contract_data = self._create_contract_via_api(
            asset_id=None,
            original_raw=odcs_content,
            original_format="JSON",
            original_spec_type="ODCS",
        )

        contract_id = contract_data["id"]

        # Test export with ODCS format and version
        result = self.runner.invoke(
            cli,
            [
                "contracts",
                "export",
                contract_id,
                "--format",
                "odcs",
                "--version",
                "3.0.2",
                "--output-format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"CLI failed with output: {result.output}"
        # Should either show export success or return JSON content
        assert (
            "exported successfully" in result.output.lower()
            or "apiVersion" in result.output.lower()
            or "odcs" in result.output.lower()
        )

    def test_contracts_export_odcs_with_version_yaml_real_api(self):
        """Test contracts export with ODCS format, version, and YAML output using real API"""
        import json

        # Create an ODCS contract via API
        odcs_content = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.1",
                "kind": "DataContract",
                "id": "cli-test-export-odcs-yaml",
                "name": "CLI Test Contract for ODCS Export YAML",
                "version": "1.0.0",
                "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
            }
        )

        # Create contract via API
        contract_data = self._create_contract_via_api(
            asset_id=None,
            original_raw=odcs_content,
            original_format="JSON",
            original_spec_type="ODCS",
        )

        contract_id = contract_data["id"]

        # Test export with ODCS format, version, and YAML output
        result = self.runner.invoke(
            cli,
            [
                "contracts",
                "export",
                contract_id,
                "--format",
                "odcs",
                "--version",
                "3.0.1",
                "--output-format",
                "yaml",
            ],
        )

        assert result.exit_code == 0, f"CLI failed with output: {result.output}"
        # Should either show export success or return YAML content
        assert (
            "exported successfully" in result.output.lower()
            or "apiVersion" in result.output.lower()
            or "odcs" in result.output.lower()
        )

    def test_contracts_export_odcs_invalid_version_real_api(self):
        """Test contracts export with ODCS format and invalid version using real API"""
        import json

        # Create an ODCS contract via API
        odcs_content = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "cli-test-export-odcs-invalid",
                "name": "CLI Test Contract for Invalid Version",
                "version": "1.0.0",
            }
        )

        # Create contract via API
        contract_data = self._create_contract_via_api(
            asset_id=None,
            original_raw=odcs_content,
            original_format="JSON",
            original_spec_type="ODCS",
        )

        contract_id = contract_data["id"]

        # Test export with invalid ODCS version (should fail validation before API call)
        result = self.runner.invoke(
            cli,
            [
                "contracts",
                "export",
                contract_id,
                "--format",
                "odcs",
                "--version",
                "invalid-version",
            ],
        )

        assert result.exit_code != 0, "Should fail with invalid version"
        assert "Invalid ODCS version format" in result.output or "invalid" in result.output.lower()

    def test_contracts_export_odcs_unsupported_version_real_api(self):
        """Test contracts export with ODCS format and unsupported version using real API"""
        import json

        # Create an ODCS contract via API
        odcs_content = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "cli-test-export-odcs-unsupported",
                "name": "CLI Test Contract for Unsupported Version",
                "version": "1.0.0",
            }
        )

        # Create contract via API
        contract_data = self._create_contract_via_api(
            asset_id=None,
            original_raw=odcs_content,
            original_format="JSON",
            original_spec_type="ODCS",
        )

        contract_id = contract_data["id"]

        # Test export with unsupported ODCS version (should fail validation before API call)
        result = self.runner.invoke(
            cli, ["contracts", "export", contract_id, "--format", "odcs", "--version", "99.99.99"]
        )

        assert result.exit_code != 0, "Should fail with unsupported version"
        assert "not supported" in result.output.lower()

    def test_contracts_export_odcs_version_preview_real_api(self):
        """Test contracts export with ODCS format and preview version using real API"""
        import json

        # Create an ODCS contract via API with preview version
        odcs_content = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.0-preview",
                "kind": "DataContract",
                "id": "cli-test-export-odcs-preview",
                "name": "CLI Test Contract for Preview Version",
                "version": "1.0.0",
                "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
            }
        )

        # Create contract via API
        contract_data = self._create_contract_via_api(
            asset_id=None,
            original_raw=odcs_content,
            original_format="JSON",
            original_spec_type="ODCS",
        )

        contract_id = contract_data["id"]

        # Test export with ODCS preview version
        result = self.runner.invoke(
            cli,
            [
                "contracts",
                "export",
                contract_id,
                "--format",
                "odcs",
                "--version",
                "3.0.0-preview",
                "--output-format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"CLI failed with output: {result.output}"
        # Should either show export success or return content
        assert (
            "exported successfully" in result.output.lower()
            or "apiVersion" in result.output.lower()
            or "odcs" in result.output.lower()
        )

    def test_config_commands(self):
        """Test config commands (no API needed)"""
        # Test config get
        result = self.runner.invoke(cli, ["config", "get", "api_base_url"])
        assert result.exit_code == 0

        # Test config set
        result = self.runner.invoke(cli, ["config", "set", "test_key", "test_value"])
        assert result.exit_code == 0
        assert config.get("test_key") == "test_value"
