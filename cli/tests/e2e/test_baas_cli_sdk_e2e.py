from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
End-to-end tests for BaaS CLI/SDK comprehensive workflows.

Tests complete workflows using both CLI and SDK together:
- Complete API key lifecycle workflows
- Usage tracking workflows
- Developer portal workflows
- CLI/SDK consistency validation
- Cross-platform workflow validation

These tests use real API endpoints - no mocks or stubs.

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured
   OR set via environment variables: DATAHUB_API_KEY or TEST_API_KEY

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Set API key: export DATAHUB_API_KEY=your-api-key
3. Run: pytest cli/tests/e2e/test_baas_cli_sdk_e2e.py -v
"""
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta

import pytest
import requests
from click.testing import CliRunner

# Add SDK to path for imports
sdk_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "..", "sdk", "python"
)
if os.path.exists(sdk_path):
    sys.path.insert(0, sdk_path)

from datahub_cli.config import config
from datahub_cli.main import cli
from datahub_interoperability import BaaSAPI, DataHubClient, DataHubClientConfig
from datahub_interoperability.errors import BaaSValidationError, NotFoundError


def _check_api_available():
    """Check if API service is available"""
    try:
        response = requests.get("http://localhost:8000/api/v1/", timeout=2)
        return response.status_code < 600
    except Exception:
        return False


@pytest.fixture(scope="module")
def api_available():
    """Fixture to check if API service is available"""
    return _check_api_available()


def setup_authentication():
    """Set up authentication for tests"""
    api_key = (
        os.environ.get("DATAHUB_API_KEY")
        or os.environ.get("TEST_API_KEY")
        or config.get_api_key()
        or _create_test_api_key()
    )
    return api_key


def _create_test_api_key():
    """Create a test API key via Django shell"""
    try:
        unique_id = uuid.uuid4().hex[:8]
        django_shell_script = f"""
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.auth.models import APIKey as AuthAPIKey
from hub.apps.baas.models import APITierModel
import sys

try:
    # Create API tiers first (required for API key creation workflow)
    free_tier, _ = APITierModel.objects.get_or_create(
        name='FREE',
        defaults={{
            'rate_limit_per_hour': 1000,
            'rate_limit_per_day': 10000,
            'max_requests_per_month': 10000
        }}
    )
    pro_tier, _ = APITierModel.objects.get_or_create(
        name='PRO',
        defaults={{
            'rate_limit_per_hour': 10000,
            'rate_limit_per_day': 100000,
            'max_requests_per_month': 100000
        }}
    )
    enterprise_tier, _ = APITierModel.objects.get_or_create(
        name='ENTERPRISE',
        defaults={{
            'rate_limit_per_hour': 100000,
            'rate_limit_per_day': 1000000,
            'max_requests_per_month': None
        }}
    )

    tenant, _ = Tenant.objects.get_or_create(
        slug=f'baas-e2e-test-tenant-{{unique_id}}',
        defaults={{'name': f'BaaS E2E Test Tenant {{unique_id}}'}}
    )

    user, _ = User.objects.get_or_create(
        email=f'baas-e2e-test-{{unique_id}}@example.com',
        defaults={{'tenant': tenant, 'status': UserStatus.ACTIVE}}
    )
    if user.tenant != tenant:
        user.tenant = tenant
        user.status = UserStatus.ACTIVE
        user.save()

    tenant_admin_role, _ = Role.objects.get_or_create(
        tenant=tenant, name='TENANT_ADMIN',
        defaults={{'description': 'Tenant Administrator'}}
    )
    UserRole.objects.get_or_create(user=user, role=tenant_admin_role)

    AuthAPIKey.objects.filter(tenant=tenant, name__startswith='BaaS E2E Test Auth Key').delete()

    api_key_value = AuthAPIKey.generate_key()
    api_key_hash = AuthAPIKey.hash_key(api_key_value)
    api_key_obj = AuthAPIKey.objects.create(
        user=user, tenant=tenant,
        name='BaaS E2E Test Auth Key {unique_id}',
        key_hash=api_key_hash
    )

    print('AUTH_API_KEY_START', file=sys.stdout, flush=True)
    print(api_key_value, file=sys.stdout, flush=True)
    print('AUTH_API_KEY_END', file=sys.stdout, flush=True)
except Exception as e:
    print(f'ERROR: {{e}}', file=sys.stderr, flush=True)
    import traceback
    traceback.print_exc(file=sys.stderr)
"""
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "api-service", "python", "manage.py", "shell"],
            check=False,
            input=django_shell_script,
            text=True,
            capture_output=True,
            timeout=30,
            cwd="/home/ph/Desktop/DataInteroperabilityHub",
        )

        if result.returncode == 0:
            output_lines = (
                (result.stdout + "\n" + result.stderr).strip().split("\n")
                if result.stderr
                else result.stdout.strip().split("\n")
            )
            in_key = False
            api_key = None
            for line in output_lines:
                line = line.strip()
                if line == "AUTH_API_KEY_START":
                    in_key = True
                    continue
                elif line == "AUTH_API_KEY_END":
                    break
                elif in_key and line and len(line) > 20:
                    api_key = line
                    break

            if api_key:
                return api_key
    except Exception as e:
        print(f"Error creating API key: {e}", file=sys.stderr)
    return None


@pytest.fixture
def cli_runner():
    """Fixture for CLI runner"""
    runner = CliRunner()
    api_base_url = "http://localhost:8000/api/v1"
    config.set_api_base_url(api_base_url)
    api_key = setup_authentication()
    if api_key:
        config.set_api_key(api_key)
    yield runner
    config.clear_auth()


@pytest.fixture
async def sdk_client():
    """Fixture for SDK client"""
    api_base_url = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")
    api_key = setup_authentication()
    if not api_key:
        pytest.skip("No API key available")

    client_config = DataHubClientConfig(
        base_url=api_base_url,
        api_token=api_key,
        timeout=30.0,
        max_retries=3,
    )
    async with DataHubClient(client_config) as client:
        yield client


@pytest.fixture
def baas_api(sdk_client):
    """Fixture for BaaSAPI"""
    # Note: sdk_client is async, but BaaSAPI can be created synchronously
    # The async context is managed by sdk_client fixture
    return BaaSAPI(sdk_client)


@pytest.mark.skipif(not _check_api_available(), reason="API service not available")
class TestBaaSCLISDKE2E:
    """End-to-end tests for BaaS CLI/SDK workflows"""

    # ==================== COMPLETE API KEY LIFECYCLE ====================

    @pytest.mark.asyncio
    async def test_complete_api_key_lifecycle_cli(self, cli_runner):
        """Test complete API key lifecycle using CLI"""
        unique_id = uuid.uuid4().hex[:8]

        # Step 1: Create API key via CLI
        create_result = cli_runner.invoke(
            cli,
            [
                "baas",
                "api-keys",
                "create",
                "--name",
                f"E2E CLI Key {unique_id}",
                "--tier",
                "FREE",
                "--format",
                "json",
            ],
        )
        assert create_result.exit_code == 0
        create_data = json.loads(create_result.output)
        api_key_id = create_data["id"]
        api_key_value = create_data["api_key"]
        assert api_key_value is not None

        # Step 2: List API keys via CLI
        list_result = cli_runner.invoke(cli, ["baas", "api-keys", "list", "--format", "json"])
        assert list_result.exit_code == 0
        list_data = json.loads(list_result.output)
        assert any(key["id"] == api_key_id for key in list_data)

        # Step 3: Get API key via CLI
        get_result = cli_runner.invoke(
            cli, ["baas", "api-keys", "get", api_key_id, "--format", "json"]
        )
        assert get_result.exit_code == 0
        get_data = json.loads(get_result.output)
        assert get_data["id"] == api_key_id
        assert "api_key" not in get_data  # Security check

        # Step 4: Update API key via CLI
        update_result = cli_runner.invoke(
            cli,
            [
                "baas",
                "api-keys",
                "update",
                api_key_id,
                "--name",
                f"E2E CLI Updated Key {unique_id}",
                "--format",
                "json",
            ],
        )
        assert update_result.exit_code == 0
        update_data = json.loads(update_result.output)
        assert update_data["name"] == f"E2E CLI Updated Key {unique_id}"

        # Step 5: Revoke API key via CLI
        revoke_result = cli_runner.invoke(cli, ["baas", "api-keys", "revoke", api_key_id])
        assert revoke_result.exit_code == 0

        # Step 6: Verify revocation
        get_revoked_result = cli_runner.invoke(
            cli, ["baas", "api-keys", "get", api_key_id, "--format", "json"]
        )
        assert get_revoked_result.exit_code == 0
        revoked_data = json.loads(get_revoked_result.output)
        assert revoked_data["is_active"] is False
        assert revoked_data["revoked_at"] is not None

    @pytest.mark.asyncio
    async def test_complete_api_key_lifecycle_sdk(self, baas_api):
        """Test complete API key lifecycle using SDK"""
        unique_id = uuid.uuid4().hex[:8]

        # Step 1: Create API key via SDK
        created = await baas_api.create_api_key(name=f"E2E SDK Key {unique_id}", tier="FREE")
        api_key_id = created["id"]
        api_key_value = created["api_key"]
        assert api_key_value is not None

        # Step 2: List API keys via SDK
        listed = await baas_api.list_api_keys()
        assert any(key["id"] == api_key_id for key in listed)

        # Step 3: Get API key via SDK
        retrieved = await baas_api.get_api_key(api_key_id)
        assert retrieved["id"] == api_key_id
        assert "api_key" not in retrieved  # Security check

        # Step 4: Update API key via SDK
        updated = await baas_api.update_api_key(api_key_id, name=f"E2E SDK Updated Key {unique_id}")
        assert updated["name"] == f"E2E SDK Updated Key {unique_id}"

        # Step 5: Revoke API key via SDK
        await baas_api.revoke_api_key(api_key_id)

        # Step 6: Verify revocation
        try:
            revoked = await baas_api.get_api_key(api_key_id)
            if "revoked_at" in revoked:
                assert revoked["revoked_at"] is not None
        except NotFoundError:
            # API might delete revoked keys
            pass

    @pytest.mark.asyncio
    async def test_cli_sdk_consistency(self, cli_runner, baas_api):
        """Test CLI and SDK consistency - create via CLI, read via SDK and vice versa"""
        unique_id = uuid.uuid4().hex[:8]

        # Create via CLI
        create_result = cli_runner.invoke(
            cli,
            [
                "baas",
                "api-keys",
                "create",
                "--name",
                f"CLI-SDK Consistency Key {unique_id}",
                "--tier",
                "PRO",
                "--format",
                "json",
            ],
        )
        assert create_result.exit_code == 0
        cli_data = json.loads(create_result.output)
        api_key_id = cli_data["id"]

        # Read via SDK
        sdk_data = await baas_api.get_api_key(api_key_id)
        assert sdk_data["id"] == api_key_id
        assert sdk_data["name"] == f"CLI-SDK Consistency Key {unique_id}"
        assert sdk_data["tier"] == "PRO"

        # Update via SDK
        await baas_api.update_api_key(api_key_id, name=f"SDK Updated Consistency Key {unique_id}")

        # Read via CLI
        get_result = cli_runner.invoke(
            cli, ["baas", "api-keys", "get", api_key_id, "--format", "json"]
        )
        assert get_result.exit_code == 0
        cli_updated_data = json.loads(get_result.output)
        assert cli_updated_data["name"] == f"SDK Updated Consistency Key {unique_id}"

    # ==================== USAGE TRACKING WORKFLOWS ====================

    @pytest.mark.asyncio
    async def test_usage_tracking_workflow_cli(self, cli_runner):
        """Test usage tracking workflow using CLI"""
        # Create a key first
        unique_id = uuid.uuid4().hex[:8]
        create_result = cli_runner.invoke(
            cli,
            [
                "baas",
                "api-keys",
                "create",
                "--name",
                f"Usage Workflow Key {unique_id}",
                "--format",
                "json",
            ],
        )
        assert create_result.exit_code == 0
        api_key_id = json.loads(create_result.output)["id"]

        # Get usage stats
        stats_result = cli_runner.invoke(
            cli, ["baas", "usage", "stats", "--api-key-id", api_key_id, "--format", "json"]
        )
        assert stats_result.exit_code == 0
        stats_data = json.loads(stats_result.output)
        assert "total_requests" in stats_data

        # Get usage by endpoint
        endpoint_result = cli_runner.invoke(
            cli, ["baas", "usage", "by-endpoint", "--api-key-id", api_key_id, "--format", "json"]
        )
        assert endpoint_result.exit_code == 0
        endpoint_data = json.loads(endpoint_result.output)
        assert isinstance(endpoint_data, list)

    @pytest.mark.asyncio
    async def test_usage_tracking_workflow_sdk(self, baas_api):
        """Test usage tracking workflow using SDK"""
        # Create a key first
        unique_id = uuid.uuid4().hex[:8]
        created = await baas_api.create_api_key(
            name=f"SDK Usage Workflow Key {unique_id}", tier="FREE"
        )
        api_key_id = created["id"]

        # Get usage stats
        stats = await baas_api.get_usage_stats(api_key_id=api_key_id)
        assert isinstance(stats, dict)
        assert "total_requests" in stats or "success_count" in stats

        # Get usage by endpoint
        endpoint_stats = await baas_api.get_usage_by_endpoint(api_key_id=api_key_id)
        assert isinstance(endpoint_stats, list)

    @pytest.mark.asyncio
    async def test_usage_tracking_cli_sdk_consistency(self, cli_runner, baas_api):
        """Test usage tracking consistency between CLI and SDK"""
        # Create a key via CLI
        unique_id = uuid.uuid4().hex[:8]
        create_result = cli_runner.invoke(
            cli,
            [
                "baas",
                "api-keys",
                "create",
                "--name",
                f"Usage Consistency Key {unique_id}",
                "--format",
                "json",
            ],
        )
        assert create_result.exit_code == 0
        api_key_id = json.loads(create_result.output)["id"]

        # Get stats via CLI
        cli_stats_result = cli_runner.invoke(
            cli, ["baas", "usage", "stats", "--api-key-id", api_key_id, "--format", "json"]
        )
        assert cli_stats_result.exit_code == 0
        cli_stats = json.loads(cli_stats_result.output)

        # Get stats via SDK
        sdk_stats = await baas_api.get_usage_stats(api_key_id=api_key_id)

        # Both should return similar structure
        assert isinstance(cli_stats, dict)
        assert isinstance(sdk_stats, dict)
        # Both should have total_requests or similar fields
        assert ("total_requests" in cli_stats) == (
            "total_requests" in sdk_stats or "success_count" in sdk_stats
        )

    # ==================== DEVELOPER PORTAL WORKFLOWS ====================

    @pytest.mark.asyncio
    async def test_developer_portal_workflow_cli(self, cli_runner):
        """Test developer portal workflow using CLI"""
        # Get API docs
        docs_result = cli_runner.invoke(cli, ["baas", "docs", "show", "--format", "json"])
        assert docs_result.exit_code == 0
        docs_data = json.loads(docs_result.output)
        assert "title" in docs_data
        assert "endpoints" in docs_data

        # Get OpenAPI schema
        openapi_result = cli_runner.invoke(cli, ["baas", "docs", "openapi", "--format", "json"])
        assert openapi_result.exit_code == 0
        openapi_data = json.loads(openapi_result.output)
        assert "openapi" in openapi_data

        # Get SDK links
        sdks_result = cli_runner.invoke(cli, ["baas", "docs", "sdks", "--format", "json"])
        assert sdks_result.exit_code == 0
        sdks_data = json.loads(sdks_result.output)
        assert isinstance(sdks_data, dict)

    @pytest.mark.asyncio
    async def test_developer_portal_workflow_sdk(self, baas_api):
        """Test developer portal workflow using SDK"""
        # Get API docs
        docs = await baas_api.get_api_docs(format="json")
        assert isinstance(docs, str)
        import json

        docs_data = json.loads(docs)
        assert "title" in docs_data

        # Get OpenAPI schema
        openapi = await baas_api.get_openapi_schema(format="json")
        assert isinstance(openapi, dict)
        assert "openapi" in openapi or "swagger" in openapi

        # Get SDK links
        sdks = await baas_api.get_sdk_download_links()
        assert isinstance(sdks, dict)

    @pytest.mark.asyncio
    async def test_developer_portal_cli_sdk_consistency(self, cli_runner, baas_api):
        """Test developer portal consistency between CLI and SDK"""
        # Get docs via CLI
        cli_docs_result = cli_runner.invoke(cli, ["baas", "docs", "show", "--format", "json"])
        assert cli_docs_result.exit_code == 0
        cli_docs = json.loads(cli_docs_result.output)

        # Get docs via SDK
        sdk_docs_str = await baas_api.get_api_docs(format="json")
        sdk_docs = json.loads(sdk_docs_str)

        # Both should have similar structure
        assert "title" in cli_docs
        assert "title" in sdk_docs

    # ==================== MULTI-TIER WORKFLOWS ====================

    @pytest.mark.asyncio
    async def test_multi_tier_workflow(self, cli_runner, baas_api):
        """Test workflow with multiple API keys of different tiers"""
        unique_id = uuid.uuid4().hex[:8]
        created_keys = []

        # Create keys with different tiers via CLI
        for tier in ["FREE", "PRO", "ENTERPRISE"]:
            create_result = cli_runner.invoke(
                cli,
                [
                    "baas",
                    "api-keys",
                    "create",
                    "--name",
                    f"Multi-Tier Key {tier} {unique_id}",
                    "--tier",
                    tier,
                    "--format",
                    "json",
                ],
            )
            assert create_result.exit_code == 0
            key_data = json.loads(create_result.output)
            created_keys.append(key_data["id"])

        # List all keys via SDK
        all_keys = await baas_api.list_api_keys()
        created_key_ids = {key["id"] for key in all_keys if key["id"] in created_keys}
        assert len(created_key_ids) == 3

        # Filter by tier via CLI
        for tier in ["FREE", "PRO", "ENTERPRISE"]:
            list_result = cli_runner.invoke(
                cli, ["baas", "api-keys", "list", "--tier", tier, "--format", "json"]
            )
            assert list_result.exit_code == 0
            tier_keys = json.loads(list_result.output)
            # Should have at least one key of this tier
            assert any(key["tier"] == tier for key in tier_keys)

    # ==================== ERROR HANDLING WORKFLOWS ====================

    @pytest.mark.asyncio
    async def test_error_handling_workflow(self, cli_runner, baas_api):
        """Test error handling across CLI and SDK"""
        # Test validation errors via CLI
        result = cli_runner.invoke(cli, ["baas", "api-keys", "create", "--name", ""])
        assert result.exit_code != 0
        assert "cannot be empty" in result.output.lower()

        # Test validation errors via SDK
        with pytest.raises(BaaSValidationError):
            await baas_api.create_api_key("", "FREE")

        # Test not found errors via CLI
        fake_id = str(uuid.uuid4())
        result = cli_runner.invoke(cli, ["baas", "api-keys", "get", fake_id])
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "404" in result.output

        # Test not found errors via SDK
        with pytest.raises(NotFoundError):
            await baas_api.get_api_key(fake_id)

    # ==================== DATE RANGE WORKFLOWS ====================

    @pytest.mark.asyncio
    async def test_date_range_workflow(self, cli_runner, baas_api):
        """Test date range filtering workflows"""
        # Create a key
        unique_id = uuid.uuid4().hex[:8]
        create_result = cli_runner.invoke(
            cli,
            [
                "baas",
                "api-keys",
                "create",
                "--name",
                f"Date Range Key {unique_id}",
                "--format",
                "json",
            ],
        )
        assert create_result.exit_code == 0
        api_key_id = json.loads(create_result.output)["id"]

        # Test date range via CLI
        now = datetime.now()
        start_date = (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_date = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        stats_result = cli_runner.invoke(
            cli,
            [
                "baas",
                "usage",
                "stats",
                "--api-key-id",
                api_key_id,
                "--start-date",
                start_date,
                "--end-date",
                end_date,
                "--format",
                "json",
            ],
        )
        assert stats_result.exit_code == 0

        # Test date range via SDK
        stats = await baas_api.get_usage_stats(
            api_key_id=api_key_id, start_date=start_date, end_date=end_date
        )
        assert isinstance(stats, dict)
